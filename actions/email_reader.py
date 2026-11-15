"""Leitura de e-mail por IMAP: checar, listar, ler e buscar.

Só leitura. Enviar e-mail é outra tarefa (e outra decisão), então este módulo
não tem como enviar nada — o que ele não pode fazer, ele não faz por acidente.

Configuração, no `config.json` (ou pedindo ao assistente para configurar):
    "email_address":      "seu@gmail.com"
    "email_app_password": "senha de app, não a senha da conta"
    "email_imap_host":    "imap.gmail.com"     (opcional: deduzido pelo domínio)

A senha nunca vai para o log nem para a resposta falada.
"""
from __future__ import annotations

import email
import email.header
import imaplib
import re
import socket
from datetime import datetime

_TIMEOUT = 20.0
_MAX_LIDOS = 25

_HOSTS = {
    "gmail.com": "imap.gmail.com", "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com", "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com", "outlook.com.br": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com", "yahoo.com.br": "imap.mail.yahoo.com",
    "uol.com.br": "imap.uol.com.br", "bol.com.br": "imap.bol.com.br",
    "terra.com.br": "imap.terra.com.br", "ig.com.br": "imap.ig.com.br",
    "zoho.com": "imap.zoho.com", "protonmail.com": "127.0.0.1",
}

# Última lista mostrada, para "lê a segunda" depois de "quais chegaram".
_ultima_lista: list[dict] = []


def _credenciais() -> tuple[str, str, str] | tuple[None, None, str]:
    try:
        from memory.config_manager import load_api_keys

        config = load_api_keys() or {}
    except Exception:                                     # noqa: BLE001
        config = {}

    usuario = str(config.get("email_address") or "").strip()
    senha = str(config.get("email_app_password") or "").strip()
    host = str(config.get("email_imap_host") or "").strip()
    if not host and "@" in usuario:
        host = _HOSTS.get(usuario.split("@")[-1].lower(), "")

    if not usuario or not senha or not host:
        return None, None, (
            "Ainda não tenho acesso ao seu e-mail. Preciso de três dados no config.json: "
            "'email_address' (seu endereço), 'email_app_password' (uma senha de app, não a "
            "senha normal da conta) e, se não for Gmail/Outlook, 'email_imap_host'. "
            "No Gmail, a senha de app é criada em myaccount.google.com/apppasswords.")
    return usuario, senha, host


def _conectar(usuario: str, senha: str, host: str) -> imaplib.IMAP4_SSL:
    anterior = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_TIMEOUT)
    try:
        caixa = imaplib.IMAP4_SSL(host, 993)
        caixa.login(usuario, senha)
        return caixa
    finally:
        socket.setdefaulttimeout(anterior)


def _decodificar(valor) -> str:
    if not valor:
        return ""
    try:
        partes = email.header.decode_header(valor)
        saida = []
        for texto, codificacao in partes:
            if isinstance(texto, bytes):
                saida.append(texto.decode(codificacao or "utf-8", errors="replace"))
            else:
                saida.append(texto)
        return re.sub(r"\s+", " ", "".join(saida)).strip()
    except Exception:                                     # noqa: BLE001
        return str(valor)


def _corpo(mensagem: email.message.Message, limite: int = 900) -> str:
    if mensagem.is_multipart():
        for parte in mensagem.walk():
            if parte.get_content_type() == "text/plain":
                try:
                    bruto = parte.get_payload(decode=True) or b""
                    charset = parte.get_content_charset() or "utf-8"
                    texto = bruto.decode(charset, errors="replace")
                    return re.sub(r"\s+", " ", texto).strip()[:limite]
                except Exception:                         # noqa: BLE001
                    continue
        return ""
    try:
        bruto = mensagem.get_payload(decode=True) or b""
        charset = mensagem.get_content_charset() or "utf-8"
        return re.sub(r"\s+", " ", bruto.decode(charset, errors="replace")).strip()[:limite]
    except Exception:                                     # noqa: BLE001
        return ""


def _mensagens(caixa: imaplib.IMAP4_SSL, pasta: str, limite: int, apenas_nao_lidas: bool) -> list[dict]:
    caixa.select(pasta, readonly=True)
    criterio = "(UNSEEN)" if apenas_nao_lidas else "ALL"
    tipo, dados = caixa.search(None, criterio)
    if tipo != "OK" or not dados or not dados[0]:
        return []
    numeros = dados[0].split()[-limite:]
    saida = []
    for numero in reversed(numeros):                     # mais recentes primeiro
        tipo, partes = caixa.fetch(numero, "(RFC822.HEADER)")
        if tipo != "OK" or not partes:
            continue
        bruto = b""
        for pedaco in partes:
            if isinstance(pedaco, tuple) and len(pedaco) > 1:
                bruto = pedaco[1]
                break
        if not bruto:
            continue
        cabecalho = email.message_from_bytes(bruto)
        saida.append({
            "uid": numero.decode() if isinstance(numero, bytes) else str(numero),
            "de": _decodificar(cabecalho.get("From")),
            "assunto": _decodificar(cabecalho.get("Subject")) or "(sem assunto)",
            "data": _decodificar(cabecalho.get("Date")),
        })
    return saida


def _formatar(lista: list[dict], cabeca: str) -> str:
    if not lista:
        return cabeca + ": nada."
    linhas = []
    for indice, item in enumerate(lista, start=1):
        remetente = item["de"].split("<")[0].strip().strip('"') or item["de"]
        linhas.append(f"{indice}. {remetente} — {item['assunto'][:90]}")
    return cabeca + ":\n" + "\n".join(linhas)


def checar() -> str:
    usuario, senha, host = _credenciais()
    if not usuario:
        return host
    try:
        caixa = _conectar(usuario, senha, host)
        try:
            caixa.select("INBOX", readonly=True)
            tipo, dados = caixa.search(None, "(UNSEEN)")
            nao_lidas = len(dados[0].split()) if (tipo == "OK" and dados and dados[0]) else 0
            recentes = _mensagens(caixa, "INBOX", 5, apenas_nao_lidas=True)
        finally:
            try:
                caixa.logout()
            except Exception:                             # noqa: BLE001
                pass
    except imaplib.IMAP4.error as exc:
        return (f"O servidor de e-mail recusou o acesso ({exc}). "
                "No Gmail, a senha precisa ser uma senha de app e o IMAP tem de estar ligado.")
    except (socket.timeout, TimeoutError):
        return "O servidor de e-mail não respondeu a tempo."
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui checar o e-mail: {type(exc).__name__}: {exc}"

    global _ultima_lista
    _ultima_lista = recentes
    if not nao_lidas:
        return "Nenhum e-mail não lido na caixa de entrada."
    return _formatar(recentes, f"{nao_lidas} e-mail(s) não lido(s)")


def listar(limite: int = 8, pasta: str = "INBOX") -> str:
    usuario, senha, host = _credenciais()
    if not usuario:
        return host
    try:
        limite = max(1, min(_MAX_LIDOS, int(limite)))
    except (TypeError, ValueError):
        limite = 8
    try:
        caixa = _conectar(usuario, senha, host)
        try:
            lista = _mensagens(caixa, pasta, limite, apenas_nao_lidas=False)
        finally:
            try:
                caixa.logout()
            except Exception:                             # noqa: BLE001
                pass
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui listar o e-mail: {type(exc).__name__}: {exc}"

    global _ultima_lista
    _ultima_lista = lista
    return _formatar(lista, f"Últimos {len(lista)} e-mail(s) em {pasta}")


def ler(indice: int = 1) -> str:
    if not _ultima_lista:
        return "Primeiro me peça para listar os e-mails; aí eu abro um deles."
    try:
        indice = int(indice)
    except (TypeError, ValueError):
        indice = 1
    if not 1 <= indice <= len(_ultima_lista):
        return f"Só tenho {len(_ultima_lista)} e-mail(s) na última lista."

    escolhido = _ultima_lista[indice - 1]
    usuario, senha, host = _credenciais()
    if not usuario:
        return host
    try:
        caixa = _conectar(usuario, senha, host)
        try:
            caixa.select("INBOX", readonly=True)
            tipo, partes = caixa.fetch(escolhido["uid"].encode(), "(RFC822)")
            corpo = ""
            if tipo == "OK" and partes:
                for pedaco in partes:
                    if isinstance(pedaco, tuple) and len(pedaco) > 1:
                        corpo = _corpo(email.message_from_bytes(pedaco[1]))
                        break
        finally:
            try:
                caixa.logout()
            except Exception:                             # noqa: BLE001
                pass
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui abrir esse e-mail: {type(exc).__name__}: {exc}"

    if not corpo:
        corpo = "(este e-mail não tem texto simples legível)"
    return (f"De: {escolhido['de']}\nAssunto: {escolhido['assunto']}\n"
            f"Data: {escolhido['data']}\n\n{corpo}")


def buscar(termo: str) -> str:
    termo = (termo or "").strip()
    if not termo:
        return "O que eu procuro no e-mail?"
    usuario, senha, host = _credenciais()
    if not usuario:
        return host
    try:
        caixa = _conectar(usuario, senha, host)
        try:
            caixa.select("INBOX", readonly=True)
            achados: list[dict] = []
            for campo in ("SUBJECT", "FROM"):
                tipo, dados = caixa.search(None, campo, f'"{termo}"')
                if tipo == "OK" and dados and dados[0]:
                    for numero in dados[0].split()[-5:]:
                        tipo, partes = caixa.fetch(numero, "(RFC822.HEADER)")
                        if tipo != "OK" or not partes:
                            continue
                        for pedaco in partes:
                            if isinstance(pedaco, tuple) and len(pedaco) > 1:
                                cabecalho = email.message_from_bytes(pedaco[1])
                                achados.append({
                                    "uid": numero.decode(),
                                    "de": _decodificar(cabecalho.get("From")),
                                    "assunto": _decodificar(cabecalho.get("Subject")) or "(sem assunto)",
                                    "data": _decodificar(cabecalho.get("Date")),
                                })
                                break
        finally:
            try:
                caixa.logout()
            except Exception:                             # noqa: BLE001
                pass
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui buscar no e-mail: {type(exc).__name__}: {exc}"

    if not achados:
        return f"Nenhum e-mail com '{termo}' no assunto ou no remetente."
    vistos, unicos = set(), []
    for item in achados:
        if item["uid"] in vistos:
            continue
        vistos.add(item["uid"])
        unicos.append(item)
    global _ultima_lista
    _ultima_lista = unicos
    return _formatar(unicos, f"{len(unicos)} e-mail(s) com '{termo}'")


def email_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "checar").strip().lower()
    try:
        if acao in ("checar", "check", "nao_lidas", "não_lidas"):
            resposta = checar()
        elif acao in ("listar", "list"):
            resposta = listar(parameters.get("limit", 8),
                              parameters.get("folder") or parameters.get("pasta") or "INBOX")
        elif acao in ("ler", "read", "abrir"):
            resposta = ler(parameters.get("index", parameters.get("indice", 1)))
        elif acao in ("buscar", "search"):
            resposta = buscar(parameters.get("query") or parameters.get("termo") or "")
        else:
            resposta = "Posso checar os não lidos, listar, ler um e-mail ou buscar por assunto."
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui mexer no e-mail agora: {exc}"

    print(f"[E-mail] {resposta[:300]}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta[:300]}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "email_reader",
    "description": (
        "Lê a caixa de e-mail do usuário (IMAP, somente leitura): 'checar' conta os não lidos "
        "e mostra os remetentes, 'listar' traz os últimos, 'ler' abre um pelo número da lista "
        "e 'buscar' procura por assunto ou remetente. Não envia e não apaga nada."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "checar | listar | ler | buscar",
                "enum": ["checar", "listar", "ler", "buscar"],
            },
            "limit": {"type": "INTEGER", "description": "Quantos e-mails listar (padrão 8)."},
            "index": {"type": "INTEGER", "description": "Número do e-mail na última lista para abrir."},
            "query": {"type": "STRING", "description": "Termo para buscar no assunto ou remetente."},
            "folder": {"type": "STRING", "description": "Pasta IMAP, padrão INBOX."},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Lê a caixa de e-mail do usuário (checar, listar, ler, buscar).",
    "handler": email_action,
}
