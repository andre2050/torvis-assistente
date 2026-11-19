"""Escrita de código que não estraga o arquivo.

O agente de desenvolvimento pedia o arquivo inteiro a um modelo só e gravava o
que voltasse. Quando a resposta vinha cortada, no meio de uma regra CSS ou de
uma função JS, o arquivo era sobrescrito com o pedaço e o projeto parava de
funcionar. E quando a cota daquele modelo estourava, os outros nem eram
tentados: o relato final era só "todos falharam", sem dizer o motivo.

Aqui ficam as três coisas que faltavam:

* validar_codigo   — recusa resposta cortada antes de encostar no arquivo;
* escrever_com_seguranca — grava num temporário, confere, e volta atrás se falhar;
* tentar_patch     — para arquivo grande, pede só o trecho que muda.

A validação é deliberadamente barata e sem dependência: conta chaves e
parênteses respeitando strings e comentários, e no Python usa o compilador de
verdade. Node, quando existe, confere o JS.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SUFIXOS_PY = {".py", ".pyw"}
SUFIXOS_JS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}
SUFIXOS_CSS = {".css", ".scss", ".sass", ".less"}
SUFIXOS_MARCACAO = {".html", ".htm", ".vue", ".svg", ".xml"}

# Marcas de resposta que veio pela metade. Não são proibidas no código em si
# (um comentário pode dizer "TODO"), então só contam no fim do texto.
_RESTOS_DE_CORTE = ("```", "... (", "// continue", "# continue", "<!--")


class EscritaFalhou(RuntimeError):
    """Nenhuma tentativa produziu um arquivo válido; nada foi gravado."""


@dataclass
class Resultado:
    ok: bool
    motivo: str = ""
    copia: Path | None = None
    bytes: int = 0

    def como_dict(self) -> dict:
        return {"ok": self.ok, "motivo": self.motivo,
                "copia": str(self.copia) if self.copia else None, "bytes": self.bytes}


# ───────────────────────────── validação ─────────────────────────────

def _varrer(texto: str, comentarios: tuple[str, ...], aspas: tuple[str, ...]) -> tuple[bool, str]:
    """Confere se chaves, colchetes e parênteses fecham.

    Respeita strings e comentários: uma chave dentro de "texto" ou depois de //
    não conta. Devolve (ok, motivo).
    """
    pilha: list[tuple[str, int]] = []
    pares = {")": "(", "]": "[", "}": "{"}
    marcas_linha = tuple(m for m in comentarios if m and m != "/*")
    tem_bloco = "/*" in comentarios
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]

        # bloco /* ... */ (CSS e JS): precisa fechar, senão a resposta foi cortada
        if tem_bloco and texto.startswith("/*", i):
            fim = texto.find("*/", i + 2)
            if fim < 0:
                return False, "comentário /* sem fechar: a resposta foi cortada"
            i = fim + 2
            continue

        # comentário de linha: // ou #
        pulou = False
        for marca in marcas_linha:
            if texto.startswith(marca, i):
                fim = texto.find("\n", i)
                i = n if fim < 0 else fim
                pulou = True
                break
        if pulou:
            continue

        if c in aspas:
            j = i + 1
            while j < n:
                if texto[j] == "\\":
                    j += 2
                    continue
                if texto[j] == c:
                    break
                if texto[j] == "\n" and c != "`":
                    return False, "string sem fechar no fim da linha: resposta cortada"
                j += 1
            if j >= n:
                return False, f"string aberta com {c} não foi fechada: resposta cortada"
            i = j + 1
            continue

        if c in "([{":
            pilha.append((c, i))
        elif c in ")]}":
            if not pilha or pilha[-1][0] != pares[c]:
                return False, f"'{c}' fecha algo que não foi aberto (posição {i})"
            pilha.pop()
        i += 1

    if pilha:
        aberto, pos = pilha[-1]
        return False, f"'{aberto}' aberto na posição {pos} e nunca fechado: resposta cortada"
    return True, ""


def _validar_js(caminho: Path, texto: str) -> tuple[bool, str]:
    ok_varre, motivo_varre = _varrer(texto, ("//", "/*"), ('"', "'", "`"))
    node = shutil.which("node")
    if not node:
        return ok_varre, motivo_varre
    destino = Path(tempfile.mkdtemp(prefix="torvis-js-")) / caminho.name
    try:
        destino.write_text(texto, encoding="utf-8")
        r = subprocess.run([node, "--check", str(destino)], capture_output=True, text=True, timeout=25)
        if r.returncode == 0:
            return True, ""
        # --check não entende módulo ESM; nesse caso vale o varredor
        if "Cannot use import statement" in (r.stderr or ""):
            return ok_varre, motivo_varre
        # syntax error: se o varredor viu algo aberto, a causa é o corte
        if not ok_varre:
            return False, motivo_varre
        linha = (r.stderr or "").strip().splitlines()
        return False, "JS inválido: " + (linha[0][:160] if linha else "erro de sintaxe")
    finally:
        shutil.rmtree(destino.parent, ignore_errors=True)


def validar_codigo(texto: str, caminho: str | Path) -> tuple[bool, str]:
    """Diz se o texto pode substituir esse arquivo, e por quê não."""
    caminho = Path(str(caminho))
    if not texto or not texto.strip():
        return False, "a resposta veio vazia"
    if len(texto.strip()) < 4:
        return False, f"a resposta tem só {len(texto.strip())} caracteres"

    sufixo = caminho.suffix.lower()
    cauda = texto.rstrip()[-60:]
    for resto in _RESTOS_DE_CORTE:
        if resto in cauda:
            return False, f"a resposta termina com '{resto}': veio cortada"

    if sufixo in SUFIXOS_PY:
        try:
            compile(texto, str(caminho), "exec")
        except SyntaxError as exc:
            return False, f"Python com erro de sintaxe na linha {exc.lineno}: {exc.msg}"
        return True, ""

    if sufixo in SUFIXOS_JS:
        return _validar_js(caminho, texto)

    if sufixo in SUFIXOS_CSS:
        return _varrer(texto, ("/*",), ('"', "'"))

    if sufixo in SUFIXOS_MARCACAO:
        return _varrer(texto, ("/*",), ('"', "'", "`"))

    return _varrer(texto, ("//", "/*"), ('"', "'", "`"))


# ──────────────────────── gravação com volta atrás ────────────────────────

def escrever_com_seguranca(caminho: Path | str, texto: str, *,
                           validar: bool = True) -> Resultado:
    """Grava só depois de validar, mantendo cópia e restaurando em caso de erro."""
    caminho = Path(caminho)
    if validar:
        ok, motivo = validar_codigo(texto, caminho)
        if not ok:
            return Resultado(False, motivo)

    copia = None
    existia = caminho.exists()
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if existia:
            copia = caminho.with_suffix(caminho.suffix + ".bak")
            shutil.copy2(caminho, copia)

        temporario = caminho.with_suffix(caminho.suffix + ".novo")
        # ponto de retorno: o desfazer global relê isto depois de um reinício
        try:
            from core import desfazer_global
            desfazer_global.guardar(caminho)
        except Exception:
            pass
        temporario.write_text(texto, encoding="utf-8")

        if validar:
            ok, motivo = validar_codigo(temporario.read_text(encoding="utf-8"), caminho)
            if not ok:
                temporario.unlink(missing_ok=True)
                return Resultado(False, motivo, copia)

        os.replace(temporario, caminho)
        return Resultado(True, "", copia, len(texto.encode("utf-8")))
    except OSError as exc:
        if copia and copia.exists():
            try:
                shutil.copy2(copia, caminho)
            except OSError:
                pass
        return Resultado(False, f"não consegui gravar: {exc}", copia)


# ───────────────────────── edição por trecho ─────────────────────────

PATCH_MARCA = "<<<ANTES>>>"


def aplicar_trecho(original: str, antes: str, depois: str) -> tuple[bool, str, str]:
    """Troca um trecho exato. Devolve (ok, novo_texto, motivo)."""
    if not antes.strip():
        return False, original, "o trecho a substituir veio vazio"
    if antes in original:
        return True, original.replace(antes, depois, 1), ""

    # Segunda chance: mesma estrutura, espaçamento diferente (o modelo reindenta
    # com frequência, e recusar por causa de espaço desperdiça a resposta).
    def normalizar(t: str) -> str:
        return "\n".join(linha.strip() for linha in t.strip().splitlines())

    alvo = normalizar(antes)
    linhas = original.splitlines(keepends=True)
    for inicio in range(len(linhas)):
        acumulado = ""
        for fim in range(inicio, min(inicio + 200, len(linhas))):
            acumulado += linhas[fim]
            if normalizar(acumulado) == alvo:
                novo = "".join(linhas[:inicio]) + depois + "".join(linhas[fim + 1:])
                return True, novo, ""
            if len(normalizar(acumulado)) > len(alvo) + 200:
                break
    return False, original, "não achei o trecho ANTES no arquivo (o arquivo pode ter mudado)"


def ler_patch(resposta: str) -> tuple[str, str] | None:
    """Extrai ANTES e DEPOIS da resposta do modelo."""
    if PATCH_MARCA not in resposta:
        return None
    resto = resposta.split(PATCH_MARCA, 1)[1]
    if "<<<DEPOIS>>>" not in resto:
        return None
    antes, depois = resto.split("<<<DEPOIS>>>", 1)
    if "<<<FIM>>>" in depois:
        depois = depois.split("<<<FIM>>>", 1)[0]
    if antes.strip().startswith("```") or depois.strip().startswith("```"):
        antes = antes.replace("```css", "").replace("```javascript", "").replace("```js", "").replace("```", "")
        depois = depois.replace("```css", "").replace("```javascript", "").replace("```js", "").replace("```", "")
    return antes, depois


def pedido_de_patch(instrucao: str, trecho_atual: str, caminho: str) -> str:
    """Prompt para mudar só um pedaço de um arquivo grande."""
    return f"""Você vai alterar apenas um trecho do arquivo {caminho}.

O que precisa mudar: {instrucao}

Trecho atual do arquivo:
{trecho_atual}

Responda neste formato exato, sem explicação nenhuma:
{PATCH_MARCA}
(o trecho ATUAL, copiado caractere por caractere do que está acima)
<<<DEPOIS>>>
(o trecho novo, no lugar dele)
<<<FIM>>>

Regras:
- Copie o trecho ATUAL exatamente como está, sem reindentar e sem corrigir nada.
- Inclua no DEPOIS apenas o que muda, mantendo o resto do arquivo intacto.
- Não devolva o arquivo inteiro. Se precisar, aumente apenas o trecho copiado.
"""


# ───────────────────── geração com escada e validação ─────────────────────

def tentar_gerar(prompt: str,
                 gerar: Callable[[str], str],
                 *,
                 caminho: str | Path,
                 tentativas: int = 3,
                 ao_falhar: Callable[[str], None] | None = None) -> str:
    """Pede o código, confere, e insiste com um pedido menor se vier cortado."""
    motivos: list[str] = []
    reforco = ""
    for n in range(1, tentativas + 1):
        try:
            texto = gerar(prompt + reforco)
        except EscritaFalhou as exc:
            # a escada inteira já falhou: insistir com o mesmo pedido não resolve
            motivos.append(str(exc))
            break
        except Exception as exc:  # falha de modelo: registra e tenta de novo
            motivos.append(f"tentativa {n}: {exc}")
            if ao_falhar:
                ao_falhar(str(exc))
            reforco = ("\n\nA resposta anterior não serviu. Gere o arquivo completo, "
                       "simples e curto, fechando todas as chaves e imports.")
            continue

        ok, motivo = validar_codigo(texto, caminho)
        if ok:
            return texto
        motivos.append(f"tentativa {n}: {motivo}")
        if ao_falhar:
            ao_falhar(motivo)
        if "cortada" in motivo or "vazi" in motivo:
            reforco = ("\n\nA resposta anterior chegou cortada. Gere a versão MAIS CURTA possível "
                       "que ainda funcione: sem comentários, sem exemplos, fechando todas as chaves.")
        else:
            reforco = f"\n\nA resposta anterior tinha este defeito: {motivo}. Corrija e devolva o arquivo inteiro."

    raise EscritaFalhou(relato_para_pessoa(str(caminho), motivos or ["nenhum modelo respondeu"]))


def relato_para_pessoa(caminho: str, erros: list[str]) -> str:
    """Mensagem que explica o que aconteceu, em vez de 'todos falharam'."""
    if not erros:
        return f"Não consegui gerar {caminho}."
    ultimo = erros[-1]
    dica = ""
    if any(m in ultimo.lower() for m in ("cota", "quota", "429", "rate")):
        dica = " A cota dos modelos acabou; dá para tentar de novo em alguns minutos."
    elif "tempo" in ultimo.lower() or "timeout" in ultimo.lower():
        dica = " Os modelos demoraram além do limite; tente de novo, ou peça um arquivo menor."
    elif "cortada" in ultimo.lower():
        dica = " A resposta veio pela metade; peça só esse arquivo, ou reduza o escopo."
    elif "sintaxe" in ultimo.lower():
        dica = " O código voltou com erro de sintaxe."
    return (f"Não consegui alterar {caminho}: {ultimo}.{dica} "
            f"O arquivo ficou exatamente como estava.")
