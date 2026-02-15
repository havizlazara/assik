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

# Fungsi Format Jam Otomatis (HHMM -> HH.MM)
def format_jam(input_jam):
    if not input_jam or input_jam == "-": return "-"
    # Ambil hanya angka
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:]}"
    elif len(digits) == 3:
        return f"0{digits[0]}.{digits[1:]}"
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
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    df_baru = df_baru.fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

# Load data
df = fetch_data()
waktu_skrg = get_waktu_wib()
tgl_str = waktu_skrg.strftime("%d-%m-%Y")

# --- SIDEBAR: PENCARIAN RIWAYAT KTP ---
st.sidebar.title("🔍 Pencarian Riwayat")
search_ktp = st.sidebar.text_input("Cek Riwayat No KTP:")

if search_ktp:
    history = df[df['No KTP'].astype(str) == search_ktp]
    if not history.empty:
        st.sidebar.success(f"**Nama:** {history['Nama'].iloc[-1]}")
        st.sidebar.info(f"**Total Kunjungan:** {len(history)} kali")
        with st.sidebar.expander("Riwayat Tanggal"):
            st.write(history[['Tanggal', 'Keperluan']].reset_index(drop=True))
    else:
        st.sidebar.warning("KTP belum pernah terdaftar.")

# --- UI UTAMA ---
st.title("🏛️ Visitor Management - GRHA TRAC")
st.markdown(f"**📅 Tanggal Operasional:** {waktu_skrg.strftime('%A, %d %B %Y')}")

# TABEL DAFTAR TAMU (DI ATAS)
st.subheader("📋 Daftar Pengunjung Terdaftar")
# Filter untuk melihat tamu hari ini saja agar tabel tetap rapi
df_display = df[df['Tanggal'] == tgl_str]
if df_display.empty:
    st.info("Belum ada pengunjung yang terdaftar hari ini.")
else:
    st.dataframe(df_display, use_container_width=True, hide_index=True)

st.markdown("---")

# INPUT CHECK-IN & CHECK-OUT (DI BAWAH)
col_in, col_out = st.columns(2)

with col_in:
    st.subheader("➕ Check-In Tamu")
    with st.form("form_checkin", clear_on_submit=True):
        in_tgl = st.date_input("Tanggal", waktu_skrg)
        in_nama = st.text_input("Nama Lengkap")
        in_ktp = st.text_input("Nomor KTP")
        in_perlu = st.text_input("Keperluan")
        in_id = st.text_input("Visitor ID")
        in_jml = st.number_input("Jumlah Tamu", min_value=1, step=1, value=1)
        in_jam = st.text_input("Jam Masuk (Contoh: 0800)")
        
        if st.form_submit_button("Simpan & Masuk", type="primary"):
            if in_nama and in_ktp and in_id:
                new_row = {
                    "No": len(df) + 1,
                    "Tanggal": in_tgl.strftime("%d-%m-%Y"),
                    "Nama": in_nama, "No KTP": in_ktp, "Keperluan": in_perlu,
                    "Jumlah Tamu": int(in_jml), "Visitor Id": in_id,
                    "Jam Masuk": format_jam(in_jam), "Jam Keluar": "-", "Status": "IN"
                }
                df_upd = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                sync_data(df_upd)
                st.rerun()
            else:
                st.error("Lengkapi data wajib (Nama, KTP, ID)!")

with col_out:
    st.subheader("🚪 Check-Out Tamu")
    list_aktif = df[df['Status'] == 'IN']['Nama'].tolist()
    if list_aktif:
        with st.form("form_checkout", clear_on_submit=True):
            t_out = st.selectbox("Pilih Nama Tamu", list_aktif)
            j_out = st.text_input("Jam Keluar (Contoh: 1700)")
            if st.form_submit_button("Konfirmasi Keluar"):
                if t_out and j_out:
                    idx = df[df['Nama'] == t_out].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(j_out)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    st.rerun()
    else:
        st.info("Tidak ada tamu yang berstatus IN.")

# TAB MANAJEMEN (OPSIONAL)
st.markdown("---")
with st.expander("⚙️ Kelola Database (Edit / Hapus)"):
    search_edit = st.text_input("Cari Nama untuk Edit:")
    if search_edit:
        df_edit = df[df['Nama'].str.contains(search_edit, case=False)]
        for index, row in df_edit.iterrows():
            st.write(f"**ID: {row['Visitor Id']} - {row['Nama']}**")
            if st.button(f"Hapus Data {row['Nama']}", key=f"del_{index}"):
                df = df.drop(index).reset_index(drop=True)
                df['No'] = range(1, len(df) + 1)
                sync_data(df)
                st.rerun()