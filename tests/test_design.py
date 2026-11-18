"""O tema Minimal Pro precisa ser coerente e não pode quebrar a troca de cor ao vivo."""
import unittest

from gui import design
from gui.theme import C


class DesignTests(unittest.TestCase):
    def test_qss_usa_a_paleta(self):
        folha = design.qss()
        for cor in (C.BG, C.PANEL, C.PANEL2, C.BORDER, C.PRI, C.TEXT):
            self.assertIn(cor, folha, f"{cor} sumiu da folha de estilo")
        self.assertIn("QScrollBar", folha)
        self.assertIn("QToolTip", folha)

    def test_contraste_do_texto(self):
        def lum(h):
            v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
            return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
        a, b = lum(C.TEXT), lum(C.BG)
        razao = (max(a, b) + 0.05) / (min(a, b) + 0.05)
        self.assertGreater(razao, 7.0, f"contraste baixo: {razao:.1f}:1")

    def test_acento_salvo_nao_reescreve_a_base(self):
        """A cor guardada na config repintava a janela inteira no tom do acento."""
        from gui.theme import apply_ui_accent
        base, texto, acento = C.BG, C.TEXT, C.PRI
        apply_ui_accent("#00d4ff")
        try:
            self.assertEqual(C.BG, base)
            self.assertEqual(C.TEXT, texto)
            self.assertNotEqual(C.PRI, acento)
        finally:
            apply_ui_accent(base if False else acento)

    def test_escala_de_espaco_crescente(self):
        self.assertEqual(list(design.ESPACO), sorted(design.ESPACO))
        self.assertGreater(design.RAIO, 0)


if __name__ == "__main__":
    unittest.main()
