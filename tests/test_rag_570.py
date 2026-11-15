"""Offline regressions for T.O.R.V.I.S. 5.7.0: LLM, RAG and safe agents."""
import json
import os
import sqlite3

import pytest

from core.knowledge_rag import KnowledgeRAG, _chunks
from core.intelligence import answer_with_knowledge, plan_with_llm
from core.autonomous_agent import AgenteAutonomo
from core.tasks.tools import TaskTools
from actions.knowledge_rag import TOOL, knowledge_rag


def test_rag_index_search_and_update(tmp_path):
    store = KnowledgeRAG(tmp_path / "rag.sqlite", tmp_path / "inbox")
    file = store.inbox / "manual.md"
    file.write_text("O núcleo I.S.A. tem modo de recuperação seguro e cita fontes.\n", encoding="utf-8")
    r = store.index("manual.md")
    assert r["alterado"] is True
    assert store.index("manual.md")["alterado"] is False
    hits = store.search("recuperação seguro")
    assert hits and hits[0]["citacao"] == "manual.md#trecho-1"
    assert "I.S.A." in store.context("núcleo recuperação")
    file.write_text("O mecanismo agora permite busca RAG sobre documentos locais.", encoding="utf-8")
    assert store.index("manual.md")["alterado"] is True
    assert store.search("busca RAG")[0]["fonte"] == "manual.md"
    assert not store.search("recuperação seguro")
    assert store.status()["documentos"] == 1


def test_no_arbitrary_files_or_symlink(tmp_path):
    store = KnowledgeRAG(tmp_path / "db.sqlite", tmp_path / "inbox")
    private = tmp_path / "secrets.txt"
    private.write_text("não indexe")
    with pytest.raises(ValueError):
        store.index("../secrets.txt")
    with pytest.raises(ValueError):
        store.index(str(private))
    (store.inbox / "run.exe").write_text("binary")
    with pytest.raises(ValueError):
        store.index("run.exe")
    try:
        (store.inbox / "alias.txt").symlink_to(private)
    except OSError:
        pass
    else:
        with pytest.raises(ValueError):
            store.index("alias.txt")


def test_fallback_without_fts5(monkeypatch, tmp_path):
    store = KnowledgeRAG(tmp_path / "db.sqlite", tmp_path / "inbox")
    (store.inbox / "x.txt").write_text("Armazenamento em banco SQLite com pesquisa lexical.")
    store.index("x.txt")
    store.fts = False
    assert store.search("pesquisa lexical")


def test_long_chunking_is_bounded():
    text = "Texto muito longo " * 900
    parts = _chunks(text)
    assert len(parts) > 1
    assert all(0 < len(s) <= 1200 for s in parts)
    assert parts[-1].endswith("longo")


def test_grounded_llm_answer_with_citations_and_untrusted_context(tmp_path):
    store = KnowledgeRAG(tmp_path / "db.sqlite", tmp_path / "inbox")
    (store.inbox / "policy.txt").write_text("A política de backup exige validação manual.")
    store.index("policy.txt")
    inputs = []

    def fake_ask(system, turns, tools):
        inputs.append((system, turns, tools))
        return {"text": "A validação é manual [Fonte: policy.txt#trecho-1].", "calls": []}

    out = answer_with_knowledge("política backup", store=store, ask_fn=fake_ask)
    assert out["ok"] and "policy.txt#trecho-1" in out["fontes"]
    assert "NÃO CONFIÁVEIS" in inputs[0][0]
    assert "policy.txt#trecho-1" in inputs[0][1][0]["text"]
    assert inputs[0][2] is None
    notfound = answer_with_knowledge("xyznonexistenttopic", store=store, ask_fn=fake_ask)
    assert not notfound["ok"]


def test_planner_authorization_and_approval():
    def good(*args):
        return {"text": json.dumps({"steps": [{"tool": "send_message", "arguments": {"message": "oi"}}]})}
    agent = AgenteAutonomo()
    plan = plan_with_llm("enviar recado", ["send_message"], agent=agent, ask_fn=good)
    called = []
    no = agent.executar(plan, lambda n, args: called.append(n))
    assert no["status"] == "aguardando_confirmacao" and not called
    yes = agent.executar(plan, lambda n, args: called.append(n) or "ok", aprovacoes=[plan.passos[0].id])
    assert yes["status"] == "concluido" and called == ["send_message"]

    def bad(*args):
        return {"text": '{"steps":[{"tool":"delete_all","arguments":{}}]}'}
    with pytest.raises(ValueError):
        plan_with_llm("apague tudo", ["send_message"], ask_fn=bad)


def test_agent_web_private_tools_segregation(tmp_path):
    tool = TaskTools(tmp_path / "agent", ["search_web", "knowledge_search", "recall_memory", "notes"])
    assert "knowledge_search" not in tool.names
    assert "recall_memory" not in tool.names
    private = TaskTools(tmp_path / "private", ["knowledge_search", "notes"])
    assert "knowledge_search" in private.names
    assert any(d["name"] == "knowledge_search" for d in private.declarations())


def test_action_registered_and_explains_location(monkeypatch, tmp_path):
    import actions.knowledge_rag as action
    monkeypatch.setattr(action, "KnowledgeRAG", lambda: KnowledgeRAG(tmp_path / "db.sqlite", tmp_path / "inbox"))
    assert TOOL["name"] == "knowledge_rag"
    status = json.loads(knowledge_rag({"mode": "status"}))
    assert status["ok"] and status["status"]["documentos"] == 0
    bad = json.loads(knowledge_rag({"mode": "index", "file": "../secret.txt"}))
    assert not bad["ok"]
    (tmp_path / "inbox" / "faq.txt").write_text("O manual informa instalação local no Windows.")
    assert json.loads(knowledge_rag({"mode": "index", "file": "faq.txt"}))["ok"]
    assert json.loads(knowledge_rag({"mode": "search", "query": "Windows"}))["resultados"]
