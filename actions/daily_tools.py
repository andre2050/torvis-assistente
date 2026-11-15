"""Ferramentas do dia a dia: calculadora, conversor de unidades e senhas.

Nada aqui usa `eval`. Uma calculadora que chama `eval` num assistente que ouve
a voz do usuário executa o que aparecer na fala — inclusive `__import__`. A
expressão é lida com `ast` e só passam números, as quatro operações, potência,
resto, parênteses e um punhado de funções matemáticas conhecidas.
"""
from __future__ import annotations

import ast
import math
import operator
import secrets
import string

_MAX_EXPRESSAO = 200

_BINARIAS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARIAS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _arredondar(valor: float, casas: float = 0) -> float:
    """`round` aceitando as casas como float, do jeito que vem da expressão."""
    return float(round(valor, int(casas)))


def _maior(*valores: float) -> float:
    return float(max(valores))


def _menor(*valores: float) -> float:
    return float(min(valores))


_FUNCOES = {
    "sqrt": math.sqrt, "raiz": math.sqrt, "abs": abs, "round": _arredondar,
    "arredondar": _arredondar, "max": _maior, "maior": _maior,
    "min": _menor, "menor": _menor, "pow": math.pow,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "floor": math.floor, "ceil": math.ceil, "hipot": math.hypot,
}
_CONSTANTES = {"pi": math.pi, "e": math.e, "tau": math.tau}

# -- unidades: tudo é convertido para a unidade base da família --------------
# valor em base = valor * fator
_UNIDADES = {
    "comprimento": {
        "base": "m",
        "m": 1.0, "metro": 1.0, "metros": 1.0,
        "km": 1000.0, "quilometro": 1000.0, "quilometros": 1000.0,
        "cm": 0.01, "centimetro": 0.01, "centimetros": 0.01,
        "mm": 0.001, "milimetro": 0.001, "milimetros": 0.001,
        "milha": 1609.344, "milhas": 1609.344, "mi": 1609.344,
        "pe": 0.3048, "pes": 0.3048, "ft": 0.3048,
        "polegada": 0.0254, "polegadas": 0.0254, "in": 0.0254,
        "jarda": 0.9144, "jardas": 0.9144, "yd": 0.9144,
    },
    "massa": {
        "base": "kg",
        "kg": 1.0, "quilo": 1.0, "quilos": 1.0, "quilograma": 1.0, "quilogramas": 1.0,
        "g": 0.001, "grama": 0.001, "gramas": 0.001,
        "mg": 1e-6, "miligrama": 1e-6, "miligramas": 1e-6,
        "tonelada": 1000.0, "toneladas": 1000.0, "t": 1000.0,
        "libra": 0.45359237, "libras": 0.45359237, "lb": 0.45359237,
        "onca": 0.028349523125, "oncas": 0.028349523125, "oz": 0.028349523125,
    },
    "volume": {
        "base": "l",
        "l": 1.0, "litro": 1.0, "litros": 1.0,
        "ml": 0.001, "mililitro": 0.001, "mililitros": 0.001,
        "galao": 3.785411784, "galoes": 3.785411784, "gal": 3.785411784,
        "xicara": 0.24, "xicaras": 0.24,
    },
    "tempo": {
        "base": "s",
        "s": 1.0, "segundo": 1.0, "segundos": 1.0,
        "min": 60.0, "minuto": 60.0, "minutos": 60.0,
        "h": 3600.0, "hora": 3600.0, "horas": 3600.0,
        "dia": 86400.0, "dias": 86400.0,
        "semana": 604800.0, "semanas": 604800.0,
    },
    "dados": {
        "base": "mb",
        "byte": 1.0 / (1024 * 1024), "bytes": 1.0 / (1024 * 1024),
        "kb": 1.0 / 1024, "kilobyte": 1.0 / 1024, "kbytes": 1.0 / 1024,
        "mb": 1.0, "megabyte": 1.0, "megabytes": 1.0,
        "gb": 1024.0, "gigabyte": 1024.0, "gigabytes": 1024.0,
        "tb": 1024.0 ** 2, "terabyte": 1024.0 ** 2, "terabytes": 1024.0 ** 2,
    },
    "velocidade": {
        "base": "kmh",
        "kmh": 1.0, "km/h": 1.0, "quilometro por hora": 1.0,
        "ms": 3.6, "m/s": 3.6, "metro por segundo": 3.6,
        "mph": 1.609344, "milha por hora": 1.609344,
        "no": 1.852, "nos": 1.852, "nó": 1.852,
    },
}

_TEMPERATURAS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _numero_texto(valor: float, max_decimais: int = 10) -> str:
    """Número no jeito brasileiro: vírgula decimal, ponto nos milhares.

    `max_decimais` existe porque converter 10 km em milhas não precisa de dez
    casas: quem ouve a resposta quer "6,2137 milhas", não a fração inteira.
    """
    if valor != valor or valor in (float("inf"), float("-inf")):
        return "valor inválido"
    if valor and abs(valor) < 10 ** (-max_decimais):
        return f"{valor:.6g}".replace(".", ",")          # muito pequeno: notação curta
    if abs(valor) >= 1e15:
        return f"{valor:.6e}".replace(".", ",")
    if abs(valor - round(valor)) < 1e-9:
        return f"{int(round(valor)):,}".replace(",", ".")
    texto = f"{valor:,.{max_decimais}f}".rstrip("0").rstrip(".")
    return texto.replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")


def _avaliar(no: ast.AST) -> float:
    if isinstance(no, ast.Expression):
        return _avaliar(no.body)
    if isinstance(no, ast.Constant):
        if isinstance(no.value, bool) or not isinstance(no.value, (int, float)):
            raise ValueError("só números")
        return float(no.value)
    if isinstance(no, ast.BinOp):
        funcao = _BINARIAS.get(type(no.op))
        if not funcao:
            raise ValueError("operação não permitida")
        esquerda, direita = _avaliar(no.left), _avaliar(no.right)
        if funcao is operator.pow and (abs(direita) > 512 or abs(esquerda) > 1e6):
            raise ValueError("potência grande demais")
        return funcao(esquerda, direita)
    if isinstance(no, ast.UnaryOp):
        funcao = _UNARIAS.get(type(no.op))
        if not funcao:
            raise ValueError("operação não permitida")
        return funcao(_avaliar(no.operand))
    if isinstance(no, ast.Name):
        if no.id.lower() in _CONSTANTES:
            return _CONSTANTES[no.id.lower()]
        raise ValueError(f"nome desconhecido: {no.id}")
    if isinstance(no, ast.Call):
        if not isinstance(no.func, ast.Name):
            raise ValueError("chamada não permitida")
        funcao = _FUNCOES.get(no.func.id.lower())
        if not funcao or no.keywords:
            raise ValueError(f"função desconhecida: {no.func.id}")
        return float(funcao(*[_avaliar(a) for a in no.args]))
    raise ValueError("expressão não permitida")


def calcular(expressao: str) -> str:
    """Resolve uma expressão aritmética e devolve o resultado falado."""
    texto = (expressao or "").strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    if not texto:
        return "Faltou a conta que você quer que eu faça."
    if len(texto) > _MAX_EXPRESSAO:
        return "Essa conta é longa demais para eu resolver de cabeça."

    # "20% de 350" e "15 por cento de 80" — do jeito que se fala.
    baixo = texto.lower()
    if "%" in baixo and " de " in baixo:
        partes = baixo.split(" de ")
        if len(partes) == 2:
            pct = partes[0].replace("por cento", "").replace("%", "").strip()
            base = partes[1]
            try:
                return ("O resultado é "
                        + _numero_texto(_avaliar(ast.parse(pct, mode="eval")) / 100
                                        * _avaliar(ast.parse(base, mode="eval"))) + ".")
            except Exception:                              # noqa: BLE001
                pass

    def _tentar(entrada: str) -> float:
        arvore = ast.parse(entrada, mode="eval")
        # "0,5*8" é lido pelo Python como uma tupla (0, 40). Isso não é conta:
        # é vírgula decimal, então vale tentar de novo trocando por ponto.
        if isinstance(arvore.body, ast.Tuple):
            raise SyntaxError("vírgula decimal")
        return _avaliar(arvore)

    try:
        resultado = _tentar(texto)
    except ZeroDivisionError:
        return "Não dá para dividir por zero."
    except (SyntaxError, ValueError) as primeira:
        if "," not in texto:
            return f"Não consegui resolver essa conta ({primeira})."
        try:
            resultado = _tentar(texto.replace(",", "."))
        except ZeroDivisionError:
            return "Não dá para dividir por zero."
        except Exception as exc:                          # noqa: BLE001
            return f"Não consegui resolver essa conta ({exc})."
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui resolver essa conta ({exc})."
    return f"O resultado é {_numero_texto(resultado)}."


def converter(valor: float, de: str, para: str) -> str:
    """Converte unidades de comprimento, massa, volume, tempo, dados, velocidade e temperatura."""
    origem = (de or "").strip().lower()
    destino = (para or "").strip().lower()
    try:
        numero = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return "O valor para converter precisa ser um número."

    if origem in _TEMPERATURAS and destino in _TEMPERATURAS:
        celsius = {"c": numero, "celsius": numero,
                   "f": (numero - 32) * 5 / 9, "fahrenheit": (numero - 32) * 5 / 9,
                   "k": numero - 273.15, "kelvin": numero - 273.15}[origem]
        resposta = {"c": celsius, "celsius": celsius,
                    "f": celsius * 9 / 5 + 32, "fahrenheit": celsius * 9 / 5 + 32,
                    "k": celsius + 273.15, "kelvin": celsius + 273.15}[destino]
        return (f"{_numero_texto(numero)} {de} equivale a "
                f"{_numero_texto(resposta, 4)} {para}.")

    for tabela in _UNIDADES.values():
        if origem in tabela and destino in tabela:
            base = numero * tabela[origem]
            return (f"{_numero_texto(numero)} {de} equivale a "
                    f"{_numero_texto(base / tabela[destino], 4)} {para}.")

    return (f"Ainda não sei converter {de} para {para}. "
            "Conheço comprimento, massa, volume, tempo, dados, velocidade e temperatura.")


def gerar_senha(tamanho: int = 16, simbolos: bool = True, numeros: bool = True,
                maiusculas: bool = True, evitar_ambiguos: bool = True) -> str:
    """Senha aleatória com `secrets`, garantindo pelo menos um de cada grupo escolhido."""
    try:
        tamanho = int(tamanho)
    except (TypeError, ValueError):
        tamanho = 16
    tamanho = max(8, min(128, tamanho))

    minusculas = string.ascii_lowercase
    maius = string.ascii_uppercase if maiusculas else ""
    dig = string.digits if numeros else ""
    simb = "!@#$%&*+-=?_" if simbolos else ""
    if evitar_ambiguos:
        ambiguos = "0O1lI|`'\";:,.o"
        limpar = lambda s: "".join(c for c in s if c not in ambiguos)   # noqa: E731
        minusculas, maius, dig, simb = limpar(minusculas), limpar(maius), limpar(dig), limpar(simb)

    grupos = [g for g in (minusculas, maius, dig, simb) if g]
    if not grupos:
        grupos = [string.ascii_letters]
    alfabeto = "".join(grupos)

    senha = [secrets.choice(g) for g in grupos]
    senha += [secrets.choice(alfabeto) for _ in range(tamanho - len(senha))]
    # Embaralha com Fisher-Yates usando `secrets`, não `random`.
    for i in range(len(senha) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        senha[i], senha[j] = senha[j], senha[i]
    return "".join(senha)


def _log(mensagem: str, player=None) -> None:
    print(f"[Ferramentas] {mensagem}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {mensagem}")
        except Exception:                                 # noqa: BLE001
            pass


def daily_tools_action(parameters: dict, player=None, session_memory=None) -> str:
    """Despacha calculadora, conversor e senha."""
    acao = str(parameters.get("action") or "").strip().lower()
    try:
        if acao in ("calcular", "calculate", "conta", "calculadora"):
            resposta = calcular(parameters.get("expression") or parameters.get("expressao") or "")
        elif acao in ("converter", "convert", "conversor"):
            resposta = converter(parameters.get("value", parameters.get("valor")),
                                 parameters.get("from_unit") or parameters.get("de") or "",
                                 parameters.get("to_unit") or parameters.get("para") or "")
        elif acao in ("senha", "password", "gerar_senha"):
            senha = gerar_senha(
                parameters.get("length", parameters.get("tamanho", 16)),
                simbolos=parameters.get("symbols", True) is not False,
                numeros=parameters.get("digits", True) is not False,
                maiusculas=parameters.get("uppercase", True) is not False,
            )
            resposta = f"Senha de {len(senha)} caracteres: {senha}"
        else:
            resposta = ("Diga o que você quer: calcular uma conta, converter unidades "
                        "ou gerar uma senha.")
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui completar isso: {exc}"
    _log(resposta, player)
    return resposta


TOOL = {
    "name": "daily_tools",
    "description": (
        "Ferramentas do dia a dia que não dependem de internet: 'calcular' resolve contas "
        "(inclusive '20% de 350' e funções como sqrt, log, sin); 'converter' troca unidades "
        "de comprimento, massa, volume, tempo, dados, velocidade e temperatura; 'senha' gera "
        "uma senha aleatória forte. Use para qualquer conta, conversão ou senha pedida."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "calcular | converter | senha",
                "enum": ["calcular", "converter", "senha"],
            },
            "expression": {"type": "STRING", "description": "A conta, ex: '12*7+3', 'sqrt(144)', '20% de 350'."},
            "value": {"type": "NUMBER", "description": "Valor numérico a converter."},
            "from_unit": {"type": "STRING", "description": "Unidade de origem, ex: 'km', 'kg', 'celsius', 'gb'."},
            "to_unit": {"type": "STRING", "description": "Unidade de destino, ex: 'milhas', 'libras', 'fahrenheit'."},
            "length": {"type": "INTEGER", "description": "Tamanho da senha (8 a 128, padrão 16)."},
            "symbols": {"type": "BOOLEAN", "description": "Incluir símbolos na senha (padrão sim)."},
            "digits": {"type": "BOOLEAN", "description": "Incluir números na senha (padrão sim)."},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Calculadora, conversor de unidades e gerador de senhas, sem internet.",
    "handler": daily_tools_action,
}
