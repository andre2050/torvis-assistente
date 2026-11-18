"""gui/design.py — Minimal Pro: as medidas e a folha de estilo base do TORVIS.

A paleta continua em gui/theme.C (todo mundo lê de lá). Este módulo cuida do
que não existia: a escala de espaçamento, os raios, e uma folha QSS única para
os widgets de base — barra de rolagem, dicas, menus, caixas de diálogo, campos.
Sem ela cada painel desenhava sua própria barra de rolagem, com três larguras
diferentes na mesma janela.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from gui.theme import C

# -- escala ---------------------------------------------------------------
ESPACO = (4, 6, 8, 12, 16, 24, 32)   # 4 = respiro curto, 32 = entre blocos
RAIO = 10                             # cartões e painéis
RAIO_ALTO = 14                        # janelas e overlays
HAIRLINE = 1                          # espessura de borda em toda parte


def qss() -> str:
    """Folha de estilo dos widgets de base.

    Só usa os hex da paleta: a troca de cor ao vivo (theme.retheme_all_widgets)
    funciona trocando essas strings exatas no stylesheet de cada widget.
    """
    return f"""
    QToolTip {{
        background: {C.PANEL2};
        color: {C.WHITE};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: 6px;
        padding: 6px 9px;
    }}
    QMenu {{
        background: {C.PANEL};
        color: {C.TEXT};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: {RAIO}px;
        padding: 6px;
    }}
    QMenu::item {{ padding: 7px 18px 7px 14px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {C.PRI_GHO}; color: {C.WHITE}; }}
    QMenu::separator {{ height: 1px; background: {C.BORDER}; margin: 6px 8px; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px 2px 2px 0; }}
    QScrollBar::handle:vertical {{
        background: {C.BORDER_A}; border-radius: 5px; min-height: 36px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {C.PRI_DIM}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0 2px 2px 2px; }}
    QScrollBar::handle:horizontal {{
        background: {C.BORDER_A}; border-radius: 5px; min-width: 36px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {C.PRI_DIM}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background: {C.PANEL2};
        color: {C.WHITE};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: {RAIO}px;
        padding: 8px 11px;
        selection-background-color: {C.PRI_DIM};
        selection-color: {C.WHITE};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border-color: {C.PRI};
    }}
    QComboBox QAbstractItemView {{
        background: {C.PANEL};
        color: {C.TEXT};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: 8px;
        selection-background-color: {C.PRI_GHO};
        selection-color: {C.WHITE};
        padding: 4px;
    }}

    QCheckBox, QRadioButton {{ color: {C.TEXT}; spacing: 8px; }}
    QLabel {{ color: {C.TEXT}; }}

    QDialog {{ background: {C.BG}; }}
    QGroupBox {{
        color: {C.TEXT_MED};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: {RAIO}px;
        margin-top: 14px;
        padding: 12px 10px 10px 10px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}

    QProgressBar {{
        background: {C.PANEL2};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: 6px;
        text-align: center;
        color: {C.TEXT};
        height: 8px;
    }}
    QProgressBar::chunk {{ background: {C.PRI}; border-radius: 5px; }}

    QPushButton {{
        background: {C.PANEL2};
        color: {C.TEXT};
        border: {HAIRLINE}px solid {C.BORDER};
        border-radius: {RAIO}px;
        padding: 8px 14px;
    }}
    QPushButton:hover {{ border-color: {C.BORDER_B}; color: {C.WHITE}; }}
    QPushButton:pressed {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
    QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}

    QSlider::groove:horizontal {{
        background: {C.PANEL2};
        border: 1px solid {C.BORDER};
        border-radius: 4px;
        height: 6px;
    }}
    QSlider::sub-page:horizontal {{ background: {C.PRI_DIM}; border-radius: 3px; }}
    QSlider::handle:horizontal {{
        background: {C.WHITE};
        border: 2px solid {C.PANEL};
        width: 14px; height: 14px;
        margin: -6px 0;
        border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{ background: {C.PRI}; }}

    QTabWidget::pane {{
        border: 1px solid {C.BORDER};
        border-radius: {RAIO}px;
        top: -1px;
        background: {C.PANEL};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {C.TEXT_DIM};
        border: none;
        padding: 7px 14px;
        margin-right: 4px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {C.WHITE}; border-bottom: 2px solid {C.PRI}; }}
    QTabBar::tab:hover {{ color: {C.TEXT}; }}

    QListWidget, QTreeWidget, QTableWidget {{
        background: {C.PANEL};
        color: {C.TEXT};
        border: 1px solid {C.BORDER};
        border-radius: {RAIO}px;
        padding: 4px;
    }}
    QListWidget::item {{ padding: 7px 9px; border-radius: 7px; }}
    QListWidget::item:selected {{ background: {C.PRI_GHO}; color: {C.WHITE}; }}
    QListWidget::item:hover {{ background: {C.PANEL2}; }}

    QScrollArea {{ background: transparent; border: none; }}
    QSplitter::handle {{ background: {C.BORDER}; }}
    QSplitter::handle:hover {{ background: {C.BORDER_B}; }}
    """



def apply(app: QApplication | None = None) -> None:
    """Aplica a folha base no aplicativo inteiro. Painéis continuam livres para
    sobrescrever o seu próprio estilo; isto é só o piso comum."""
    alvo = app or QApplication.instance()
    if alvo is not None:
        alvo.setStyleSheet(qss())
