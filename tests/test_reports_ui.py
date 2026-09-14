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
        self.assertIn('id="export-current-reports"', html)
        self.assertIn('Exportar CSV', html)

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

    def test_current_export_is_aggregated_and_spreadsheet_safe(self):
        js = (ROOT / 'static' / 'js' / 'relatorios_dashboard.js').read_text(encoding='utf-8')

        self.assertIn('buildCurrentReportCsv', js)
        self.assertIn('latestSnapshot = { dashboard, pipeline, pending, month }', js)
        self.assertIn("new Blob([csv], { type: 'text/csv;charset=utf-8' })", js)
        self.assertIn('relatorio_gerencial_atual', js)
        self.assertIn("/^[=+\\-@]/", js)
        self.assertNotIn('nome, email', js.lower())
        self.assertNotIn('/api/residentes/exportar-csv', js)


if __name__ == '__main__':
    unittest.main()
