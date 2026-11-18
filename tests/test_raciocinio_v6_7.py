"""Ciclo de raciocínio dos agentes autônomos. Sem rede: o LLM é simulado."""
import json
from datetime import datetime

from core import outcome
from core.isa import NucleoISA
from core.raciocinio import (CadernoDeCorrecoes, CatalogoFerramentas, CicloRaciocinio, contexto_do_momento,
                             decidir, eh_correcao, entender_intencao, replanejar_com_llm, verificar)


def llm(*respostas):
    fila = list(respostas)
    chamadas = []

    def ask(system, turns, decls):
        chamadas.append((system, turns[-1]["text"]))
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return {"text": r if isinstance(r, str) else json.dumps(r), "calls": []}
    ask.chamadas = chamadas
    return ask


def isa_com_ferramentas(tmp_path):
    isa = NucleoISA()
    isa.raciocinio.caderno = CadernoDeCorrecoes(tmp_path / "c.json")
    isa.raciocinio.memoria = None
    isa.registrar_ferramenta("tocar_musica", lambda musica="": f"status=done action=tocar_musica musica={musica}",
                             "Toca uma música no Spotify", {"properties": {"musica": {"type": "STRING"}}, "required": ["musica"]})
    isa.registrar_ferramenta("apagar_arquivo", lambda caminho="": "status=done action=apagar_arquivo",
                             "Apaga um arquivo", {"properties": {"caminho": {"type": "STRING"}}, "required": ["caminho"]})
    return isa


def test_intencao_json_e_obrigatorio_faltando(tmp_path):
    cat = isa_com_ferramentas(tmp_path).catalogo
    ask = llm({"acao": "tocar música", "ferramenta": "tocar_musica", "parametros": {}, "confianca": 0.9})
    i = entender_intencao("toca aquela música de ontem", cat, ask_fn=ask)
    assert i.ferramenta == "tocar_musica" and i.faltando == ["musica"]
    assert decidir(i, cat).modo == "perguntar"


def test_ferramenta_inventada_e_descartada_e_llm_fora_usa_regras(tmp_path):
    cat = isa_com_ferramentas(tmp_path).catalogo
    i = entender_intencao("oi", cat, ask_fn=llm({"ferramenta": "hackear", "confianca": 0.9}))
    assert i.ferramenta is None
    def quebrado(*_a): raise RuntimeError("sem modelo")
    i = entender_intencao("tocar música no spotify", cat, ask_fn=quebrado)
    assert i.origem == "regras" and i.ferramenta == "tocar_musica"


def test_perguntar_so_quando_o_erro_e_caro(tmp_path):
    cat = isa_com_ferramentas(tmp_path).catalogo
    barato = entender_intencao("x", cat, ask_fn=llm({"ferramenta": "tocar_musica", "parametros": {"musica": "a"},
                                                     "ambiguidades": ["duas versões"], "confianca": 0.6}))
    assert decidir(barato, cat).modo == "assumir_e_avisar"
    claro = entender_intencao("x", cat, ask_fn=llm({"ferramenta": "tocar_musica", "parametros": {"musica": "a"}, "confianca": 0.95}))
    assert decidir(claro, cat).modo == "executar"
    caro = entender_intencao("x", cat, ask_fn=llm({"ferramenta": "apagar_arquivo", "parametros": {"caminho": "a"}, "confianca": 0.99}))
    d = decidir(caro, cat)
    assert d.modo == "perguntar" and d.confirmacao


def test_ciclo_pergunta_depois_executa(tmp_path):
    isa = isa_com_ferramentas(tmp_path)
    ask = llm({"ferramenta": "tocar_musica", "parametros": {}, "confianca": 0.9},
              {"ferramenta": "tocar_musica", "parametros": {"musica": "Evidências"}, "confianca": 0.95})
    r = isa.processar_pedido("toca uma música", ask_fn=ask)
    assert r["estado"] == "pergunta"
    r = isa.processar_pedido("Evidências", ask_fn=ask)
    assert r["estado"] == "executado" and r["execucao"]["resultados"][0]["verificado"] is True


def test_confirmacao_de_acao_cara(tmp_path):
    isa = isa_com_ferramentas(tmp_path)
    ask = llm({"ferramenta": "apagar_arquivo", "parametros": {"caminho": "a.txt"}, "confianca": 0.99})
    assert isa.processar_pedido("apaga a.txt", ask_fn=ask)["estado"] == "pergunta"
    assert isa.processar_pedido("sim, pode", ask_fn=ask)["estado"] == "executado"
    assert isa.processar_pedido("apaga a.txt", ask_fn=ask)["estado"] == "pergunta"
    assert isa.processar_pedido("não", ask_fn=ask)["estado"] == "cancelado"


def test_falso_sucesso_nao_passa_e_replaneja(tmp_path):
    isa = NucleoISA()
    isa.raciocinio.caderno = CadernoDeCorrecoes(tmp_path / "c.json")
    isa.registrar_ferramenta("abrir_app", lambda nome="": outcome.failed("abrir_app", "app não instalado"), "Abre um app",
                             {"properties": {"nome": {"type": "STRING"}}, "required": ["nome"]})
    isa.registrar_ferramenta("abrir_site", lambda url="": outcome.done("abrir_site", url=url), "Abre um site",
                             {"properties": {"url": {"type": "STRING"}}, "required": ["url"]})
    assert isa.executar("abrir_app", nome="x").bloqueado is False   # parâmetro "nome" não colide
    ask = llm({"ferramenta": "abrir_app", "parametros": {"nome": "spotify"}, "confianca": 0.95},
              {"steps": [{"tool": "abrir_site", "arguments": {"url": "https://open.spotify.com"}}]})
    r = isa.processar_pedido("abre o spotify", ask_fn=ask)
    assert r["estado"] == "executado" and r["execucao"]["replanos"] == 1


def test_falha_sem_alternativa_e_reportada(tmp_path):
    isa = NucleoISA()
    isa.raciocinio.caderno = CadernoDeCorrecoes(tmp_path / "c.json")
    isa.registrar_ferramenta("abrir_app", lambda nome="": outcome.failed("abrir_app", "sumiu"), "Abre app",
                             {"properties": {"nome": {"type": "STRING"}}, "required": ["nome"]})
    ask = llm({"ferramenta": "abrir_app", "parametros": {"nome": "x"}, "confianca": 0.95}, {"steps": []})
    r = isa.processar_pedido("abre x", ask_fn=ask)
    assert r["estado"] == "falhou" and "sumiu" in r["execucao"]["erro"]


def test_unverified_segue_mas_marca_nao_verificado():
    assert verificar("f", {}, outcome.unverified("f", "sem prova")) == "unverified"
    assert verificar("f", {}, "Tool 'f' failed: boom") == "failed"
    assert verificar("f", {}, outcome.done("f")) == "done"
    assert verificar("f", {}, outcome.done("f"), verificador=lambda *a: False) == "failed"


def test_aprende_com_correcao(tmp_path):
    isa = isa_com_ferramentas(tmp_path)
    ask = llm({"ferramenta": "tocar_musica", "parametros": {"musica": "A"}, "confianca": 0.95},
              {"ferramenta": "tocar_musica", "parametros": {"musica": "B"}, "confianca": 0.95})
    isa.processar_pedido("toca aquela música do Roberto", ask_fn=ask)
    assert eh_correcao("não, não era isso")
    isa.processar_pedido("não, não era isso, era a do Roberto Carlos", ask_fn=ask)
    ex = isa.raciocinio.caderno.exemplos_relevantes("toca a música do Roberto")
    assert ex and "Roberto Carlos" in ex[0]["correcao"]
    entender_intencao("toca a música do Roberto", isa.catalogo, exemplos=ex, ask_fn=ask)
    assert "Roberto Carlos" in ask.chamadas[-1][1]


def test_contexto_e_habitos(tmp_path):
    ctx = contexto_do_momento([{"pedido": "abre o chrome", "ok": True}], janela_fn=lambda: "Spotify",
                              agora=datetime(2026, 11, 17, 19, 0))
    assert ctx["periodo"] == "noite" and ctx["ultimo_pedido"] == "abre o chrome" and ctx["app_em_foco"] == "Spotify"
    c = CadernoDeCorrecoes(tmp_path / "h.json")
    for _ in range(3):
        c.registrar_uso("tocar_musica", {"musica": "x"}, agora=datetime(2026, 11, 17, 20, 0))
    assert "tocar_musica" in c.habitos(agora=datetime(2026, 11, 18, 21, 0))


def test_replanejador_ignora_ferramenta_inventada(tmp_path):
    cat = isa_com_ferramentas(tmp_path).catalogo
    r = replanejar_com_llm("x", {"ferramenta": "a", "argumentos": {}}, "erro", cat,
                           ask_fn=llm({"steps": [{"tool": "inventada", "arguments": {}}]}))
    assert r == []


def test_engine_checa_resultado_antes_de_entregar(tmp_path):
    from core.tasks.engine import TaskEngine
    vistos = []
    def ask(system, turns, decls):
        vistos.append(turns[-1].get("text", ""))
        if len(vistos) == 1:
            return {"text": "", "calls": [{"id": "1", "name": "notes", "args": {"action": "add", "text": "x"}, "sig": ""}]}
        return {"text": "Resultado final", "calls": []}
    eng = TaskEngine(tmp_path / "t", tmp_path / "r", [tmp_path / "nenhum"], ask_fn=ask, autostart=False)
    t = eng.start("faça algo")
    eng._flags[t["id"]] = {"cancel": False, "finish": False, "halt": False}
    eng._run(t["id"])
    assert any(v.startswith("[CHECK BEFORE YOU FINISH]") for v in vistos)
    assert eng.get(t["id"])["status"] == "done"
