# ElectionAI — Integrated Election System

Three modules in one Django project:
- **📍 Booth Locator** — GeoPy nearest-booth finder + Folium map
- **📊 Result Prediction** — XGBoost + GradientBoosting ML pipeline
- **📈 Dashboard** — Plotly charts, live stats, news-channel style UI

---

## Setup

```bash
# 1. Create virtualenv
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Migrations
python manage.py makemigrations
python manage.py migrate

# 4. Seed sample data (Ahmedabad booths)
python manage.py seed_data

# 5. Create admin user
python manage.py createsuperuser

# 6. Run server
python manage.py runserver
```

Open: http://127.0.0.1:8000

---

## Usage Flow

### Step 1 — Train ML Models
Click **"Train Models"** button on the dashboard, OR:
```bash
curl -X POST http://127.0.0.1:8000/api/predict/train/
```

### Step 2 — Booth Locator API
```bash
# Nearest booths to a GPS coordinate
GET /api/booth/nearest/?lat=23.03&lng=72.58&limit=5

# Folium map HTML for a constituency
GET /api/booth/map/?constituency=Maninagar

# List all booths
GET /api/booth/list/?constituency=Maninagar
```

### Step 3 — Prediction API
```bash
# Single constituency
POST /api/predict/
{
  "constituency": "Maninagar",
  "year": 2027,
  "candidates": [
    {
      "party": "BJP",
      "incumbent": 1,
      "prev_vote_share": 48.5,
      "candidate_age": 52,
      "criminal_cases": 0,
      "assets_cr": 12.5,
      "voter_turnout": 67.0,
      "swing": 3.2
    }
  ]
}

# Bulk prediction — seat projection
POST /api/predict/bulk/
{
  "constituencies": ["Maninagar", "Ellisbridge", "Sabarmati"],
  "year": 2027
}
```

### Step 4 — Dashboard
Open http://127.0.0.1:8000/dashboard/

---

## Replace Sample Data with Real ECI Data

1. Download constituency/candidate data from https://eci.gov.in/
2. Parse CSV into `ElectionHistory` model via Django admin or custom import command
3. Re-train models: `POST /api/predict/train/`
4. Add real booth coordinates via Django Admin at `/admin/`

---

## Project Structure

```
election_system/
├── apps/
│   ├── booth_locator/          # GeoPy + Folium
│   │   ├── models.py           # PollingBooth, Constituency
│   │   ├── views.py            # NearestBooth, BoothMap, BoothList
│   │   └── management/commands/seed_data.py
│   ├── prediction/             # XGBoost ML
│   │   ├── models.py           # ElectionHistory, PredictionResult
│   │   ├── ml_engine.py        # train_models(), predict_constituency()
│   │   └── views.py            # Train, Predict, BulkPredict
│   └── dashboard/
│       ├── views.py            # Plotly charts, stats
│       └── (templates in root templates/dashboard/)
├── templates/
│   └── dashboard/index.html   # News-channel style UI
├── ml_models/                  # Saved .pkl files (auto-created)
├── election_system/
│   ├── settings.py
│   └── urls.py
└── requirements.txt
```

---

## ML Model Details

| Model | Algorithm | Target | Metric |
|-------|-----------|--------|--------|
| Winner Classifier | XGBoost | Won (0/1) | Accuracy |
| Vote Share | GradientBoosting | Vote % | MAE |

**Features used:**
- `incumbent`, `prev_vote_share`, `candidate_age`
- `criminal_cases`, `assets_cr` (log-scaled)
- `voter_turnout`, `swing` (= current - prev vote share)
- `party_enc`, `constituency_enc` (label encoded)

To improve accuracy: add more years of ECI data, include demographic features (SC/ST %, literacy, urban-rural ratio), sentiment from social media.
