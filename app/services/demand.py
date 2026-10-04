"""Week 5: historical data cleaning, hotspot clustering, ambulance pre-positioning."""
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score

EARTH_KM = 6371.0088
DEFAULT_K = 3
MAX_DISTANCE_FROM_CITY_KM = 50      # calls farther than this from the median are not "local"


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorised great-circle distance in km."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


# ------------------------------------------------------------------ cleaning

def calls_from_db(conn):
    return pd.read_sql_query(
        "SELECT latitude, longitude, date, time, emergency_type FROM historical_calls", conn)


def clean_calls(raw):
    """Return (clean DataFrame, report dict explaining what was removed)."""
    df = raw.copy()
    report = {"raw_rows": len(df)}

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df["emergency_type"] = (df["emergency_type"].fillna("").astype(str)
                            .str.strip().str.lower().replace("", "unknown"))

    before = len(df)
    df = df.dropna(subset=["latitude", "longitude"])
    report["removed_missing_coordinates"] = before - len(df)

    before = len(df)
    valid = df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)
    not_zero = ~((df["latitude"] == 0) & (df["longitude"] == 0))
    df = df[valid & not_zero]
    report["removed_invalid_coordinates"] = before - len(df)

    before = len(df)
    df = df.drop_duplicates()
    report["removed_duplicates"] = before - len(df)

    before = len(df)
    if len(df):
        d = haversine_km(df["latitude"].median(), df["longitude"].median(),
                         df["latitude"], df["longitude"])
        df = df[d <= MAX_DISTANCE_FROM_CITY_KM]
    report["removed_outside_service_area"] = before - len(df)

    df["hour"] = pd.to_datetime(df["time"], format="%H:%M", errors="coerce").dt.hour
    df = df.reset_index(drop=True)
    report["clean_rows"] = len(df)
    return df, report


# ---------------------------------------------------------------- clustering

def _describe(df, labels, centers=None):
    """Turn cluster labels into a ranked list of hotspot dictionaries."""
    total = len(df)
    spots = []
    for label in sorted(set(labels) - {-1}):             # -1 = DBSCAN noise
        members = df[labels == label]
        hours = members["hour"].dropna()
        spots.append({
            "latitude": float(members["latitude"].mean() if centers is None else centers[label][0]),
            "longitude": float(members["longitude"].mean() if centers is None else centers[label][1]),
            "calls": int(len(members)),
            "share_pct": round(100 * len(members) / total, 1),
            "top_type": members["emergency_type"].mode().iat[0],
            "peak_hour": int(hours.mode().iat[0]) if len(hours) else None,
        })
    spots.sort(key=lambda s: s["calls"], reverse=True)
    for rank, s in enumerate(spots, start=1):
        s["hotspot_id"] = rank
    return spots


def suggest_k(df, k_min=2, k_max=6):
    """Silhouette score for each k (a guide only: scattered noise calls can push it to a larger k)."""
    if len(df) < k_max + 1:
        return k_min, {}
    X = df[["latitude", "longitude"]].to_numpy()
    scores = {}
    for k in range(k_min, k_max + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(X)
        scores[k] = round(float(silhouette_score(X, labels)), 3)
    return max(scores, key=scores.get), scores


def kmeans_hotspots(df, k=None):
    if len(df) == 0:
        return []
    k = min(k or DEFAULT_K, len(df))
    model = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = model.fit_predict(df[["latitude", "longitude"]].to_numpy())
    return _describe(df, labels, centers=model.cluster_centers_)


def dbscan_hotspots(df, eps_km=0.3, min_samples=10):
    """Density-based clustering; scattered calls are treated as noise."""
    if len(df) == 0:
        return []
    coords = np.radians(df[["latitude", "longitude"]].to_numpy())
    labels = DBSCAN(eps=eps_km / EARTH_KM, min_samples=min_samples,
                    metric="haversine", algorithm="ball_tree").fit_predict(coords)
    return _describe(df, labels)


def find_hotspots(df, method="kmeans", k=None, eps_km=0.3, min_samples=10):
    if method == "dbscan":
        return dbscan_hotspots(df, eps_km, min_samples)
    return kmeans_hotspots(df, k)


def demand_by_hour(df):
    """Number of calls in each hour 0..23 (for the Week 6 chart)."""
    counts = df["hour"].dropna().astype(int).value_counts()
    return [int(counts.get(h, 0)) for h in range(24)]


# -------------------------------------------------------------- pre-positioning

def allocate_slots(calls, n_ambulances):
    """How many ambulances to station at each hotspot (proportional to demand)."""
    n_spots = len(calls)
    if n_ambulances <= 0 or n_spots == 0:
        return [0] * n_spots
    if n_ambulances <= n_spots:                          # busiest hotspots get one each
        order = sorted(range(n_spots), key=lambda i: calls[i], reverse=True)
        slots = [0] * n_spots
        for i in order[:n_ambulances]:
            slots[i] = 1
        return slots
    slots = [1] * n_spots                                # everyone gets one, rest by share
    spare = n_ambulances - n_spots
    total = sum(calls)
    exact = [spare * c / total for c in calls]
    slots = [s + int(e) for s, e in zip(slots, exact)]
    leftover = n_ambulances - sum(slots)
    by_remainder = sorted(range(n_spots), key=lambda i: exact[i] - int(exact[i]), reverse=True)
    for i in by_remainder[:leftover]:
        slots[i] += 1
    return slots


def average_nearest_distance(calls, positions):
    """Mean distance (km) from each historical call to its closest ambulance position."""
    if len(calls) == 0 or not positions:
        return 0.0
    lat = calls["latitude"].to_numpy()[:, None]
    lon = calls["longitude"].to_numpy()[:, None]
    p_lat = np.array([p[0] for p in positions])[None, :]
    p_lon = np.array([p[1] for p in positions])[None, :]
    return float(haversine_km(lat, lon, p_lat, p_lon).min(axis=1).mean())


def recommend_positions(hotspots, junctions, ambulances, calls=None):
    """Suggest standby junctions and which ambulance should move where.

    hotspots   : list from find_hotspots()
    junctions  : {junction_id: Location}
    ambulances : list of Ambulance objects (only AVAILABLE ones are moved)
    calls      : cleaned calls DataFrame, used to measure the improvement
    """
    from .dispatch import nearest_junction
    from app.models import Location

    free = [a for a in ambulances if a.is_available()]
    allocation = allocate_slots([h["calls"] for h in hotspots], len(free))

    standby, slots = [], []
    for h, count in zip(hotspots, allocation):
        if count == 0:
            continue
        j = nearest_junction(Location(h["latitude"], h["longitude"]), junctions)
        standby.append({"hotspot_id": h["hotspot_id"], "junction_id": j,
                        "latitude": junctions[j].latitude, "longitude": junctions[j].longitude,
                        "ambulances_recommended": count, "calls": h["calls"]})
        slots.extend([j] * count)

    moves = []
    if free and slots:
        cost = np.array([[a.location.distance_km(junctions[j]) for j in slots] for a in free])
        rows, cols = linear_sum_assignment(cost)         # fewest total kilometres moved
        for r, c in zip(rows, cols):
            amb, target = free[r], slots[c]
            here = nearest_junction(amb.location, junctions)
            moves.append({"vehicle_number": amb.vehicle_number,
                          "from_junction": here, "to_junction": target,
                          "distance_km": round(float(cost[r, c]), 2),
                          "already_in_place": here == target})

    result = {"standby_points": standby, "moves": moves}
    if calls is not None and len(calls) and free:
        before = average_nearest_distance(calls, [(a.location.latitude, a.location.longitude) for a in free])
        after = average_nearest_distance(calls, [(junctions[j].latitude, junctions[j].longitude) for j in slots])
        result["avg_distance_km_before"] = round(before, 2)
        result["avg_distance_km_after"] = round(after, 2)
        result["improvement_pct"] = round(100 * (before - after) / before, 1) if before else 0.0
    return result
