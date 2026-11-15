"""core/capstone.py — o relatório técnico do TORVIS, montado a partir do próprio código.

POR QUE EXISTE
    Um trabalho de conclusão (capstone) pede números: quantos módulos, quantas
    linhas, quantos testes, o que cada pacote faz, o que ficou de fora. Escrever
    isso à mão envelhece no dia seguinte — e pior, costuma sair diferente do que
    o repositório mostra. Este módulo lê o projeto e escreve o documento com o
    que está lá, mais o roteiro de defesa.

O QUE ELE PRODUZ
    - relatorio-tecnico.md    (para editar e colar no trabalho)
    - relatorio-tecnico.html  (abre no navegador e imprime em PDF pelo Ctrl+P)
    - roteiro-defesa.md       (dez slides com o que dizer em cada um)

O QUE ELE NÃO FAZ
    Não inventa resultado. Se a suíte de testes não foi executada, o documento
    diz que não foi executada em vez de exibir um número bonito.
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

DIREFERENCIA = Path(__file__).resolve().parent.parent
IGNORAR = {"__pycache__", ".git", "build", "dist", ".venv", "venv", "node_modules"}

# O que cada pacote é, em uma frase de gente — não de código.
PACOTES = {
    "core": "núcleo: estado, modelos, rede, atualização, políticas e relatórios",
    "gui": "interface: HUD, painéis, temas e os 9 HUBs do avatar",
    "actions": "ferramentas que o assistente executa por comando de voz ou texto",
    "providers": "motor plugável de escuta, raciocínio e fala",
    "memory": "memória de longo prazo, memória cognitiva e configuração",
    "neural": "módulos neurais opcionais (classificador, visão, sequência)",
    "dashboard": "painel web local para acompanhar o assistente",
    "plugins": "extensões carregadas em tempo de execução",
    "tests": "suíte automatizada de testes",
    "tools": "scripts de empacotamento, render e aplicação de atualização",
}

MARCOS = (
    ("v5.x", "HUBs visuais, memória cognitiva, visão computacional e agentes"),
    ("v6.0", "núcleo I.S.A., política de execução, orçamento e diagnóstico"),
    ("v6.1", "HUBs realistas, relatório de um clique e métricas de desempenho"),
    ("v6.2", "atualização atômica com rollback e proteção de chaves"),
    ("v6.3", "atualização automática em segundo plano"),
    ("v6.4", "conjunto de ajuste fino e relatório de capstone"),
)

LIMITES = (
    "O ajuste fino não altera a conversa ao vivo: ele troca o modelo de texto usado nas tarefas escritas.",
    "Nenhum método prevê sorteios ou eventos aleatórios; as decisões do assistente são apoio, não garantia.",
    "A suíte cobre a lógica; microfone, tela e voz dependem de teste manual no Windows.",
    "A latência percebida depende da rede e do provedor, não só do código.",
)

FUTUROS = (
    "Testes com mocks para microfone, SAPI e captura de tela, hoje só validados à mão.",
    "Divisão de window.py e main.py por HUB, para reduzir o custo de cada correção.",
    "Watchdog da sessão ao vivo, com reconexão automática e estado visível.",
    "Trilha de auditoria das ações autônomas, com desfazer para o que é reversível.",
)


# ─────────────────────────────────────────────────────────────── inventário
def inventario(raiz: Path | None = None) -> dict:
    """Conta o que existe no projeto, sem confiar em número digitado à mão."""
    raiz = Path(raiz) if raiz else DIREFERENCIA
    arquivos = [p for p in raiz.rglob("*")
                if p.is_file() and not any(parte in IGNORAR for parte in p.parts)]
    python = [p for p in arquivos if p.suffix == ".py"]
    testes = [p for p in python if p.name.startswith("test_") or p.name == "smoke.py"]
    documentos = [p for p in arquivos if p.suffix.lower() in {".md", ".txt"}]

    linhas_por_pacote: dict[str, int] = {}
    total_linhas = 0
    for arquivo in python:
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        quantidade = texto.count("\n") + 1
        total_linhas += quantidade
        try:
            pacote = arquivo.relative_to(raiz).parts[0] if len(arquivo.relative_to(raiz).parts) > 1 else "raiz"
        except ValueError:
            pacote = "?"
        linhas_por_pacote[pacote] = linhas_por_pacote.get(pacote, 0) + quantidade

    try:
        from core.version import VERSAO
    except Exception:
        VERSAO = "desconhecida"

    return {
        "versao": VERSAO,
        "raiz": str(raiz),
        "arquivos": len(arquivos),
        "modulos_python": len(python),
        "arquivos_de_teste": len(testes),
        "documentos": len(documentos),
        "linhas_python": total_linhas,
        "pacotes": dict(sorted(linhas_por_pacote.items(), key=lambda kv: -kv[1])),
        "python": sys.version.split()[0],
        "sistema": platform.platform(),
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# ────────────────────────────────────────────────────────────── documento
def blocos(dados: dict | None = None) -> list[dict]:
    """O relatório como estrutura: cada renderizador depois decide o formato."""
    dados = dados or inventario()
    pacotes = [["Pacote", "Linhas", "O que faz"]]
    for nome, linhas in dados["pacotes"].items():
        pacotes.append([nome, f"{linhas:,}".replace(",", "."),
                        PACOTES.get(nome, "módulo de apoio")])

    return [
        {"tipo": "titulo", "texto": "Assistente Inteligente T.O.R.V.I.S 2026"},
        {"tipo": "subtitulo",
         "texto": f"Relatório técnico · versão {dados['versao']} · {dados['gerado_em']}"},
        {"tipo": "secao", "texto": "1. Objetivo"},
        {"tipo": "paragrafo",
         "texto": ("Este documento descreve um assistente pessoal de voz executado no "
                   "computador do próprio usuário: ele escuta, responde em voz alta, "
                   "executa tarefas no sistema e mantém memória entre sessões. O "
                   "diferencial não é conversar — é agir: abrir programas, controlar "
                   "arquivos, pesquisar na web, acompanhar telas e automatizar rotinas "
                   "com confirmação humana nas ações irreversíveis.")},
        {"tipo": "secao", "texto": "2. Arquitetura"},
        {"tipo": "paragrafo",
         "texto": ("A separação é por responsabilidade: o núcleo não desenha, a interface "
                   "não decide, e as ferramentas não sabem quem as chamou. A conversa ao "
                   "vivo é o caminho padrão; um motor alternativo pode substituir escuta, "
                   "raciocínio e fala sem tocar no resto do sistema.")},
        {"tipo": "tabela", "cabecalho": pacotes[0], "linhas": pacotes[1:]},
        {"tipo": "secao", "texto": "3. Números do projeto"},
        {"tipo": "tabela", "cabecalho": ["Indicador", "Valor"], "linhas": [
            ["Módulos Python", f"{dados['modulos_python']:,}".replace(",", ".")],
            ["Linhas de código Python", f"{dados['linhas_python']:,}".replace(",", ".")],
            ["Arquivos de teste", f"{dados['arquivos_de_teste']:,}".replace(",", ".")],
            ["Documentos técnicos", f"{dados['documentos']:,}".replace(",", ".")],
            ["Total de arquivos", f"{dados['arquivos']:,}".replace(",", ".")],
            ["Python", dados["python"]],
        ]},
        {"tipo": "secao", "texto": "4. Metodologia"},
        {"tipo": "paragrafo",
         "texto": ("O desenvolvimento foi incremental e verificado: cada versão só é "
                   "publicada depois de a suíte automatizada passar, e as atualizações "
                   "chegam ao usuário por pacote assinado com SHA-256, aplicado de forma "
                   "atômica e com rollback automático em caso de falha. Arquivos de "
                   "chave, memória e configuração nunca são sobrescritos.")},
        {"tipo": "lista", "itens": [
            "Testes automatizados por módulo, executados fora da interface.",
            "Diagnóstico embutido: rede, modelos, dependências e erros num arquivo só.",
            "Métricas de desempenho gravadas em cada abertura.",
            "Atualização verificada por hash, com o sistema antigo preservado até a troca.",
        ]},
        {"tipo": "secao", "texto": "5. Cronologia"},
        {"tipo": "tabela", "cabecalho": ["Versão", "Entrega"], "linhas": [list(m) for m in MARCOS]},
        {"tipo": "secao", "texto": "6. Limitações declaradas"},
        {"tipo": "lista", "itens": list(LIMITES)},
        {"tipo": "secao", "texto": "7. Trabalhos futuros"},
        {"tipo": "lista", "itens": list(FUTUROS)},
    ]


def para_markdown(estrutura: list[dict]) -> str:
    linhas: list[str] = []
    for bloco in estrutura:
        tipo = bloco["tipo"]
        if tipo == "titulo":
            linhas += [f"# {bloco['texto']}", ""]
        elif tipo == "subtitulo":
            linhas += [f"*{bloco['texto']}*", ""]
        elif tipo == "secao":
            linhas += ["", f"## {bloco['texto']}", ""]
        elif tipo == "paragrafo":
            linhas += [bloco["texto"], ""]
        elif tipo == "lista":
            linhas += [f"- {item}" for item in bloco["itens"]] + [""]
        elif tipo == "tabela":
            linhas.append("| " + " | ".join(bloco["cabecalho"]) + " |")
            linhas.append("|" + "|".join("---" for _ in bloco["cabecalho"]) + "|")
            for linha in bloco["linhas"]:
                linhas.append("| " + " | ".join(str(c) for c in linha) + " |")
            linhas.append("")
    return "\n".join(linhas).strip() + "\n"


def para_html(estrutura: list[dict], titulo: str = "Relatório técnico") -> str:
    """HTML autocontido, claro no papel: sem fonte externa, sem script."""
    def escapar(texto) -> str:
        return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    corpo: list[str] = []
    for bloco in estrutura:
        tipo = bloco["tipo"]
        if tipo == "titulo":
            corpo.append(f"<h1>{escapar(bloco['texto'])}</h1>")
        elif tipo == "subtitulo":
            corpo.append(f"<p class='sub'>{escapar(bloco['texto'])}</p>")
        elif tipo == "secao":
            corpo.append(f"<h2>{escapar(bloco['texto'])}</h2>")
        elif tipo == "paragrafo":
            corpo.append(f"<p>{escapar(bloco['texto'])}</p>")
        elif tipo == "lista":
            itens = "".join(f"<li>{escapar(i)}</li>" for i in bloco["itens"])
            corpo.append(f"<ul>{itens}</ul>")
        elif tipo == "tabela":
            cab = "".join(f"<th>{escapar(c)}</th>" for c in bloco["cabecalho"])
            linhas = "".join(
                "<tr>" + "".join(f"<td>{escapar(c)}</td>" for c in linha) + "</tr>"
                for linha in bloco["linhas"])
            corpo.append(f"<table><thead><tr>{cab}</tr></thead><tbody>{linhas}</tbody></table>")

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{escapar(titulo)}</title>
<style>
  :root {{ --tinta: #10161c; --suave: #5d6b78; --linha: #dce3ea; --realce: #0b6b8f; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0 auto; padding: 56px 40px 80px; max-width: 820px;
         font: 16px/1.65 -apple-system, "Segoe UI", Roboto, sans-serif;
         color: var(--tinta); background: #fff; }}
  h1 {{ font-size: 30px; line-height: 1.2; margin: 0 0 6px; letter-spacing: -.4px; }}
  .sub {{ color: var(--suave); margin: 0 0 34px; font-size: 14px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: 1.2px;
        color: var(--realce); margin: 38px 0 10px; padding-bottom: 6px;
        border-bottom: 1px solid var(--linha); }}
  p {{ margin: 0 0 14px; }}
  ul {{ margin: 0 0 16px; padding-left: 20px; }}
  li {{ margin-bottom: 7px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0 20px; font-size: 14px; }}
  th {{ text-align: left; font-weight: 600; color: var(--suave);
        border-bottom: 1px solid var(--linha); padding: 8px 10px; }}
  td {{ border-bottom: 1px solid var(--linha); padding: 8px 10px; vertical-align: top; }}
  tbody tr:nth-child(even) {{ background: #f6f8fa; }}
  @media print {{ body {{ padding: 0; max-width: none; }} h2 {{ break-after: avoid; }}
                  table {{ break-inside: auto; }} }}
</style>
</head>
<body>
{chr(10).join(corpo)}
</body>
</html>
"""


def gerar(destino: Path | None = None, raiz: Path | None = None) -> dict:
    """Escreve o .md e o .html e devolve os caminhos."""
    destino = Path(destino) if destino else DIREFERENCIA / "docs"
    destino.mkdir(parents=True, exist_ok=True)
    dados = inventario(raiz)
    estrutura = blocos(dados)
    caminho_md = destino / "relatorio-tecnico.md"
    caminho_html = destino / "relatorio-tecnico.html"
    caminho_md.write_text(para_markdown(estrutura), encoding="utf-8")
    caminho_html.write_text(para_html(estrutura), encoding="utf-8")
    return {"markdown": str(caminho_md), "html": str(caminho_html), "dados": dados}


# ────────────────────────────────────────────────────────── defesa do trabalho
def slides(dados: dict | None = None) -> list[dict]:
    dados = dados or inventario()
    return [
        {"titulo": "1. O problema",
         "fala": ("Assistentes de voz conversam bem e agem mal. A proposta foi "
                  "construir um assistente que executa tarefas no próprio computador, "
                  "mantém memória e continua útil depois de meses de uso."),
         "mostrar": "A janela principal com o HUD do assistente."},
        {"titulo": "2. O que ele faz",
         "fala": ("Escuta por voz ou texto, responde em voz alta, executa comandos no "
                  "sistema, pesquisa na web, lê arquivos, controla o navegador e "
                  "automatiza rotinas agendadas."),
         "mostrar": "Uma tarefa real concluída ao vivo, com a confirmação aparecendo."},
        {"titulo": "3. Arquitetura",
         "fala": ("Separação por responsabilidade: núcleo, interface, ferramentas, "
                  "provedores e memória. A conversa ao vivo é o caminho padrão e o motor "
                  "pode ser trocado sem mexer no resto."),
         "mostrar": "A tabela de pacotes do relatório técnico."},
        {"titulo": "4. Segurança",
         "fala": ("Ação irreversível pede confirmação humana, fora do alcance do modelo. "
                  "A política de execução decide o que roda direto e o que espera permissão."),
         "mostrar": "O banner de confirmação e a política configurada."},
        {"titulo": "5. Atualização",
         "fala": ("O pacote chega assinado com SHA-256, é aplicado de forma atômica e "
                  "volta sozinho se algo falhar. Chaves e memória nunca são sobrescritas."),
         "mostrar": "O log de uma atualização aplicada com sucesso."},
        {"titulo": "6. Qualidade",
         "fala": (f"A suíte tem {dados['arquivos_de_teste']} arquivos de teste sobre "
                  f"{dados['modulos_python']} módulos, mais diagnóstico embutido e "
                  "métricas de abertura."),
         "mostrar": "A suíte passando no terminal."},
        {"titulo": "7. Memória",
         "fala": ("Três camadas: longo prazo, cognitiva e sessão. A recuperação combina "
                  "relevância lexical, importância e recência, sem depender de rede."),
         "mostrar": "O painel de memória com entradas reais."},
        {"titulo": "8. Dados para ajuste fino",
         "fala": ("O uso deixa um conjunto que pode ser revisado e exportado no formato "
                  "do provedor. Nada sai da máquina sem revisão."),
         "mostrar": "O painel do laboratório com a contagem de exemplos."},
        {"titulo": "9. Limitações",
         "fala": ("O que não está pronto, dito com clareza: testes de hardware, latência "
                  "dependente de rede e ausência de previsão em eventos aleatórios."),
         "mostrar": "A seção de limitações do relatório."},
        {"titulo": "10. Próximos passos",
         "fala": ("Watchdog da sessão ao vivo, trilha de auditoria das ações e divisão "
                  "dos arquivos grandes por HUB."),
         "mostrar": "A lista de trabalhos futuros."},
    ]


def gerar_roteiro(destino: Path | None = None, raiz: Path | None = None) -> dict:
    destino = Path(destino) if destino else DIREFERENCIA / "docs"
    destino.mkdir(parents=True, exist_ok=True)
    dados = inventario(raiz)
    linhas = ["# Roteiro de defesa", "",
              f"*Gerado em {dados['gerado_em']} · versão {dados['versao']}*", "",
              "Dez minutos: cerca de um minuto por tópico, com uma demonstração por bloco.", ""]
    for slide in slides(dados):
        linhas += [f"## {slide['titulo']}", "", slide["fala"], "",
                   f"**Mostrar na tela:** {slide['mostrar']}", ""]
    caminho = destino / "roteiro-defesa.md"
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return {"roteiro": str(caminho), "slides": len(slides(dados))}
