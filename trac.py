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

# 2. SISTEM KONEKSI (LOGIKA ADAPTIF)
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # Karena Secrets Anda terdeteksi memiliki kunci ['connections']
    # Maka kita ambil data dari dalam folder connections tersebut
    if "connections" in st.secrets:
        # Mengambil info gcp_service_account yang ada di dalam connections
        creds_info = dict(st.secrets["connections"]["gcp_service_account"])
        
        # Mengambil info gsheets yang ada di dalam connections
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    else:
        # Fallback jika struktur berubah menjadi rata (flat)
        creds_info = dict(st.secrets["gcp_service_account"])
        url = st.secrets["gsheets"]["spreadsheet"]

    # Inisialisasi gspread
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(url).sheet1

except Exception as e:
    st.error(f"❌ Koneksi Gagal: {e}")
    st.info(f"Kunci Secrets yang terbaca: {list(st.secrets.keys())}")
    st.stop()

# --- FUNGSI PENGOLAHAN DATA ---
def fetch_data():
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])
    return pd.DataFrame(data)

def sync_to_sheets(dataframe):
    dataframe = dataframe.fillna("-")
    sheet.clear()
    sheet.update([dataframe.columns.values.tolist()] + dataframe.values.tolist())

# Load data
df = fetch_data()

# 3. UI Header
st.title("Visitor Management - GRHA Trac Condet")
st.write(f"Sistem Online | {hari_ini_wib.strftime('%d %B %Y')}")
st.markdown("---")

# 4. Tab Menu
tab1, tab2 = st.tabs(["📊 Daftar Pengunjung", "⚙️ Kelola Data"])

with tab1:
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    if not df.empty:
        for idx, row in df.iterrows():
            with st.expander(f"Edit: {row['Nama']}"):
                new_status = st.selectbox("Update Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1, key=f"s_{idx}")
                if st.button("Update", key=f"b_{idx}"):
                    df.at[idx, 'Status'] = new_status
                    sync_to_sheets(df)
                    st.rerun()

st.markdown("---")

# 5. Form Input Sederhana
st.subheader("➕ Tambah Tamu Baru")
with st.form("input_tamu", clear_on_submit=True):
    col1, col2 = st.columns(2)
    in_nama = col1.text_input("Nama Tamu")
    in_ktp = col2.text_input("No KTP")
    in_id = col1.text_input("Visitor ID")
    in_jam = col2.text_input("Jam Masuk (Contoh: 0800)")
    
    if st.form_submit_button("Simpan Data"):
        if in_nama and in_ktp and in_id and in_jam:
            new_row = {
                "No": len(df) + 1, "Tanggal": hari_ini_wib.strftime("%d-%b"),
                "Nama": in_nama, "No KTP": in_ktp, "Keperluan": "Kunjungan",
                "Jumlah Tamu": 1, "Visitor Id": in_id,
                "Jam Masuk": format_jam(in_jam), "Jam Keluar": "-", "Status": "IN"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            sync_to_sheets(df)
            st.rerun()