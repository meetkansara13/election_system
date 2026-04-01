import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISTRICTS_SOURCE = Path(r"d:\Upag\upag-dash\assets\data\all_districts.geojson")
STATES_SOURCE = Path(r"d:\Upag\upag-dash\assets\data\all_states.json")
MAPS_DIR = PROJECT_ROOT / "static" / "maps"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def build_districts():
    raw = load_json(DISTRICTS_SOURCE)
    gujarat_features = []
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        if str(props.get("stname", "")).strip().upper() != "GUJARAT":
            continue
        gujarat_features.append({
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": {
                "district": props.get("dtname"),
                "name": props.get("dtname"),
                "state": props.get("stname"),
                "district_code": props.get("dtcode11"),
                "state_code": props.get("stcode11"),
                "district_lgd": props.get("Dist_LGD"),
                "state_lgd": props.get("State_LGD"),
                "source_year": props.get("year_stat"),
            },
        })

    return {
        "type": "FeatureCollection",
        "name": "gujarat_districts",
        "features": gujarat_features,
    }


def build_state():
    raw = load_json(STATES_SOURCE)
    gujarat_features = []
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        if str(props.get("ST_NM", "")).strip().upper() != "GUJARAT":
            continue
        gujarat_features.append({
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": {
                "name": props.get("ST_NM"),
                "state": props.get("ST_NM"),
                "inside_x": props.get("INSIDE_X"),
                "inside_y": props.get("INSIDE_Y"),
                "source_id": props.get("id"),
            },
        })

    return {
        "type": "FeatureCollection",
        "name": "gujarat_state",
        "features": gujarat_features,
    }


def main():
    districts = build_districts()
    state = build_state()

    save_json(MAPS_DIR / "gujarat_districts.geojson", districts)
    save_json(MAPS_DIR / "gujarat_state.geojson", state)

    print(f"District features: {len(districts['features'])}")
    print(f"State features: {len(state['features'])}")
    print(f"Wrote: {MAPS_DIR / 'gujarat_districts.geojson'}")
    print(f"Wrote: {MAPS_DIR / 'gujarat_state.geojson'}")


if __name__ == "__main__":
    main()
