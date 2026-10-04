# Problem 19 requirements checklist (from the project PDF)

| Requirement | Where | Status |
|---|---|---|
| Receive emergency location | dashboard form + map click, `POST /api/incidents/dispatch` | Done |
| Nearest available ambulance | `DispatchService.select_ambulance` (travel time) | Done |
| Fastest route, Dijkstra | `road_graph.py` (own code, checked vs NetworkX) | Done |
| Dynamic weights: traffic and road condition, closed = blocked | `Road.travel_weight`, road controls | Done |
| Suitable hospital (distance, beds, specialty) | `DispatchService.select_hospital`, hospital diversion | Done |
| Historical data, K-Means / DBSCAN hotspots | `demand.py`, hotspot map, dashboard | Done |
| Pre-positioning suggestions | `recommend_positions`, dashboard panel, `/api/prepositioning` | Done |
| OOP entities with status tracking | `app/models/` (Ambulance, Incident status machines; Hospital status and beds) | Done |
| Users: dispatcher, administrator, driver | login, roles, driver page | Done |
| Register ambulances and hospitals | admin forms, `POST /api/ambulances`, `/api/hospitals` | Done |
| Update incident and ambulance status | status buttons, driver page | Done |
| Reports | CSV download, `reports/performance.json` | Done |
| Tables in architecture picture: users, traffic snapshots, predicted hotspots | `schema.sql` | Done |
| Notifications / real-time status | notifications panel, 5 s auto-refresh | Done |
| Feedback of completed dispatches into history | `record_completed_call` | Done |
| Live GPS and live traffic feeds | simulated (admin sets traffic) | Simulated |
| Native mobile app | mobile-friendly driver web page | Web page |
| Live re-routing of ambulances already dispatched | `reroute.py`, progress reports from the map | Done |
| Incident queue with priority | `process_queue` | Done |
| Analytics and response-time charts | `/analytics` | Done |
| Time-of-day (rush-hour) traffic | `traffic.py`, admin switch | Done |
| Pytest scenarios, response times | `tests/`, `measure_performance.py` | Done |
