import pathlib
import sys
import types
import unittest
from unittest import mock


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.is_json = True

    def get_json(self, silent=False):
        return self.data


class FakeApp:
    def __init__(self, result):
        self.view_functions = {'api_importar_excel': lambda: result}

    def make_response(self, value):
        if isinstance(value, FakeResponse):
            return value
        return FakeResponse(value[0].data if isinstance(value[0], FakeResponse) else value[0], value[1])


request = types.SimpleNamespace(files={}, args={})
try:
    from flask import Flask
except ImportError:
    Flask = None


class ImportFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exercise the wrapper without touching the production DB.
        import importlib.util
        fake_flask = types.ModuleType('flask')
        fake_flask.request = request
        fake_flask.jsonify = lambda data: FakeResponse(data)
        with mock.patch.dict(sys.modules, {'flask': fake_flask}):
            spec = importlib.util.spec_from_file_location(
                'isolated_import_feedback',
                pathlib.Path(__file__).resolve().parents[1] / 'import_feedback.py',
            )
            cls.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mod)

    def setUp(self):
        request.files = {'arquivo': types.SimpleNamespace(filename='alunos.xlsx')}
        request.args = {}

    def call_import(self, data):
        app = FakeApp(FakeResponse(data))
        self.mod.install_import_feedback(app)
        return app.make_response(app.view_functions['api_importar_excel']())

    def test_empty_sheet_is_error(self):
        response = self.call_import({'total_planilha': 0, 'abas_disponiveis': []})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['codigo'], 'NENHUM_REGISTRO_RECONHECIDO')

    def test_old_xls_is_explicitly_rejected(self):
        request.files['arquivo'].filename = 'alunos.xls'
        self.assertEqual(self.call_import({'total_planilha': 1}).status_code, 415)

    def test_partial_write_is_reported(self):
        request.args = {'confirmar': '1'}
        response = self.call_import({'total_planilha': 4, 'duplicados': 1, 'importados': 2})
        self.assertEqual(response.status_code, 207)
        self.assertEqual(response.data['falhas'], 1)

    def test_valid_preview_is_unchanged(self):
        self.assertEqual(self.call_import({'total_planilha': 2}).status_code, 200)

    def test_duplicates_do_not_count_as_failed_writes(self):
        request.args = {'confirmar': '1'}
        self.assertEqual(self.call_import({'total_planilha': 2, 'duplicados': 2, 'importados': 0}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
