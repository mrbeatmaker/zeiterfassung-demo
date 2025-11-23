import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime, date, timedelta

# --- 1. KONFIGURATION ---
st.set_page_config(
    page_title="ERDAL SAKARYA HR System", 
    page_icon="🔒", 
    layout="wide"
)

# --- 2. DESIGN & CSS ---
def load_custom_css():
    st.markdown("""
        <style>
        [data-testid="stHeader"], footer, [data-testid="stDecoration"] {display: none !important;}
        .stApp {background-color: #0E1117;}
        
        /* Cards für KPIs */
        div[data-testid="stMetric"] {
            background-color: #1E1E1E;
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #F63366;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
        }
        
        /* Buttons */
        .stButton > button {
            background: linear-gradient(90deg, #FF4B4B 0%, #F63366 100%);
            color: white; border: none; border-radius: 8px; font-weight: bold;
        }
        
        /* Status Badges */
        .status-pending {color: #FFA500; font-weight: bold;}
        .status-approved {color: #00FF00; font-weight: bold;}
        .status-rejected {color: #FF0000; font-weight: bold;}
        </style>
        """, unsafe_allow_html=True)

# --- 3. DATENBANK INIT ---
def init_db():
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    
    # Tabelle Buchungen
    c.execute('''CREATE TABLE IF NOT EXISTS buchungen (
        id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter TEXT, 
        projekt TEXT, aktion TEXT, zeitstempel DATETIME)''')
    
    # Tabelle Users (ERWEITERT um Job-Details)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, full_name TEXT,
        department TEXT, job_title TEXT, vacation_days_total INTEGER)''')
    
    # Tabelle Abwesenheiten (ERWEITERT um Status)
    c.execute('''CREATE TABLE IF NOT EXISTS abwesenheiten (
        id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter TEXT, 
        start_datum DATE, end_datum DATE, typ TEXT, kommentar TEXT,
        status TEXT DEFAULT 'Ausstehend', admin_note TEXT)''')
    
    # --- DEMO DATEN GENERIEREN ---
    c.execute('SELECT count(*) FROM users')
    if c.fetchone()[0] == 0:
        users = [
            ('admin', 'admin123', 'admin', 'Personalabteilung (HR)', 'HR', 'Head of HR', 30),
            ('max', '1234', 'user', 'Max Mustermann', 'IT', 'Senior Developer', 30),
            ('erika', '1234', 'user', 'Erika Musterfrau', 'Marketing', 'Content Manager', 28)
        ]
        c.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?)', users)

        # Demo Buchungen (Vergangenheit)
        heute = date.today()
        # Wir simulieren 5 Tage Arbeit
        buchungen = []
        for i in range(1, 6):
            tag = heute - timedelta(days=i)
            # Nur Wochentage
            if tag.weekday() < 5: 
                buchungen.append(("Max Mustermann", "Web-Entwicklung", "Kommen", f"{tag} 08:00:00"))
                buchungen.append(("Max Mustermann", "Web-Entwicklung", "Gehen", f"{tag} 17:00:00")) # 9 Stunden (1h Pause inkludiert in Logik)
        
        for item in buchungen:
            ts = datetime.strptime(item[3], "%Y-%m-%d %H:%M:%S")
            c.execute('INSERT INTO buchungen (mitarbeiter, projekt, aktion, zeitstempel) VALUES (?, ?, ?, ?)', 
                      (item[0], item[1], item[2], ts))
        
        # Demo Antrag (Ausstehend)
        next_mon = heute + timedelta(days=10)
        c.execute("INSERT INTO abwesenheiten (mitarbeiter, start_datum, end_datum, typ, kommentar, status) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Max Mustermann", next_mon, next_mon + timedelta(days=4), "🌴 Urlaub", "Sommerurlaub bitte!", "Ausstehend"))

    conn.commit()
    conn.close()

# --- FUNKTIONEN (User & DB) ---

def get_user_details(fullname):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE full_name=?", (fullname,))
    u = c.fetchone() # Returns tuple
    conn.close()
    return u # (username, pass, role, fullname, dept, job, vac_total)

def get_all_users():
    conn = sqlite3.connect('zeiterfassung.db')
    df = pd.read_sql_query("SELECT full_name, department, job_title FROM users WHERE role!='admin'", conn)
    conn.close()
    return df

def login_user(username, password):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=? AND password=?', (username.lower(), password))
    user = c.fetchone()
    conn.close()
    return user

def buchung_speichern(mitarbeiter, projekt, aktion):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO buchungen (mitarbeiter, projekt, aktion, zeitstempel) VALUES (?, ?, ?, ?)', 
              (mitarbeiter, projekt, aktion, zeit))
    conn.commit()
    conn.close()
    st.toast(f"✅ {aktion} gespeichert!", icon="💾")

def lade_daten(table, user_role, username):
    conn = sqlite3.connect('zeiterfassung.db')
    if user_role == 'admin':
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    else:
        df = pd.read_sql_query(f"SELECT * FROM {table} WHERE mitarbeiter=?", conn, params=(username,))
    conn.close()
    return df

# --- LOGIK: STUNDEN & ÜBERSTUNDEN ---

def berechne_kpis(df_buchungen, fullname):
    """Berechnet Arbeitsstunden, Soll/Ist und Überstunden."""
    if df_buchungen.empty:
        return pd.DataFrame(), 0
    
    df = df_buchungen.copy()
    df['zeitstempel'] = pd.to_datetime(df['zeitstempel'])
    df['datum'] = df['zeitstempel'].dt.date
    
    statistik = []
    saldo_gesamt = 0
    
    # Nur User Daten
    df = df[df['mitarbeiter'] == fullname]
    
    for datum, gruppe in df.groupby('datum'):
        start = gruppe[gruppe['aktion'] == 'Kommen']['zeitstempel'].min()
        ende = gruppe[gruppe['aktion'] == 'Gehen']['zeitstempel'].max()
        
        stunden = 0.0
        soll = 8.0 # Standard 8 Stunden Tag
        
        if pd.notna(start) and pd.notna(ende):
            diff = ende - start
            stunden = diff.total_seconds() / 3600
        
        # Einfache Pausenregelung: Ab 6h werden 30min abgezogen, wenn nicht gestempelt (vereinfacht)
        # Hier nehmen wir die reine Differenz Start-Ende.
        
        saldo = stunden - soll
        saldo_gesamt += saldo
        
        statistik.append({
            "Datum": datum,
            "Ist": round(stunden, 2),
            "Soll": soll,
            "Saldo": round(saldo, 2)
        })
        
    return pd.DataFrame(statistik), round(saldo_gesamt, 2)

# --- LOGIK: URLAUB & ANTRÄGE ---

def urlaub_beantragen(mitarbeiter, start, ende, typ, kommentar):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    c.execute("INSERT INTO abwesenheiten (mitarbeiter, start_datum, end_datum, typ, kommentar, status) VALUES (?, ?, ?, ?, ?, 'Ausstehend')", 
              (mitarbeiter, start, ende, typ, kommentar))
    conn.commit()
    conn.close()
    st.toast("Antrag gesendet!", icon="📨")

def urlaub_entscheiden(id_val, entscheidung, notiz):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    status = "Genehmigt" if entscheidung == "ok" else "Abgelehnt"
    c.execute("UPDATE abwesenheiten SET status=?, admin_note=? WHERE id=?", (status, notiz, id_val))
    conn.commit()
    conn.close()
    st.toast(f"Status gesetzt auf: {status}")

def get_vacation_stats(fullname, total_days):
    conn = sqlite3.connect('zeiterfassung.db')
    # Zähle nur GENEHMIGTE Urlaubstage
    df = pd.read_sql_query("SELECT start_datum, end_datum FROM abwesenheiten WHERE mitarbeiter=? AND typ='🌴 Urlaub' AND status='Genehmigt'", conn, params=(fullname,))
    conn.close()
    
    taken = 0
    for index, row in df.iterrows():
        d1 = datetime.strptime(row['start_datum'], "%Y-%m-%d")
        d2 = datetime.strptime(row['end_datum'], "%Y-%m-%d")
        delta = (d2 - d1).days + 1
        taken += delta
        
    remaining = total_days - taken
    return taken, remaining

def count_sick_days(fullname):
    conn = sqlite3.connect('zeiterfassung.db')
    df = pd.read_sql_query("SELECT start_datum, end_datum FROM abwesenheiten WHERE mitarbeiter=? AND typ='🤒 Krank'", conn, params=(fullname,))
    conn.close()
    days = 0
    for index, row in df.iterrows():
        d1 = datetime.strptime(row['start_datum'], "%Y-%m-%d")
        d2 = datetime.strptime(row['end_datum'], "%Y-%m-%d")
        days += (d2 - d1).days + 1
    return days

# --- UI SEITEN ---

def login_screen():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("## 🔒 ERDAL SAKARYA Login")
        with st.form("login"):
            u = st.text_input("User")
            p = st.text_input("Passwort", type="password")
            if st.form_submit_button("Anmelden"):
                user = login_user(u, p)
                if user:
                    st.session_state.update({'logged_in':True, 'user':user})
                    st.rerun()
                else:
                    st.error("Falsch.")

# === ADMIN DASHBOARD ===
def admin_view():
    st.title("👨‍💼 HR Admin Cockpit")
    
    # Navigation
    tab_overview, tab_requests = st.tabs(["👥 Mitarbeiter-Übersicht", "📨 Anträge genehmigen"])
    
    # --- TAB 1: MITARBEITER DETAILS ---
    with tab_overview:
        col_list, col_detail = st.columns([1, 3])
        
        with col_list:
            st.markdown("### Mitarbeiter wählen")
            users_df = get_all_users()
            selected_name = st.radio("Liste:", users_df['full_name'], label_visibility="collapsed")
        
        with col_detail:
            if selected_name:
                # Hole User Details aus DB
                u_details = get_user_details(selected_name) # (user, pass, role, name, dept, job, vac_total)
                
                # Header Card
                with st.container():
                    c_img, c_info = st.columns([1, 4])
                    with c_img:
                        st.markdown("# 👤")
                    with c_info:
                        st.markdown(f"## {u_details[3]}")
                        st.caption(f"Abteilung: **{u_details[4]}** | Position: **{u_details[5]}**")
                
                st.divider()
                
                # KPIs berechnen
                df_b = lade_daten('buchungen', 'admin', 'all')
                stats_df, saldo = berechne_kpis(df_b, selected_name)
                taken, rest = get_vacation_stats(selected_name, u_details[6])
                sick = count_sick_days(selected_name)
                
                # KPI Row
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Überstunden-Konto", f"{saldo} h", delta_color="normal")
                k2.metric("Urlaub Genommen", f"{taken} Tage")
                k3.metric("Urlaub Rest", f"{rest} Tage")
                k4.metric("Krankheitstage", f"{sick} Tage")
                
                st.markdown("### 📊 Arbeitszeiten & 40h Trend")
                if not stats_df.empty:
                    # Diagramm Soll vs Ist
                    chart_data = stats_df[['Datum', 'Ist', 'Soll']].set_index('Datum')
                    st.bar_chart(chart_data, color=["#F63366", "#333333"])
                    
                    with st.expander("Detaillierte Tabelle ansehen"):
                        st.dataframe(stats_df, use_container_width=True)
                else:
                    st.info("Keine Arbeitszeiten erfasst.")

    # --- TAB 2: GENEHMIGUNGEN ---
    with tab_requests:
        st.markdown("### Offene Anträge")
        conn = sqlite3.connect('zeiterfassung.db')
        df_req = pd.read_sql_query("SELECT * FROM abwesenheiten WHERE status='Ausstehend'", conn)
        conn.close()
        
        if not df_req.empty:
            for index, row in df_req.iterrows():
                with st.container():
                    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                    c1.markdown(f"**{row['mitarbeiter']}**")
                    c2.markdown(f"{row['typ']}<br>{row['start_datum']} bis {row['end_datum']}", unsafe_allow_html=True)
                    c3.markdown(f"📝 *{row['kommentar']}*")
                    
                    with c4:
                        notiz = st.text_input("Admin-Notiz", key=f"n_{row['id']}")
                        cA, cB = st.columns(2)
                        if cA.button("✅ Genehmigen", key=f"ok_{row['id']}"):
                            urlaub_entscheiden(row['id'], "ok", notiz)
                            st.rerun()
                        if cB.button("❌ Ablehnen", key=f"no_{row['id']}"):
                            urlaub_entscheiden(row['id'], "no", notiz)
                            st.rerun()
                    st.divider()
        else:
            st.success("Alles erledigt! Keine offenen Anträge.")

# === EMPLOYEE DASHBOARD ===
def employee_view(user_data):
    fullname = user_data[3]
    vac_total = user_data[6]
    
    st.markdown(f"## 👋 Hallo, {fullname}")
    
    # 1. HEADER KPIs (Überstunden & Urlaub)
    df_b = lade_daten('buchungen', 'user', fullname)
    stats_df, saldo = berechne_kpis(df_b, fullname)
    taken, rest = get_vacation_stats(fullname, vac_total)
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Mein Zeit-Konto", f"{saldo} h", delta="Überstunden / Minusstunden")
    k2.metric("Urlaub Rest", f"{rest} Tage", f"von {vac_total}")
    k3.metric("Urlaub Genommen", f"{taken} Tage")
    
    st.divider()
    
    tab_stempel, tab_urlaub = st.tabs(["⏱️ Stempeln & Zeiten", "🌴 Urlaub & Status"])
    
    with tab_stempel:
        col_act, col_chart = st.columns([1, 2])
        with col_act:
            st.markdown("#### Stempuhr")
            p = st.selectbox("Projekt", ["Web", "Video", "Intern"])
            if st.button("🟢 KOMMEN", use_container_width=True): 
                buchung_speichern(fullname, p, "Kommen"); st.rerun()
            if st.button("🔴 GEHEN", use_container_width=True): 
                buchung_speichern(fullname, p, "Gehen"); st.rerun()
            if st.button("☕ PAUSE", use_container_width=True): 
                buchung_speichern(fullname, p, "Pause"); st.rerun()
                
        with col_chart:
            st.markdown("#### Meine Woche")
            if not stats_df.empty:
                # Zeige nur die letzten 7 Einträge im Chart
                recent = stats_df.tail(7)[['Datum', 'Ist', 'Soll']].set_index('Datum')
                st.bar_chart(recent, color=["#F63366", "#333333"])

    with tab_urlaub:
        c_req, c_stat = st.columns(2)
        with c_req:
            st.markdown("#### Neuen Antrag stellen")
            with st.form("req"):
                typ = st.selectbox("Typ", ["🌴 Urlaub", "🤒 Krank", "🏫 Schulung"])
                d1 = st.date_input("Start")
                d2 = st.date_input("Ende")
                kom = st.text_area("Grund / Notiz")
                if st.form_submit_button("Beantragen"):
                    urlaub_beantragen(fullname, d1, d2, typ, kom)
                    st.rerun()
                    
        with c_stat:
            st.markdown("#### Status meiner Anträge")
            conn = sqlite3.connect('zeiterfassung.db')
            df_my = pd.read_sql_query("SELECT * FROM abwesenheiten WHERE mitarbeiter=? ORDER BY id DESC", conn, params=(fullname,))
            conn.close()
            
            if not df_my.empty:
                for i, r in df_my.iterrows():
                    color = "#FFA500" if r['status']=='Ausstehend' else ("#00FF00" if r['status']=='Genehmigt' else "#FF0000")
                    st.markdown(
                        f"""
                        <div style="padding:10px; border-radius:5px; border:1px solid #333; margin-bottom:10px;">
                            <strong>{r['typ']}</strong> ({r['start_datum']} - {r['end_datum']})<br>
                            Status: <span style="color:{color}">{r['status']}</span><br>
                            <small>Admin Notiz: {r['admin_note'] if r['admin_note'] else '-'}</small>
                        </div>
                        """, unsafe_allow_html=True
                    )
            else:
                st.info("Keine Anträge.")

# --- MAIN ---
def main():
    load_custom_css()
    init_db()
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        
    if not st.session_state['logged_in']:
        login_screen()
    else:
        # Header Logout
        c1, c2 = st.columns([5,1])
        c1.markdown("**ERDAL SAKARYA SYSTEMS**")
        if c2.button("Abmelden"):
            st.session_state['logged_in'] = False
            st.rerun()
            
        # Routing
        user_data = st.session_state['user'] # (user, pass, role, full_name, dept, job, vac)
        if user_data[2] == 'admin':
            admin_view()
        else:
            employee_view(user_data)

if __name__ == '__main__':
    main()