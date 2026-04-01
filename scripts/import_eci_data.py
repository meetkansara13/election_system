"""
scripts/import_eci_data.py
Imports Lok Dhaba Gujarat CSV (Assembly 2007/2012/2017/2022) into ElectionHistory.

Run:
    python scripts/import_eci_data.py --file data/gujarat.csv
"""

import os
import sys
import django
import argparse
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'election_system.settings')
django.setup()

from apps.prediction.models import ElectionHistory


# Lok Dhaba column → model field
COLUMN_MAP = {
    'State_Name':              'state',
    'Assembly_No':             'assembly_no',
    'Constituency_No':         'constituency_no',
    'Year':                    'year',
    'Constituency_Name':       'constituency',
    'Constituency_Type':       'constituency_type',
    'District_Name':           'district',
    'Sub_Region':              'sub_region',
    'Candidate':               'candidate',
    'Sex':                     'sex',
    'Age':                     'age',
    'Candidate_Type':          'candidate_type',
    'Party':                   'party',
    'Party_ID':                'party_id',
    'Party_Type_TCPD':         'party_type',
    'Votes':                   'votes',
    'Valid_Votes':             'valid_votes',
    'Electors':                'electors',
    'Vote_Share_Percentage':   'vote_share',
    'Turnout_Percentage':      'voter_turnout',
    'Position':                'position',
    'Deposit_Lost':            'deposit_lost',
    'N_Cand':                  'n_candidates',
    'Margin':                  'margin',
    'Margin_Percentage':       'margin_pct',
    'ENOP':                    'enop',
    'Incumbent':               'incumbent',
    'Recontest':               'recontest',
    'Turncoat':                'turncoat',
    'No_Terms':                'no_terms',
    'Same_Constituency':       'same_constituency',
    'Same_Party':              'same_party',
    'Last_Party':              'last_party',
    'Last_Party_ID':           'last_party',       # overwrite with name if available
    'Last_Constituency_Name':  'last_constituency',
    'last_poll':               'last_poll',
    'Contested':               'contested',
    'MyNeta_education':        'education',
    'TCPD_Prof_Main_Desc':     'profession_main',
    'TCPD_Prof_Second_Desc':   'profession_second',
}


def safe_int(val, default=None):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return default


def safe_bool(val, default=False):
    try:
        return int(float(val)) == 1
    except (ValueError, TypeError):
        return default


def safe_str(val, default=''):
    if pd.isna(val):
        return default
    return str(val).strip()


def import_csv(filepath: str, state_filter: str = 'Gujarat', clear_first: bool = False):
    df = pd.read_csv(filepath, encoding='utf-8-sig', low_memory=False)
    print(f"Loaded {len(df):,} rows | columns: {df.columns.tolist()}\n")

    # Filter to state
    if 'State_Name' in df.columns:
        df = df[df['State_Name'].str.strip().str.lower() == state_filter.lower()]
        print(f"After state filter ({state_filter}): {len(df):,} rows")

    if df.empty:
        print("No rows after filtering. Check State_Name values in your CSV.")
        return

    if clear_first:
        deleted, _ = ElectionHistory.objects.filter(state__iexact=state_filter).delete()
        print(f"Cleared {deleted} existing records for {state_filter}")

    created = updated = skipped = 0

    for _, row in df.iterrows():
        year    = safe_int(row.get('Year'))
        c_no    = safe_int(row.get('Constituency_No'))
        cand    = safe_str(row.get('Candidate'))
        party   = safe_str(row.get('Party'))

        if not year or not cand or not party:
            skipped += 1
            continue

        defaults = {
            'state':              safe_str(row.get('State_Name'), 'Gujarat'),
            'assembly_no':        safe_int(row.get('Assembly_No')),
            'constituency':       safe_str(row.get('Constituency_Name')),
            'constituency_type':  safe_str(row.get('Constituency_Type')),
            'district':           safe_str(row.get('District_Name')),
            'sub_region':         safe_str(row.get('Sub_Region')),
            'sex':                safe_str(row.get('Sex')),
            'age':                safe_int(row.get('Age')),
            'candidate_type':     safe_str(row.get('Candidate_Type')),
            'party_id':           safe_str(row.get('Party_ID')),
            'party_type':         safe_str(row.get('Party_Type_TCPD')),
            'votes':              safe_int(row.get('Votes'), 0),
            'valid_votes':        safe_int(row.get('Valid_Votes'), 0),
            'electors':           safe_int(row.get('Electors'), 0),
            'vote_share':         safe_float(row.get('Vote_Share_Percentage')),
            'voter_turnout':      safe_float(row.get('Turnout_Percentage')),
            'position':           safe_int(row.get('Position')),
            'won':                safe_int(row.get('Position')) == 1,
            'deposit_lost':       safe_bool(row.get('Deposit_Lost')),
            'n_candidates':       safe_int(row.get('N_Cand')),
            'margin':             safe_int(row.get('Margin')),
            'margin_pct':         safe_float(row.get('Margin_Percentage')),
            'enop':               safe_float(row.get('ENOP')),
            'incumbent':          safe_int(row.get('Incumbent'), 0),
            'recontest':          safe_int(row.get('Recontest'), 0),
            'turncoat':           safe_int(row.get('Turncoat'), 0),
            'no_terms':           safe_int(row.get('No_Terms')),
            'same_constituency':  safe_int(row.get('Same_Constituency')),
            'same_party':         safe_int(row.get('Same_Party')),
            'last_party':         safe_str(row.get('Last_Party')),
            'last_constituency':  safe_str(row.get('Last_Constituency_Name')),
            'last_poll':          safe_int(row.get('last_poll')),
            'contested':          safe_int(row.get('Contested')),
            'education':          safe_str(row.get('MyNeta_education')),
            'profession_main':    safe_str(row.get('TCPD_Prof_Main_Desc')),
            'profession_second':  safe_str(row.get('TCPD_Prof_Second_Desc')),
        }

        obj, is_new = ElectionHistory.objects.update_or_create(
            year=year,
            constituency_no=c_no,
            candidate=cand,
            party=party,
            defaults=defaults,
        )
        if is_new:
            created += 1
        else:
            updated += 1

    print(f"\n✓ Done — created: {created:,} | updated: {updated:,} | skipped: {skipped:,}")
    print(f"  Total in DB: {ElectionHistory.objects.count():,}")

    # Summary by year
    from django.db.models import Count
    for yr in ElectionHistory.objects.values_list('year', flat=True).distinct().order_by('year'):
        cnt = ElectionHistory.objects.filter(year=yr).count()
        winners = ElectionHistory.objects.filter(year=yr, won=True).count()
        print(f"  {yr}: {cnt:,} candidates, {winners} constituencies")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Lok Dhaba Gujarat CSV')
    parser.add_argument('--file',  required=True, help='Path to CSV, e.g. data/gujarat.csv')
    parser.add_argument('--state', default='Gujarat', help='State name to filter')
    parser.add_argument('--clear', action='store_true', help='Delete existing records first')
    args = parser.parse_args()

    import_csv(args.file, state_filter=args.state, clear_first=args.clear)