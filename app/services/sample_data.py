"""Synthetic historical emergency calls (for development and demonstration).

Replace with real call records when you have them: same columns
(latitude, longitude, date, time, emergency_type) in data/historical_calls.csv.
The data is intentionally a little messy so the cleaning step has work to do.
"""
import numpy as np
import pandas as pd

# (latitude, longitude, share of calls, type probabilities, peak hour)
CENTRES = [
    (15.4696, 78.4746, 0.40, {"accident": 0.6, "cardiac": 0.2, "general": 0.2}, 9),
    (15.4841, 78.4891, 0.35, {"cardiac": 0.5, "accident": 0.3, "child": 0.2}, 18),
    (15.4931, 78.4981, 0.25, {"child": 0.4, "general": 0.4, "accident": 0.2}, 23),
]
NOISE_SHARE = 0.08
SPREAD_DEG = 0.0012          # about 130 m
AREA = (15.4536, 15.5036, 78.4636, 78.5086)   # lat_min, lat_max, lon_min, lon_max


def make_sample_calls(n=600, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    n_noise = int(n * NOISE_SHARE)
    n_main = n - n_noise
    for lat, lon, share, types, peak in CENTRES:
        count = int(n_main * share)
        names, probs = zip(*types.items())
        hours = np.clip(np.round(rng.normal(peak, 2.5, count)), 0, 23) % 24
        for i in range(count):
            rows.append({
                "latitude": rng.normal(lat, SPREAD_DEG),
                "longitude": rng.normal(lon, SPREAD_DEG),
                "hour": int(hours[i]),
                "emergency_type": rng.choice(names, p=probs),
            })
    for _ in range(n_noise):                   # scattered background calls
        rows.append({
            "latitude": rng.uniform(AREA[0], AREA[1]),
            "longitude": rng.uniform(AREA[2], AREA[3]),
            "hour": int(rng.integers(0, 24)),
            "emergency_type": rng.choice(["accident", "cardiac", "child", "general"]),
        })

    df = pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)
    days = pd.to_datetime("2026-06-01") + pd.to_timedelta(rng.integers(0, 90, len(df)), unit="D")
    df["date"] = days.strftime("%Y-%m-%d")
    df["time"] = [f"{h:02d}:{int(m):02d}" for h, m in zip(df["hour"], rng.integers(0, 60, len(df)))]
    df = df[["latitude", "longitude", "date", "time", "emergency_type"]]

    # ---- deliberately dirty rows -------------------------------------------
    dirty = df.copy()
    dirty = pd.concat([dirty, dirty.sample(15, random_state=1)])           # duplicates
    bad = dirty.sample(10, random_state=2).index
    dirty.loc[dirty.index.isin(bad), "latitude"] = np.nan                  # missing coordinates
    zeros = pd.DataFrame({"latitude": [0.0] * 8, "longitude": [0.0] * 8,
                          "date": ["2026-07-01"] * 8, "time": ["12:00"] * 8,
                          "emergency_type": ["accident"] * 8})              # GPS failures
    far = pd.DataFrame({"latitude": [28.6, 12.9], "longitude": [78.0786, 78.4786],
                        "date": ["2026-07-02"] * 2, "time": ["10:00"] * 2,
                        "emergency_type": ["cardiac"] * 2})                 # other cities
    dirty = pd.concat([dirty, zeros, far], ignore_index=True)
    dirty["emergency_type"] = dirty["emergency_type"].astype(object)
    messy = dirty.sample(40, random_state=3).index
    dirty.loc[messy, "emergency_type"] = dirty.loc[messy, "emergency_type"].str.upper() + " "
    dirty.loc[dirty.sample(10, random_state=4).index, "emergency_type"] = None
    return dirty.sample(frac=1, random_state=5).reset_index(drop=True)
