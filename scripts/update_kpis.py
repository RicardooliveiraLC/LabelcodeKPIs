#!/usr/bin/env python3
"""
Script para atualizar data.json com dados da planilha Google Sheets.

Setup:
  1. Crie uma Service Account no Google Cloud Console
  2. Habilite a Google Sheets API
  3. Compartilhe a planilha com o email da Service Account
  4. Adicione o JSON de credenciais como secret GOOGLE_CREDENTIALS no GitHub

Uso local:
  export GOOGLE_CREDENTIALS='{"type":"service_account",...}'
  export SPREADSHEET_ID='16w6VYi0RFFYgDKtZdk92NPLg_sqp6kKVoF02doOiCVs'
  python scripts/update_kpis.py
"""

import json
import os
import sys
from datetime import date

SPREADSHEET_ID = os.environ.get(
    'SPREADSHEET_ID',
    '16w6VYi0RFFYgDKtZdk92NPLg_sqp6kKVoF02doOiCVs'
)

MONTHS = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

# Mapa: nome na planilha → id no data.json
INDICATOR_MAP = {
    'Satisfação dos clientes':                                    'satisfacao_clientes',
    'Taxa de conversão de orçamentos em pedidos':                 'taxa_conversao_orcamentos',
    'Conversão de amostras em pedido':                            'conversao_amostras',
    'Amostras conforme necessidade do cliente (Assertividade)':   'assertividade_amostras',
    'Giro de estoque (matéria prima)':                            'giro_estoque_mp',
    'Produtos Acabados Parado em estoque':                        'produtos_acabados_parado',
    'Perdas - Flexo':                                             'perdas_flexo',
    'Perdas - Offset':                                            'perdas_offset',
    'Perdas - Digital':                                           'perdas_digital',
    '%tempo produtivo':                                           'tempo_produtivo',
    'Pontualidade na entrega interna':                            'pontualidade_entrega',
    'IGF - Índice Geral de Fornecedores':                         'igf',
    'Reclamação de clientes (produtos)':                          'reclamacao_clientes',
    'Não Conformidades Internas (produtos)':                      'nc_internas',
    'Pesquisa de clima organizacional':                           'pesquisa_clima',
    'Avaliações de desempenho':                                   'avaliacoes_desempenho',
    'Consumo energético (Kw/M²)':                                 'consumo_energia',
    'Consumo água (L/DIA/Colaborador) (trimestral)':              'consumo_agua',
    'Percentual Descarte Aparas de Papel/Total de Papel Utilizado': 'descarte_aparas',
    'Percentual de Descarte Não Reciclado/Total Utilizado':       'descarte_nao_reciclado',
    'Emissão de GEE por Fonte de Energia / m2 produzido':         'emissao_gee',
}


def parse_value(s):
    if not s or not s.strip():
        return None
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None


def get_sheets_service():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise ValueError(
            "Variável GOOGLE_CREDENTIALS não definida.\n"
            "Adicione o JSON de credenciais da Service Account."
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    return build('sheets', 'v4', credentials=creds)


def fetch_sheet_values(service, range_name='SGI!A:N'):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name
    ).execute()
    return result.get('values', [])


def recalc_monthly_results(indicators):
    results = {}
    for m in MONTHS:
        hits = total = 0
        for ind in indicators:
            v = ind['values'].get(m)
            if v is not None:
                total += 1
                better = ind['better']
                target = ind['target']
                if (better == 'higher' and v >= target) or \
                   (better == 'lower'  and v <= target):
                    hits += 1
        results[m] = round(hits / total, 4) if total > 0 else None
    return results


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path  = os.path.join(script_dir, '..', 'data.json')

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Conectando ao Google Sheets ({SPREADSHEET_ID})...")
    service = get_sheets_service()
    rows    = fetch_sheet_values(service)

    updated_count = 0
    for row in rows:
        if not row:
            continue
        name = row[0].strip()
        ind_id = INDICATOR_MAP.get(name)
        if not ind_id:
            continue

        ind = next((i for i in data['indicators'] if i['id'] == ind_id), None)
        if not ind:
            print(f"  ⚠ Indicador '{ind_id}' não encontrado em data.json")
            continue

        # Colunas 3..14 correspondem a jan..dez
        for i, month in enumerate(MONTHS):
            col = 3 + i
            val = parse_value(row[col]) if col < len(row) else None
            ind['values'][month] = val

        updated_count += 1
        print(f"  ✓ {name}")

    data['monthly_results'] = recalc_monthly_results(data['indicators'])
    data['meta']['updated'] = date.today().isoformat()

    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ data.json atualizado — {updated_count} indicadores, {date.today()}")


if __name__ == '__main__':
    main()
