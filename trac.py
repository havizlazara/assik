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
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])
        df = pd.DataFrame(data)
        # Pastikan kolom Tanggal dalam format datetime untuk pencarian
        df['Tanggal_dt'] = pd.to_datetime(df['Tanggal'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    # Buang kolom bantuan sebelum simpan
    if 'Tanggal_dt' in df_baru.columns:
        df_baru = df_baru.drop(columns=['Tanggal_dt'])
    df_baru = df_baru.fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

# Load data awal
df = fetch_data()
waktu_skrg = get_waktu_wib()
tgl_hari_ini = waktu_skrg.strftime("%d-%m-%Y")

# --- SIDEBAR: SUMMARY & PENCARIAN ---
st.sidebar.title("📊 Dashboard Summary")

# 1. Pencarian Berdasarkan Tanggal
st.sidebar.subheader("🔍 Cari Tamu per Tanggal")
with st.sidebar.expander("Filter Tanggal", expanded=True):
    start_date = st.date_input("Dari Tanggal", waktu_skrg)
    end_date = st.date_input("Sampai Tanggal", waktu_skrg)
    
    if st.button("Tampilkan Jumlah"):
        mask = (df['Tanggal_dt'].dt.date >= start_date) & (df['Tanggal_dt'].dt.date <= end_date)
        hasil_filter = df.loc[mask]
        total_tamu = hasil_filter['Jumlah Tamu'].apply(lambda x: int(x) if str(x).isdigit() else 0).sum()
        st.sidebar.success(f"Total Tamu: {total_tamu}")
        st.sidebar.info(f"Jumlah Transaksi: {len(hasil_filter)}")

st.sidebar.markdown("---")

# 2. Ringkasan Pengunjung Sering Datang (KTP)
st.sidebar.subheader("⭐ Pengunjung Teraktif")
if not df.empty:
    freq = df['No KTP'].value_counts().reset_index()
    freq.columns = ['No KTP', 'Kali']
    # Ambil nama terakhir untuk KTP tersebut
    nama_map = df.drop_duplicates('No KTP', keep='last')[['No KTP', 'Nama']]
    freq = freq.merge(nama_map, on='No KTP')
    loyal = freq[freq['Kali'] > 1].head(5)
    
    if not loyal.empty:
        for i, row in loyal.iterrows():
            st.sidebar.write(f"**{row['Nama']}** ({row['No KTP']})")
            st.sidebar.caption(f"Sudah berkunjung {row['Kali']} kali")
    else:
        st.sidebar.write("Belum ada tamu berulang.")

st.sidebar.markdown("---")
if st.sidebar.button("Refresh Data"):
    st.rerun()

# --- UI UTAMA ---
st.title("🏛️ Visitor Management - GRHA TRAC")

# Statistik Baris Atas
c1, c2, c3 = st.columns(3)
c1.metric("Tamu di Dalam (IN)", len(df[df['Status'] == 'IN']))
c2.metric("Tamu Keluar (OUT)", len(df[df['Status'] == 'OUT']))
c3.metric("Total Riwayat", len(df))

st.markdown("---")

tab1, tab2 = st.tabs(["📋 Daftar Pengunjung", "➕ Registrasi Tamu Baru"])

with tab1:
    st.subheader("Data Pengunjung Terdaftar")
    search_main = st.text_input("🔍 Cari Nama/KTP di Tabel:")
    df_disp = df.copy()
    if search_main:
        df_disp = df[df['Nama'].str.contains(search_main, case=False) | df['No KTP'].astype(str).str.contains(search_main)]
    
    # Tampilkan Tabel (Tanpa kolom bantuan datetime)
    cols_to_show = ["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"]
    st.dataframe(df_disp[cols_to_show], use_container_width=True, hide_index=True)
    
    # Check-Out
    list_in = df[df['Status'] == 'IN']['Nama'].tolist()
    if list_in:
        with st.expander("🚪 Proses Check-Out"):
            with st.form("form_out"):
                t_out = st.selectbox("Pilih Tamu", list_in)
                j_out = st.text_input("Jam Keluar (HHMM)")
                if st.form_submit_button("Konfirmasi"):
                    idx = df[df['Nama'] == t_out].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(j_out)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    st.rerun()

with tab2:
    st.subheader("Form Registrasi")
    with st.form("form_in", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            i_tgl = st.text_input("Tanggal", value=tgl_hari_ini)
            i_nama = st.text_input("Nama Lengkap")
            i_ktp = st.text_input("Nomor KTP")
            i_perlu = st.text_input("Keperluan")
        with col_b:
            i_id = st.text_input("Visitor ID")
            i_jml = st.number_input("Jumlah Tamu", min_value=1, step=1, value=1)
            i_jam = st.text_input("Jam Masuk (HHMM)")
            i_stat = st.selectbox("Status", ["IN", "OUT"])

        if st.form_submit_button("Simpan & Masuk", type="primary"):
            if i_nama and i_ktp and i_id:
                new_row = {
                    "No": len(df) + 1, "Tanggal": i_tgl, "Nama": i_nama,
                    "No KTP": i_ktp, "Keperluan": i_perlu, "Jumlah Tamu": int(i_jml),
                    "Visitor Id": i_id, "Jam Masuk": format_jam(i_jam),
                    "Jam Keluar": "-", "Status": i_stat
                }
                df_upd = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                sync_data(df_upd)
                st.success("Data disimpan!")
                st.rerun()