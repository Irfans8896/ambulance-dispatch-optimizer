CREATE TABLE ambulances (
  ambulance_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vehicle_number TEXT UNIQUE NOT NULL,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'AVAILABLE'
);

CREATE TABLE hospitals (
  hospital_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  available_beds INTEGER NOT NULL,
  specialties TEXT,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE incidents (
  incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  emergency_type TEXT,
  severity INTEGER,
  status TEXT NOT NULL DEFAULT 'REPORTED',
  call_time TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE road_edges (
  source INTEGER NOT NULL,
  destination INTEGER NOT NULL,
  distance REAL NOT NULL,
  traffic_level TEXT DEFAULT 'LOW',
  road_condition TEXT DEFAULT 'GOOD',
  PRIMARY KEY (source, destination)
);

CREATE TABLE dispatches (
  dispatch_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ambulance_id INTEGER REFERENCES ambulances(ambulance_id),
  incident_id INTEGER REFERENCES incidents(incident_id),
  hospital_id INTEGER REFERENCES hospitals(hospital_id),
  route TEXT,
  response_time REAL,
  progress REAL NOT NULL DEFAULT 0,
  reroutes INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE historical_calls (
  call_id INTEGER PRIMARY KEY AUTOINCREMENT,
  latitude REAL,
  longitude REAL,
  date TEXT,
  time TEXT,
  emergency_type TEXT
);

CREATE TABLE users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin','dispatcher','driver')),
  ambulance_id INTEGER REFERENCES ambulances(ambulance_id)
);

CREATE TABLE notifications (
  notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  audience TEXT NOT NULL DEFAULT 'all',
  message TEXT NOT NULL
);

CREATE TABLE traffic_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  source INTEGER NOT NULL,
  destination INTEGER NOT NULL,
  traffic_level TEXT,
  road_condition TEXT
);

CREATE TABLE predicted_hotspots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  method TEXT NOT NULL,
  hotspot_id INTEGER,
  latitude REAL,
  longitude REAL,
  calls INTEGER,
  top_type TEXT,
  peak_hour INTEGER
);

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
