import io
import unittest

from openpyxl import Workbook
from flexible_import import detect_header, parse_sheet, key_of


class FlexibleImportTests(unittest.TestCase):
    def make_sheet(self, headers, records, title='Alunos'):
        wb = Workbook()
        ws = wb.active
        ws.title = title
        ws.append(headers)
        for record in records:
            ws.append(record)
        return ws

    def test_header_aliases_and_accents(self):
        offset, mapping = detect_header([('Nome completo', 'Área médica', 'E-mail')])
        self.assertEqual(offset, 0)
        self.assertEqual(mapping['nome'], 0)
        self.assertEqual(mapping['especialidade'], 1)
        self.assertEqual(mapping['email'], 2)

    def test_regular_tabular_sheet(self):
        ws = self.make_sheet(['Nome', 'Especialidade', 'Mês/Ano', 'Modalidade'],
                             [['Maria Teste', 'Cardiologia', '2026-10', 'Optativo']])
        items, errors = parse_sheet(ws, ws.title)
        self.assertFalse(errors)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tipo_id'], 3)
        self.assertEqual(items[0]['mes_ano'], '2026-10')

    def test_missing_required_value_reports_line(self):
        ws = self.make_sheet(['Nome', 'Especialidade'], [['Maria Teste', None]])
        items, errors = parse_sheet(ws, ws.title)
        self.assertFalse(items)
        self.assertEqual(errors[0]['linha'], 2)

    def test_invalid_month_blocks_row(self):
        ws = self.make_sheet(['Nome', 'Especialidade', 'Competência'],
                             [['Maria Teste', 'Cardiologia', 'outubro']])
        items, errors = parse_sheet(ws, ws.title)
        self.assertFalse(items)
        self.assertIn('Mes/ano', errors[0]['motivo'])

    def test_duplicate_key_normalizes_accents(self):
        first = {'nome': 'João Teste', 'especialidade': 'Clínica Médica', 'mes_ano': '2026-10'}
        second = {'nome': 'JOAO TESTE', 'especialidade': 'Clinica Medica', 'mes_ano': '2026-10'}
        self.assertEqual(key_of(first), key_of(second))

    def test_unrecognized_sheet_reports_error(self):
        ws = self.make_sheet(['Código', 'Turma'], [[123, 'A']])
        items, errors = parse_sheet(ws, ws.title)
        self.assertFalse(items)
        self.assertEqual(errors[0]['linha'], 0)


if __name__ == '__main__':
    unittest.main()
