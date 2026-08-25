import unittest

from collector.anp_bioenergy import latest_competence, parse_ethanol_csv, state_monthly


SAMPLE = """ANO;MÊS;GRANDE REGIÃO;UNIDADE DA FEDERAÇÃO;PRODUTO;PRODUÇÃO
2026;JUN;REGIÃO CENTRO OESTE;MATO GROSSO;ANIDRO;1000,5
2026;JUN;REGIÃO CENTRO OESTE;MATO GROSSO;HIDRATADO;2000,5
2026;JUL;REGIÃO CENTRO OESTE;MATO GROSSO;ANIDRO;1200
2026;JUL;REGIÃO CENTRO OESTE;MATO GROSSO;HIDRATADO;2200
"""


class AnpBioenergyTest(unittest.TestCase):
    def test_parse_and_latest(self):
        rows = parse_ethanol_csv(SAMPLE)
        self.assertEqual(len(rows), 4)
        self.assertEqual(latest_competence(rows), (2026, 7))

    def test_state_monthly(self):
        result = state_monthly(parse_ethanol_csv(SAMPLE))
        self.assertEqual(result[-1]["ethanol_m3"], 3400.0)
        self.assertEqual(result[-2]["ethanol_m3"], 3001.0)


if __name__ == "__main__":
    unittest.main()
