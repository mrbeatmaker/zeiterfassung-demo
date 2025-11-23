import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime, date, timedelta
import os # Neu: Um zu prüfen, ob das Bild da ist

# --- 1. KONFIGURATION & LOGO SETUP ---
# Wir definieren das Logo hier, damit wir es leicht ändern können
LOGO_FILE = "ES_favicon-transparent.png"

st.set_page_config(
    page_title="ERDAL SAKARYA HR System", 
    page_icon=LOGO_FILE, # Hier wird das Favicon im Browser-Tab gesetzt
    layout="wide"
)

# --- 2. DESIGN & CSS ---
def load_custom_css():
    st.markdown("""
        <style>
        /* Versteckt Standard-Elemente */
        [data-testid="stHeader"], footer, [data-testid="stDecoration"] {display: none !important;}
        .stApp {background-color: #0E1117;}
        
        /* Sidebar Design anpassen */
        [data-testid="stSidebar"] {
            background-color: #1E1E1E;
            border-right: 1px solid #333;
        }

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
        </style>
        """, unsafe_allow_html=True)

# --- 3. DATENBANK INIT ---
DB_NAME = 'zeiterfassung_v2.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS buchungen (id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter TEXT, projekt TEXT, aktion TEXT, zeitstempel DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, full_name TEXT, department TEXT, job_title TEXT, vacation_days_total INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS abwesenheiten (id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter TEXT, start_datum DATE, end_datum DATE, typ TEXT, kommentar TEXT, status TEXT DEFAULT 'Ausstehend', admin_note TEXT)''')
    
    # Check User / Demo Daten
    c.execute('SELECT count(*) FROM users')
    if c.fetchone()[0] == 0:
        users = [
            ('admin', 'admin123', 'admin', 'Personalabteilung (HR)', 'HR', 'Head of HR', 30),
            ('max', '1234', 'user', 'Max Mustermann', 'IT', 'Senior Developer', 30),
            ('erika', '1234', 'user', 'Erika Musterfrau', 'Marketing', 'Content Manager', 28)
        ]
        c.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?)', users)
        
        heute = date.today()
        buchungen = []
        for i in range(1, 6):
            tag = heute - timedelta(days=i)
            if tag.weekday() < 5: 
                buchungen.append(("Max Mustermann", "Web-Entwicklung", "Kommen", f"{tag} 08:00:00"))
                buchungen.append(("Max Mustermann", "Web-Entwicklung", "Gehen", f"{tag} 17:00:00"))
        
        for item in buchungen:
            ts = datetime.strptime(item[3], "%Y-%m-%d %H:%M:%S")
            c.execute('INSERT INTO buchungen (mitarbeiter, projekt, aktion, zeitstempel) VALUES (?, ?, ?, ?)', (item[0], item[1], item[2], ts))
            
        next_mon = heute + timedelta(days=10)
        c.execute("INSERT INTO abwesenheiten (mitarbeiter, start_datum, end_datum, typ, kommentar, status) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Max Mustermann", next_mon, next_mon + timedelta(days=4), "🌴 Urlaub", "Sommerurlaub bitte!", "Ausstehend"))
                  
    conn.commit()
    conn.close()

# --- HELFER FUNKTIONEN ---

def get_all_users_full():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM users WHERE role!='admin'", conn)
    conn.close()
    return df

def get_company_stats():
    conn = sqlite3.connect(DB_NAME)
    df_b = pd.read_sql_query("SELECT b.*, u.department FROM buchungen b JOIN users u ON b.mitarbeiter = u.full_name", conn)
    df_a = pd.read_sql_query("SELECT * FROM abwesenheiten", conn)
    df_u = pd.read_sql_query("SELECT * FROM users WHERE role!='admin'", conn)
    conn.close()
    return df_b, df_a, df_u

def get_user_details(fullname):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE full_name=?", (fullname,))
    u = c.fetchone()
    conn.close()
    return u 

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=? AND password=?', (username.lower(), password))
    user = c.fetchone()
    conn.close()
    return user

def buchung_speichern(mitarbeiter, projekt, aktion):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO buchungen (mitarbeiter, projekt, aktion, zeitstempel) VALUES (?, ?, ?, ?)', (mitarbeiter, projekt, aktion, zeit))
    conn.commit()
    conn.close()
    st.toast(f"✅ {aktion} gespeichert!", icon="💾")

def lade_daten(table, user_role, username):
    conn = sqlite3.connect(DB_NAME)
    if user_role == 'admin':
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    else:
        df = pd.read_sql_query(f"SELECT * FROM {table} WHERE mitarbeiter=?", conn, params=(username,))
    conn.close()
    return df

def berechne_kpis(df_buchungen, fullname):
    if df_buchungen.empty: return pd.DataFrame(), 0
    df = df_buchungen.copy()
    df['zeitstempel'] = pd.to_datetime(df['zeitstempel'])
    df['datum'] = df['zeitstempel'].dt.date
    if fullname != 'all':
        df = df[df['mitarbeiter'] == fullname]
    
    statistik = []
    saldo_gesamt = 0
    groupby_cols = ['datum'] if fullname != 'all' else ['datum', 'mitarbeiter']
    
    for idx, gruppe in df.groupby(groupby_cols):
        if fullname == 'all': datum = idx[0]
        else: datum = idx
            
        start = gruppe[gruppe['aktion'] == 'Kommen']['zeitstempel'].min()
        ende = gruppe[gruppe['aktion'] == 'Gehen']['zeitstempel'].max()
        stunden = 0.0
        soll = 8.0
        if pd.notna(start) and pd.notna(ende):
            diff = ende - start
            stunden = diff.total_seconds() / 3600
        saldo = stunden - soll
        saldo_gesamt += saldo
        entry = {"Datum": datum, "Ist": round(stunden, 2), "Soll": soll, "Saldo": round(saldo, 2)}
        if fullname == 'all': entry['Mitarbeiter'] = idx[1]
        statistik.append(entry)
        
    return pd.DataFrame(statistik), round(saldo_gesamt, 2)

def urlaub_beantragen(mitarbeiter, start, ende, typ, kommentar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO abwesenheiten (mitarbeiter, start_datum, end_datum, typ, kommentar, status) VALUES (?, ?, ?, ?, ?, 'Ausstehend')", 
              (mitarbeiter, start, ende, typ, kommentar))
    conn.commit()
    conn.close()
    st.toast("Antrag gesendet!", icon="📨")

def urlaub_entscheiden(id_val, entscheidung, notiz):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    status = "Genehmigt" if entscheidung == "ok" else "Abgelehnt"
    c.execute("UPDATE abwesenheiten SET status=?, admin_note=? WHERE id=?", (status, notiz, id_val))
    conn.commit()
    conn.close()
    st.toast(f"Status gesetzt auf: {status}")

def get_vacation_stats(fullname, total_days):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT start_datum, end_datum FROM abwesenheiten WHERE mitarbeiter=? AND typ='🌴 Urlaub' AND status='Genehmigt'", conn, params=(fullname,))
    conn.close()
    taken = 0
    for index, row in df.iterrows():
        d1 = datetime.strptime(row['start_datum'], "%Y-%m-%d")
        d2 = datetime.strptime(row['end_datum'], "%Y-%m-%d")
        taken += (d2 - d1).days + 1
    remaining = total_days - taken
    return taken, remaining

def count_sick_days(fullname):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT start_datum, end_datum FROM abwesenheiten WHERE mitarbeiter=? AND typ='🤒 Krank'", conn, params=(fullname,))
    conn.close()
    days = 0
    for index, row in df.iterrows():
        d1 = datetime.strptime(row['start_datum'], "%Y-%m-%d")
        d2 = datetime.strptime(row['end_datum'], "%Y-%m-%d")
        days += (d2 - d1).days + 1
    return days

# --- UI SEITEN ---

def render_sidebar():
    """Zeigt das Logo und die Navigation in der Sidebar an"""
    with st.sidebar:
        # LOGO ANZEIGE
        try:
            # Wir nutzen use_container_width für saubere Skalierung
            st.image(LOGO_FILE, use_container_width=True)
        except:
            st.warning("Logo-Datei nicht gefunden. Bitte 'ES_favicon-transparent.png' hochladen.")
        
        st.markdown("---")
        st.markdown("**ERDAL SAKARYA SYSTEMS**")
        st.caption("HR & Time Management v20.0")
        
        # Logout Button jetzt in der Sidebar für besseres Layout
        if st.button("🔒 Ausloggen", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

def login_screen():
    # Beim Login zeigen wir das Logo zentriert über dem Formular
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        try:
            st.image(LOGO_FILE, width=150) # Kleineres Logo für Login
        except:
            pass
        st.markdown("## 🔒 System Login")
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

def admin_view():
    st.title("👨‍💼 HR Admin Cockpit")
    
    tab_overview, tab_requests = st.tabs(["📊 Firmen-Dashboard & Mitarbeiter", "📨 Anträge genehmigen"])
    
    with tab_overview:
        col_list, col_detail = st.columns([1, 3])
        with col_list:
            st.markdown("### Auswahl")
            users_df = get_all_users_full()
            user_list = users_df['full_name'].tolist()
            options = ["🏠 FIRMEN-COCKPIT"] + user_list
            selected_option = st.radio("Ansicht wählen:", options, label_visibility="collapsed")
        
        with col_detail:
            if selected_option == "🏠 FIRMEN-COCKPIT":
                st.markdown("## 🚀 Firmen-Übersicht")
                st.caption("Echtzeit-Daten über die gesamte Belegschaft")
                
                df_buchungen, df_absences, df_users = get_company_stats()
                
                # KPIs
                if not df_buchungen.empty:
                    df_buchungen['zeitstempel'] = pd.to_datetime(df_buchungen['zeitstempel'])
                    stats_all, saldo_all = berechne_kpis(df_buchungen, 'all')
                    total_hours_worked = stats_all['Ist'].sum() if not stats_all.empty else 0
                else:
                    total_hours_worked = 0

                sick_count = 0
                if not df_absences.empty:
                    today_str = date.today().strftime("%Y-%m-%d")
                    sick_df = df_absences[(df_absences['typ'] == '🤒 Krank') & (df_absences['start_datum'] <= today_str) & (df_absences['end_datum'] >= today_str)]
                    sick_count = len(sick_df)

                total_vac_days_available = df_users['vacation_days_total'].sum()
                total_vac_taken = 0
                if not df_absences.empty:
                    vac_df = df_absences[(df_absences['typ'] == '🌴 Urlaub') & (df_absences['status'] == 'Genehmigt')]
                    for _, row in vac_df.iterrows():
                        d1 = datetime.strptime(row['start_datum'], "%Y-%m-%d")
                        d2 = datetime.strptime(row['end_datum'], "%Y-%m-%d")
                        total_vac_taken += (d2 - d1).days + 1
                
                vac_percentage = (total_vac_taken / total_vac_days_available * 100) if total_vac_days_available > 0 else 0
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Gesamtstunden (Ist)", f"{total_hours_worked:.1f} h")
                k2.metric("Mitarbeiter Krank", f"{sick_count}", delta_color="inverse")
                k3.metric("Urlaubsquote", f"{vac_percentage:.1f}%")
                k4.metric("Mitarbeiter", f"{len(df_users)}")
                
                st.divider()
                c_chart1, c_chart2 = st.columns(2)
                with c_chart1:
                    st.markdown("##### 🏢 Stunden pro Abteilung")
                    if not df_buchungen.empty and 'department' in df_buchungen.columns:
                        dept_activity = df_buchungen[df_buchungen['aktion']=='Kommen']['department'].value_counts()
                        st.bar_chart(dept_activity, color="#F63366")
                with c_chart2:
                    st.markdown("##### 📈 Trend")
                    if not df_buchungen.empty:
                        daily_hours = stats_all.groupby('Datum')['Ist'].sum()
                        st.line_chart(daily_hours, color="#FF4B4B")

            else:
                u_details = get_user_details(selected_option)
                with st.container():
                    c_img, c_info = st.columns([1, 4])
                    with c_img: st.markdown("# 👤")
                    with c_info:
                        st.markdown(f"## {u_details[3]}")
                        st.caption(f"Abteilung: **{u_details[4]}** | Position: **{u_details[5]}**")
                st.divider()
                df_b = lade_daten('buchungen', 'admin', 'all')
                stats_df, saldo = berechne_kpis(df_b, selected_option)
                taken, rest = get_vacation_stats(selected_option, u_details[6])
                sick = count_sick_days(selected_option)
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Überstunden", f"{saldo} h")
                k2.metric("Urlaub Genommen", f"{taken}")
                k3.metric("Urlaub Rest", f"{rest}")
                k4.metric("Krank", f"{sick}")
                st.markdown("### 📊 Arbeitszeiten")
                if not stats_df.empty:
                    st.bar_chart(stats_df[['Datum', 'Ist', 'Soll']].set_index('Datum'), color=["#F63366", "#333333"])

    with tab_requests:
        st.markdown("### Offene Anträge")
        conn = sqlite3.connect(DB_NAME)
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
                            urlaub_entscheiden(row['id'], "ok", notiz); st.rerun()
                        if cB.button("❌ Ablehnen", key=f"no_{row['id']}"):
                            urlaub_entscheiden(row['id'], "no", notiz); st.rerun()
                    st.divider()
        else:
            st.success("Keine offenen Anträge.")

def employee_view(user_data):
    fullname = user_data[3]
    vac_total = user_data[6]
    st.markdown(f"## 👋 Hallo, {fullname}")
    
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
            if st.button("🟢 KOMMEN", use_container_width=True): buchung_speichern(fullname, p, "Kommen"); st.rerun()
            if st.button("🔴 GEHEN", use_container_width=True): buchung_speichern(fullname, p, "Gehen"); st.rerun()
            if st.button("☕ PAUSE", use_container_width=True): buchung_speichern(fullname, p, "Pause"); st.rerun()
        with col_chart:
            st.markdown("#### Meine Woche")
            if not stats_df.empty:
                st.bar_chart(stats_df.tail(7)[['Datum', 'Ist', 'Soll']].set_index('Datum'), color=["#F63366", "#333333"])

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
                    urlaub_beantragen(fullname, d1, d2, typ, kom); st.rerun()
        with c_stat:
            st.markdown("#### Status")
            conn = sqlite3.connect(DB_NAME)
            df_my = pd.read_sql_query("SELECT * FROM abwesenheiten WHERE mitarbeiter=? ORDER BY id DESC", conn, params=(fullname,))
            conn.close()
            if not df_my.empty:
                for i, r in df_my.iterrows():
                    color = "#FFA500" if r['status']=='Ausstehend' else ("#00FF00" if r['status']=='Genehmigt' else "#FF0000")
                    st.markdown(f"<div style='padding:10px; border:1px solid #333; margin-bottom:5px;'><strong>{r['typ']}</strong> ({r['start_datum']} - {r['end_datum']})<br>Status: <span style='color:{color}'>{r['status']}</span></div>", unsafe_allow_html=True)
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
        # HIER WIRD DAS LOGO IN DER SIDEBAR GELADEN
        render_sidebar()
        
        user_data = st.session_state['user']
        if user_data[2] == 'admin':
            admin_view()
        else:
            employee_view(user_data)

if __name__ == '__main__':
    main()