"""Builds a self-contained Leaflet.js map page (no Python map library needed)."""
import json

PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Ambulance demand hotspots</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; }
  .legend { background: white; padding: 8px 10px; line-height: 1.6; font: 13px Arial; border-radius: 4px; }
  .dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; }
</style>
</head>
<body>
<div id="map"></div>
<script>
const DATA = __DATA__;
const map = L.map('map').setView(DATA.center, 14);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);

DATA.calls.forEach(p => L.circleMarker(p, {radius: 2, color: '#6c757d', weight: 0, fillOpacity: 0.5}).addTo(map));

DATA.hotspots.forEach(h => {
  L.circle([h.latitude, h.longitude], {radius: 120 + h.calls * 1.5, color: '#d9534f', fillOpacity: 0.25})
   .bindPopup('<b>Hotspot ' + h.hotspot_id + '</b><br>Calls: ' + h.calls + ' (' + h.share_pct + '%)' +
              '<br>Main type: ' + h.top_type + '<br>Peak hour: ' + h.peak_hour + ':00').addTo(map);
});

DATA.standby.forEach(s => {
  L.circleMarker([s.latitude, s.longitude], {radius: 10, color: '#198754', fillColor: '#198754', fillOpacity: 0.9})
   .bindPopup('<b>Standby point</b> (junction ' + s.junction_id + ')<br>Hotspot ' + s.hotspot_id +
              '<br>Ambulances recommended: ' + s.ambulances_recommended).addTo(map);
});

DATA.ambulances.forEach(a => {
  L.circleMarker([a.latitude, a.longitude], {radius: 7, color: '#0d6efd', fillColor: '#ffffff', fillOpacity: 1, weight: 3})
   .bindPopup('<b>' + a.vehicle_number + '</b><br>Status: ' + a.status).addTo(map);
});

DATA.hospitals.forEach(h => {
  L.marker([h.latitude, h.longitude]).bindPopup('<b>' + h.name + '</b><br>Beds: ' + h.available_beds).addTo(map);
});

const legend = L.control({position: 'bottomright'});
legend.onAdd = () => {
  const d = L.DomUtil.create('div', 'legend');
  d.innerHTML = '<span class="dot" style="background:#6c757d"></span>Past calls<br>' +
    '<span class="dot" style="background:#d9534f"></span>Demand hotspot<br>' +
    '<span class="dot" style="background:#198754"></span>Recommended standby point<br>' +
    '<span class="dot" style="background:#fff;border:3px solid #0d6efd;box-sizing:border-box"></span>Ambulance now<br>' +
    '<span style="color:#2a81cb">&#9679;</span> Hospital' + DATA.summary;
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
            "summary": ("<br><br>" + summary) if summary else ""}
    return PAGE.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
