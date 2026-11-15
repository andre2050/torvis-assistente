"""I.S.A. — Inteligência, Síntese e Ação."""
from dataclasses import dataclass, field
from collections import deque
from hashlib import sha256
from time import monotonic
from typing import Any, Callable, Dict, Optional
from core.version import VERSAO as VERSAO_SISTEMA

@dataclass(slots=True)
class ISAContexto:
    texto: str
    intencao: str = "conversa"
    confianca: float = 0.5
    requer_acao: bool = False
    requer_confirmacao: bool = False
    metadados: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ISAResultado:
    resposta: Optional[str] = None
    acao: Optional[str] = None
    argumentos: Dict[str, Any] = field(default_factory=dict)
    bloqueado: bool = False
    motivo: Optional[str] = None

class NucleoISA:
    VERSAO = VERSAO_SISTEMA
    def __init__(self, historico_maximo=40, repeticao_maxima=3):
        self.historico=deque(maxlen=historico_maximo)
        self.repeticao_maxima=max(1,repeticao_maxima)
        self._assinaturas=deque(maxlen=12)
        self._ferramentas={}
        self.iniciado_em=monotonic()
        from neural.manager import GerenciadorNeural
        self.neural = GerenciadorNeural()
        from memory.cognitive_memory import MemoriaCognitiva
        self.memoria_cognitiva = MemoriaCognitiva()
        from core.autonomous_agent import AgenteAutonomo
        self.agente_autonomo = AgenteAutonomo()
        from core.adaptive_intelligence import obter_adaptativo
        self.adaptativo = obter_adaptativo()

    def registrar_ferramenta(self, nome: str, funcao: Callable[..., Any]):
        if not nome or not callable(funcao): raise ValueError("Ferramenta inválida.")
        self._ferramentas[nome]=funcao

    def interpretar(self, texto: str):
        limpo=(texto or "").strip(); baixo=limpo.casefold()
        acao=any(x in baixo for x in ("abra ","abrir ","execute ","executar ","crie ","criar ","envie ","enviar ","feche ","fechar ","apague ","exclua "))
        sensivel=any(x in baixo for x in ("apague ","exclua ","remova ","formate ","senha","credencial","pagamento","comprar ","publicar "))
        intencao="acao" if acao else ("pergunta" if "?" in limpo else "conversa")
        ctx=ISAContexto(limpo,intencao,0.85 if limpo else 0.0,acao,sensivel)
        self.historico.append({"tipo":"entrada","texto":limpo,"intencao":intencao})
        return ctx

    def _assinatura(self,nome,args):
        return sha256(f"{nome}|{repr(sorted(args.items()))}".encode("utf-8",errors="replace")).hexdigest()

    def executar(self,nome,**argumentos):
        if nome not in self._ferramentas:
            return ISAResultado(bloqueado=True,motivo=f"Ferramenta não registrada: {nome}")
        sig=self._assinatura(nome,argumentos)
        repeticoes=sum(x==sig for x in self._assinaturas)
        self._assinaturas.append(sig)
        if repeticoes>=self.repeticao_maxima:
            return ISAResultado(bloqueado=True,motivo="I.S.A. interrompeu uma ação repetitiva para proteger o sistema.")
        try:
            valor=self._ferramentas[nome](**argumentos)
            self.historico.append({"tipo":"acao","nome":nome,"ok":True})
            return ISAResultado(None if valor is None else str(valor),nome,argumentos)
        except Exception as exc:
            self.historico.append({"tipo":"acao","nome":nome,"ok":False})
            return ISAResultado(acao=nome,argumentos=argumentos,bloqueado=True,motivo=str(exc))


    def consultar_documentos(self, pergunta, *, ask_fn=None):
        """Ponto de entrada da I.S.A. para perguntas RAG com citação de fontes."""
        from core.intelligence import answer_with_knowledge
        return answer_with_knowledge(pergunta, ask_fn=ask_fn)

    def planejar_com_llm(self, objetivo, *, ask_fn=None):
        """Planeja somente usando ferramentas registradas. Nunca executa automaticamente."""
        from core.intelligence import plan_with_llm
        return plan_with_llm(objetivo, self._ferramentas.keys(),
                             agent=self.agente_autonomo, ask_fn=ask_fn)

    def criar_plano(self, objetivo, passos):
        return self.agente_autonomo.criar_plano(objetivo, passos)

    def executar_plano(self, plano, aprovacoes=()):
        def _executor(nome, args):
            resultado = self.executar(nome, **args)
            if resultado.bloqueado:
                raise RuntimeError(resultado.motivo or "ação bloqueada pelo I.S.A.")
            return resultado.resposta
        return self.agente_autonomo.executar(plano, _executor, aprovacoes=aprovacoes)

    @staticmethod
    def _estado_rag():
        try:
            from core.knowledge_rag import KnowledgeRAG
            return KnowledgeRAG().status()
        except Exception as exc:
            return {"ativo": False, "motivo": str(exc)[:160]}

    def estado(self):
        return {"nome":"I.S.A.","versao":self.VERSAO,"ativo":True,"ferramentas":len(self._ferramentas),
                "eventos_contexto":len(self.historico),"tempo_ativo_s":round(monotonic()-self.iniciado_em,2), "neural":self.neural.status(),
                "memoria_cognitiva":self.memoria_cognitiva.status(),
                "agente_autonomo":self.agente_autonomo.status(),
                "inteligencia_adaptativa":self.adaptativo.status(),
                "rag":self._estado_rag()}

_isa_global=None
def obter_isa():
    global _isa_global
    if _isa_global is None: _isa_global=NucleoISA()
    return _isa_global
