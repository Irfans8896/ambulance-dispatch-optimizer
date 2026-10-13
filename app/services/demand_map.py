"""Builds a self-contained Leaflet.js map page (no Python map library needed)."""
import json

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Geospatial Demand Intelligence & Hotspot Map</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<!-- Bootstrap 5 & Icons -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
  html, body { height: 100%; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
  #map { height: 100%; width: 100%; z-index: 1; }
  
  .top-overlay {
    position: absolute;
    top: 15px;
    left: 15px;
    right: 15px;
    z-index: 1000;
    pointer-events: none;
  }
  .glass-card {
    background: rgba(15, 23, 42, 0.88);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 12px;
    padding: 0.8rem 1.25rem;
    color: white;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    pointer-events: auto;
  }
  
  .legend-card {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.82rem;
    box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    line-height: 1.8;
  }
  
  .dot-icon {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
    vertical-align: middle;
  }
  
  .pulse-cluster {
    animation: pulse-ring 2s infinite ease-out;
  }
  
  @keyframes pulse-ring {
    0% { transform: scale(0.9); opacity: 0.8; }
    50% { transform: scale(1.15); opacity: 0.4; }
    100% { transform: scale(0.9); opacity: 0.8; }
  }
</style>
</head>
<body>

<div class="top-overlay d-flex justify-content-between align-items-center">
  <div class="glass-card d-flex align-items-center gap-3">
    <div class="bg-danger text-white rounded-circle p-2 d-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
      <i class="bi bi-fire fs-5"></i>
    </div>
    <div>
      <div class="fw-bold fs-6">Geospatial Emergency Demand Hotspots</div>
      <div class="text-white-50 small" style="font-size: 0.72rem;">DBSCAN / K-Means Spatial Clustering & Pre-positioning Hubs</div>
    </div>
  </div>
  
  <div class="glass-card d-flex align-items-center gap-2">
    <a href="/" class="btn btn-sm btn-outline-light d-flex align-items-center gap-1">
      <i class="bi bi-arrow-left"></i> Live Dashboard
    </a>
  </div>
</div>

<div id="map"></div>

<script>
const DATA = __DATA__;
const map = L.map('map', {zoomControl: false}).setView(DATA.center, 14);
L.control.zoom({position: 'bottomleft'}).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Historical Incidents Scatter
DATA.calls.forEach(p => {
  L.circleMarker(p, {
    radius: 3, 
    color: '#64748b', 
    fillColor: '#94a3b8', 
    weight: 0, 
    fillOpacity: 0.45
  }).addTo(map);
});

// Demand Hotspot Clusters
DATA.hotspots.forEach(h => {
  L.circle([h.latitude, h.longitude], {
    radius: 130 + h.calls * 2, 
    color: '#ef4444', 
    fillColor: '#ef4444', 
    fillOpacity: 0.3,
    weight: 2
  }).bindPopup(`
    <div style="font-family:'Inter',sans-serif;">
      <h6 style="font-weight:700;color:#dc2626;margin-bottom:4px;"><i class="bi bi-fire"></i> Hotspot Cluster #${h.hotspot_id}</h6>
      <div style="font-size:12px;line-height:1.5;">
        <b>Total Emergency Incidents:</b> ${h.calls} (${h.share_pct}% share)<br>
        <b>Primary Incident Type:</b> <span style="text-transform:capitalize">${h.top_type}</span><br>
        <b>Peak Demand Hour:</b> ${h.peak_hour}:00
      </div>
    </div>
  `).addTo(map);
});

// Recommended Standby Pre-positioning Hubs
DATA.standby.forEach(s => {
  L.circleMarker([s.latitude, s.longitude], {
    radius: 11, 
    color: '#10b981', 
    fillColor: '#10b981', 
    fillOpacity: 0.95,
    weight: 2
  }).bindPopup(`
    <div style="font-family:'Inter',sans-serif;">
      <h6 style="font-weight:700;color:#059669;margin-bottom:4px;"><i class="bi bi-geo-alt-fill"></i> Standby Hub (Node ${s.junction_id})</h6>
      <div style="font-size:12px;line-height:1.5;">
        <b>Associated Hotspot:</b> Cluster #${s.hotspot_id}<br>
        <b>Pre-positioned Fleet:</b> <b>${s.ambulances_recommended} ambulance(s)</b> recommended
      </div>
    </div>
  `).addTo(map);
});

// Realtime Ambulances
DATA.ambulances.forEach(a => {
  const isAvail = a.status === 'AVAILABLE';
  L.circleMarker([a.latitude, a.longitude], {
    radius: 8, 
    color: isAvail ? '#10b981' : '#f59e0b', 
    fillColor: '#ffffff', 
    fillOpacity: 1, 
    weight: 3
  }).bindPopup(`<b>Ambulance ${a.vehicle_number}</b><br>Live Status: <b>${a.status}</b>`).addTo(map);
});

// Hospitals
DATA.hospitals.forEach(h => {
  const hospIcon = L.divIcon({
    html: `<div style="background:#dc2626;color:#fff;border-radius:6px;padding:3px 6px;font-size:10px;font-weight:700;display:flex;align-items:center;gap:3px;box-shadow:0 2px 6px rgba(0,0,0,0.3);"><i class="bi bi-hospital"></i> ${h.name.split(' ')[0]}</div>`,
    className: '',
    iconSize: [80, 20]
  });
  L.marker([h.latitude, h.longitude], {icon: hospIcon})
    .bindPopup(`<b>${h.name}</b><br>Available Beds: <b>${h.available_beds}</b>`).addTo(map);
});

// Floating Legend
const legend = L.control({position: 'bottomright'});
legend.onAdd = () => {
  const d = L.DomUtil.create('div', 'legend-card');
  d.innerHTML = `
    <div style="font-weight:700;font-size:0.85rem;margin-bottom:6px;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">
      <i class="bi bi-layers-fill text-primary"></i> Map Layers
    </div>
    <div><span class="dot-icon" style="background:#94a3b8;"></span> Historical Incident Point</div>
    <div><span class="dot-icon" style="background:#ef4444;"></span> Demand Hotspot Cluster</div>
    <div><span class="dot-icon" style="background:#10b981;"></span> Recommended Standby Hub</div>
    <div><span class="dot-icon" style="background:#ffffff;border:3px solid #10b981;box-sizing:border-box;"></span> Live Ambulance</div>
    <div><span class="dot-icon" style="background:#dc2626;"></span> Emergency Hospital Facility</div>
    ${DATA.summary ? '<div style="margin-top:8px;padding-top:6px;border-top:1px solid #e2e8f0;color:#0f172a;font-weight:600;">' + DATA.summary + '</div>' : ''}
  `;
  return d;
};
legend.addTo(map);
</script>
</body>
</html>
"""


def build_map_html(calls, hotspots, standby, ambulances, hospitals, summary="", max_points=500):
    """All arguments are plain lists/dicts so this function is easy to test."""
    points = [[round(r["latitude"], 6), round(r["longitude"], 6)]
              for r in calls.head(max_points).to_dict("records")] if calls is not None else []
    if hotspots:
        center = [sum(h["latitude"] for h in hotspots) / len(hotspots),
                  sum(h["longitude"] for h in hotspots) / len(hotspots)]
    else:
        center = [15.4736, 78.4786]
    data = {"center": center, "calls": points, "hotspots": hotspots, "standby": standby,
            "ambulances": ambulances, "hospitals": hospitals,
            "summary": summary}
    return PAGE.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
