"""Entry point for Render:  gunicorn wsgi:app --workers 1"""
from app import create_app
from setup_demo import build_demo_db

app = create_app()
build_demo_db(app.config["DATABASE"])   # fresh sample data on every start
