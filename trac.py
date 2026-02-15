import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os

# --- FUNGSI HELPER ---
def format_jam(input_jam):
    if not input_jam or input_jam == "-": return "-"
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:]}"
    return input_jam

# 1. Konfigurasi Halaman & Waktu
st.set_page_config(page_title="Visitor Management TRAC", layout="wide")
hari_ini_wib = datetime.utcnow() + timedelta(hours=7)

# 2. SISTEM KONEKSI GOOGLE SHEETS
@st.cache_resource
def init_connection():
    # Proteksi: Jika dijalankan di GitHub Codespace tanpa file secrets lokal
    if len(st.secrets) == 0:
        st.warning("⚠️ Aplikasi berjalan di lingkungan lokal (Codespaces).")
        st.info("Untuk melihat hasil database, silakan buka link resmi: https://visitor.streamlit.app/")
        st.stop()

    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        # Mengambil info dari Secrets (Streamlit Cloud Dashboard)
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            url = st.secrets["gsheets"]["spreadsheet"]
        elif "connections" in st.secrets:
            creds_info = dict(st.secrets["connections"]["gcp_service_account"])
            url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        else:
            st.error("Kunci akses tidak ditemukan di Dashboard Secrets.")
            st.stop()

        # Pembersihan Private Key dari karakter ilegal
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_url(url).sheet1
    except Exception as e:
        st.error(f"❌ Gagal Koneksi: {e}")
        st.stop()

# Menjalankan Koneksi
sheet = init_connection()

# --- FUNGSI PENGOLAHAN DATA ---
def fetch_data():
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_to_sheets(dataframe):
    # Membersihkan nilai kosong agar API Google tidak error
    dataframe = dataframe.fillna("-")
    sheet.clear()
    sheet.update([dataframe.columns.values.tolist()] + dataframe.values.tolist())

# Load data awal
df = fetch_data()

# 3. UI Header
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("trac.png"):
        st.image("trac.png", width=180)
    else:
        st.markdown("### [TRAC]")

with col_title:
    st.title("Visitor Management GRHA Trac Condet")
    st.success(f"🌐 **Sistem Online | Database: Terkoneksi | {hari_ini_wib.strftime('%d %B %Y')}**")

st.markdown("---")

# 4. Statistik & Filter
st.sidebar.header("🔍 Pencarian")
search_ktp = st.sidebar.text_input("Cari No KTP Tamu:")
df_display = df.copy()
if search_ktp:
    df_display = df_display[df_display['No KTP'].astype(str).str.contains(search_ktp)]

c1, c2, c3 = st.columns(3)
c1.metric("Tamu di Dalam (IN)", len(df[df['Status'] == 'IN']))
c2.metric("Tamu Keluar (OUT)", len(df[df['Status'] == 'OUT']))
c3.metric("Total Riwayat", len(df))

# 5. Tab Menu
tab_data, tab_edit = st.tabs(["📊 Daftar Pengunjung", "⚙️ Kelola / Edit Data"])

with tab_data:
    st.dataframe(df_display, use_container_width=True, hide_index=True)

with tab_edit:
    if not df.empty:
        for index, row in df.iterrows():
            with st.expander(f"Edit: {row['Nama']} (ID: {row['Visitor Id']})"):
                en = st.text_input("Nama", value=row['Nama'], key=f"en_{index}")
                es = st.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1, key=f"es_{index}")
                
                b1, b2 = st.columns(2)
                if b1.button("Simpan", key=f"sv_{index}"):
                    df.at[index, 'Nama'] = en
                    df.at[index, 'Status'] = es
                    sync_to_sheets(df)
                    st.rerun()
                if b2.button("Hapus", key=f"dl_{index}"):
                    df = df.drop(index).reset_index(drop=True)
                    df['No'] = range(1, len(df) + 1)
                    sync_to_sheets(df)
                    st.rerun()

st.markdown("---")

# 6. Form Input (Check-In & Out)
if "tick" not in st.session_state: st.session_state.tick = 0
t = st.session_state.tick

col_in, col_out = st.columns(2)

with col_in:
    st.subheader("➕ Check In")
    with st.form("form_in", clear_on_submit=True):
        f_nama = st.text_input("Nama Lengkap")
        f_ktp = st.text_input("Nomor KTP")
        f_vid = st.text_input("Visitor ID")
        f_jam = st.text_input("Jam Masuk (Contoh: 0800)")
        if st.form_submit_button("Simpan Masuk", type="primary"):
            if f_nama and f_ktp and f_vid:
                new_row = {
                    "No": len(df) + 1, "Tanggal": hari_ini_wib.strftime("%d-%b"),
                    "Nama": f_nama, "No KTP": f_ktp, "Keperluan": "Kunjungan",
                    "Jumlah Tamu": 1, "Visitor Id": f_vid,
                    "Jam Masuk": format_jam(f_jam), "Jam Keluar": "-", "Status": "IN"
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                sync_to_sheets(df)
                st.rerun()

with col_out:
    st.subheader("🚪 Check Out")
    list_in = df[df['Status'] == 'IN']['Nama'].tolist()
    if list_in:
        with st.form("form_out", clear_on_submit=True):
            f_pilih = st.selectbox("Pilih Tamu", ["-- Pilih --"] + list_in)
            f_jam_o = st.text_input("Jam Keluar (Contoh: 1700)")
            if st.form_submit_button("Konfirmasi Keluar"):
                if f_pilih != "-- Pilih --" and f_jam_o:
                    idx = df[df['Nama'] == f_pilih].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(f_jam_o)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_to_sheets(df)
                    st.rerun()