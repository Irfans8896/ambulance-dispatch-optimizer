# Demo script (about 5 minutes)

Open the live link 2 minutes early (the free tier may need ~1 minute to wake). Backup: `python3 run.py`.

1. **Login** as `admin` / `admin123`. Point out the role shown in the top bar.
2. **Dispatch**: click the map near junction 5 (or type 15.4881, 78.4931), Accident, severity 4, press *Dispatch*.
   Show ambulance, hospital, route and ETA, the ambulance driving, and the *Live notifications* panel.
3. **Status buttons**: use *Next stage* (or let it drive): At Scene, To Hospital, Available. Beds drop by 1.
4. **Traffic**: set road 4-5 to HEAVY, dispatch again: ETA rises, route changes. Then CLOSED on 4-5 and 5-6: another ambulance.
5. **Register**: add an ambulance (e.g. AP21-1004 near the map point) and a hospital. Then put City General *on diversion*
   and dispatch a trauma case: it goes to the other hospital.
6. **Hotspots**: *Show demand hotspots*, switch DBSCAN / K-Means, show the standby points and the
   *Ambulance pre-positioning* panel ("x% better"), then open the *Hotspot map* link.
7. **Driver view**: open a private window, login as `driver2` / `driver123`: only their ambulance, a navigation button
   and the next-stage button. Show that a driver cannot dispatch (403).
8. **Live re-routing**: dispatch an emergency, and while the ambulance is driving close a road on its route
   (admin, road controls). The message says which ambulance was rerouted, and the marker continues on the new route.
9. **Queue**: dispatch 4 emergencies in a row. The 4th waits in *Waiting queue*; when an ambulance finishes
   it is dispatched automatically (most severe first).
10. **Rush hour**: switch on *Automatic rush-hour traffic*; between 08-10 and 17-20 the roads turn one level busier.
11. **Analytics**: open *Analytics*, press *generate 10 demo emergencies* if empty.
12. **Report**: *Download report (CSV)*.
13. **Evidence**: `python3 -m pytest -v` (88 passed) and `reports/performance.json`.
