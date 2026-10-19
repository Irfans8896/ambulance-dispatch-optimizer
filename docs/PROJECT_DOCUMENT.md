# AMBULANCE DISPATCH ROUTE OPTIMIZER
**Project Document: Problem Statement No. 19**  
**Regd No:** 25091A3298, 25091A3297  
**Source code:** https://github.com/Irfans8896/ambulance-dispatch-optimizer  
**Live application:** https://ambulance-dispatch-optimizer.onrender.com  

---

## 1. Introduction
In an emergency, the minutes before an ambulance reaches the patient often decide the outcome. In tier-2 and tier-3 cities, delay comes from congested roads, closed roads, unpredictable adverse weather conditions, and ambulances waiting far from where calls occur. This is the golden-hour problem of emergency medical response.

The Ambulance Dispatch Route Optimizer is a web application that takes an emergency location, finds the ambulance that can reach it fastest, calculates the route with Dijkstra's algorithm on road weights that change dynamically with traffic, road conditions, and weather friction, and recommends a suitable hospital using severity-tier matching and bed availability. It keeps working after the dispatch: if a road closes, traffic surges, adverse weather strikes, or a hospital stops accepting patients, ambulances already on the way are re-routed in real-time from their current transit position. Calls that cannot be served at once wait in an automated priority queue. Historical call data is cleaned and clustered with DBSCAN and K-Means to identify high-demand zones, and the system uses the Hungarian algorithm to suggest where free ambulances should wait in advance.

Ambulances, hospitals, and incidents are modelled as object-oriented classes with enforced finite state transitions. The application is built with Python Flask and SQLite, shows a live Leaflet map dashboard with route animations, supports three user roles, and features a dual-mode interface allowing the Admin Command Center and Driver Cockpit HUD to run simultaneously in separate tabs at the root URL. The demonstration area is Nandyal, Andhra Pradesh, using a 6-junction municipal road network and synthetic call history.

---

## 2. Objectives
1. **Receive an emergency incident location** and find the nearest available ambulance by Dijkstra travel time.
2. **Calculate the fastest route** using Dijkstra's algorithm with a custom binary min-heap.
3. **Change road weights dynamically** using traffic level, road condition, and adverse weather; a closed road is removed from the graph.
4. **Recommend the most suitable hospital** using proximity, available beds, specialty matching, and patient triage severity tiers (Tiers 1–4).
5. **Re-route ambulances already on their way** when roads close, traffic spikes, weather deteriorates, or hospital destinations change.
6. **Enable driver in-transit control** to re-classify patient triage severity (Levels 1–5) and reroute destination hospitals from the Driver Cockpit HUD.
7. **Use historical emergency data and clustering (DBSCAN & K-Means)** to identify high-demand accident zones.
8. **Suggest where ambulances should be positioned in advance** using the Hungarian Algorithm (`linear_sum_assignment`) to minimize fleet transit distance.
9. **Track ambulance, incident, and hospital lifecycles** with object-oriented classes and enforced status transitions.
10. **Provide a unified web dashboard** with tab-isolated Admin Command Center and Driver HUD views, real-time notifications, CSV reports, and analytics.
11. **Test the system with 92 automated scenarios** and measure response time and arrival-time improvements.

---

## 3. Modules

| Module | What it does | Main files |
|:---|:---|:---|
| **Object-oriented models** | `Ambulance`, `Hospital`, `Incident`, `Road`, and `Location` classes. Each enforces its own finite status flow (`AVAILABLE` &rarr; `DISPATCHED` &rarr; `AT_SCENE` &rarr; `TO_HOSPITAL` &rarr; `AVAILABLE`), so an illegal change raises `InvalidStatusChange`. `Location` computes Haversine distance. | `app/models/` |
| **Road graph and Dijkstra** | Junctions are nodes and roads are weighted edges. Dijkstra's algorithm is written by hand with a binary min-heap (`heapq`) and verified against NetworkX. Closed roads are removed from the graph (&infin;). | `services/road_graph.py` |
| **Dynamic weights & Weather** | $\text{Weight} = d \times \tau \times \rho \times \omega$. Traffic factor $\tau$ (LOW 1.0, MEDIUM 1.5, HEAVY 2.5), condition factor $\rho$ (GOOD 1.0, POOR 1.4, CLOSED blocked), and **Weather friction factor $\omega$ (CLEAR 1.0, RAIN 1.25, MONSOON 1.6, FLOOD 2.2)**. Optional automatic rush-hour traffic (08&ndash;10 and 17&ndash;20) raises each road one level. | `models/road.py`, `services/traffic.py` |
| **Dispatch engine** | Runs Dijkstra from every available ambulance to the incident and picks the fastest; **matches patient triage severity (1&ndash;5) against a 4-tier hospital capability matrix (`SEVERITY_MIN_TIER`)** to ensure ICU/trauma care for critical cases; filters active hospitals with free beds; stores the dispatch and updates statuses and beds. | `services/dispatch.py` |
| **Live re-routing** | When a road, weather setting, or hospital changes, every trip in progress is re-checked from the last junction it reached. The route is updated dynamically if a road ahead closed or a significantly faster path exists, notifying the driver and dispatcher. | `services/reroute.py` |
| **Waiting queue** | A call with no available ambulance waits in `incident_queue`, ordered by triage severity then time, and is dispatched automatically the moment an ambulance frees up, a road reopens, or a reserve unit is deployed. | `services/dispatch.py`, `services/automation.py` |
| **Demand prediction & pre-positioning** | Cleans dirty historical call records, identifies demand hotspots with DBSCAN or K-Means with Silhouette scoring, describes each hotspot (calls, share, type, peak hour), **assigns standby junctions using the Hungarian Algorithm (`linear_sum_assignment`)**, and reports the distance saved. Completed dispatches feed back into history. | `services/demand.py`, `services/demand_map.py` |
| **Dashboard & Driver Cockpit HUD** | Dual-mode interface at `http://127.0.0.1:5001/` with per-tab `sessionStorage` isolation. **Admin View:** Summary KPI cards, Leaflet map with animated routes, weather switcher, bed surge controls (+5/+10 beds), queue, pre-positioning drawer, Chart.js chart, and CSV export. **Driver HUD:** In-transit triage severity buttons (1&ndash;5), candidate hospital selector, live patient telemetry (HR, $\text{SpO}_2$, BP), GPS navigation link, and trip stage progression. | `app/dashboard.py`, `templates/dashboard.html`, `templates/driver.html` |
| **Login, roles & permissions** | Administrator, dispatcher, and driver accounts with role-based permission rules (`app/auth.py`) on every endpoint. | `app/auth.py` |
| **Administration & notifications** | Register ambulances and hospitals, put a hospital on diversion, change bed capacity, trigger emergency ICU surge (+10 beds to all hospitals), set road traffic and closures; role-filtered notifications feed. | `app/manage.py`, `services/ops.py` |
| **Analytics** | Totals, average and median response time, share within an 8-minute target, emergencies by type, severity, and hour, trips per ambulance and patients per hospital; demo data generator. | `services/analytics.py`, `templates/analytics.html` |
| **Database** | SQLite with 12 relational tables: `ambulances`, `hospitals`, `incidents`, `junctions`, `road_edges`, `dispatches`, `historical_calls`, `users`, `notifications`, `traffic_snapshots`, `predicted_hotspots`, `settings`. | `schema.sql`, `setup_demo.py` |
| **Testing and deployment** | **92 automated Pytest tests**, performance measurement benchmark script, GitHub Actions CI running tests on every push, and Render cloud deployment. | `tests/`, `measure_performance.py`, `render.yaml`, `wsgi.py` |

---

## 4. Execution Steps

### 4.1 Requirements
Python 3.12 (or a recent 3.x), Git, and a modern web browser. An internet connection is needed for Leaflet map tiles and OSRM street geometry interpolation.

### 4.2 Run on a Mac / Local Machine
1. Open Terminal in the project folder:
   ```bash
   cd /Users/irfan/ambulance-dispatch-optimizer
   ```
2. Create and activate the virtual environment, then install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Initialize the database with sample data (8 hospitals, 3 ambulances, 9 roads, historical calls):
   ```bash
   python3 setup_demo.py
   ```
4. Run the automated test suite. **All 92 tests should pass:**
   ```bash
   python3 -m pytest -v
   ```
5. Start the web application:
   ```bash
   python3 run.py
   ```
   Open `http://127.0.0.1:5001` in your browser (port 5001 is used to avoid macOS AirPlay conflict on port 5000).

6. Log in with demo accounts:
   | Username | Password | Role | Permissions |
   |:---|:---|:---|:---|
   | `admin` | `admin123` | Administrator | Full access: register units, set traffic/closures/weather, hospital surge, dispatch |
   | `dispatcher` | `dispatch123` | Dispatcher | Intake and dispatch emergencies, update weather, view hotspots, download reports |
   | `driver1`, `driver2`, `driver3` | `driver123` | Ambulance Driver | Driver Cockpit HUD for assigned vehicle, triage severity, hospital selector |

---

### 4.3 Using the Application

* **Dispatching:** Click the map near junction 5 (15.4886, 78.4936) or enter coordinates, select emergency type and severity, and click **Dispatch**. The nearest ambulance, severity-matched hospital, dynamic route, and estimated ETA appear, and the ambulance animates along the path.
* **Dual Tab Operation (Admin + Driver at Same URL):**
  1. **Tab 1:** Keep open at `http://127.0.0.1:5001/` (Admin Command Center).
  2. **Tab 2:** Click the green **`[ ↗ Open Driver Tab ]`** button in the navbar (or open a new tab at `http://127.0.0.1:5001/` and click **`Driver View`**). Tab 2 immediately becomes the **Driver Cockpit HUD**. Both tabs run at the exact same base address without session collisions or needing incognito mode.
* **In-Transit Triage Severity & Hospital Re-routing:**
  * In Tab 2 (Driver HUD), tap any severity level (e.g. **5 Fatal**) to re-classify patient distress.
  * Click **Change Hospital** to inspect nearby candidate facilities ranked by proximity and capability tier, then click **Confirm Destination**.
  * Switch to Tab 1 (Admin) to see the ambulance route dynamically divert to the new hospital with a live notification banner.
* **Weather & Flood Simulation:**
  * In the top navbar, change the **Weather** selector from `☀️ Clear (1.0x)` to `🌧️ Rain (+25%)`, `⛈️ Monsoon (+60%)`, or `🌊 Flood (+120%)`.
  * Active trip ETAs dynamically increase to reflect road friction; if travel time exceeds 15 minutes, a **Golden Hour Critical Warning** is triggered.
* **Traffic & Road Closures:** In the Road controls panel, select a road segment, set traffic to `HEAVY` or condition to `CLOSED`, and click Apply. Ambulances on that segment are dynamically rerouted.
* **Queue Management:** Dispatch 4 incidents with only 3 ambulances. The 4th call is held in the priority queue and auto-dispatched the instant a vehicle finishes its run.
* **Surge Capacity:** In the Admin drawer, click **+5 Beds**, **+10 Beds**, or **⚡ Emergency Surge (+10 All)** to scale hospital capacities, or **Deploy 2 Reserve Ambulances**.
* **Demand Hotspots & Pre-positioning:** Click **Show Demand Hotspots**, toggle between DBSCAN and K-Means, and inspect the pre-positioning recommendations drawer showing the percentage coverage improvement.
* **Analytics & CSV Reports:** Open `/analytics` for response-time distributions or click **CSV Export** on the dashboard.

---

### 4.4 Performance Measurement
```bash
python3 measure_performance.py
```
This evaluates Dijkstra decision speed, full request cycles, and cluster extraction, saving metrics to `reports/performance.json`.

---

### 4.5 Deployment on GitHub and Render
* Repository hosted at: `https://github.com/Irfans8896/ambulance-dispatch-optimizer`
* Connected to Render via Blueprint (`render.yaml`).
* Build command: `pip install -r requirements.txt`
* Start command: `gunicorn wsgi:app --workers 1 --timeout 120`

---

## 5. Results

### 5.1 Features Verified

| Feature | Verified Result |
|:---|:---|
| **Nearest Ambulance & Fastest Route** | Selects the ambulance with lowest travel time; dynamic traffic and closures change both vehicle choice and route. |
| **Custom Dijkstra vs NetworkX** | Mathematically identical route costs for every pair of junctions across dry, congested, and closed roads. |
| **Severity-Tier Hospital Matching** | Matches patient severity (1&ndash;5) to minimum hospital tiers (`SEVERITY_MIN_TIER`), ensuring critical patients reach Tier-1 ICU/trauma facilities while skipping full or diverted hospitals. |
| **Dynamic Weather Friction** | Rainfall and monsoon friction multipliers scale edge costs ($W = d \times \tau \times \rho \times \omega$), adjusting ETAs and prompting diversion to safer bypasses. |
| **In-Transit Triage & Hospital Rerouting** | Driver can update triage severity and reroute destination hospitals mid-mission; synchronized in real-time between Admin and Driver tabs via per-tab `sessionStorage`. |
| **Live Mid-Trip Rerouting** | Closing a road ahead of an en-route ambulance dynamically reroutes it from the last passed junction; unaffected trips remain unchanged. |
| **Automated Priority Queue** | Overflow calls wait in queue sorted by severity and timestamp; automatically served when an ambulance completes handover. |
| **Hotspots & Pre-positioning** | DBSCAN and K-Means isolate high-demand clusters; Hungarian algorithm repositioning reduces average incident distance from 0.82 km to 0.60 km (**26.7% improvement**). |
| **RBAC Security** | Role-based endpoint guards block unauthorized dispatch, road modification, or foreign trip progression. |

---

### 5.2 Testing
**92 automated tests pass** locally and on GitHub Actions CI:
* 6 Object-oriented model tests
* 7 Dijkstra routing & NetworkX validation tests
* 10 Dispatch & severity-tier selection tests
* 14 Demand clustering & pre-positioning tests
* 4 Dashboard & report tests
* 15 End-to-end operational scenarios
* 18 Live re-routing, queue, rush-hour, and analytics tests
* 18 Authentication, RBAC, Driver HUD hospital change, and Dynamic Weather simulation tests

---

### 5.3 Software Response Time
Measured with `measure_performance.py`:
| Operation | Mean (ms) | 95th Percentile (ms) | Max (ms) |
|:---|:---:|:---:|:---:|
| Dispatch decision only (Dijkstra across all units & hospitals) | 0.21 | 0.25 | 0.96 |
| Full dispatch HTTP request | 6.17 | 7.15 | 8.17 |
| Dashboard state refresh | 1.02 | 1.18 | 1.52 |
| Hotspot extraction (DBSCAN) | 32.22 | 35.28 | 114.05 |
| Hotspot extraction (K-Means) | 29.50 | 30.81 | 31.82 |
| Pre-positioning optimization (Hungarian Algorithm) | 28.21 | 31.37 | 32.14 |

---

### 5.4 Ambulance Arrival Time Improvement
Across 499 seeded random scenarios with stochastic traffic and a 10% road closure probability:
| Strategy | Average Arrival Time |
|:---|:---:|
| Nearest in a straight line, route ignores traffic | 3.10 min |
| Nearest in a straight line, route uses live traffic | 3.00 min |
| **This system: Nearest by Dijkstra travel time, live traffic & weather** | **2.90 min (6.5% faster)** |

---

### 5.5 Limitations
* The road network is a demonstration model of Nandyal with 6 major junctions and 9 arterial road edges.
* Live GPS and external sensor feeds are simulated within the web application.

---

### 5.6 Conclusion
The system covers every requirement of Problem Statement No. 19 and extends beyond it: nearest-ambulance selection, Dijkstra routing on dynamic weights with weather friction, severity-tiered hospital recommendation, Hungarian-algorithm pre-positioning, in-transit driver controls, and object-oriented lifecycle management. It is fully tested (92 passing tests), documented, and verified.
