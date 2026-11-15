"""gui/finetuning_panel.py — LABORATÓRIO: conjunto de ajuste fino e o relatório do capstone.

POR QUE É UM PAINEL SEPARADO, E NÃO UM BOTÃO NO DRAWER
    As duas coisas aqui geram ARQUIVO a partir do que o assistente já acumulou.
    Nem toda a gente quer isso no caminho do dia a dia, e ninguém quer que isso
    aconteça sozinho. Por isso a regra do painel é a mesma da apresentação:
    nada roda no clique de abrir, nada escreve sem um segundo clique, e nada
    sai da máquina em momento nenhum.

O QUE ELE MOSTRA ANTES DE PEDIR QUALQUER COISA
    Quantas memórias existem, quantos exemplos sairiam delas, quantos tokens
    isso dá em estimativa e quantos dados sensíveis seriam mascarados. Um número
    antes do botão é a diferença entre decidir e apostar.
"""
from __future__ import annotations

import os
import platform
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from gui.overlays import _HudOverlay
from gui.style import hud_font, scroll_css
from gui.theme import C


def _abrir_pasta(caminho: str) -> None:
    """Abre a pasta no explorador de arquivos do sistema, sem depender de Qt."""
    try:
        pasta = str(Path(caminho))
        Path(pasta).mkdir(parents=True, exist_ok=True)
        sistema = platform.system()
        if sistema == "Windows":
            os.startfile(pasta)                                   # noqa: S606
        elif sistema == "Darwin":
            subprocess.Popen(["open", pasta])
        else:
            subprocess.Popen(["xdg-open", pasta])
    except Exception:
        pass


class LaboratorioOverlay(_HudOverlay):
    """Fine-tuning e capstone num lugar só, com número na tela antes da ação."""

    _pronto = pyqtSignal(dict)          # resultado de uma tarefa em segundo plano
    _OW = 720

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ocupado = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            LaboratorioOverlay {{
                background: rgba(0, 6, 10, 249);
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._pronto.connect(self._ao_terminar)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(22, 18, 22, 18)
        externo.setSpacing(10)

        titulo = QLabel("🎓  LABORATÓRIO")
        titulo.setFont(hud_font(13, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        externo.addWidget(titulo)

        legenda = QLabel("O que o assistente já aprendeu, transformado em arquivo: "
                         "um conjunto de ajuste fino para revisar e o relatório técnico "
                         "do projeto. Nada é enviado para fora desta máquina.")
        legenda.setWordWrap(True)
        legenda.setFont(hud_font(8))
        legenda.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        externo.addWidget(legenda)

        externo.addWidget(self._caixa_treino())
        externo.addWidget(self._caixa_capstone())

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setFont(hud_font(8))
        self._status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        externo.addWidget(self._status)

        rodape = QLabel("Revisão obrigatória: o conjunto é montado de memórias, sessões e "
                        "correções que você registrou. Dados sensíveis saem mascarados, mas "
                        "quem decide enviar é você.")
        rodape.setWordWrap(True)
        rodape.setFont(hud_font(7))
        rodape.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        externo.addWidget(rodape)

        # O panorama é lido no próximo ciclo do laço de eventos: abrir o painel
        # não pode custar a leitura de todos os arquivos de memória.
        QTimer.singleShot(0, self.analisar)

    # ───────────────────────────────────────────────────────────── construção
    def _caixa_treino(self) -> QWidget:
        caixa = QWidget()
        caixa.setStyleSheet(f"background: {C.PANEL}; border: 1px solid {C.BORDER}; "
                            f"border-radius: 5px;")
        lay = QVBoxLayout(caixa)
        lay.setContentsMargins(12, 10, 12, 11)
        lay.setSpacing(6)

        titulo = QLabel("①  CONJUNTO DE AJUSTE FINO")
        titulo.setFont(hud_font(8, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        lay.addWidget(titulo)

        self._resumo = QLabel("Lendo a memória…")
        self._resumo.setWordWrap(True)
        self._resumo.setFont(hud_font(8))
        self._resumo.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        lay.addWidget(self._resumo)

        self._detalhe = QLabel("")
        self._detalhe.setWordWrap(True)
        self._detalhe.setFont(hud_font(7))
        self._detalhe.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        lay.addWidget(self._detalhe)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        self._btn_analisar = self._botao("ANALISAR", self.analisar)
        self._btn_gerar = self._botao("GERAR CONJUNTO", self.gerar_conjunto, C.PRI)
        self._btn_pasta = self._botao("ABRIR PASTA", self.abrir_pasta_treino)
        for botao in (self._btn_analisar, self._btn_gerar, self._btn_pasta):
            linha.addWidget(botao)
        linha.addStretch(1)
        lay.addLayout(linha)
        return caixa

    def _caixa_capstone(self) -> QWidget:
        caixa = QWidget()
        caixa.setStyleSheet(f"background: {C.PANEL}; border: 1px solid {C.BORDER}; "
                            f"border-radius: 5px;")
        lay = QVBoxLayout(caixa)
        lay.setContentsMargins(12, 10, 12, 11)
        lay.setSpacing(6)

        titulo = QLabel("②  CAPSTONE")
        titulo.setFont(hud_font(8, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        lay.addWidget(titulo)

        self._capstone_info = QLabel("Conta módulos, linhas, testes e documentos "
                                     "do projeto e escreve o documento com esses números.")
        self._capstone_info.setWordWrap(True)
        self._capstone_info.setFont(hud_font(8))
        self._capstone_info.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        lay.addWidget(self._capstone_info)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        self._btn_relatorio = self._botao("RELATÓRIO TÉCNICO", self.gerar_relatorio, C.PRI)
        self._btn_roteiro = self._botao("ROTEIRO DE DEFESA", self.gerar_roteiro)
        for botao in (self._btn_relatorio, self._btn_roteiro):
            linha.addWidget(botao)
        linha.addStretch(1)
        lay.addLayout(linha)
        return caixa

    def _botao(self, texto: str, slot, cor: str | None = None) -> QPushButton:
        botao = QPushButton(texto)
        botao.setFixedHeight(27)
        botao.setFont(hud_font(7, QFont.Weight.Bold))
        botao.setCursor(Qt.CursorShape.PointingHandCursor)
        cor = cor or C.TEXT_MED
        botao.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {cor};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 0 14px; }}
            QPushButton:hover {{ border-color: {C.BORDER_B}; color: {C.TEXT}; }}
            QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}
        """)
        botao.clicked.connect(slot)
        return botao

    # ───────────────────────────────────────────────────────────────── ações
    def _dizer(self, texto: str, cor: str = None) -> None:
        self._status.setStyleSheet(
            f"color: {cor or C.TEXT_MED}; background: transparent;")
        self._status.setText(texto)

    def _em_segundo_plano(self, tarefa, rotulo: str) -> None:
        """Uma tarefa de disco por vez, sem travar a interface."""
        if self._ocupado:
            return
        self._ocupado = True
        for botao in (self._btn_analisar, self._btn_gerar, self._btn_pasta,
                      self._btn_relatorio, self._btn_roteiro):
            botao.setEnabled(False)
        self._dizer(f"{rotulo}…", C.PRI)

        def _rodar():
            try:
                self._pronto.emit({"ok": True, "dados": tarefa(), "rotulo": rotulo})
            except Exception as exc:                     # disco, permissão, import
                self._pronto.emit({"ok": False, "erro": f"{type(exc).__name__}: {exc}",
                                   "rotulo": rotulo})

        threading.Thread(target=_rodar, daemon=True).start()

    def _ao_terminar(self, resultado: dict) -> None:
        self._ocupado = False
        for botao in (self._btn_analisar, self._btn_gerar, self._btn_pasta,
                      self._btn_relatorio, self._btn_roteiro):
            botao.setEnabled(True)
        if not resultado.get("ok"):
            self._dizer(f"{resultado.get('rotulo')} não deu certo: {resultado.get('erro')}",
                        C.RED)
            return
        dados = resultado.get("dados") or {}
        acao = dados.get("acao")
        if acao == "analisar":
            self._pintar_estado(dados["estado"])
            self._dizer("Panorama atualizado.", C.GREEN)
        elif acao == "conjunto":
            arquivos = dados["resultado"]["arquivos"]
            resumo = dados["resultado"]["resumo"]
            # Sem reanalisar aqui: a leitura de memória terminaria depois e
            # trocaria esta mensagem por "Panorama atualizado", que não diz
            # nada sobre o arquivo que acabou de ser gravado.
            self._detalhe.setText(
                f"{resumo['exemplos_treino']} exemplo(s) de treino · "
                f"{resumo['exemplos_validacao']} de validação · "
                f"~{resumo['tokens_estimados']} tokens · {Path(arquivos['treino']).parent}")
            self._dizer(f"Conjunto gravado: {resumo['exemplos_treino']} exemplos de treino e "
                        f"{resumo['exemplos_validacao']} de validação em "
                        f"{Path(arquivos['treino']).parent}.", C.GREEN)
        elif acao == "relatorio":
            self._dizer(f"Relatório gravado em {Path(dados['caminho']['markdown']).parent} "
                        f"(.md e .html).", C.GREEN)
        elif acao == "roteiro":
            self._dizer(f"Roteiro com {dados['caminho']['slides']} tópicos gravado em "
                        f"{Path(dados['caminho']['roteiro']).parent}.", C.GREEN)

    # ─────────────────────────────────────────────────────────── o que roda
    def analisar(self) -> None:
        self._em_segundo_plano(self._tarefa_analisar, "Lendo memória")

    def _tarefa_analisar(self) -> dict:
        from core import finetuning
        return {"acao": "analisar", "estado": finetuning.estado()}

    def _pintar_estado(self, estado: dict) -> None:
        exemplos = estado["exemplos"]
        origens = estado.get("por_origem") or {}
        partes = [f"{quantidade} de {nome}" for nome, quantidade in origens.items()]
        self._resumo.setText(
            f"{exemplos} exemplo(s) a partir de {estado['memorias']} memória(s), "
            f"{estado['lembrancas']} lembrança(s), {estado['sessoes']} sessão(ões) e "
            f"{estado['correcoes']} correção(ões)."
            + (f"  ({', '.join(partes)})" if partes else ""))

        linhas = [f"Estimativa: {estado['tokens_estimados']} tokens · "
                  f"{estado['validos']} exemplo(s) válidos depois da revisão automática."]
        mascaras = estado.get("mascaras") or {}
        if mascaras:
            resumo_mascaras = ", ".join(f"{q} {n}" for n, q in mascaras.items())
            linhas.append(f"Dados sensíveis que sairiam mascarados: {resumo_mascaras}.")
        else:
            linhas.append("Nenhum dado sensível detectado até aqui.")
        for aviso in (estado.get("avisos") or [])[:2]:
            linhas.append(aviso)
        self._detalhe.setText("  ".join(linhas))

        self._btn_gerar.setEnabled(exemplos > 0)

    def gerar_conjunto(self) -> None:
        self._em_segundo_plano(self._tarefa_conjunto, "Montando o conjunto")

    def _tarefa_conjunto(self) -> dict:
        from core import finetuning
        exemplos, _ = finetuning.coletar()
        return {"acao": "conjunto", "resultado": finetuning.exportar(exemplos)}

    def abrir_pasta_treino(self) -> None:
        try:
            from core.finetuning import DIRETORIO_TREINO
            _abrir_pasta(str(DIRETORIO_TREINO))
            self._dizer(f"Abrindo {DIRETORIO_TREINO}.", C.TEXT_MED)
        except Exception as exc:
            self._dizer(f"Não consegui abrir a pasta: {type(exc).__name__}", C.RED)

    def gerar_relatorio(self) -> None:
        self._em_segundo_plano(self._tarefa_relatorio, "Escrevendo o relatório")

    def _tarefa_relatorio(self) -> dict:
        from core import capstone
        return {"acao": "relatorio", "caminho": capstone.gerar()}

    def gerar_roteiro(self) -> None:
        self._em_segundo_plano(self._tarefa_roteiro, "Montando o roteiro")

    def _tarefa_roteiro(self) -> dict:
        from core import capstone
        return {"acao": "roteiro", "caminho": capstone.gerar_roteiro()}
