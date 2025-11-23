import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime, date, timedelta, time as dt_time

# --- 1. KONFIGURATION (Muss immer als erstes stehen) ---
st.set_page_config(
    page_title="ERDAL SAKARYA System", 
    page_icon="🔒", 
    layout="wide"
)

# --- 2. MODERNES DESIGN & STRONG WHITE LABELING ---
def load_custom_css():
    st.markdown("""
        <style>
        /* --- STRONG WHITE LABELING (Aggressives Verstecken) --- */
        
        /* 1. Header oben komplett entfernen */
        header[data-testid="stHeader"] {
            display: none !important;
        }
        
        /* 2. Footer (Unten) komplett entfernen */
        footer {
            display: none !important;
            visibility: hidden !important;
        }
        
        /* 3. Bunte Linie oben entfernen */
        [data-testid="stDecoration"] {
            display: none !important;
        }
        
        /* 4. Hamburger Menü & Watermarks */
        #MainMenu {
            display: none !important;
        }
        
        /* 5. Viewer Badge (Unten rechts im Cloud Hosting) */
        /* Hinweis: Dies funktioniert in den meisten Browsern, aber Streamlit kämpft manchmal dagegen an */
        .viewerBadge_container__1QSob {
            display: none !important;
        }

        /* --- APP DESIGN (Dunkel & Modern) --- */
        
        /* Hintergrund */
        .stApp {
            background-color: #0E1117;
        }

        /* Buttons: Farbverlauf & Rundungen */
        .stButton > button {
            background: linear-gradient(90deg, #FF4B4B 0%, #F63366 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 15px 20px;
            font-size: 16px;
            font-weight: bold;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
            width: 100%;
        }
        
        /* Button Hover Effekt */
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(246, 51, 102, 0.4);
            background: linear-gradient(90deg, #F63366 0%, #FF4B4B 100%);
        }

        /* Input Felder */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            border-radius: 10px;
            background-color: #262730;
            color: white;
            border: 1px solid #444;
        }

        /* Tabellen */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #333;
        }

        /* Große Zahlen (Metrics) */
        div[data-testid="stMetric"] {
            background-color: #1E1E1E;
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #F63366;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #1E1E1E;
            border-radius: 5px;
            padding: 5px 15px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #F63366 !important;
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)

# --- 3. DATENBANK & LOGIK ---

def init_db():
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    
    # Tabellen erstellen
    c.execute('''CREATE TABLE IF NOT EXISTS buchungen (id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter TEXT, projekt TEXT, aktion TEXT, zeitstempel DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, full_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS abwesenheiten (id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter TEXT, start_datum DATE, end_datum DATE, typ TEXT, kommentar TEXT)''')
    
    # Standard-User anlegen
    c.execute('SELECT count(*) FROM users')
    if c.fetchone()[0] == 0:
        users = [
            ('admin', 'admin123', 'admin', 'Personalabteilung (HR)'),
            ('max', '1234', 'user', 'Max Mustermann'),
            ('erika', '1234', 'user', 'Erika Musterfrau')
        ]
        c.executemany('INSERT INTO users VALUES (?,?,?,?)', users)

    # Demo-Daten erzeugen (für den Show-Effekt)
    c.execute('SELECT count(*) FROM buchungen')
    if c.fetchone()[0] == 0:
        heute = date.today()
        gestern = heute - timedelta(days=1)
        vorgestern = heute - timedelta(days=2)
        vor_vorgestern = heute - timedelta(days=3)
        
        demo_buchungen = [
            ("Max Mustermann", "Web-Entwicklung", "Kommen", f"{vor_vorgestern} 08:00:00"),
            ("Max Mustermann", "Web-Entwicklung", "Pause", f"{vor_vorgestern} 12:00:00"),
            ("Max Mustermann", "Web-Entwicklung", "Gehen", f"{vor_vorgestern} 16:30:00"),
            ("Max Mustermann", "Video-Produktion", "Kommen", f"{vorgestern} 08:15:00"),
            ("Max Mustermann", "Video-Produktion", "Pause", f"{vorgestern} 12:30:00"),
            ("Max Mustermann", "Video-Produktion", "Gehen", f"{vorgestern} 17:00:00"),
            ("Max Mustermann", "Meeting", "Kommen", f"{gestern} 09:00:00"),
            ("Max Mustermann", "Meeting", "Gehen", f"{gestern} 15:00:00"),
            ("Max Mustermann", "Web-Entwicklung", "Kommen", f"{heute} 07:45:00"),
        ]
        
        final_data = []
        for item in demo_buchungen:
            ts = datetime.strptime(item[3], "%Y-%m-%d %H:%M:%S")
            final_data.append((item[0], item[1], item[2], ts))
        c.executemany('INSERT INTO buchungen (mitarbeiter, projekt, aktion, zeitstempel) VALUES (?, ?, ?, ?)', final_data)

    # Demo-Urlaub erzeugen
    c.execute('SELECT count(*) FROM abwesenheiten')
    if c.fetchone()[0] == 0:
        next_week = date.today() + timedelta(days=7)
        c.execute('INSERT INTO abwesenheiten (mitarbeiter, start_datum, end_datum, typ, kommentar) VALUES (?, ?, ?, ?, ?)', 
                 ("Max Mustermann", next_week, next_week + timedelta(days=5), "🌴 Urlaub", "Sommerurlaub Demo"))

    conn.commit()
    conn.close()

# --- HELFER FUNKTIONEN ---

def create_user(username, password, role, fullname):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users VALUES (?,?,?,?)', (username.lower(), password, role, fullname))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False
    finally:
        conn.close()
    return result

def get_all_users():
    conn = sqlite3.connect('zeiterfassung.db')
    df = pd.read_sql_query("SELECT username, role, full_name FROM users", conn)
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

def buchung_loeschen(buchungs_id):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    c.execute("DELETE FROM buchungen WHERE id=?", (buchungs_id,))
    conn.commit()
    conn.close()

def buchung_nachtragen(mitarbeiter, projekt, aktion, datum, uhrzeit):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    zeit_str = f"{datum} {uhrzeit}"
    zeit_obj = datetime.strptime(zeit_str, "%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO buchungen (mitarbeiter, projekt, aktion, zeitstempel) VALUES (?, ?, ?, ?)', 
              (mitarbeiter, projekt, aktion, zeit_obj))
    conn.commit()
    conn.close()

def lade_buchungen(user_role, username):
    conn = sqlite3.connect('zeiterfassung.db')
    if user_role == 'admin':
        df = pd.read_sql_query("SELECT * FROM buchungen ORDER BY zeitstempel DESC", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM buchungen WHERE mitarbeiter=? ORDER BY zeitstempel DESC", conn, params=(username,))
    conn.close()
    if not df.empty:
        df['zeitstempel'] = pd.to_datetime(df['zeitstempel'])
    return df

def berechne_stunden(df):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    df['datum'] = df['zeitstempel'].dt.date
    statistik = []
    for (ma, datum), gruppe in df.groupby(['mitarbeiter', 'datum']):
        start = gruppe[gruppe['aktion'] == 'Kommen']['zeitstempel'].min()
        ende = gruppe[gruppe['aktion'] == 'Gehen']['zeitstempel'].max()
        stunden = 0.0
        status = "Fehlt"
        if pd.notna(start) and pd.notna(ende):
            diff = ende - start
            stunden = diff.total_seconds() / 3600
            status = "Abgeschlossen"
        elif pd.notna(start):
            status = "Arbeitet noch"
        statistik.append({
            "Mitarbeiter": ma, "Datum": datum,
            "Start": start.strftime("%H:%M") if pd.notna(start) else "-",
            "Ende": ende.strftime("%H:%M") if pd.notna(ende) else "-",
            "Stunden": round(stunden, 2), "Status": status
        })
    return pd.DataFrame(statistik)

def abwesenheit_eintragen(mitarbeiter, start, ende, typ, kommentar):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    c.execute('INSERT INTO abwesenheiten (mitarbeiter, start_datum, end_datum, typ, kommentar) VALUES (?, ?, ?, ?, ?)', 
              (mitarbeiter, start, ende, typ, kommentar))
    conn.commit()
    conn.close()
    st.toast(f"✅ {typ} eingetragen!", icon="🌴")

def lade_abwesenheiten(user_role, username):
    conn = sqlite3.connect('zeiterfassung.db')
    if user_role == 'admin':
        df = pd.read_sql_query("SELECT * FROM abwesenheiten ORDER BY start_datum DESC", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM abwesenheiten WHERE mitarbeiter=? ORDER BY start_datum DESC", conn, params=(username,))
    conn.close()
    return df

def abwesenheit_loeschen(id_val):
    conn = sqlite3.connect('zeiterfassung.db')
    c = conn.cursor()
    c.execute("DELETE FROM abwesenheiten WHERE id=?", (id_val,))
    conn.commit()
    conn.close()

# --- UI SEITEN ---

def login_screen():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("## 🔒 ERDAL SAKARYA Login")
        st.info("Bitte anmelden.")
        with st.form("login_form"):
            username = st.text_input("Benutzername")
            password = st.text_input("Passwort", type="password")
            submit = st.form_submit_button("Jetzt Anmelden")
            if submit:
                user = login_user(username, password)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user[0]
                    st.session_state['role'] = user[2]
                    st.session_state['fullname'] = user[3]
                    st.rerun()
                else:
                    st.error("❌ Falsche Daten.")

def admin_view():
    st.info("🔧 Admin-Bereich: HR Management")
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Arbeitszeiten", "🌴 Urlaubs-Verwaltung", "👤 Mitarbeiter", "🛠️ Korrektur"])
    
    with tab1:
        df = lade_buchungen('admin', 'alle')
        if not df.empty:
            stats = berechne_stunden(df)
            st.dataframe(stats, use_container_width=True)
            csv = stats.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel-Export", csv, "export.csv")
        else:
            st.warning("Keine Daten.")

    with tab2:
        df_ab = lade_abwesenheiten('admin', 'alle')
        col_a, col_b = st.columns([3, 1])
        with col_a:
            if not df_ab.empty:
                st.dataframe(df_ab, use_container_width=True)
            else:
                st.info("Leer.")
        with col_b:
            if not df_ab.empty:
                del_id = st.selectbox("Löschen ID", df_ab['id'].tolist())
                if st.button("Eintrag entfernen"):
                    abwesenheit_loeschen(del_id)
                    st.rerun()

    with tab3:
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("##### ➕ Mitarbeiter")
            with st.form("new_user"):
                new_user = st.text_input("User (klein)", placeholder="max")
                new_pass = st.text_input("Passwort", type="password")
                new_name = st.text_input("Voller Name")
                new_role = st.selectbox("Rolle", ["user", "admin"])
                if st.form_submit_button("Mitarbeiter hinzufügen"):
                    if create_user(new_user, new_pass, new_role, new_name):
                        st.success("Angelegt!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Name vergeben.")
        with c_right:
            st.dataframe(get_all_users(), use_container_width=True, hide_index=True)

    with tab4:
        c_del, c_add = st.columns(2)
        with c_del:
            st.markdown("##### 🗑️ Löschen")
            df_raw = lade_buchungen('admin', 'alle')
            if not df_raw.empty:
                st.dataframe(df_raw, use_container_width=True, height=200)
                buchung_id = st.selectbox("ID wählen", df_raw['id'].tolist())
                if st.button("Endgültig löschen"):
                    buchung_loeschen(buchung_id)
                    st.rerun()
        with c_add:
            st.markdown("##### ✏️ Nachtrag")
            with st.form("add_entry"):
                users = get_all_users()['full_name'].tolist()
                u = st.selectbox("Wer?", users)
                p = st.selectbox("Projekt", ["Web-Entwicklung", "Video-Produktion", "Sonstiges"])
                a = st.selectbox("Was?", ["Kommen", "Gehen", "Pause"])
                d = st.date_input("Datum")
                t = st.time_input("Uhrzeit")
                if st.form_submit_button("Eintrag speichern"):
                    buchung_nachtragen(u, p, a, d.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S"))
                    st.rerun()

def employee_view():
    tab_stempel, tab_urlaub = st.tabs(["⏱️ Stempuhr", "🌴 Urlaub"])
    with tab_stempel:
        st.markdown("### Stempeln")
        projekt = st.selectbox("Projekt", ["Web-Entwicklung", "Video-Produktion", "Meeting", "Sonstiges"])
        col_btns = st.columns(3)
        with col_btns[0]:
            if st.button("🟢 KOMMEN", use_container_width=True):
                buchung_speichern(st.session_state['fullname'], projekt, "Kommen")
                time.sleep(0.5)
                st.rerun()
        with col_btns[1]:
            if st.button("☕ PAUSE", use_container_width=True):
                buchung_speichern(st.session_state['fullname'], projekt, "Pause")
                time.sleep(0.5)
                st.rerun()
        with col_btns[2]:
            if st.button("🔴 GEHEN", use_container_width=True):
                buchung_speichern(st.session_state['fullname'], projekt, "Gehen")
                time.sleep(0.5)
                st.rerun()
        
        st.markdown("---")
        st.markdown("### Geschichte")
        df = lade_buchungen('user', st.session_state['fullname'])
        stats = berechne_stunden(df)
        if not stats.empty:
            st.dataframe(stats.sort_values("Datum", ascending=False), use_container_width=True, hide_index=True)
            heute_df = stats[stats['Datum'] == date.today()]
            if not heute_df.empty:
                st.info(f"Status heute: {heute_df.iloc[0]['Status']}")
        else:
            st.info("Keine Daten.")

    with tab_urlaub:
        st.markdown("### Abwesenheit")
        col_input, col_view = st.columns(2)
        with col_input:
            with st.form("urlaub_form"):
                typ = st.selectbox("Grund", ["🌴 Urlaub", "🤒 Krank", "🏫 Schulung"])
                d_range = st.date_input("Zeitraum", value=(date.today(), date.today()))
                kommentar = st.text_area("Notiz")
                if st.form_submit_button("Antrag absenden"):
                    if isinstance(d_range, tuple):
                        start_d = d_range[0]
                        end_d = d_range[1] if len(d_range) > 1 else start_d
                        abwesenheit_eintragen(st.session_state['fullname'], start_d, end_d, typ, kommentar)
                        st.rerun()
        with col_view:
            st.markdown("### Geplant")
            my_abs = lade_abwesenheiten('user', st.session_state['fullname'])
            if not my_abs.empty:
                st.dataframe(my_abs[['start_datum', 'end_datum', 'typ', 'kommentar']], use_container_width=True, hide_index=True)

def dashboard():
    c1, c2 = st.columns([5, 1])
    with c1:
        st.title(f"👋 Hallo, {st.session_state['fullname']}")
        st.markdown("**Audiovisuelle Werbung ERDAL SAKARYA**")
    with c2:
        if st.button("👋 Ausloggen", type="primary"):
            st.session_state['logged_in'] = False
            st.rerun()
    st.divider()
    if st.session_state['role'] == 'admin':
        admin_view()
    else:
        employee_view()

# --- MAIN ---
def main():
    load_custom_css()
    init_db()
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if not st.session_state['logged_in']:
        login_screen()
    else:
        dashboard()

if __name__ == '__main__':
    main()