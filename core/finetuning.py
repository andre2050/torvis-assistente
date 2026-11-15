"""core/finetuning.py — transforma o que o TORVIS já aprendeu em conjunto de treino.

POR QUE EXISTE
    Um assistente pessoal acumula, em meses de uso, exatamente o material que um
    ajuste fino precisa: como o dono fala, o que ele prefere, o que ele corrigiu,
    o tom das respostas. Só que esse material está espalhado em JSONs de memória
    e nunca teve forma de virar dataset. Este módulo dá essa forma — sem chamar
    nenhuma API, sem mandar nada para a nuvem e sem escrever nada até alguém
    clicar.

O QUE ELE NÃO FAZ (e é importante dizer)
    - Não treina nada. Ele monta o ARQUIVO; o treino acontece no provedor.
    - Não sobe arquivo. Quem envia é você, depois de revisar.
    - Não inventa exemplo. Cada par sai de uma memória, de uma sessão ou de uma
      correção registrada, e o manifesto guarda de onde veio cada um.

FORMATO
    JSONL no esquema de ajuste do Gemini (uma conversa por linha):

        {"messages": [{"role": "user", "content": "..."},
                      {"role": "model", "content": "..."}]}

PRIVACIDADE
    Antes de escrever, o texto passa por um saneador que mascara chaves de API,
    e-mails, telefones e CPF/CNPJ. O relatório diz quantas máscaras foram
    aplicadas e em quantos exemplos, para a revisão não ser no escuro.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from core.paths import MEMORY_DIR, STATE_DIR
except Exception:                                        # módulo isolado em teste
    MEMORY_DIR = Path("memory")
    STATE_DIR = Path("state")

DIRETORIO_TREINO = STATE_DIR / "finetuning"
CORRECOES = DIRETORIO_TREINO / "correcoes.jsonl"
MEMORIA_LONGA = MEMORY_DIR / "long_term.json"
MEMORIA_COGNITIVA = MEMORY_DIR / "cognitive_memory.json"

MINIMO_PADRAO = 100          # mínimo configurável, não uma regra do provedor
MAXIMO_CARACTERES = 4000     # exemplos maiores que isso são descartados na revisão

CATEGORIAS = {
    "identity": "quem é o seu dono e como ele se apresenta",
    "preferences": "gostos e preferências declaradas",
    "projects": "projetos e o estado deles",
    "relationships": "pessoas ao redor do dono",
    "wishes": "o que ele quer fazer ou ter",
    "notes": "anotações gerais",
}

PERGUNTAS = {
    "identity": "Quem eu sou?",
    "preferences": "Do que eu gosto?",
    "projects": "No que eu estou trabalhando?",
    "relationships": "Quem são as pessoas importantes para mim?",
    "wishes": "O que eu quero fazer?",
    "notes": "O que você anotou para mim?",
}


# ─────────────────────────────────────────────────────────────────── saneador
_PADROES = (
    ("chave_api", re.compile(r"\b(AIza[0-9A-Za-z_\-]{30,}|sk-[A-Za-z0-9]{16,}"
                             r"|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9\-]{10,})")),
    ("email", re.compile(r"\b[\w.+\-]+@[\w\-]+\.[\w.\-]{2,}\b")),
    ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("cnpj", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
    # O 55 do país é opcional: a primeira versão exigia o "5" e não pegava
    # "(11) 98765-4321" — o número que aparece de fato nas conversas.
    ("telefone", re.compile(r"(?<![\d.])(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[-.\s]?\d{4}(?![\d.])")),
)


@dataclass
class Saneamento:
    texto: str
    mascarados: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.mascarados.values())


def sanear(texto: str) -> Saneamento:
    """Mascara dados sensíveis mantendo o formato legível para o modelo."""
    resultado = Saneamento(texto or "")
    for nome, padrao in _PADROES:
        trocas = len(padrao.findall(resultado.texto))
        if trocas:
            resultado.texto = padrao.sub(f"[{nome}]", resultado.texto)
            resultado.mascarados[nome] = trocas
    return resultado


# ──────────────────────────────────────────────────────────────── leitura
def ler_memoria_longa(caminho: Path | None = None) -> dict:
    caminho = Path(caminho) if caminho else MEMORIA_LONGA
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def ler_memoria_cognitiva(caminho: Path | None = None) -> list[dict]:
    caminho = Path(caminho) if caminho else MEMORIA_COGNITIVA
    if not caminho.is_file():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(dados, dict):
        for chave in ("lembrancas", "memories", "items", "entries"):
            if isinstance(dados.get(chave), list):
                return dados[chave]
        return [v for v in dados.values() if isinstance(v, dict)]
    return dados if isinstance(dados, list) else []


def ler_correcoes(caminho: Path | None = None) -> list[dict]:
    """Correções registradas pelo próprio uso: o par certo, vindo do dono."""
    caminho = Path(caminho) if caminho else CORRECOES
    if not caminho.is_file():
        return []
    exemplos = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            item = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if item.get("pergunta") and item.get("resposta"):
            exemplos.append(item)
    return exemplos


def registrar_correcao(pergunta: str, resposta: str, origem: str = "uso",
                       caminho: Path | None = None) -> Path:
    """Guarda uma correção real para entrar no próximo conjunto."""
    caminho = Path(caminho) if caminho else CORRECOES
    caminho.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "pergunta": sanear(pergunta).texto,
        "resposta": sanear(resposta).texto,
        "origem": origem,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
    }
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return caminho


# ───────────────────────────────────────────────────────── coleta de exemplos
def _par(pergunta: str, resposta: str) -> dict:
    return {"messages": [{"role": "user", "content": pergunta},
                         {"role": "model", "content": resposta}]}


def coletar(memoria_longa: Path | None = None,
            memoria_cognitiva: Path | None = None,
            correcoes: Path | None = None) -> tuple[list[dict], dict]:
    """Monta os pares a partir das três fontes. Devolve (exemplos, manifesto)."""
    exemplos: list[dict] = []
    manifesto: list[dict] = []
    mascaras: dict[str, int] = {}
    exemplos_com_mascara = 0

    def _adicionar(pergunta: str, resposta: str, origem: str, referencia: str = "") -> None:
        nonlocal exemplos_com_mascara
        pergunta_limpa = sanear(pergunta)
        resposta_limpa = sanear(resposta)
        if pergunta_limpa.total or resposta_limpa.total:
            exemplos_com_mascara += 1
            for nome, quantidade in {**pergunta_limpa.mascarados,
                                     **resposta_limpa.mascarados}.items():
                mascaras[nome] = mascaras.get(nome, 0) + quantidade
        exemplos.append(_par(pergunta_limpa.texto.strip(), resposta_limpa.texto.strip()))
        manifesto.append({"indice": len(exemplos) - 1, "origem": origem,
                          "referencia": referencia})

    # 1) memória de longo prazo — o que o dono contou sobre si
    memoria = ler_memoria_longa(memoria_longa)
    for categoria, itens in memoria.items():
        if categoria == "sessions" or not isinstance(itens, dict):
            continue
        pergunta = PERGUNTAS.get(categoria, f"O que você sabe sobre {categoria}?")
        for chave, entrada in itens.items():
            valor = entrada.get("value") if isinstance(entrada, dict) else entrada
            if isinstance(valor, (dict, list)):
                valor = json.dumps(valor, ensure_ascii=False)
            if not valor:
                continue
            _adicionar(f"{pergunta} ({chave})", str(valor),
                       origem=f"memoria:{categoria}", referencia=str(chave))

    # 2) memória cognitiva — lembranças com importância
    for lembranca in ler_memoria_cognitiva(memoria_cognitiva):
        conteudo = (lembranca.get("conteudo") or lembranca.get("content") or "").strip()
        if not conteudo:
            continue
        categoria = lembranca.get("categoria") or "geral"
        _adicionar(PERGUNTAS.get(categoria, "O que você lembra sobre isso?"), conteudo,
                   origem="cognitiva", referencia=str(lembranca.get("id", "")))

    # 3) resumos de sessão — o estilo do dia a dia
    for sessao in memoria.get("sessions") or []:
        resumo = (sessao.get("summary") or "").strip() if isinstance(sessao, dict) else ""
        if not resumo:
            continue
        _adicionar(f"O que a gente fez em {sessao.get('date', 'outra sessão')}?", resumo,
                   origem="sessao", referencia=str(sessao.get("date", "")))

    # 4) correções registradas — o exemplo mais valioso, porque veio do dono
    for correcao in ler_correcoes(correcoes):
        _adicionar(correcao["pergunta"], correcao["resposta"],
                   origem="correcao", referencia=str(correcao.get("origem", "")))

    relatorio = {
        "exemplos": len(exemplos),
        "por_origem": _contar_origens(manifesto),
        "exemplos_com_mascara": exemplos_com_mascara,
        "mascaras": mascaras,
    }
    return exemplos, {"exemplos": manifesto, "relatorio": relatorio}


def _contar_origens(manifesto: list[dict]) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for item in manifesto:
        raiz = str(item.get("origem", "?")).split(":")[0]
        contagem[raiz] = contagem.get(raiz, 0) + 1
    return contagem


# ─────────────────────────────────────────────────────────────── validação
CHAVE_NORMAL = re.compile(r"\s+")


def estimar_tokens(texto: str) -> int:
    """Estimativa grosseira (~4 caracteres por token). Serve para dimensionar."""
    return max(1, round(len(texto) / 4))


def validar(exemplos: list[dict], minimo: int = MINIMO_PADRAO) -> dict:
    """Confere o conjunto e devolve o que precisa de atenção antes de treinar."""
    problemas: list[str] = []
    avisos: list[str] = []
    vistos: set[str] = set()
    validos: list[dict] = []
    duplicados = 0
    longos = 0
    vazios = 0
    tokens = 0

    for indice, exemplo in enumerate(exemplos):
        mensagens = exemplo.get("messages") or []
        if len(mensagens) != 2:
            problemas.append(f"exemplo {indice}: precisa de exatamente 2 mensagens")
            continue
        papeis = [m.get("role") for m in mensagens]
        if papeis != ["user", "model"]:
            problemas.append(f"exemplo {indice}: papéis fora de ordem ({papeis})")
            continue
        pergunta = (mensagens[0].get("content") or "").strip()
        resposta = (mensagens[1].get("content") or "").strip()
        if not pergunta or not resposta:
            vazios += 1
            continue
        if len(pergunta) + len(resposta) > MAXIMO_CARACTERES:
            longos += 1
            continue
        chave = CHAVE_NORMAL.sub(" ", f"{pergunta}|{resposta}").casefold()
        if chave in vistos:
            duplicados += 1
            continue
        vistos.add(chave)
        validos.append(exemplo)
        tokens += estimar_tokens(pergunta) + estimar_tokens(resposta)

    if len(validos) < minimo:
        avisos.append(f"{len(validos)} exemplos: abaixo do mínimo configurado ({minimo})")
    if duplicados:
        avisos.append(f"{duplicados} exemplo(s) repetido(s) removido(s)")
    if vazios:
        avisos.append(f"{vazios} exemplo(s) vazio(s) removido(s)")
    if longos:
        avisos.append(f"{longos} exemplo(s) longo(s) demais (> {MAXIMO_CARACTERES} caracteres)")
    if validos and len({m["messages"][0]["content"][:40] for m in validos}) < len(validos) / 2:
        avisos.append("muitas perguntas parecidas: o modelo pode decorar a pergunta, não o estilo")

    return {
        "total": len(exemplos),
        "validos": len(validos),
        "tokens_estimados": tokens,
        "duplicados": duplicados,
        "vazios": vazios,
        "longos": longos,
        "problemas": problemas[:20],
        "avisos": avisos,
        "exemplos": validos,
    }


def dividir(validos: list[dict], fracao_teste: float = 0.1) -> tuple[list[dict], list[dict]]:
    """Separa treino e validação de forma determinística (sem embaralhar o rng)."""
    if not validos:
        return [], []
    corte = max(1, int(len(validos) * fracao_teste))
    return validos[:-corte], validos[-corte:]


# ──────────────────────────────────────────────────────────────── exportação
def exportar(exemplos: list[dict], destino: Path | None = None,
             fracao_teste: float = 0.1) -> dict:
    """Valida, divide e grava JSONL + manifesto + resumo. Não envia nada."""
    destino = Path(destino) if destino else DIRETORIO_TREINO
    destino.mkdir(parents=True, exist_ok=True)
    resultado = validar(exemplos)
    treino, teste = dividir(resultado["exemplos"], fracao_teste)

    data = datetime.now().strftime("%Y%m%d-%H%M")
    arquivo_treino = destino / f"treino-{data}.jsonl"
    arquivo_teste = destino / f"validacao-{data}.jsonl"
    arquivo_resumo = destino / f"resumo-{data}.json"

    for caminho, itens in ((arquivo_treino, treino), (arquivo_teste, teste)):
        with caminho.open("w", encoding="utf-8") as arquivo:
            for item in itens:
                arquivo.write(json.dumps(item, ensure_ascii=False) + "\n")

    resumo = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "exemplos_treino": len(treino),
        "exemplos_validacao": len(teste),
        "tokens_estimados": resultado["tokens_estimados"],
        "validacao": {k: v for k, v in resultado.items() if k != "exemplos"},
        "arquivos": {"treino": arquivo_treino.name, "validacao": arquivo_teste.name},
        "como_enviar": instrucoes_envio(),
    }
    arquivo_resumo.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sem **resumo aqui: o resumo tem uma chave "validacao" que sobrescreveria o
    # caminho do arquivo de validação. Estrutura aninhada evita a colisão.
    return {
        "diretorio": str(destino),
        "arquivos": {"treino": str(arquivo_treino),
                     "validacao": str(arquivo_teste),
                     "resumo": str(arquivo_resumo)},
        "resumo": resumo,
    }


def instrucoes_envio() -> list[str]:
    """O caminho honesto entre 'arquivo pronto' e 'modelo ajustado'."""
    return [
        "1. Revise o JSONL: cada linha precisa continuar verdadeira e sem dado pessoal.",
        "2. Confira no console do provedor o mínimo de exemplos e o preço do ajuste — "
        "os dois mudam, e este programa não adivinha nenhum deles.",
        "3. Envie o arquivo de treino pelo console ou pela API de ajuste do provedor.",
        "4. Guarde o nome do modelo ajustado: ele substitui o modelo de texto, não a "
        "conversa ao vivo.",
        "5. Compare as respostas do modelo novo com as do antigo antes de trocar o padrão.",
    ]


def estado(caminho: Path | None = None) -> dict:
    """Panorama rápido, para a interface abrir com número em vez de 'clique para ver'."""
    memoria = ler_memoria_longa()
    cognitiva = ler_memoria_cognitiva()
    correcoes = ler_correcoes()
    exemplos, meta = coletar()
    validacao = validar(exemplos)
    return {
        "memorias": sum(len(v) for k, v in memoria.items()
                        if isinstance(v, dict)),
        "sessoes": len(memoria.get("sessions") or []),
        "lembrancas": len(cognitiva),
        "correcoes": len(correcoes),
        "exemplos": meta["relatorio"]["exemplos"],
        "por_origem": meta["relatorio"]["por_origem"],
        "exemplos_com_mascara": meta["relatorio"]["exemplos_com_mascara"],
        "mascaras": meta["relatorio"]["mascaras"],
        "validos": validacao["validos"],
        "tokens_estimados": validacao["tokens_estimados"],
        "avisos": validacao["avisos"],
        "diretorio": str(caminho or DIRETORIO_TREINO),
    }
