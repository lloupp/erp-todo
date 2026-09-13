from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReportsUiRegressionTests(unittest.TestCase):
    def test_reports_page_uses_current_workflow_dashboard(self):
        html = (ROOT / 'templates' / 'relatorios.html').read_text(encoding='utf-8')

        self.assertIn('Visão gerencial', html)
        self.assertIn('relatorios_dashboard.js', html)
        self.assertIn('Fila por etapa', html)
        self.assertIn('Pagamentos pendentes', html)

        legacy_stage_labels = (
            'Venda realizada',
            'Pagamento confirmado',
            'Docs enviados',
            'Docs validados',
            'Vaga confirmada',
            'Comprovante recebido',
        )
        for label in legacy_stage_labels:
            self.assertNotIn(label, html)

    def test_reports_javascript_uses_aggregated_endpoints(self):
        js = (ROOT / 'static' / 'js' / 'relatorios_dashboard.js').read_text(encoding='utf-8')

        self.assertIn("getJson('/api/pipeline/dashboard')", js)
        self.assertIn("getJson('/api/pendencias')", js)
        self.assertIn("'/api/dashboard'", js)
        self.assertNotIn('/api/residentes?page=', js)
        self.assertNotIn('innerHTML', js)


if __name__ == '__main__':
    unittest.main()
