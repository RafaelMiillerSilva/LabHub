"""
Serviço para leitura e importação de alunos via planilha Excel (.xlsx) e CSV.
"""

import csv
import io

ALIAS_NOME = {'nome', 'aluno', 'nome do aluno', 'nome completo', 'nome completo do aluno'}
ALIAS_RA = {'ra', 'ra (registro)', 'registro', 'matricula', 'matrícula',
            'numero', 'número', 'nº', 'n', 'registro do aluno'}
ALIAS_DIGITO = {'digito', 'dígito', 'dig', 'digito ra', 'dígito ra', 'digito_ra', 'dígito_ra'}
ALIAS_UF = {'uf', 'estado', 'uf ra', 'uf_ra'}


def normalizar_texto(valor):
    if valor is None:
        return ''
    return str(valor).strip()


def normalizar_ra(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def normalizar_digito(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip().upper()


def normalizar_uf(valor):
    if valor is None:
        return 'SP'
    val_str = str(valor).strip().upper()
    return val_str if val_str else 'SP'


def detectar_separador(texto):
    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ''
    return ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','


def ler_planilha(arquivo):
    """
    Lê um arquivo de planilha (.xlsx ou .csv) e devolve (linhas, erro).
    """
    nome_arquivo = arquivo.name.lower()

    if nome_arquivo.endswith('.csv'):
        dados = arquivo.read()
        try:
            texto = dados.decode('utf-8-sig')
        except UnicodeDecodeError:
            texto = dados.decode('latin-1')
        separador = detectar_separador(texto)
        leitor = csv.reader(io.StringIO(texto), delimiter=separador)
        return [list(linha) for linha in leitor], None

    if nome_arquivo.endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            return None, (
                'Para importar arquivos .xlsx é preciso instalar a biblioteca openpyxl. '
                'Como alternativa, envie um arquivo .csv.'
            )
        wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            return None, 'O arquivo .xlsx não contém nenhuma planilha ativa.'
        linhas = []
        for row in ws.iter_rows(values_only=True):
            linhas.append(['' if c is None else c for c in row])
        return linhas, None

    return None, 'Formato não suportado. Envie um arquivo .xlsx ou .csv.'


def mapear_colunas(cabecalho):
    """
    Identifica os índices das colunas 'nome', 'ra', 'digito' e 'uf' a partir do cabeçalho da planilha.
    """
    nome_idx = ra_idx = digito_idx = uf_idx = None
    for i, valor in enumerate(cabecalho):
        v = str(valor).strip().lower()
        if nome_idx is None and v in ALIAS_NOME:
            nome_idx = i
        if ra_idx is None and v in ALIAS_RA:
            ra_idx = i
        if digito_idx is None and v in ALIAS_DIGITO:
            digito_idx = i
        if uf_idx is None and v in ALIAS_UF:
            uf_idx = i
    return nome_idx, ra_idx, digito_idx, uf_idx
