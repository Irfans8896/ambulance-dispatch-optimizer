"""Creates the historical call dataset and loads it into the historical_calls table.

  python load_calls.py                     -> generate sample data (data/historical_calls.csv)
  python load_calls.py path/to/real.csv    -> load your own file instead
CSV columns: latitude, longitude, date, time, emergency_type
"""
import os
import sqlite3
import sys

import pandas as pd

from app.services.sample_data import make_sample_calls

BASE = os.path.dirname(os.path.abspath(__file__))
COLUMNS = ["latitude", "longitude", "date", "time", "emergency_type"]


def load(conn, df):
    conn.execute("DELETE FROM historical_calls")
    conn.executemany(
        "INSERT INTO historical_calls (latitude, longitude, date, time, emergency_type) "
        "VALUES (?,?,?,?,?)",
        [tuple(None if pd.isna(v) else v for v in row) for row in df[COLUMNS].itertuples(index=False)])
    conn.commit()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        df = pd.read_csv(sys.argv[1])
    else:
        df = make_sample_calls()
        os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
        df.to_csv(os.path.join(BASE, "data", "historical_calls.csv"), index=False)
    conn = sqlite3.connect(os.path.join(BASE, "dispatch.db"))
    load(conn, df)
    print("Loaded", len(df), "historical calls")
    conn.close()
