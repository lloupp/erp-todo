"""Make legacy spreadsheet import failures explicit rather than reporting success.

The older importer recognizes only month-named sheets and dated week blocks.
Keep its existing write behavior unchanged until a generic mapper is reviewed.
"""
from functools import wraps

from flask import jsonify, request


def install_import_feedback(app):
    original = app.view_functions['api_importar_excel']

    @wraps(original)
    def checked_import():
        uploaded = request.files.get('arquivo')
        if uploaded and uploaded.filename.lower().endswith('.xls'):
            return jsonify({
                'erro': 'O formato .xls antigo nao e suportado pelo leitor atual. Salve como .xlsx e tente novamente.',
                'codigo': 'FORMATO_XLS_NAO_SUPORTADO',
            }), 415

        response = app.make_response(original())
        if response.status_code != 200 or not response.is_json:
            return response
        data = response.get_json(silent=True)
        if not isinstance(data, dict):
            return response
        if data.get('total_planilha') == 0:
            return jsonify({
                'erro': 'Nenhum registro compativel encontrado. Confira as abas, cabecalhos e datas da planilha; nenhum dado foi importado.',
                'codigo': 'NENHUM_REGISTRO_RECONHECIDO',
                'abas_disponiveis': data.get('abas_disponiveis', []),
                'total_planilha': 0,
                'importados': 0,
            }), 422
        if request.args.get('confirmar', '0') == '1':
            novos = data.get('total_planilha', 0) - data.get('duplicados', 0)
            if novos > 0 and data.get('importados', 0) < novos:
                return jsonify({
                    **data,
                    'aviso': 'Alguns registros nao foram gravados. Revise os dados e confira a base antes de importar novamente.',
                    'codigo': 'IMPORTACAO_PARCIAL',
                    'falhas': novos - data.get('importados', 0),
                }), 207
        return response

    app.view_functions['api_importar_excel'] = checked_import
