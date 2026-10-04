# Ambulance Dispatch Route Optimizer

![tests](https://github.com/YOUR_USER/YOUR_REPO/actions/workflows/tests.yml/badge.svg)

Problem Statement No. 19 | Regd Nos: 25091A3298, 25091A3297

**Live app:** [LIVE_URL] (free tier: the first load after 15 idle minutes takes about 1 minute to wake up)
**Repository:** [REPO_URL]

A system that takes an emergency location, finds the nearest available ambulance, calculates the
fastest route with Dijkstra's algorithm on live traffic and road conditions, recommends a suitable
hospital, and uses historical call data (K-Means / DBSCAN) to find high-demand zones and suggest
where to pre-position ambulances.

## Features
| Feature | Where |
|---|---|
| OOP models with status tracking (Ambulance, Hospital, Incident, Road, Location) | `app/models/` |
| Own Dijkstra on a road graph, checked against NetworkX | `app/services/road_graph.py` |
| Dynamic weights: distance x traffic x road condition (closed road = blocked) | `app/models/road.py` |
| Nearest ambulance by travel time, hospital by specialty and free beds | `app/services/dispatch.py` |
| Admin controls for traffic and road closures | dashboard + `POST /api/roads/traffic` |
| Hotspots (DBSCAN / K-Means), pre-positioning advice, hotspot map | `app/services/demand.py` |
| Dashboard: Leaflet map, status buttons, Chart.js, auto-refresh, CSV report | `app/templates/dashboard.html` |
| Login with 3 roles (admin, dispatcher, driver) and per-endpoint permissions | `app/auth.py` |
| Driver page (mobile): own assignment, navigation link, next-stage button | `app/templates/driver.html` |
| Register ambulances and hospitals; hospital diversion and bed control | `app/manage.py`, `app/services/ops.py` |
| Pre-positioning panel, K-Means/DBSCAN switch, hotspot map link | dashboard |
| **Live re-routing**: ambulances already on their way are re-planned when a road closes, traffic changes or a hospital goes on diversion | `app/services/reroute.py` |
| **Waiting queue** with priority (most severe first), served automatically when an ambulance is free | `app/services/dispatch.py` (`process_queue`) |
| **Analytics page** (response times, types, severity, ambulance use) and demo-data generator | `/analytics`, `app/services/analytics.py` |
| **Automatic rush-hour traffic** (08-10, 17-20, switch on/off by the admin) | `app/services/traffic.py` |
| Notifications, traffic snapshots, stored predicted hotspots, feedback of completed calls into history | `app/services/ops.py` |

## Run locally (Mac)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 setup_demo.py        # creates dispatch.db with sample data
python3 run.py               # http://127.0.0.1:5001  (port 5000 is used by AirPlay on macOS)
```

## Tests and measurements
```bash
python3 -m pytest -v          # 88 tests: models, routing, dispatch, hotspots, dashboard, scenarios, login/roles, registration
python3 measure_performance.py   # response times, saved to reports/performance.json
```

### Results
Ambulance ETA to the scene, 500 seeded random traffic/closure scenarios (small 6-junction demo map):

| Strategy | Average ETA |
|---|---|
| Nearest in a straight line, route ignores traffic | 3.10 min |
| Nearest in a straight line + live-traffic routing | 3.00 min |
| **This system** (nearest by travel time + live routing) | **2.90 min** |

The system is 6.5% faster than the naive approach on this map. The gain is small because the map is
small; it grows with bigger networks and more ambulances. Software response times (dispatch decision
about 0.1 ms, full API call a few ms, hotspot analysis about 20 ms) are in `reports/performance.json`
and vary with the machine.

## Login accounts (demo)
| Username | Password | Can do |
|---|---|---|
| admin | admin123 | everything (register units, hospital status, traffic and closures, dispatch) |
| dispatcher | dispatch123 | report emergencies, dispatch, status buttons, hotspots, reports |
| driver1, driver2, driver3 | driver123 | driver page for their own ambulance only |

These are public demo passwords. On the live site set `ADMIN_PASSWORD`, `DISPATCHER_PASSWORD`, `DRIVER_PASSWORD`
and `SHOW_DEMO_LOGINS=0` in Render > Environment. Set `AUTH_REQUIRED=0` only for local experiments.

## API
| Method | URL | Purpose |
|---|---|---|
| POST | `/api/incidents/dispatch` | report an emergency, get ambulance, hospital, routes, ETA |
| POST | `/api/dispatches/<id>/advance` | move to the next status (At Scene, To Hospital, Available) |
| POST | `/api/roads/traffic` | set traffic level / road condition (CLOSED blocks the road) |
| GET | `/api/state`, `/api/summary` | everything the dashboard shows |
| GET | `/api/hotspots?method=dbscan` or `?method=kmeans&k=3` | demand zones |
| GET | `/api/prepositioning` | standby points and ambulance moves |
| GET | `/hotspot-map` | hotspot map page |
| GET | `/api/reports/dispatches.csv` | downloadable dispatch report |
| POST | `/api/ambulances`, `/api/hospitals`, `/api/hospitals/<id>` | register units, change hospital status/beds (admin) |
| POST | `/api/dispatches/<id>/progress`, `/api/dispatches/recheck` | report trip progress (0-1); re-check active trips and the queue |
| POST | `/api/settings/auto-traffic`, `/api/demo/simulate` | rush-hour traffic on/off, demo data (admin) |
| GET | `/api/queue`, `/api/analytics`, `/analytics` | waiting incidents, statistics, analytics page |
| GET | `/api/notifications`, `/api/traffic-history`, `/api/driver/status`, `/api/me`, `/health` | notifications, road-change history, driver view, session, health |
| GET | `/api/route?source=1&target=6`, `/api/roads`, `/api/ambulances`, `/api/hospitals`, `/api/dispatches` | data and routing |

## Deploy on Render (free tier)
1. Push this repo to GitHub.
2. Render: New > Web Service > connect the repo.
3. Build command `pip install -r requirements.txt`, start command `gunicorn wsgi:app --workers 1 --timeout 120`
   (or use the included `render.yaml`).
4. Free-tier limits: the service sleeps after 15 idle minutes (about 1 minute to wake) and local files are
   lost on restart, so `wsgi.py` rebuilds the SQLite database with sample data on every start.

## Weekly progress (git tags)
week-1 requirements and database | week-2 OOP models | week-3 road graph and Dijkstra |
week-4 dynamic weights and dispatch | week-5 clustering and pre-positioning |
week-6 dashboard | week-7 scenarios, measurements, deployment, documentation

## Project structure
```
app/models/      Ambulance, Hospital, Incident, Road, Location
app/services/    road_graph, dispatch, demand, demand_map, sample_data
app/templates/   dashboard.html
tests/           test_models, test_routing, test_dispatch, test_demand, test_dashboard, test_scenarios
setup_demo.py    builds the sample database      wsgi.py   Render entry point
measure_performance.py   response-time measurement      schema.sql  database tables
```

Demo area: Nandyal, Andhra Pradesh (map centre 15.4786, 78.4836). Junction positions, ambulances, hospitals and call
hotspots are demonstration points placed in the town, not surveyed locations.

How re-routing works: the map reports how far along its leg an ambulance is (0 to 1). When something changes, the
server finds the last junction it passed and plans again from there; if the road ahead is closed, or a clearly
faster route exists (at least 5% and 0.3 min better), the route is replaced and the driver is notified. Without
progress reports (for example a driver who only uses the driver page) the ambulance is assumed to be at the start
of its current leg. The queue uses severity first, then first come first served; it does not take an ambulance away
from a less severe call.

Limits: the call history and road network are simulated; there is no live GPS or live traffic feed (traffic is set by the
administrator). Data resets on every restart on the Render free tier. The road map is a small hand-made network (6 junctions, 9 roads) with synthetic call history;
real map data and real call records would replace `seed_roads.py` and `data/historical_calls.csv`.
