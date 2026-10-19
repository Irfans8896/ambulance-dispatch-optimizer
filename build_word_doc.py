import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_document():
    doc = docx.Document()

    # Page setup - 1 inch margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

        # Header
        header = section.header
        p_hdr = header.paragraphs[0]
        p_hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_hdr = p_hdr.add_run("Ambulance Dispatch Route Optimizer  |  Problem Statement #19")
        r_hdr.font.name = 'Calibri'
        r_hdr.font.size = Pt(8.5)
        r_hdr.font.color.rgb = RGBColor(148, 163, 184)

        # Footer with page number
        footer = section.footer
        p_ftr = footer.paragraphs[0]
        p_ftr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_ftr = p_ftr.add_run("Page ")
        r_ftr.font.name = 'Calibri'
        r_ftr.font.size = Pt(8.5)
        r_ftr.font.color.rgb = RGBColor(148, 163, 184)
        
        fldChar1 = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls('w'))
        instrText = parse_xml(r'<w:instrText %s xml:space="preserve"> PAGE </w:instrText>' % nsdecls('w'))
        fldChar2 = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls('w'))
        fldChar3 = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls('w'))
        r_ftr._r.append(fldChar1)
        r_ftr._r.append(instrText)
        r_ftr._r.append(fldChar2)
        r_ftr._r.append(fldChar3)

    # Palette
    COLOR_PRIMARY = RGBColor(15, 23, 42)     # #0F172A Deep Navy
    COLOR_SECONDARY = RGBColor(37, 99, 235)  # #2563EB Blue
    COLOR_ACCENT = RGBColor(230, 57, 70)    # #E63946 Crimson Red
    COLOR_MUTED = RGBColor(100, 116, 139)   # #64748B Slate Gray
    COLOR_BODY = RGBColor(30, 41, 59)       # #1E293B Dark Slate

    def set_cell_background(cell, hex_color):
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shd)

    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    def style_table(table, col_widths, headers, data):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Header Row
        hdr_cells = table.rows[0].cells
        for i, header_text in enumerate(headers):
            hdr_cells[i].text = header_text
            set_cell_background(hdr_cells[i], "1E293B")
            set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
            p = hdr_cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.name = 'Calibri'
        
        # Data Rows
        for r_idx, row_data in enumerate(data):
            row_cells = table.add_row().cells
            bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            for c_idx, cell_value in enumerate(row_data):
                row_cells[c_idx].text = cell_value
                set_cell_background(row_cells[c_idx], bg_color)
                set_cell_margins(row_cells[c_idx], top=90, bottom=90, left=150, right=150)
                p = row_cells[c_idx].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in p.runs:
                    run.font.size = Pt(9)
                    run.font.color.rgb = COLOR_BODY
                    run.font.name = 'Calibri'

        # Set column widths
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(13)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = COLOR_SECONDARY
        return p

    def add_para(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(10)
        run.font.color.rgb = COLOR_BODY
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        r_bold = p.add_run(bold_prefix + ": ")
        r_bold.font.name = 'Calibri'
        r_bold.font.size = Pt(10)
        r_bold.font.bold = True
        r_bold.font.color.rgb = COLOR_PRIMARY
        r_text = p.add_run(text)
        r_text.font.name = 'Calibri'
        r_text.font.size = Pt(10)
        r_text.font.color.rgb = COLOR_BODY
        return p

    def add_callout(label_text, body_text, border_color="2563EB", bg_color="F1F5F9"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.5)
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(r'''
            <w:tcBorders %s>
                <w:top w:val="none"/>
                <w:left w:val="single" w:sz="30" w:space="0" w:color="%s"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''' % (nsdecls('w'), border_color))
        tcPr.append(borders)
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=100, bottom=100, left=160, right=140)

        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        r_lbl = p.add_run(label_text + " — ")
        r_lbl.font.name = 'Calibri'
        r_lbl.font.size = Pt(9.5)
        r_lbl.font.bold = True
        r_lbl.font.color.rgb = COLOR_PRIMARY
        r_bdy = p.add_run(body_text)
        r_bdy.font.name = 'Calibri'
        r_bdy.font.size = Pt(9.5)
        r_bdy.font.color.rgb = COLOR_BODY

        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_before = Pt(0)
        p_after.paragraph_format.space_after = Pt(4)

    def add_image_with_caption(img_path, caption_text, width_inches=6.0):
        if not os.path.exists(img_path):
            print(f"Warning: Image not found at {img_path}")
            return
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(12)
        p_img.paragraph_format.space_after = Pt(4)
        p_img.add_run().add_picture(img_path, width=Inches(width_inches))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(0)
        p_cap.paragraph_format.space_after = Pt(12)
        run = p_cap.add_run(caption_text)
        run.font.name = 'Calibri'
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = COLOR_MUTED

    # ==================== COVER PAGE ====================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(18)
    p_inst.paragraph_format.space_after = Pt(4)
    r_inst = p_inst.add_run("ACADEMIC PROJECT EVALUATION REPORT\nDEPARTMENT OF COMPUTER SCIENCE & ENGINEERING")
    r_inst.font.name = 'Arial'
    r_inst.font.size = Pt(11)
    r_inst.font.bold = True
    r_inst.font.color.rgb = COLOR_MUTED

    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div.paragraph_format.space_after = Pt(28)
    r_div = p_div.add_run("—" * 38)
    r_div.font.color.rgb = COLOR_ACCENT

    p_maintitle = doc.add_paragraph()
    p_maintitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_maintitle.paragraph_format.space_before = Pt(0)
    p_maintitle.paragraph_format.space_after = Pt(8)
    r_maintitle = p_maintitle.add_run("AMBULANCE DISPATCH &\nROUTE OPTIMIZER")
    r_maintitle.font.name = 'Arial'
    r_maintitle.font.size = Pt(26)
    r_maintitle.font.bold = True
    r_maintitle.font.color.rgb = COLOR_ACCENT

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(24)
    r_sub = p_sub.add_run("Intelligent Golden-Hour Response Engine with Dynamic Multi-Factor Dijkstra,\nAdverse Weather Modeling, and ML Demand Pre-Positioning")
    r_sub.font.name = 'Calibri'
    r_sub.font.size = Pt(12)
    r_sub.font.italic = True
    r_sub.font.color.rgb = COLOR_PRIMARY

    # Candidate Meta Box
    tbl_meta = doc.add_table(rows=4, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_rows = [
        ["Problem Statement No:", "Problem Statement #19 (Ambulance Dispatch Optimization)"],
        ["Candidate Regd Numbers:", "25091A3298, 25091A3297"],
        ["Source Code Repository:", "https://github.com/Irfans8896/ambulance-dispatch-optimizer"],
        ["Live Cloud Deployment:", "https://ambulance-dispatch-optimizer.onrender.com"]
    ]
    for r_idx, (lbl, val) in enumerate(meta_rows):
        c1, c2 = tbl_meta.rows[r_idx].cells
        c1.text = lbl
        c2.text = val
        c1.width = Inches(2.2)
        c2.width = Inches(4.3)
        set_cell_background(c1, "F8FAFC")
        set_cell_background(c2, "FFFFFF")
        set_cell_margins(c1, top=60, bottom=60, left=100, right=100)
        set_cell_margins(c2, top=60, bottom=60, left=100, right=100)
        p1 = c1.paragraphs[0]
        p2 = c2.paragraphs[0]
        p1.runs[0].font.bold = True
        p1.runs[0].font.size = Pt(9.5)
        p1.runs[0].font.name = 'Calibri'
        p2.runs[0].font.size = Pt(9.5)
        p2.runs[0].font.name = 'Calibri'

    doc.add_paragraph().paragraph_format.space_after = Pt(24)

    # 4-KPI Metric Box on Cover Page
    tbl_kpi = doc.add_table(rows=1, cols=4)
    tbl_kpi.alignment = WD_TABLE_ALIGNMENT.CENTER
    kpis = [
        ("6.5% Faster", "Arrival Speedup vs Static", "10B981"),
        ("26.7% Better", "Repositioning Coverage Gain", "2563EB"),
        ("92 / 92", "Automated Pytest Pass Rate", "059669"),
        ("0.21 ms", "Dijkstra Dispatch Decision", "D97706")
    ]
    for idx, (val, label, border_hex) in enumerate(kpis):
        cell = tbl_kpi.rows[0].cells[idx]
        cell.width = Inches(1.6)
        set_cell_background(cell, "F8FAFC")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        tcPr = cell._tc.get_or_add_tcPr()
        bdr = parse_xml(r'''
            <w:tcBorders %s>
                <w:top w:val="single" w:sz="18" w:space="0" w:color="%s"/>
                <w:left w:val="none"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''' % (nsdecls('w'), border_hex))
        tcPr.append(bdr)
        p_val = cell.paragraphs[0]
        p_val.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_val.paragraph_format.space_after = Pt(2)
        r_v = p_val.add_run(val)
        r_v.font.name = 'Arial'
        r_v.font.size = Pt(13)
        r_v.font.bold = True
        r_v.font.color.rgb = COLOR_PRIMARY
        p_lbl = cell.add_paragraph()
        p_lbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_lbl.paragraph_format.space_after = Pt(2)
        r_l = p_lbl.add_run(label)
        r_l.font.name = 'Calibri'
        r_l.font.size = Pt(8)
        r_l.font.color.rgb = COLOR_MUTED

    doc.add_page_break()

    # ==================== 1. INTRODUCTION ====================
    add_heading_1("1. Introduction")
    add_para(
        "In emergency medicine, the minutes elapsed between an incident call and the arrival of advanced life support "
        "critically dictate patient survival. In tier-2 and tier-3 municipal centers, emergency response systems frequently "
        "collapse due to compounded infrastructural challenges: narrow arterial congestion, unpredictable road closures, "
        "monsoonal waterlogging, uncoordinated hospital triage capabilities, and vehicle placement that remains purely static. "
        "This latency represents the quintessential Golden-Hour problem in modern emergency healthcare logistics."
    )
    add_para(
        "The Ambulance Dispatch Route Optimizer is an integrated, full-stack decision-support platform designed to eliminate "
        "preventable golden-hour transit fatalities. The system accepts emergency incident coordinates, queries available fleet units, "
        "and executes a custom min-heap Dijkstra shortest-path algorithm across dynamically weighted road graphs. The edge weight formula "
        "incorporates real-time traffic levels, physical pavement conditions, and weather friction factors (Clear, Moderate Rain, "
        "Severe Monsoon, Flash Flood). Concurrently, a severity-tier selection matrix maps patient triage scores (Levels 1–5) to certified "
        "receiving hospital capabilities, guaranteeing immediate intensive care unit (ICU) and trauma bed availability."
    )
    add_para(
        "Beyond initial dispatch, the platform maintains active oversight throughout mission progression: if a road closes ahead, "
        "traffic surges, or a facility institutes patient diversion, en-route ambulances are dynamically rerouted from their latest traversed "
        "junction. Emergency calls exceeding fleet capacity are managed via an automated priority queue. To transition from reactive dispatch "
        "to proactive positioning, historical call datasets are cleaned and clustered via DBSCAN and K-Means. The Hungarian algorithm "
        "(linear sum assignment) then computes optimal proactive ambulance staging hubs, slashing average response distances by 26.7%."
    )
    add_callout(
        "Clinical Context & Problem Significance",
        "Clinical studies in emergency medicine prove that for every minute of delay in acute cardiac arrest or severe traumatic hemorrhage, "
        "survival probability diminishes by 7% to 10%. Optimizing dispatch routing and pre-positioning directly translates to saved human lives."
    )

    # ==================== 2. OBJECTIVES & FORMULATIONS ====================
    add_heading_1("2. Objectives & Mathematical Formulations")
    add_bullet("Emergency Location Intake", "Ingest incident coordinates via interactive Leaflet GIS map or structured REST payload.")
    add_bullet("Fastest Path Routing", "Calculate minimum-cost paths using custom binary min-heap Dijkstra algorithm.")
    add_bullet("Dynamic Multi-Factor Road Weights", "Dynamically scale road edge costs based on real-time traffic levels, pavement conditions, and weather friction.")
    add_bullet("Severity-Tier Hospital Matching", "Map patient distress scores (Levels 1–5) against a 4-tier hospital capability matrix (SEVERITY_MIN_TIER) to ensure ICU/trauma availability.")
    add_bullet("In-Transit Dynamic Rerouting", "Continuously re-evaluate en-route ambulances when network obstacles or destination changes occur.")
    add_bullet("Driver Cockpit In-Transit Control", "Empower drivers to adjust patient triage severity, select proximity-ranked candidate hospitals, launch GPS turn-by-turn navigation, and stream live vitals telemetry (HR, SpO2, BP) directly from the mobile HUD.")
    add_bullet("Machine Learning Hotspot Prediction", "Sanitize historical call logs and execute DBSCAN density clustering and K-Means centroids with Silhouette score validation.")
    add_bullet("Optimal Pre-Positioning Allocation", "Solve the bipartite matching problem using the Hungarian Algorithm (scipy.optimize.linear_sum_assignment) to position free units at high-demand standby junctions.")
    add_bullet("OOP Lifecycle State Enforcement", "Encapsulate vehicle, facility, and incident states within object-oriented finite state machines raising InvalidStatusChange exceptions upon illegal transitions.")
    add_bullet("Unified Dual-Mode Web Interface", "Provide a single-URL (http://127.0.0.1:5001/) dual-mode interface utilizing per-tab sessionStorage isolation for concurrent Admin and Driver HUD operations.")
    add_bullet("Comprehensive Test Suite Verification", "Validate system reliability across 92 automated test suites covering all operational scenarios.")

    add_callout(
        "Mathematical Formulations",
        "1. Dynamic Edge Weight: W(e) = d(e) * tau(traffic) * rho(condition) * omega(weather)\n"
        "   where tau in {1.0, 1.5, 2.5}, rho in {1.0, 1.4, inf}, omega in {1.0, 1.25, 1.6, 2.2}.\n"
        "2. Haversine Distance: d = 2R * arcsin(sqrt(sin^2(dlat/2) + cos(lat1)*cos(lat2)*sin^2(dlon/2))).\n"
        "3. Optimal Assignment (Hungarian Method): min sum(i=1..n) sum(j=1..n) C_ij * X_ij subject to row and column matching constraints."
    )

    # ==================== 3. MODULES ====================
    add_heading_1("3. Modular System Architecture")
    add_para("The application architecture is decomposed into thirteen interconnected functional modules:")

    mod_headers = ["Module", "Technical Description", "Primary Source Files"]
    mod_data = [
        ["Object-Oriented Domain Models", "Ambulance, Hospital, Incident, Road, and Location classes. Enforces finite status lifecycles (AVAILABLE -> DISPATCHED -> AT_SCENE -> TO_HOSPITAL -> AVAILABLE). Location computes Haversine distances.", "app/models/"],
        ["Road Graph & Dijkstra Engine", "Junctions are nodes and roads are weighted edges. Custom Dijkstra algorithm built with binary min-heap (heapq), verified against NetworkX benchmarks. Closed roads are removed (cost = inf).", "services/road_graph.py"],
        ["Dynamic Weights & Weather Engine", "Calculates multi-factor edge weights: W = d * tau * rho * omega. Persists weather states (CLEAR, RAIN, MONSOON, FLOOD). Implements automatic rush-hour time windows (08-10, 17-20).", "models/road.py, services/traffic.py"],
        ["Intelligent Dispatch Engine", "Runs Dijkstra from all available units to incident; matches patient triage severity (1-5) against a 4-tier hospital capability matrix (SEVERITY_MIN_TIER); filters active hospitals with free beds; stores dispatches.", "services/dispatch.py"],
        ["Live Mid-Trip Rerouting", "When roads, weather, or hospital statuses change, active trips are re-evaluated from their latest traversed junction. The path is dynamically updated if a road ahead is blocked or a faster path emerges.", "services/reroute.py"],
        ["Automated Triage Queue", "Overflow emergency calls wait in priority queue sorted by triage severity then timestamp; served automatically when an ambulance completes handover or a reserve unit is deployed.", "services/dispatch.py, automation.py"],
        ["Demand Prediction & Pre-Positioning", "Cleans dirty call records, identifies hotspots via DBSCAN or K-Means with Silhouette scoring, describes each hotspot (calls, share, type, peak hour), assigns standby junctions using the Hungarian Algorithm.", "services/demand.py, demand_map.py"],
        ["Dual-Mode Dashboard & Driver HUD", "Dual-mode interface at http://127.0.0.1:5001/ with per-tab sessionStorage isolation. Admin view has live map, weather widget, bed controls. Driver HUD has triage selector, hospital chooser, live vitals.", "dashboard.py, dashboard.html, driver.html"],
        ["RBAC Security & Authentication", "Administrator, dispatcher, and driver accounts with role-based access control (app/auth.py) protecting sensitive administrative and dispatch endpoints.", "auth.py"],
        ["Fleet & Hospital Administration", "Register ambulances and hospitals, set diversion, adjust beds, trigger emergency ICU surge (+10 beds), set road traffic and closures; role-filtered live notification stream.", "manage.py, services/ops.py"],
        ["Operational Analytics & Reporting", "Total dispatches, average and median response times, share within 8-minute target, emergency breakdowns by type, severity, and hour, ambulance workload; demo data generator.", "services/analytics.py, analytics.html"],
        ["Relational Database Architecture", "SQLite relational schema with 12 normalized tables: ambulances, hospitals, incidents, junctions, road_edges, dispatches, historical_calls, users, notifications, traffic_snapshots, predicted_hotspots, settings.", "schema.sql, setup_demo.py"],
        ["Automated Testing & Deployment", "92 automated Pytest test cases, performance benchmarking scripts, GitHub Actions CI workflow running tests on every commit, and Render cloud deployment configuration.", "tests/, measure_performance.py, render.yaml"]
    ]
    t_mod = doc.add_table(rows=1, cols=3)
    style_table(t_mod, [1.6, 3.4, 1.5], mod_headers, mod_data)

    # Figure 1: Architecture
    add_image_with_caption(
        "reports/system_architecture.png",
        "Figure 1: 4-Tier System Architecture Diagram (Presentation Layer, API Security, Intelligent Engine, and Persistence Layer)",
        width_inches=6.2
    )

    # ==================== 4. EXECUTION STEPS ====================
    add_heading_1("4. Execution Steps & Operational Guide")
    
    add_heading_2("4.1 Requirements & Technical Stack")
    add_para("Python 3.12 (or recent 3.x), Git, and modern web browser. Active internet connection required for Leaflet OpenStreetMap tiles and OSRM route geometry interpolation.")

    add_heading_2("4.2 Local Execution & Verification")
    add_para("1. Clone repository and initialize isolated Python virtual environment:")
    add_para("   git clone https://github.com/Irfans8896/ambulance-dispatch-optimizer.git\n   cd ambulance-dispatch-optimizer\n   python3 -m venv venv\n   source venv/bin/activate\n   pip install -r requirements.txt")
    add_para("2. Initialize SQLite schema and seed Nandyal demonstration infrastructure (8 hospitals, 3 ambulances, 9 roads, historical call logs):")
    add_para("   python3 setup_demo.py")
    add_para("3. Execute full automated test suite (all 92 automated test suites must pass):")
    add_para("   python3 -m pytest -v")
    add_para("4. Launch the application server on local port 5001 (port 5001 prevents macOS Monterey+ AirPlay Receiver conflict on port 5000):")
    add_para("   python3 run.py")
    add_para("5. Access the application in browser at http://127.0.0.1:5001 and authenticate using pre-seeded accounts:")

    auth_headers = ["Username", "Password", "Role", "Operational Scope"]
    auth_data = [
        ["admin", "admin123", "Administrator", "Unrestricted administrative control: fleet management, weather/traffic overrides, ICU surge scaling, manual dispatch."],
        ["dispatcher", "dispatch123", "Dispatcher", "Call intake, emergency dispatch, weather protocol toggling, demand hotspot review, CSV export generation."],
        ["driver1, driver2, driver3", "driver123", "Ambulance Driver", "Driver Cockpit HUD restricted to assigned vehicle, in-transit triage severity adjustment, hospital rerouting."]
    ]
    t_auth = doc.add_table(rows=1, cols=4)
    style_table(t_auth, [1.2, 1.0, 1.3, 3.0], auth_headers, auth_data)

    add_heading_2("4.3 Live Operational Workflows")
    add_bullet("Emergency Incident Intake", "Click any coordinate on the GIS map (e.g. junction 5: 15.4886, 78.4936) or enter coordinates into the dispatch card. Select emergency category (e.g. cardiac) and initial severity. Click 'Dispatch Ambulance' — the engine picks the optimal unit and hospital within 0.21 ms, animating the route on the map.")
    add_bullet("Concurrent Dual-Tab Operation", "Open http://127.0.0.1:5001/ in Tab 1 (Admin Command Center). Click the green '[ ↗ Open Driver Tab ]' button in the navbar (or open a 2nd tab and select 'Driver View'). Tab 2 immediately renders the Driver Cockpit HUD at the exact same base URL without session collision or requiring incognito mode.")
    add_bullet("In-Transit Triage & Hospital Re-Routing", "In Tab 2 (Driver HUD), tap any severity button (e.g., 5 Fatal) to re-classify patient distress. Click 'Change Hospital' to inspect candidate facilities ranked by proximity and capability tier, then click 'Confirm Destination'. Switch back to Tab 1 to observe the live route divert in real-time.")
    add_bullet("Dynamic Weather & Flood Simulation", "In the top navigation bar, toggle the Weather selector between Clear (1.0x), Rain (+25%), Monsoon (+60%), and Flood (+120%). Active trip ETAs immediately scale to reflect road friction, triggering Golden Hour Critical Warnings if travel time exceeds 15 minutes.")
    add_bullet("Road Traffic & Dynamic Closures", "In the Road Controls panel, select any road segment and set condition to 'CLOSED'. Active ambulances en route along that road dynamically recalculate and divert around the blocked segment.")
    add_bullet("Hospital Surge & Fleet Expansion", "In the Admin Drawer, click '+5 Beds', '+10 Beds', or 'Emergency Surge (+10 All)' to increase hospital ICU beds, or deploy reserve ambulances during mass-casualty incidents.")
    add_bullet("Demand Hotspots & Pre-Positioning", "Click 'Show Demand Hotspots', switch between DBSCAN and K-Means, and inspect the pre-positioning recommendations panel showing suggested standby hubs and percentage distance improvement.")

    # Figure 2: Admin Dashboard & Map
    add_image_with_caption(
        "/Users/irfan/.gemini/antigravity/brain/84ac8ec5-de2e-41ea-b2ab-7af413b79f92/.user_uploaded/media_1791213507968.png",
        "Figure 2: Command Center Dashboard Overview — Live GIS Map with Active Dispatch Route, Weather Controller, and KPI Summary Cards",
        width_inches=6.0
    )

    # Figure 3: Operations & Dispatches
    add_image_with_caption(
        "/Users/irfan/.gemini/antigravity/brain/84ac8ec5-de2e-41ea-b2ab-7af413b79f92/.user_uploaded/media_1791213507962.png",
        "Figure 3: Active Dispatches Table, Overflow Triage Queue, Hospital Bed Availability, and Real-Time Mission Notifications Stream",
        width_inches=6.0
    )

    # Figure 4: Driver Cockpit HUD
    add_image_with_caption(
        "reports/driver_hud.png",
        "Figure 4: Driver Mobile Cockpit HUD — In-Transit Triage Severity Assessment (Levels 1–5), Receiving Facility Selector, Live Patient Telemetry Stream, and GPS Navigation Link",
        width_inches=4.2
    )

    add_heading_2("4.4 Performance Benchmarking")
    add_para("Run the automated benchmark script to measure algorithm execution latencies across 500 test scenarios:")
    add_para("   python3 measure_performance.py\nResults are exported to reports/performance.json.")

    add_heading_2("4.5 Deployment on GitHub and Render")
    add_bullet("Version Control", "Repository maintained at https://github.com/Irfans8896/ambulance-dispatch-optimizer. GitHub Actions CI pipeline executes test suite on every push.")
    add_bullet("Cloud Hosting", "Deployed on Render using Blueprint configuration (render.yaml). Gunicorn WSGI server handles production traffic with automatic schema seeding on cold-start wakeups.")

    add_heading_2("4.6 Troubleshooting")
    prob_headers = ["Observed Issue", "Root Cause", "Recommended Resolution"]
    prob_data = [
        ["Port 5000 occupied on macOS", "macOS Monterey+ reserves port 5000 for AirPlay Receiver", "Launch server with python3 run.py, which binds to port 5001."],
        ["Schema error or missing column", "Outdated SQLite database file", "Delete local dispatch.db and execute python3 setup_demo.py."],
        ["Missing package error", "Virtual environment not active", "Activate environment via source venv/bin/activate and pip install -r requirements.txt."],
        ["Slow initial load on Render", "Free hosting tier spins down after 15 min idle", "Allow 60 seconds for server instance wakeup on initial request."]
    ]
    t_prob = doc.add_table(rows=1, cols=3)
    style_table(t_prob, [1.8, 2.2, 2.5], prob_headers, prob_data)

    # ==================== 5. RESULTS ====================
    add_heading_1("5. Empirical Results & Verification")

    add_heading_2("5.1 Features Verified")
    res_headers = ["Engine Feature", "Observed Empirical Result"]
    res_data = [
        ["Nearest Ambulance & Shortest Path", "Selects unit with minimum travel time; dynamic traffic and closures dynamically shift unit and path selection."],
        ["Custom Dijkstra vs NetworkX", "Verified mathematical equivalence across all junction pairs under variable traffic and road closures."],
        ["Severity-Tier Hospital Selection", "Enforces minimum hospital capability tiers (SEVERITY_MIN_TIER), routing high-severity incidents to ICU/trauma facilities."],
        ["Dynamic Weather Multipliers", "Scales road weights (Clear 1.0x, Rain 1.25x, Monsoon 1.6x, Flood 2.2x), dynamically recalculating ETAs and Golden Hour status."],
        ["In-Transit Triage & Hospital Reroute", "Ambulance driver can reclassify patient severity (1-5) and reroute destination hospitals mid-transit from the Driver HUD."],
        ["Live Mid-Trip Rerouting", "Closing a road ahead of an ambulance causes immediate rerouting from the last crossed junction."],
        ["Automated Priority Queue", "Calls exceeding fleet capacity wait in triage queue sorted by severity and time, dispatched automatically upon vehicle availability."],
        ["Hotspots & Pre-Positioning", "DBSCAN and K-Means isolate demand zones; Hungarian algorithm pre-positioning reduces incident distance from 0.82 km to 0.60 km (26.7% improvement)."],
        ["Role-Based Access Control", "Security rules prevent unauthorized call dispatch, unauthorized road closures, or cross-driver trip manipulation."]
    ]
    t_res = doc.add_table(rows=1, cols=2)
    style_table(t_res, [2.3, 4.2], res_headers, res_data)

    add_heading_2("5.2 Automated Testing Suite Breakdown")
    add_para(
        "The application is safeguarded by 92 automated Pytest test suites executing cleanly with zero failures on local machines "
        "and GitHub Actions CI. The test coverage spans every algorithmic layer:"
    )

    suite_headers = ["Test Suite File", "Component Verified", "Number of Tests"]
    suite_data = [
        ["tests/test_complete.py", "Authentication, RBAC rules, hospital severity changing, dynamic weather", "19 tests"],
        ["tests/test_dashboard.py", "Dashboard state synthesis, CSV export, summary counters", "4 tests"],
        ["tests/test_demand.py", "Data cleaning, K-Means centroids, DBSCAN clusters, Hungarian allocation", "14 tests"],
        ["tests/test_dispatch.py", "Proximity ambulance selection, hospital tier matching, lifecycle status", "10 tests"],
        ["tests/test_live.py", "Mid-transit rerouting, automatic rush-hour scaling, priority queue", "18 tests"],
        ["tests/test_models.py", "OOP entity state machines, Haversine distance, road cost calculation", "6 tests"],
        ["tests/test_routing.py", "Custom Dijkstra vs NetworkX mathematical equivalence, closed roads", "7 tests"],
        ["tests/test_scenarios.py", "End-to-end multi-incident life-saving simulations and stress cases", "14 tests"]
    ]
    t_suite = doc.add_table(rows=1, cols=3)
    style_table(t_suite, [2.2, 3.3, 1.0], suite_headers, suite_data)

    # Figure 5: Pytest Output
    add_image_with_caption(
        "reports/pytest_output.png",
        "Figure 5: Automated Pytest Suite Execution — 92 Tests Passing with Zero Failures (pytest -v in 4.90s)",
        width_inches=6.0
    )

    add_heading_2("5.3 Software Response Time Benchmarking")
    add_para("Measured via measure_performance.py across 500 operational cycles on a local environment:")
    
    perf_headers = ["Operation", "Mean (ms)", "95th Percentile (ms)", "Maximum (ms)"]
    perf_data = [
        ["Dijkstra Dispatch Decision (All Units & Hospitals)", "0.21", "0.25", "0.96"],
        ["Full Dispatch HTTP Request & DB Commit", "6.17", "7.15", "8.17"],
        ["Dashboard State Refresh (/api/state)", "1.02", "1.18", "1.52"],
        ["Hotspot Clustering (DBSCAN)", "32.22", "35.28", "114.05"],
        ["Hotspot Clustering (K-Means)", "29.50", "30.81", "31.82"],
        ["Pre-Positioning Optimization (Hungarian Algorithm)", "28.21", "31.37", "32.14"]
    ]
    t_perf = doc.add_table(rows=1, cols=4)
    style_table(t_perf, [2.7, 1.2, 1.4, 1.2], perf_headers, perf_data)

    add_heading_2("5.4 Ambulance Arrival Time Performance")
    add_para("Across 499 Monte Carlo simulation scenarios with stochastic traffic multipliers and a 10% road closure probability:")

    arr_headers = ["Dispatch & Routing Strategy", "Average Arrival Time", "Golden Hour Efficiency"]
    arr_data = [
        ["Nearest in straight line, static road routing", "3.10 min", "Baseline (100%)"],
        ["Nearest in straight line, live traffic routing", "3.00 min", "3.2% Faster"],
        ["This System: Nearest by Dijkstra travel time, live traffic & weather", "2.90 min", "6.5% Faster (Optimal)"]
    ]
    t_arr = doc.add_table(rows=1, cols=3)
    style_table(t_arr, [3.2, 1.6, 1.7], arr_headers, arr_data)

    # Figure 6: Pre-positioning & Hourly Calls Chart
    add_image_with_caption(
        "/Users/irfan/.gemini/antigravity/brain/84ac8ec5-de2e-41ea-b2ab-7af413b79f92/.user_uploaded/media_1791213507959.png",
        "Figure 6: Demand Forecasting Analytics — Proactive Ambulance Pre-Positioning Standby Hubs and Hourly Emergency Call Histogram",
        width_inches=6.0
    )

    add_heading_2("5.5 Limitations")
    add_para("The road network is a demonstration model representing Nandyal municipal core with 6 junctions and 9 road segments. Real-world municipal deployment would ingest OpenStreetMap vector graphs and vehicle telemetry via IoT hardware.")

    add_heading_2("5.6 Conclusion")
    add_para(
        "The Ambulance Dispatch Route Optimizer completely satisfies and extends the requirements of Problem Statement No. 19. "
        "By uniting custom min-heap Dijkstra routing, dynamic weather and traffic edge weights, severity-tiered hospital selection, "
        "machine learning demand clustering, Hungarian algorithm pre-positioning, in-transit driver controls, and concurrent dual-tab view isolation, "
        "the system delivers an end-to-end technological solution ensuring emergency medical care is delivered within the critical Golden Hour."
    )

    output_path = "docs/AMBULANCE_DISPATCH_ROUTE_OPTIMIZER.docx"
    doc.save(output_path)
    print(f"Successfully generated enhanced Word document at {output_path}")

    # Also save a copy in the root folder for easy user access
    root_copy = "Ambulance_Dispatch_Route_Optimizer_Report.docx"
    doc.save(root_copy)
    print(f"Successfully saved root copy at {root_copy}")

if __name__ == '__main__':
    create_document()
