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
        # Bantuan untuk filter tanggal
        df['Tanggal_dt'] = pd.to_datetime(df['Tanggal'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    if 'Tanggal_dt' in df_baru.columns:
        df_baru = df_baru.drop(columns=['Tanggal_dt'])
    df_baru = df_baru.fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

# Load data
df = fetch_data()
waktu_skrg = get_waktu_wib()

# --- SIDEBAR: PENCARIAN RIWAYAT KTP ---
st.sidebar.title("🔍 Cek Riwayat Tamu")
search_ktp_sidebar = st.sidebar.text_input("Masukkan No KTP:")

if search_ktp_sidebar:
    # Filter data berdasarkan KTP
    history = df[df['No KTP'].astype(str) == search_ktp_sidebar]
    if not history.empty:
        nama_tamu = history['Nama'].iloc[-1]
        kali_datang = len(history)
        st.sidebar.success(f"**Nama:** {nama_tamu}")
        st.sidebar.info(f"**Total Kunjungan:** {kali_datang} kali")
        with st.sidebar.expander("Lihat Detail Tanggal"):
            st.write(history[['Tanggal', 'Keperluan']].reset_index(drop=True))
    else:
        st.sidebar.warning("Data KTP tidak ditemukan.")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# --- UI UTAMA ---
st.title("🏛️ Visitor Management - GRHA TRAC")

tab_utama, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data (Edit/Hapus)"])

# --- TAB 1: REGISTRASI & DAFTAR (DISATUKAN) ---
with tab_utama:
    col_input, col_table = st.columns([1, 2])
    
    with col_input:
        st.subheader("➕ Check-In Baru")
        with st.form("form_checkin", clear_on_submit=True):
            in_tgl = st.date_input("Tanggal Kunjungan", waktu_skrg)
            in_nama = st.text_input("Nama Lengkap")
            in_ktp = st.text_input("Nomor KTP")
            in_perlu = st.text_input("Keperluan")
            in_id = st.text_input("Visitor ID")
            in_jml = st.number_input("Jumlah Tamu", min_value=1, step=1, value=1)
            in_jam = st.text_input("Jam Masuk (HHMM)")
            
            if st.form_submit_button("Simpan & Check-In", type="primary"):
                if in_nama and in_ktp and in_id:
                    new_row = {
                        "No": len(df) + 1,
                        "Tanggal": in_tgl.strftime("%d-%m-%Y"),
                        "Nama": in_nama,
                        "No KTP": in_ktp,
                        "Keperluan": in_perlu,
                        "Jumlah Tamu": int(in_jml),
                        "Visitor Id": in_id,
                        "Jam Masuk": format_jam(in_jam),
                        "Jam Keluar": "-",
                        "Status": "IN"
                    }
                    df_upd = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    sync_data(df_upd)
                    st.success("✅ Berhasil disimpan!")
                    st.rerun()
                else:
                    st.error("Lengkapi Nama, KTP, dan ID!")

    with col_table:
        st.subheader("📋 Daftar Tamu Hari Ini")
        # Menampilkan data hari ini secara default
        df_today = df[df['Tanggal'] == waktu_skrg.strftime("%d-%m-%Y")]
        st.dataframe(df_today[["No", "Nama", "Keperluan", "Jam Masuk", "Status"]], use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("🚪 Cepat Check-Out")
        list_in = df[df['Status'] == 'IN']['Nama'].tolist()
        if list_in:
            with st.form("form_out_quick"):
                t_out = st.selectbox("Pilih Tamu Keluar", list_in)
                j_out = st.text_input("Jam Keluar (HHMM)")
                if st.form_submit_button("Konfirmasi Out"):
                    idx = df[df['Nama'] == t_out].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(j_out)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    st.rerun()
        else:
            st.info("Tidak ada tamu aktif.")

# --- TAB 2: MANAJEMEN DATA (EDIT/HAPUS) ---
with tab_manage:
    st.subheader("🛠️ Pengaturan Data Database")
    search_edit = st.text_input("Cari data yang ingin diubah (Nama/KTP):")
    df_edit = df.copy()
    
    if search_edit:
        df_edit = df[df['Nama'].str.contains(search_edit, case=False) | df['No KTP'].astype(str).str.contains(search_edit)]

    if not df_edit.empty:
        for index, row in df_edit.tail(10).iterrows(): # Tampilkan 10 data terbaru untuk performa
            with st.expander(f"Data: {row['Nama']} | Tanggal: {row['Tanggal']}"):
                col_e1, col_e2 = st.columns(2)
                new_n = col_e1.text_input("Nama", value=row['Nama'], key=f"n_{index}")
                new_k = col_e1.text_input("Keperluan", value=row['Keperluan'], key=f"k_{index}")
                new_s = col_e2.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1, key=f"s_{index}")
                new_j = col_e2.text_input("Jam Keluar", value=row['Jam Keluar'], key=f"j_{index}")
                
                b_edit, b_del = st.columns(2)
                if b_edit.button("Simpan Perubahan", key=f"be_{index}"):
                    df.at[index, 'Nama'] = new_n
                    df.at[index, 'Keperluan'] = new_k
                    df.at[index, 'Status'] = new_s
                    df.at[index, 'Jam Keluar'] = format_jam(new_j)
                    sync_data(df)
                    st.success("Data diupdate!")
                    st.rerun()
                
                if b_del.button("❌ Hapus Baris Ini", key=f"bd_{index}"):
                    df = df.drop(index).reset_index(drop=True)
                    df['No'] = range(1, len(df) + 1)
                    sync_data(df)
                    st.warning("Data dihapus!")
                    st.rerun()
    else:
        st.write("Data tidak ditemukan.")