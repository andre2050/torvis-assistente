"""Modelos visuais do TORVIS.

O mesmo programa, duas leituras. `minimal` é o padrão: superfície chapada,
fio de cabelo, acento ciano. `carbon` é o oposto controlado: grafite quase
preto, raio menor, tipografia mais dura e um único acento âmbar de instrumento.
Trocar de modelo é trocar a paleta aqui — nada no resto do código precisa saber.
"""

MODELOS: dict[str, dict] = {
    "minimal": {
        "nome": "Minimal Pro",
        "raio": 14,          # molduras
        "raio_campo": 10,    # campos e cartões
        "cores": {},
    },
    "carbon": {
        "nome": "Carbon",
        "raio": 8,
        "raio_campo": 6,
        "cores": {
            "BG":       "#070809",
            "PANEL":    "#0d0f11",
            "PANEL2":   "#14171a",
            "BORDER":   "#1c2126",
            "BORDER_B": "#2c3339",
            "BORDER_A": "#232a30",
            "PRI":      "#c8a45c",
            "PRI_DIM":  "#8a7340",
            "PRI_GHO":  "#1d1810",
            "ACC":      "#e0603c",
            "TEXT":     "#e8eaec",
            "TEXT_DIM": "#6e767d",
            "TEXT_MED": "#9aa3aa",
            "WHITE":    "#ffffff",
            "DARK":     "#040505",
            "BAR_BG":   "#0a0b0d",
        },
    },
}

PADRAO = "minimal"


def nomes() -> list[str]:
    return list(MODELOS)
