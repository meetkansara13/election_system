from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
import plotly.graph_objects as go
import json
import os
import base64
import urllib.parse
import urllib.request
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from apps.prediction.ml_engine import predict_constituency, generate_sample_data
from django.db.models import Sum
from apps.prediction.models import ElectionHistory
from django.db.models import Q


GUJARAT_DISTRICT_COORDS = {
    'KACHCHH': {'x': 10, 'y': 18},
    'KUTCH': {'x': 10, 'y': 18},
    'BANASKANTHA': {'x': 28, 'y': 12},
    'PATAN': {'x': 33, 'y': 19},
    'MEHSANA': {'x': 38, 'y': 24},
    'SABARKANTHA': {'x': 46, 'y': 18},
    'ARAVALLI': {'x': 51, 'y': 24},
    'GANDHINAGAR': {'x': 42, 'y': 30},
    'AHMEDABAD': {'x': 43, 'y': 38},
    'SURENDRANAGAR': {'x': 31, 'y': 35},
    'MORBI': {'x': 22, 'y': 33},
    'RAJKOT': {'x': 20, 'y': 42},
    'JAMNAGAR': {'x': 11, 'y': 38},
    'DEVBHOOMI DWARKA': {'x': 4, 'y': 36},
    'PORBANDAR': {'x': 8, 'y': 50},
    'JUNAGADH': {'x': 15, 'y': 56},
    'GIR SOMNATH': {'x': 18, 'y': 64},
    'AMRELI': {'x': 25, 'y': 56},
    'BHAVNAGAR': {'x': 34, 'y': 60},
    'BOTAD': {'x': 31, 'y': 50},
    'ANAND': {'x': 49, 'y': 45},
    'KHEDA': {'x': 51, 'y': 39},
    'VADODARA': {'x': 60, 'y': 42},
    'PANCHMAHAL': {'x': 61, 'y': 32},
    'MAHISAGAR': {'x': 58, 'y': 27},
    'DAHOD': {'x': 69, 'y': 26},
    'CHHOTA UDAIPUR': {'x': 66, 'y': 38},
    'NARMADA': {'x': 63, 'y': 52},
    'BHARUCH': {'x': 56, 'y': 57},
    'SURAT': {'x': 52, 'y': 68},
    'TAPI': {'x': 63, 'y': 65},
    'NAVSARI': {'x': 54, 'y': 77},
    'VALSAD': {'x': 57, 'y': 86},
    'DANG': {'x': 66, 'y': 79},
}


PARTY_COLORS = {
    'BJP':      '#FF9933',
    'INC':      '#38BDF8',
    'Congress': '#38BDF8',
    'AAP':      '#10B981',
    'IND':      '#E5E7EB',
    'BSP':      '#1B4F8A',
    'NCP':      '#C084FC',
    'SP':       '#F43F5E',
    'TMC':      '#22C55E',
    'JD':       '#FACC15',
    'AAAP':     '#A78BFA',
    'INC(I)':   '#64748B',
    'Other':    '#AAAAAA',
}


def get_party_color(party):
    return PARTY_COLORS.get(party, '#888888')


DISTRICT_NAME_ALIASES = {
    'AHMEDABAD': 'AHMEDABAD',
    'AHMADABAD': 'AHMEDABAD',
    'MEHSANA': 'MEHSANA',
    'MAHESANA': 'MEHSANA',
    'BANASKANTHA': 'BANASKANTHA',
    'BANAS KANTHA': 'BANASKANTHA',
    'SABARKANTHA': 'SABARKANTHA',
    'SABAR KANTHA': 'SABARKANTHA',
    'DAHOD': 'DAHOD',
    'DOHAD': 'DAHOD',
    'CHHOTA UDAIPUR': 'CHHOTA UDAIPUR',
    'CHOTA UDAIPUR': 'CHHOTA UDAIPUR',
    'DEVBHOOMI DWARKA': 'DEVBHOOMI DWARKA',
    'DEVBHUMI DWARKA': 'DEVBHOOMI DWARKA',
    'PANCHMAHAL': 'PANCHMAHAL',
    'PANCHMAHALS': 'PANCHMAHAL',
    'PANCH MAHAL': 'PANCHMAHAL',
    'PANCH MAHALS': 'PANCHMAHAL',
    'THE DANGS': 'DANG',
    'DANG': 'DANG',
    'DANGS': 'DANG',
    'KACHCHH': 'KACHCHH',
    'KUTCH': 'KACHCHH',
    'ARAVALI': 'ARAVALLI',
    'ARAVALLI': 'ARAVALLI',
}


def normalize_district_name(value):
    raw = str(value or '').strip().upper()
    cleaned = (
        raw.replace('(', ' ')
        .replace(')', ' ')
        .replace('.', ' ')
        .replace(',', ' ')
        .replace('-', ' ')
    )
    cleaned = ' '.join(cleaned.split())
    return DISTRICT_NAME_ALIASES.get(cleaned, cleaned)


def normalize_constituency_name(value):
    raw = str(value or '').strip().upper()
    cleaned = (
        raw.replace('(', ' ')
        .replace(')', ' ')
        .replace('.', ' ')
        .replace(',', ' ')
        .replace('-', ' ')
        .replace('&', ' AND ')
        .replace('/', ' ')
    )
    return ' '.join(cleaned.split())


def build_constituency_district_lookup(df):
    lookup = {}
    if df.empty:
        return lookup

    for _, row in df.iterrows():
        district = normalize_district_name(row.get('district'))
        constituency = normalize_constituency_name(row.get('constituency'))
        if not district or not constituency:
            continue
        lookup.setdefault(constituency, district)
    return lookup


def fig_to_json(fig):
    return json.loads(fig.to_json())


def load_df():
    """Use real DB data if available, else synthetic."""
    from apps.prediction.models import ElectionHistory
    if ElectionHistory.objects.exists():
        import pandas as pd
        qs = ElectionHistory.objects.all().values(
            'year', 'constituency', 'party', 'candidate',
            'votes', 'vote_share', 'won', 'electors',
            'voter_turnout', 'district', 'incumbent',
        )
        df = pd.DataFrame(list(qs))
        df['total_voters'] = df['electors']
        return df
    else:
        df = generate_sample_data()
        df['total_voters'] = df['electors']
        return df


def get_filtered_df(request):
    df = load_df()
    available_years = sorted(int(y) for y in df['year'].dropna().unique().tolist())
    selected_year = request.GET.get('year')
    if selected_year:
        try:
            selected_year = int(selected_year)
        except ValueError:
            selected_year = available_years[-1]
    else:
        selected_year = available_years[-1]
    if selected_year not in available_years:
        selected_year = available_years[-1]

    party_alias = {'Congress': 'INC'}
    df['party_normalized'] = df['party'].replace(party_alias)
    year_df = df[df['year'] == selected_year].copy()
    party_options = []
    if not year_df.empty:
        party_summary = (
            year_df.groupby('party_normalized')
            .agg(
                total_votes=('votes', 'sum'),
                avg_vote_share=('vote_share', 'mean'),
                seats=('won', 'sum'),
            )
            .reset_index()
            .sort_values(['seats', 'total_votes'], ascending=[False, False])
        )
        party_options = [
            {
                'value': row['party_normalized'],
                'label': row['party_normalized'],
                'seats': int(row['seats']),
                'avg_vote_share': round(float(row['avg_vote_share']), 1),
            }
            for _, row in party_summary.iterrows()
        ]

    available_parties = [item['value'] for item in party_options]
    selected_party = request.GET.get('party', 'ALL').strip() or 'ALL'
    if selected_party != 'ALL' and selected_party not in available_parties:
        selected_party = 'ALL'

    return df, year_df, selected_year, selected_party, available_years, party_options



@login_required(login_url='/login/')
def index(request):
    return render(request, 'dashboard/index.html', {
        'profile_name': getattr(request.user, 'full_name', '') or getattr(request.user, 'username', '') or 'User',
        'profile_email': getattr(request.user, 'email', ''),
        'profile_role': getattr(request.user, 'role', 'user'),
    })

class SeatsChartView(APIView):
    def get(self, request):
        _, year_df, year, selected_party, _, _ = get_filtered_df(request)
        winners = year_df[year_df['won']].groupby('party_normalized').size().reset_index(name='seats')
        winners.rename(columns={'party_normalized': 'party'}, inplace=True)
        winners = winners.sort_values('seats', ascending=False).reset_index(drop=True)
        total_seats = int(winners['seats'].sum()) if not winners.empty else 0
        selected_row = winners[winners['party'] == selected_party].iloc[0] if selected_party != 'ALL' and not winners[winners['party'] == selected_party].empty else None
        top_party = selected_row if selected_row is not None else (winners.iloc[0] if not winners.empty else None)
        top_two_share = round(float(winners.head(2)['seats'].sum() / total_seats * 100), 1) if total_seats else 0.0

        fig = go.Figure(go.Pie(
            labels=winners['party'],
            values=winners['seats'],
            hole=0.62,
            marker_colors=[get_party_color(p) for p in winners['party']],
            textinfo='none',
            sort=False,
            direction='clockwise',
            hovertemplate='%{label}: %{value} seats (%{percent})<extra></extra>',
        ))
        fig.update_layout(
            title=f'Seat Distribution ({year})',
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e0e0e0'),
            margin=dict(t=30, b=20, l=20, r=20),
            annotations=[dict(
                text=f"<b>{year}</b><br>{total_seats} seats",
                x=0.5, y=0.5,
                font=dict(size=18, color='#e2e8f0'),
                showarrow=False,
            )],
        )
        return Response({
            'chart': fig_to_json(fig),
            'summary': {
                'year': int(year),
                'total_seats': total_seats,
                'top_party': top_party['party'] if top_party is not None else 'N/A',
                'top_party_seats': int(top_party['seats']) if top_party is not None else 0,
                'top_party_share': round(float(top_party['seats'] / total_seats * 100), 1) if top_party is not None and total_seats else 0.0,
                'top_two_share': top_two_share,
                'selected_party': selected_party,
                'party_breakdown': winners.to_dict('records'),
            }
        })


class VoteShareTrendView(APIView):
    def get(self, request):
        df, _, selected_year, selected_party, _, _ = get_filtered_df(request)
        vote_totals = df.groupby('party_normalized')['votes'].sum().nlargest(6)
        top_parties = vote_totals.index.tolist()
        if selected_party != 'ALL' and selected_party not in top_parties:
            top_parties = [selected_party] + top_parties[:5]
        df = df[df['party_normalized'].isin(top_parties)]
        trend = df.groupby(['year', 'party_normalized'])['vote_share'].mean().reset_index()
        trend.rename(columns={'party_normalized': 'party'}, inplace=True)
        latest_year = selected_year
        latest = trend[trend['year'] == latest_year].sort_values('vote_share', ascending=False) if latest_year is not None else trend
        leader = latest.iloc[0] if not latest.empty else None
        momentum = []
        for party in trend['party'].unique():
            pdata = trend[trend['party'] == party].sort_values('year')
            upto = pdata[pdata['year'] <= latest_year]
            if len(upto) >= 2:
                change = round(float(upto.iloc[-1]['vote_share'] - upto.iloc[-2]['vote_share']), 1)
                momentum.append({'party': party, 'change': change})
        momentum.sort(key=lambda item: item['change'], reverse=True)

        fig = go.Figure()
        for party in trend['party'].unique():
            pdata = trend[trend['party'] == party]
            fig.add_trace(go.Scatter(
                x=pdata['year'], y=pdata['vote_share'],
                mode='lines+markers', name=party,
                line=dict(color=get_party_color(party), width=2.5),
                marker=dict(size=8),
            ))

        fig.update_layout(
            title='Party Vote Share Trend',
            xaxis_title='Year', yaxis_title='Vote Share (%)',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e0e0e0'),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            legend=dict(bgcolor='rgba(0,0,0,0)'),
            margin=dict(t=30, b=40, l=40, r=20),
        )
        return Response({
            'chart': fig_to_json(fig),
            'summary': {
                'latest_year': latest_year,
                'leader': leader['party'] if leader is not None else 'N/A',
                'leader_vote_share': round(float(leader['vote_share']), 1) if leader is not None else 0.0,
                'fastest_rising_party': momentum[0]['party'] if momentum else 'N/A',
                'fastest_rising_change': momentum[0]['change'] if momentum else 0.0,
                'selected_party': selected_party,
                'latest_snapshot': latest.to_dict('records'),
            }
        })


class TurnoutMapView(APIView):
    def get(self, request):
        _, df_yr, year, _, _, _ = get_filtered_df(request)
        df_yr = df_yr.drop_duplicates('constituency')
        df_yr = df_yr.sort_values('voter_turnout', ascending=True)

        fig = go.Figure(go.Bar(
            x=df_yr['voter_turnout'],
            y=df_yr['constituency'],
            orientation='h',
            marker_color='#4fc3f7',
            text=[f"{v:.1f}%" for v in df_yr['voter_turnout']],
            textposition='outside',
        ))
        fig.update_layout(
            title=f'Voter Turnout by Constituency ({year})',
            xaxis_title='Turnout (%)',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e0e0e0'),
            xaxis=dict(range=[0, 100], showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            yaxis=dict(showgrid=False),
            margin=dict(t=40, b=40, l=140, r=80),
        )
        return Response(fig_to_json(fig))


class PredictionConfidenceView(APIView):
    def get(self, request):
        constituency = request.GET.get('constituency', 'Maninagar')

        if not os.path.exists(os.path.join(settings.ML_MODELS_DIR, 'winner_clf.pkl')):
            return Response({'error': 'Train models first via POST /api/predict/train/'}, status=400)

        result = predict_constituency(constituency)
        parties = [r['party'] for r in result['all_parties']]
        probs   = [r['confidence_pct'] for r in result['all_parties']]

        fig = go.Figure(go.Bar(
            x=probs, y=parties, orientation='h',
            marker_color=[get_party_color(p) for p in parties],
            text=[f"{p:.1f}%" for p in probs],
            textposition='outside',
        ))
        fig.update_layout(
            title=f'Win Probability — {constituency}',
            xaxis_title='Win Probability (%)',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e0e0e0'),
            xaxis=dict(range=[0, 110], showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            yaxis=dict(showgrid=False),
            margin=dict(t=40, b=40, l=80, r=60),
        )
        return Response({'chart': fig_to_json(fig), 'prediction': result})


class CandidateListView(APIView):
    def get(self, request):
        _, _, year, selected_party, _, _ = get_filtered_df(request)
        search = request.GET.get('search', '').strip()
        page = request.GET.get('page', '1')
        try:
            page = max(int(page), 1)
        except ValueError:
            page = 1

        qs = ElectionHistory.objects.filter(year=year).order_by('position', '-votes', 'candidate')
        if selected_party != 'ALL':
            qs = qs.filter(party__iexact=selected_party)
        if search:
            qs = qs.filter(
                Q(candidate__icontains=search) |
                Q(constituency__icontains=search) |
                Q(party__icontains=search) |
                Q(district__icontains=search)
            ).order_by('position', '-votes', 'candidate')

        total = qs.count()
        page_size = 6
        total_pages = max((total + page_size - 1) // page_size, 1)
        page = min(page, total_pages)
        start = (page - 1) * page_size
        items = []
        for row in qs[start:start + page_size]:
            items.append({
                'candidate': row.candidate,
                'party': row.party,
                'constituency': row.constituency,
                'district': row.district,
                'votes': int(row.votes),
                'vote_share': round(float(row.vote_share), 1),
                'position': row.position or 0,
                'won': bool(row.won),
            })

        return Response({
            'year': year,
            'search': search,
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
            'items': items,
        })


class GeoServerMapView(APIView):
    def get(self, request):
        map_geojson_path = settings.MAP_GEOJSON_PATH
        map_geojson_url = settings.MAP_GEOJSON_URL

        if map_geojson_path:
            try:
                candidate_path = Path(map_geojson_path)
                if not candidate_path.is_absolute():
                    candidate_path = Path(settings.BASE_DIR) / map_geojson_path
                with candidate_path.open('r', encoding='utf-8') as file_obj:
                    payload = json.load(file_obj)
                return Response({
                    'configured': True,
                    'source': str(candidate_path),
                    'mode': 'file',
                    'geojson': payload,
                })
            except Exception as exc:
                return Response({
                    'configured': False,
                    'error': f'Local map file load failed: {exc}',
                }, status=200)

        if map_geojson_url:
            try:
                req = urllib.request.Request(map_geojson_url)
                with urllib.request.urlopen(req, timeout=20) as response:
                    payload = json.loads(response.read().decode('utf-8'))
                return Response({
                    'configured': True,
                    'source': map_geojson_url,
                    'mode': 'url',
                    'geojson': payload,
                })
            except Exception as exc:
                return Response({
                    'configured': False,
                    'error': f'Direct map URL fetch failed: {exc}',
                }, status=200)

        geoserver_url = settings.GEOSERVER_URL
        workspace = settings.GEOSERVER_WORKSPACE
        layer = settings.GEOSERVER_LAYER
        if not geoserver_url or not workspace or not layer:
            return Response({
                'configured': False,
                'error': 'No map source configured. Set MAP_GEOJSON_PATH, MAP_GEOJSON_URL, or GeoServer settings.',
            }, status=200)

        typename = f'{workspace}:{layer}'
        params = urllib.parse.urlencode({
            'service': 'WFS',
            'version': '1.0.0',
            'request': 'GetFeature',
            'typeName': typename,
            'outputFormat': 'application/json',
        })
        endpoint = f'{geoserver_url}/ows?{params}'
        req = urllib.request.Request(endpoint)

        if settings.GEOSERVER_USERNAME and settings.GEOSERVER_PASSWORD:
            token = base64.b64encode(
                f'{settings.GEOSERVER_USERNAME}:{settings.GEOSERVER_PASSWORD}'.encode('utf-8')
            ).decode('ascii')
            req.add_header('Authorization', f'Basic {token}')

        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read().decode('utf-8'))
            return Response({
                'configured': True,
                'source': endpoint,
                'mode': 'geoserver',
                'geojson': payload,
            })
        except Exception as exc:
            return Response({
                'configured': False,
                'error': f'GeoServer fetch failed: {exc}',
            }, status=200)


class LiveStatsView(APIView):
    def get(self, request):
        df, df_yr, year, selected_party, available_years, party_options = get_filtered_df(request)
        constituency_district_lookup = build_constituency_district_lookup(df)

        winners = df_yr[df_yr['won']]
        leading_party = winners.groupby('party_normalized').size().idxmax() if not winners.empty else 'N/A'
        selected_party_df = df_yr[df_yr['party_normalized'] == selected_party] if selected_party != 'ALL' else df_yr
        selected_party_wins = int(selected_party_df['won'].sum()) if selected_party != 'ALL' else None
        selected_party_vote_share = round(float(selected_party_df['vote_share'].mean()), 1) if selected_party != 'ALL' and not selected_party_df.empty else None
        selected_party_votes = int(selected_party_df['votes'].sum()) if selected_party != 'ALL' and not selected_party_df.empty else None
        leading_party_votes = int(df_yr[df_yr['party_normalized'] == leading_party]['votes'].sum()) if leading_party != 'N/A' else 0
        election_rows = ElectionHistory.objects.filter(year=year)
        state_name = election_rows.values_list('state', flat=True).first() or 'Gujarat'
        election_label = f"{state_name} Assembly Election"
        winner_records = []
        standout_race = None
        district_map = []
        if not winners.empty:
            winners = winners.copy()
            winners['district_inferred'] = winners.apply(
                lambda row: normalize_district_name(row.get('district')) or constituency_district_lookup.get(
                    normalize_constituency_name(row.get('constituency')),
                    ''
                ),
                axis=1,
            )
            winners_sorted = winners.sort_values(['votes', 'vote_share'], ascending=False)
            winner_records = [
                {
                    'constituency': row['constituency'],
                    'candidate': row['candidate'],
                    'party': row['party_normalized'],
                    'votes': int(row['votes']),
                    'vote_share': round(float(row['vote_share']), 1),
                    'district': row.get('district_inferred', '') or row.get('district', ''),
                }
                for _, row in winners_sorted.head(4).iterrows()
            ]
            standout = winners.sort_values('vote_share', ascending=False).iloc[0]
            standout_race = {
                'constituency': standout['constituency'],
                'candidate': standout['candidate'],
                'party': standout['party_normalized'],
                'vote_share': round(float(standout['vote_share']), 1),
                'votes': int(standout['votes']),
            }
            district_winners = (
                winners[winners['district_inferred'] != '']
                .groupby(['district_inferred', 'party_normalized'])['votes']
                .sum()
                .reset_index()
                .sort_values(['district_inferred', 'votes'], ascending=[True, False])
            )
            district_winners = district_winners.drop_duplicates('district_inferred')
            for _, row in district_winners.iterrows():
                district_name = normalize_district_name(row['district_inferred'])
                coords = GUJARAT_DISTRICT_COORDS.get(district_name)
                if not coords:
                    continue
                district_map.append({
                    'district': district_name.title(),
                    'party': row['party_normalized'],
                    'votes': int(row['votes']),
                    'x': coords['x'],
                    'y': coords['y'],
                    'color': get_party_color(row['party_normalized']),
                })

        return Response({
            'total_constituencies': int(df_yr['constituency'].nunique()),
            'avg_turnout':          round(float(df_yr['voter_turnout'].mean()), 1),
            'leading_party':        leading_party,
            'leading_party_votes':  leading_party_votes,
            'total_voters':         int(df_yr.drop_duplicates('constituency')['total_voters'].sum()),
            'year':                 int(year),
            'selected_party':       selected_party,
            'selected_party_wins':  selected_party_wins,
            'selected_party_vote_share': selected_party_vote_share,
            'selected_party_votes': selected_party_votes,
            'available_years':      available_years,
            'party_options':        party_options,
            'winner_records':       winner_records,
            'standout_race':        standout_race,
            'election_label':       election_label,
            'district_map':         district_map,
        })
