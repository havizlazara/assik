import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Visitor Management TRAC", layout="wide")

# Fungsi Waktu WIB
def get_waktu_wib():
    return datetime.utcnow() + timedelta(hours=7)

# Fungsi Format Jam (HHMM -> HH.MM)
def format_jam(input_jam):
    if not input_jam or input_jam == "-": return "-"
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:]}"
    return input_jam

# --- KONEKSI GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        creds_info["private_key"] = creds_info["private_key"].strip().replace("\\n", "\n")
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["gsheets"]["spreadsheet"]
        return client.open_by_url(url).sheet1
    except Exception as e:
        st.error(f"❌ Koneksi Gagal: {e}")
        st.stop()

sheet = init_connection()

# --- FUNGSI DATA ---
def fetch_data():
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])
    return pd.DataFrame(data)

def sync_data(df_baru):
    df_baru = df_baru.fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

# Load data awal
df = fetch_data()
waktu_skrg = get_waktu_wib()
tgl_hari_ini = waktu_skrg.strftime("%d-%m-%Y")

# --- UI HEADER ---
st.title("🏛️ Visitor Management - GRHA TRAC")
st.markdown(f"**Hari Ini:** {waktu_skrg.strftime('%A, %d %B %Y')}")

# --- SECTION 1: SUMMARY DASHBOARD ---
st.subheader("📊 Summary Pengunjung")
col1, col2, col3, col4 = st.columns(4)

# Filter data hari ini saja untuk statistik harian
df_hari_ini = df[df['Tanggal'] == tgl_hari_ini]

col1.metric("Tamu Aktif (IN)", len(df[df['Status'] == 'IN']))
col2.metric("Tamu Keluar (OUT)", len(df[df['Status'] == 'OUT']))
col3.metric("Tamu Baru Hari Ini", len(df_hari_ini))
col4.metric("Total Seluruh Riwayat", len(df))

# Summary Pengunjung Sering Datang (Loyalty)
if not df.empty:
    st.markdown("---")
    st.subheader("⭐ Pengunjung Sering Datang (Frequent Visitors)")
    # Hitung frekuensi berdasarkan No KTP
    loyalty_df = df['No KTP'].value_counts().reset_index()
    loyalty_df.columns = ['No KTP', 'Frekuensi Datang']
    
    # Ambil Nama terakhir untuk No KTP tersebut
    nama_map = df.drop_duplicates('No KTP', keep='last')[['No KTP', 'Nama']]
    loyalty_df = loyalty_df.merge(nama_map, on='No KTP')
    
    # Tampilkan yang datang > 1 kali
    frequent = loyalty_df[loyalty_df['Frekuensi Datang'] > 1].sort_values('Frekuensi Datang', ascending=False)
    if not frequent.empty:
        st.table(frequent[['Nama', 'No KTP', 'Frekuensi Datang']].head(5))
    else:
        st.info("Belum ada pengunjung yang tercatat datang lebih dari satu kali.")

st.markdown("---")

# --- SECTION 2: MENU TAB ---
tab1, tab2 = st.tabs(["📋 Daftar Pengunjung", "➕ Registrasi Tamu Baru"])

with tab1:
    st.subheader("Detail Data")
    # Filter pencarian di sidebar
    search = st.text_input("Cari Nama atau No KTP:")
    df_filtered = df.copy()
    if search:
        df_filtered = df[df['Nama'].str.contains(search, case=False) | df['No KTP'].astype(str).str.contains(search)]
    
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)
    
    # Fitur Check-Out
    list_aktif = df[df['Status'] == 'IN']['Nama'].tolist()
    if list_aktif:
        with st.expander("🚪 Proses Check-Out Tamu"):
            with st.form("form_checkout"):
                tamu_pilih = st.selectbox("Pilih Tamu", list_aktif)
                jam_out = st.text_input("Jam Keluar (HHMM, contoh: 1630)")
                if st.form_submit_button("Konfirmasi Keluar"):
                    idx = df[df['Nama'] == tamu_pilih].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(jam_out)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    st.rerun()

with tab2:
    st.subheader("Form Input Tamu")
    with st.form("form_checkin", clear_on_submit=True):
        c_a, c_b = st.columns(2)
        
        with c_a:
            in_tgl = st.text_input("Tanggal", value=tgl_hari_ini)
            in_nama = st.text_input("Nama Lengkap")
            in_ktp = st.text_input("Nomor KTP")
            in_perlu = st.text_input("Keperluan (Contoh: Meeting, Kurir, Vendor)")
            
        with c_b:
            in_id = st.text_input("Visitor ID / No. Kartu")
            in_jumlah = st.number_input("Jumlah Tamu", min_value=1, step=1)
            in_jam = st.text_input("Jam Masuk (HHMM, contoh: 0900)")
            in_status = st.selectbox("Status Awal", ["IN", "OUT"])

        submit = st.form_submit_button("Simpan Data Pengunjung", type="primary")
        
        if submit:
            if in_nama and in_ktp and in_id:
                new_entry = {
                    "No": len(df) + 1,
                    "Tanggal": in_tgl,
                    "Nama": in_nama,
                    "No KTP": in_ktp,
                    "Keperluan": in_perlu,
                    "Jumlah Tamu": int(in_jumlah),
                    "Visitor Id": in_id,
                    "Jam Masuk": format_jam(in_jam),
                    "Jam Keluar": "-",
                    "Status": in_status
                }
                
                df_updated = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                sync_data(df_updated)
                st.success(f"Berhasil mencatat kunjungan {in_nama}!")
                st.rerun()
            else:
                st.error("Mohon isi minimal Nama, KTP, dan Visitor ID.")