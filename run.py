"""Run locally:  python3 run.py   ->  http://127.0.0.1:5001   (port 5000 is used by AirPlay on macOS)"""
import os

from app import create_app
from setup_demo import build_demo_db

app = create_app()

if __name__ == "__main__":
    if not os.path.exists(app.config["DATABASE"]):
        build_demo_db(app.config["DATABASE"])
        print("Created demo database")
    app.run(host="127.0.0.1", port=5001, debug=True)
