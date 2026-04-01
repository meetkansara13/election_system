"""
ml_engine.py — Train and predict using real Lok Dhaba Gujarat data.
Features upgraded to use incumbent, turncoat, no_terms, margin_pct, enop, sex, deposit_lost etc.
"""
import os
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, mean_absolute_error
import xgboost as xgb


def get_model_path():
    from django.conf import settings
    return settings.ML_MODELS_DIR

# All features available from Lok Dhaba CSV
FEATURE_COLS = [
    'year',
    'party_enc',
    'const_enc',
    'district_enc',
    'constituency_type_enc',   # GEN / SC / ST
    'sex_enc',                 # M / F
    'age',
    'incumbent',
    'recontest',
    'turncoat',
    'no_terms',
    'same_constituency',
    'same_party',
    'n_candidates',            # competition level
    'prev_vote_share',
    'swing',                   # vote_share - prev_vote_share
    'log_margin',              # log of last winning margin
    'voter_turnout',
    'enop',                    # effective number of parties
    'historical_win_rate',
    'deposit_lost_rate',       # how often party loses deposit here
]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_from_db() -> pd.DataFrame:
    from apps.prediction.models import ElectionHistory
    qs = ElectionHistory.objects.all().values()
    df = pd.DataFrame(list(qs))
    if df.empty:
        raise ValueError(
            "No data in DB. Run: python scripts/import_eci_data.py --file data/gujarat.csv"
        )
    print(f"[DB] {len(df):,} rows | years: {sorted(df['year'].unique())} | "
          f"{df['constituency'].nunique()} constituencies")
    return df


def generate_sample_data() -> pd.DataFrame:
    """Fallback synthetic data — dev/demo only. NOT for real predictions."""
    np.random.seed(42)
    parties = ['BJP', 'INC', 'AAP', 'IND', 'BSP', 'NCP']
    constituencies = [
        'Maninagar', 'Ellisbridge', 'Sabarmati', 'Vejalpur', 'Nikol',
        'Naroda', 'Bapunagar', 'Amraiwadi', 'Dariapur', 'Jamalpur'
    ]
    years = [2007, 2012, 2017, 2022]
    records = []
    for year in years:
        for const in constituencies:
            electors = np.random.randint(80000, 200000)
            turnout = np.random.uniform(55, 75)
            n_cand = np.random.randint(5, 15)
            shares = np.random.dirichlet(np.ones(len(parties))) * 100
            winner_idx = np.argmax(shares)
            sorted_shares = sorted(enumerate(shares), key=lambda x: -x[1])
            margin = sorted_shares[0][1] - sorted_shares[1][1]
            for i, party in enumerate(parties):
                records.append({
                    'year': year, 'constituency': const, 'district': 'Ahmedabad',
                    'constituency_type': 'GEN', 'sub_region': 'Urban',
                    'party': party, 'party_id': party, 'party_type': 'INC',
                    'candidate': f'{party}_{const}_{year}',
                    'sex': np.random.choice(['M', 'F'], p=[0.85, 0.15]),
                    'age': np.random.randint(30, 70),
                    'votes': int(electors * turnout / 100 * shares[i] / 100),
                    'valid_votes': int(electors * turnout / 100),
                    'electors': electors,
                    'vote_share': round(shares[i], 2),
                    'voter_turnout': round(turnout, 2),
                    'position': sorted([j for j in range(len(parties))], key=lambda j: -shares[j]).index(i) + 1,
                    'won': (i == winner_idx),
                    'deposit_lost': shares[i] < 5,
                    'n_candidates': n_cand,
                    'margin': round(margin, 2) if i == winner_idx else 0,
                    'margin_pct': round(margin, 2) if i == winner_idx else 0,
                    'enop': round(np.random.uniform(2, 5), 2),
                    'incumbent': np.random.choice([0, 1], p=[0.7, 0.3]),
                    'recontest': np.random.choice([0, 1], p=[0.4, 0.6]),
                    'turncoat': np.random.choice([0, 1], p=[0.9, 0.1]),
                    'no_terms': np.random.randint(0, 4),
                    'same_constituency': np.random.choice([0, 1]),
                    'same_party': np.random.choice([0, 1]),
                    'education': np.random.choice(['Graduate', 'Post Graduate', '12th Pass']),
                    'profession_main': np.random.choice(['Business', 'Agriculture', 'Social Work']),
                })
    return pd.DataFrame(records)


# ── Feature engineering ───────────────────────────────────────────────────────

def feature_engineer(df: pd.DataFrame, encoders: dict = None, fit: bool = True) -> tuple[pd.DataFrame, dict]:
    df = df.copy()

    # Fill missing numerics
    df['age']              = pd.to_numeric(df['age'], errors='coerce').fillna(45)
    df['incumbent']        = pd.to_numeric(df['incumbent'], errors='coerce').fillna(0).astype(int)
    df['recontest']        = pd.to_numeric(df['recontest'], errors='coerce').fillna(0).astype(int)
    df['turncoat']         = pd.to_numeric(df['turncoat'], errors='coerce').fillna(0).astype(int)
    df['no_terms']         = pd.to_numeric(df['no_terms'], errors='coerce').fillna(0)
    df['same_constituency']= pd.to_numeric(df['same_constituency'], errors='coerce').fillna(0)
    df['same_party']       = pd.to_numeric(df['same_party'], errors='coerce').fillna(0)
    df['n_candidates']     = pd.to_numeric(df['n_candidates'], errors='coerce').fillna(10)
    df['voter_turnout']    = pd.to_numeric(df['voter_turnout'], errors='coerce').fillna(65)
    df['enop']             = pd.to_numeric(df['enop'], errors='coerce').fillna(3)
    df['vote_share']       = pd.to_numeric(df['vote_share'], errors='coerce').fillna(0)
    df['margin_pct']       = pd.to_numeric(df['margin_pct'], errors='coerce').fillna(0)
    df['deposit_lost']     = df['deposit_lost'].astype(int)

    # Previous vote share (shifted by constituency+party)
    df = df.sort_values(['constituency', 'party', 'year'])
    df['prev_vote_share'] = df.groupby(['constituency', 'party'])['vote_share'].shift(1)
    df['prev_vote_share'] = df['prev_vote_share'].fillna(df['vote_share'])

    # Swing
    df['swing'] = (df['vote_share'] - df['prev_vote_share']).clip(-40, 40)

    # Log margin
    df['log_margin'] = np.log1p(df['margin_pct'].abs())

    # Historical win rate per party per constituency
    win_rate = df.groupby(['constituency', 'party'])['won'].mean().reset_index()
    win_rate.columns = ['constituency', 'party', 'historical_win_rate']
    df = df.merge(win_rate, on=['constituency', 'party'], how='left')
    df['historical_win_rate'] = df['historical_win_rate'].fillna(0)

    # Deposit lost rate
    dl_rate = df.groupby(['constituency', 'party'])['deposit_lost'].mean().reset_index()
    dl_rate.columns = ['constituency', 'party', 'deposit_lost_rate']
    df = df.merge(dl_rate, on=['constituency', 'party'], how='left')
    df['deposit_lost_rate'] = df['deposit_lost_rate'].fillna(0.5)

    # Label encoders
    if encoders is None:
        encoders = {}

    cat_cols = {
        'party':              'party_enc',
        'constituency':       'const_enc',
        'district':           'district_enc',
        'constituency_type':  'constituency_type_enc',
        'sex':                'sex_enc',
    }
    for col, enc_col in cat_cols.items():
        df[col] = df[col].fillna('Unknown').astype(str).str.strip()
        if fit:
            le = LabelEncoder()
            df[enc_col] = le.fit_transform(df[col])
            encoders[col] = le
        else:
            le = encoders[col]
            known = set(le.classes_)
            df[col] = df[col].apply(lambda x: x if x in known else le.classes_[0])
            df[enc_col] = le.transform(df[col])

    return df, encoders


# ── Training ──────────────────────────────────────────────────────────────────

def train_models(use_real_data: bool = True):
    os.makedirs(get_model_path(), exist_ok=True)

    df = load_from_db() if use_real_data else generate_sample_data()
    df, encoders = feature_engineer(df, fit=True)

    # Drop rows where target is ambiguous
    df = df.dropna(subset=FEATURE_COLS + ['won', 'vote_share'])

    X       = df[FEATURE_COLS]
    y_win   = df['won'].astype(int)
    y_share = df['vote_share']

    X_train, X_test, yw_tr, yw_te = train_test_split(X, y_win,   test_size=0.2, random_state=42)
    _,       _,      ys_tr, ys_te = train_test_split(X, y_share, test_size=0.2, random_state=42)

    # Winner classifier — XGBoost
    clf = xgb.XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.75,
        min_child_weight=3, gamma=0.1,
        eval_metric='logloss', random_state=42, verbosity=0,
        scale_pos_weight=(y_win == 0).sum() / max((y_win == 1).sum(), 1),
    )
    clf.fit(X_train, yw_tr)
    acc    = accuracy_score(yw_te, clf.predict(X_test))
    cv_acc = cross_val_score(clf, X, y_win, cv=5, scoring='accuracy').mean()

    # Vote share regressor — Gradient Boosting
    reg = GradientBoostingRegressor(
        n_estimators=400, max_depth=5, learning_rate=0.04,
        subsample=0.8, min_samples_leaf=5, random_state=42,
    )
    reg.fit(X_train, ys_tr)
    mae = mean_absolute_error(ys_te, reg.predict(X_test))

    # Feature importance
    importance  = dict(zip(FEATURE_COLS, clf.feature_importances_))
    top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:7]

    # Save everything
    joblib.dump(clf,          os.path.join(get_model_path(), 'winner_clf.pkl'))
    joblib.dump(reg,          os.path.join(get_model_path(), 'vote_share_reg.pkl'))
    joblib.dump(encoders,     os.path.join(get_model_path(), 'encoders.pkl'))
    joblib.dump(FEATURE_COLS, os.path.join(get_model_path(), 'features.pkl'))

    source = 'REAL LOK DHABA DATA' if use_real_data else 'SYNTHETIC (demo only)'
    print(f"[✓] Trained on {source} | Acc: {acc:.4f} | CV: {cv_acc:.4f} | MAE: {mae:.4f}%")
    return {
        'accuracy':         round(acc, 4),
        'cv_accuracy':      round(cv_acc, 4),
        'vote_share_mae':   round(mae, 4),
        'data_source':      source,
        'training_rows':    len(df),
        'top_features':     top_features,
    }


# ── Prediction ────────────────────────────────────────────────────────────────

def predict_constituency(constituency: str, year: int = 2027, candidates: list = None):
    clf      = joblib.load(os.path.join(get_model_path(), 'winner_clf.pkl'))
    reg      = joblib.load(os.path.join(get_model_path(), 'vote_share_reg.pkl'))
    encoders = joblib.load(os.path.join(get_model_path(), 'encoders.pkl'))
    features = joblib.load(os.path.join(get_model_path(), 'features.pkl'))

    le_party = encoders['party']
    le_const = encoders['constituency']
    le_dist  = encoders['district']
    le_ctype = encoders['constituency_type']
    le_sex   = encoders['sex']

    def safe_enc(le, val):
        known = set(le.classes_)
        return int(le.transform([val if val in known else le.classes_[0]])[0])

    const_enc = safe_enc(le_const, constituency)

    # Only predict for parties that actually contested in this constituency
    from apps.prediction.models import ElectionHistory
    from django.db.models import Sum
    contested_parties = list(
        ElectionHistory.objects.filter(constituency__iexact=constituency)
        .values_list('party', flat=True).distinct()
    )
    if not contested_parties:
        contested_parties = list(
            ElectionHistory.objects.values('party')
            .annotate(total=Sum('votes')).order_by('-total')[:10]
            .values_list('party', flat=True)
        )
    known_parties = set(le_party.classes_)
    parties_to_predict = [p for p in contested_parties if p in known_parties] or list(le_party.classes_[:10])

    results = []
    for party in parties_to_predict:
        cand = next((c for c in (candidates or []) if c.get('party') == party), {})
        row = {
            'year':                  year,
            'party_enc':             safe_enc(le_party, party),
            'const_enc':             const_enc,
            'district_enc':          safe_enc(le_dist,  cand.get('district', 'Ahmedabad')),
            'constituency_type_enc': safe_enc(le_ctype, cand.get('constituency_type', 'GEN')),
            'sex_enc':               safe_enc(le_sex,   cand.get('sex', 'M')),
            'age':                   cand.get('age', 45),
            'incumbent':             cand.get('incumbent', 0),
            'recontest':             cand.get('recontest', 0),
            'turncoat':              cand.get('turncoat', 0),
            'no_terms':              cand.get('no_terms', 0),
            'same_constituency':     cand.get('same_constituency', 0),
            'same_party':            cand.get('same_party', 0),
            'n_candidates':          cand.get('n_candidates', 10),
            'prev_vote_share':       cand.get('prev_vote_share', 15.0),
            'swing':                 cand.get('swing', 0),
            'log_margin':            np.log1p(cand.get('margin_pct', 0)),
            'voter_turnout':         cand.get('voter_turnout', 65),
            'enop':                  cand.get('enop', 3.5),
            'historical_win_rate':   cand.get('historical_win_rate', 0),
            'deposit_lost_rate':     cand.get('deposit_lost_rate', 0.3),
        }
        X = pd.DataFrame([row])[features]
        win_prob  = float(clf.predict_proba(X)[0][1])
        pred_share = max(0.0, float(reg.predict(X)[0]))
        results.append({
            'party':                party,
            'win_probability':      round(win_prob, 4),
            'predicted_vote_share': round(pred_share, 2),
        })

    results.sort(key=lambda x: x['win_probability'], reverse=True)
    total = sum(r['win_probability'] for r in results) or 1
    for r in results:
        r['win_probability'] = round(r['win_probability'] / total, 4)
        r['confidence_pct']  = round(r['win_probability'] * 100, 1)

    return {
        'constituency':    constituency,
        'year':            year,
        'predicted_winner': results[0]['party'],
        'confidence':      results[0]['win_probability'],
        'all_parties':     results,
    }