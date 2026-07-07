"""
Importador: Observership_2025_Consolidado.xlsx → estagios.db
Uso: python importar_consolidado.py [--confirmar]
  Sem --confirmar: apenas exibe o preview (sem gravar).
  Com --confirmar: grava no banco.
"""
import sys
import re
import sqlite3
import os
import openpyxl

XLSX = r'C:\Users\eduardo.dantas\Downloads\Observership_2025_Consolidado.xlsx'
DB   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'estagios.db')

CONFIRMAR = '--confirmar' in sys.argv

# ── Mapeamento de meses PT ────────────────────────────────────
MESES_PT = {
    'Janeiro':'01', 'Fevereiro':'02', 'Março':'03', 'Abril':'04',
    'Maio':'05',    'Junho':'06',     'Julho':'07', 'Agosto':'08',
    'Setembro':'09','Outubro':'10',   'Novembro':'11','Dezembro':'12',
    'Marco':'03',   'Marcao':'03',
}

def parse_mes(mes_str, inicio_str):
    s = str(mes_str or '').strip()
    # Coluna contém só o ano ("2026") → deriva do campo início
    if re.match(r'^\d{4}$', s) and inicio_str:
        p = str(inicio_str).split('/')
        if len(p) == 3:
            return f'{s}-{p[1].zfill(2)}'
    # Formato "Janeiro-25" / "Janeiro-2025"
    for pt, num in MESES_PT.items():
        if s.lower().startswith(pt.lower()):
            sufixo = s.split('-')[-1].strip() if '-' in s else '25'
            ano = '20' + sufixo if len(sufixo) == 2 else sufixo
            return f'{ano}-{num}'
    return None

# ── Normaliza data DD/MM/AAAA → AAAA-MM-DD ───────────────────
def parse_date(v):
    if not v: return None
    s = str(v).strip()
    if re.match(r'\d{2}/\d{2}/\d{4}', s):
        d, m, a = s[:10].split('/')
        return f'{a}-{m}-{d}'
    if re.match(r'\d{4}-\d{2}-\d{2}', s):
        return s[:10]
    return None

# ── Normaliza valor ───────────────────────────────────────────
def parse_valor(v):
    """Retorna (float_ou_None, status_pagamento)."""
    if not v or str(v).strip() in ('None', ''):
        return None, 'Pendente'
    s = str(v).strip()
    if s.lower() == 'isento':
        return None, 'Isento'
    # Remove "R$", pontos de milhar, troca vírgula decimal
    s = re.sub(r'[R$\s]', '', s).replace('.', '').replace(',', '.')
    try:
        return float(s), 'Pendente'
    except ValueError:
        return None, 'Pendente'

# ── Normaliza envio_certificado ───────────────────────────────
def parse_cert(v):
    if not v or str(v).strip() in ('None', ''):
        return None
    s = str(v).strip().lower()
    # E-mails padrão no campo errado
    if '@' in s:
        return 'Pendente'
    if re.match(r'\d{4}-\d{2}-\d{2}', str(v).strip()):
        return 'Enviado'
    enviado_pats = ['envi', 'enviou', 'enviado']
    ecommerce_pats = ['ecommerce', 'ecommecer', 'e-commerce', 'ecomerce']
    pendente_pats = ['pendente', 'pend', 'a enviar', 'processo', 'documentação',
                     'falta', 'orientações', 'orienta']
    nao_pats = ['não enviado', 'nao enviado']
    for p in nao_pats:
        if p in s: return 'Não enviado'
    for p in ecommerce_pats:
        if p in s: return 'e-commerce'
    for p in enviado_pats:
        if p in s: return 'Enviado'
    for p in pendente_pats:
        if p in s: return 'Pendente'
    return str(v).strip()[:100]

# ── Normaliza especialidade ───────────────────────────────────
ESP_ALIASES = {
    # ALL CAPS → sentence case
    'CIRURGIA GERAL': 'Cirurgia geral',
    'ANESTESIOLOGIA': 'Anestesiologia',
    'CLÍNICA MÉDICA': 'Clínica médica',
    'CLINICA MEDICA': 'Clínica médica',
    'CIRURGIA CARDIOVASCULAR': 'Cirurgia cardiovascular',
    'GINECOLOGIA E OBSTETRÍCIA': 'Ginecologia e obstetrícia',
    'GINECOLOGIA E OBSTETRICIA': 'Ginecologia e obstetrícia',
    'CIRURGIA PEDIÁTRICA': 'Cirurgia pediátrica',
    'CIRURGIA PEDIATRICA': 'Cirurgia pediátrica',
    'CUIDADOS PALIATIVOS': 'Cuidados paliativos',
    'EMERGÊNCIA ADULTA SUS E CONVÊNIO': 'Emergência adulta SUS e convênio',
    'EMERGENCIA ADULTA SUS E CONVENIO': 'Emergência adulta SUS e convênio',
    'EMERGÊNCIA ADULTA': 'Emergência adulta',
    'CIRURGIA ONCOLÓGICA': 'Cirurgia oncológica',
    'CIRURGIA ONCOLOGICA': 'Cirurgia oncológica',
    'NEUROCIRURGIA': 'Neurocirurgia',
    'DERMATOLOGIA': 'Dermatologia',
    'OFTALMOLOGIA': 'Oftalmologia',
    'CARDIOLOGIA': 'Cardiologia',
    'PEDIATRIA': 'Pediatria',
    'ORTOPEDIA E TRAUMATOLOGIA': 'Ortopedia e traumatologia',
    'OTORRINOLARINGOLOGIA': 'Otorrinolaringologia',
    # Capitalização variada → forma padrão
    'Cirurgia Geral': 'Cirurgia geral',
    'Cirurgia Cardiovascular': 'Cirurgia cardiovascular',
    'Cirurgia Plástica': 'Cirurgia plástica',
    'Cirurgia Torácica': 'Cirurgia torácica',
    'Cirurgia de Cabeça e Pescoço': 'Cirurgia de cabeça e pescoço',
    'Clínica Médica': 'Clínica médica',
    'cLínica médica': 'Clínica médica',
    'Emergência Cardiológica': 'Emergência cardiológica',
    'Ginecologia e Obstetrícia': 'Ginecologia e obstetrícia',
    'Terapia Intensiva': 'Terapia intensiva',
    'Oncologia Clinica': 'Oncologia clínica',
    'Oncologia Clínica': 'Oncologia clínica',
    'Cirurgia do Aparelho Digestivo': 'Cirurgia do aparelho digestivo',
    'Endoscopia Digestiva': 'Endoscopia digestiva',
    'Obsevacional': 'Observacional',
}

def norm_esp(v):
    if not v: return None
    s = str(v).strip()
    return ESP_ALIASES.get(s, s)

# ── Normaliza nome ────────────────────────────────────────────
def title_pt(nome):
    minusc = {'de','da','do','das','dos','e','em','na','no','nas','nos','a','o','as','os'}
    partes = nome.strip().split()
    result = []
    for i, p in enumerate(partes):
        if i == 0 or p.lower() not in minusc:
            result.append(p[0].upper() + p[1:].lower() if p else p)
        else:
            result.append(p.lower())
    return ' '.join(result)

def norm_nome(v):
    if not v: return None
    s = str(v).strip()
    if s == s.upper() and len(s) > 3:
        s = title_pt(s)
    return s

# ── Leitura da planilha ───────────────────────────────────────
print(f'Lendo {XLSX} ...')
wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb['Consolidado']

registros = []
erros = []
for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
    mes, inicio, nome, modal, esp, cracha, valor, termino, email, tel, cert, obs = row
    if not nome or str(nome).strip() in ('', 'None'): continue

    mes_ano = parse_mes(mes, inicio)
    if not mes_ano:
        erros.append(f'L{i}: mês inválido {repr(mes)} nome={repr(nome)}')
        continue

    nome_n    = norm_nome(nome)
    esp_n     = norm_esp(esp) or 'Não informada'
    inicio_n  = parse_date(inicio)
    termino_n = parse_date(termino)
    val_f, status_pag = parse_valor(valor)
    cert_n    = parse_cert(cert)
    cracha_n  = None if not cracha or str(cracha).strip() in ('0', 'None', '') else str(cracha).strip()
    email_n   = str(email).strip() if email else None
    tel_n     = str(tel).strip() if tel else None
    obs_n     = str(obs).strip() if obs else None

    registros.append({
        'mes_ano': mes_ano,
        'nome': nome_n,
        'especialidade': esp_n,
        'inicio': inicio_n,
        'termino': termino_n,
        'valor': val_f,
        'status_pagamento': status_pag,
        'envio_certificado': cert_n,
        'cracha': cracha_n,
        'email': email_n,
        'telefone': tel_n,
        'observacao': obs_n,
    })

print(f'Registros lidos: {len(registros)}  |  Erros de parse: {len(erros)}')
for e in erros[:10]: print(' ', e)

# ── Deduplicação ──────────────────────────────────────────────
db = sqlite3.connect(DB)
db.execute('PRAGMA journal_mode=WAL')
existentes = set()
for r in db.execute('SELECT lower(nome), lower(coalesce(especialidade,"")), mes_ano FROM estagios'):
    existentes.add((r[0], r[1], r[2]))

novos = [r for r in registros
         if (r['nome'].lower(), (r['especialidade'] or '').lower(), r['mes_ano']) not in existentes]
dups  = len(registros) - len(novos)

print(f'Duplicatas ignoradas: {dups}')
print(f'NOVOS A INSERIR: {len(novos)}')
print()

# ── Preview de amostra ────────────────────────────────────────
print('=== Amostra dos 10 primeiros novos ===')
for r in novos[:10]:
    print(f"  {r['mes_ano']} | {r['nome'][:30]:30s} | {str(r['especialidade'])[:25]:25s} | R${r['valor']} | {r['status_pagamento']} | cert:{r['envio_certificado']}")

if not CONFIRMAR:
    print()
    print('>>> MODO PREVIEW. Para importar de verdade: python importar_consolidado.py --confirmar')
    db.close()
    sys.exit(0)

# ── Inserção ──────────────────────────────────────────────────
print()
print('Inserindo...')
cur = db.cursor()
inseridos = 0
for r in novos:
    cur.execute('''
        INSERT INTO estagios
            (tipo_id, mes_ano, semana, nome, especialidade, cracha,
             valor, status_pagamento, inicio, termino,
             email, telefone, envio_certificado, observacao, etapa)
        VALUES (1, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (
        r['mes_ano'], r['nome'], r['especialidade'], r['cracha'],
        r['valor'], r['status_pagamento'], r['inicio'], r['termino'],
        r['email'], r['telefone'], r['envio_certificado'], r['observacao'],
    ))
    inseridos += 1

db.commit()
db.close()
print(f'OK! Inseridos com sucesso: {inseridos}')
