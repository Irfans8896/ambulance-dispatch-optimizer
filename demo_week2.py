from app.models import Location, Ambulance, Incident, Hospital, Road, InvalidStatusChange

amb = Ambulance(1, "AP21-1001", Location(15.4755, 78.4792))
inc = Incident(1, Location(15.4836, 78.4886), "accident", 4)
hosp = Hospital(1, "City General", Location(15.4686, 78.4736), 2, ["trauma"])

print("Distance ambulance -> incident: %.2f km" % amb.location.distance_km(inc.location))
print("Distance incident -> hospital: %.2f km" % inc.location.distance_km(hosp.location))

print("\n--- Ambulance status flow ---")
print("Start:", amb.status)
for step in [Ambulance.DISPATCHED, Ambulance.AT_SCENE, Ambulance.TO_HOSPITAL, Ambulance.AVAILABLE]:
    amb.update_status(step)
    print("->", amb.status)

print("\n--- Illegal change ---")
try:
    amb.update_status(Ambulance.AT_SCENE)
except InvalidStatusChange as e:
    print("Blocked:", e)

print("\n--- Hospital beds ---")
hosp.admit_patient()
hosp.admit_patient()
try:
    hosp.admit_patient()
except ValueError as e:
    print("Blocked:", e)

print("\n--- Road weights ---")
for traffic, cond in [("LOW", "GOOD"), ("HEAVY", "GOOD"), ("HEAVY", "POOR"), ("LOW", "CLOSED")]:
    r = Road(1, 2, 2.0, traffic, cond)
    print(f"2 km road, traffic={traffic}, condition={cond} -> weight {r.travel_weight()}")
