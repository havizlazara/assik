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
        df = pd.DataFrame(data)
        df['Tanggal_Filter'] = pd.to_datetime(df['Tanggal'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    if 'Tanggal_Filter' in df_baru.columns:
        df_baru = df_baru.drop(columns=['Tanggal_Filter'])
    # Mengurutkan ulang kolom "No" secara otomatis
    df_baru['No'] = range(1, len(df_baru) + 1)
    df_baru = df_baru.fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

# Load data
df = fetch_data()
waktu_skrg = get_waktu_wib()
tgl_str = waktu_skrg.strftime("%d-%m-%Y")

# --- HEADER ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    if os.path.exists("trac.png"):
        st.image("trac.png", width=150)

with col_text:
    st.title("Visitor Management - GRHA TRAC")
    st.markdown(f"**📅 Tanggal:** {waktu_skrg.strftime('%A, %d %B %Y')}")

st.markdown("---")

# --- SIDEBAR ---
st.sidebar.title("📊 Rekap Data")
view_option = st.sidebar.radio("Tampilkan Data:", ["Hari Ini Saja", "Semua Riwayat"])

filter_tgl = st.sidebar.date_input("Cek Total Tamu per Tanggal", waktu_skrg)
if not df.empty:
    df_rekap = df[df['Tanggal_Filter'].dt.date == filter_tgl]
    total_tamu_tgl = df_rekap['Jumlah Tamu'].apply(lambda x: int(x) if str(x).isdigit() else 0).sum()
    st.sidebar.metric(f"Total Tamu ({filter_tgl.strftime('%d/%m')})", f"{total_tamu_tgl} Orang")

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Cek Riwayat KTP")
search_ktp = st.sidebar.text_input("Input No KTP:")
if search_ktp:
    history = df[df['No KTP'].astype(str) == search_ktp]
    if not history.empty:
        st.sidebar.success(f"**Nama:** {history['Nama'].iloc[-1]}")
        st.sidebar.write(f"Kunjungan: {len(history)} kali")

# --- UI UTAMA DENGAN TAB ---
tab_reg, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data (Edit/Hapus)"])

# --- TAB 1: DAFTAR & INPUT ---
with tab_reg:
    st.subheader("📋 Daftar Pengunjung")
    
    # Logika Filter Tampilan
    if view_option == "Hari Ini Saja":
        df_display = df[df['Tanggal'] == tgl_str]
    else:
        df_display = df.copy()

    if df_display.empty:
        st.info("Tidak ada data untuk ditampilkan.")
    else:
        # Menggunakan height=400 agar tabel memiliki scrollbar internal jika data banyak
        st.dataframe(
            df_display[["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"]], 
            use_container_width=True, 
            hide_index=True,
            height=400 
        )

    st.markdown("---")
    
    col_in, col_out = st.columns(2)
    with col_in:
        st.subheader("➕ Check-In")
        with st.form("form_checkin", clear_on_submit=True):
            in_tgl = st.date_input("Tanggal", waktu_skrg)
            in_nama = st.text_input("Nama Lengkap")
            in_ktp = st.text_input("Nomor KTP")
            in_perlu = st.text_input("Keperluan")
            in_id = st.text_input("Visitor ID")
            in_jml = st.number_input("Jumlah Tamu", min_value=1, step=1, value=1)
            in_jam = st.text_input("Jam Masuk (HHMM)")
            
            if st.form_submit_button("Simpan", type="primary"):
                if in_nama and in_ktp:
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

    with col_out:
        st.subheader("🚪 Check-Out")
        list_aktif = df[df['Status'] == 'IN']['Nama'].tolist()
        if list_aktif:
            with st.form("form_checkout", clear_on_submit=True):
                t_out = st.selectbox("Pilih Nama", list_aktif)
                j_out = st.text_input("Jam Keluar (HHMM)")
                if st.form_submit_button("Konfirmasi Out"):
                    idx = df[df['Nama'] == t_out].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(j_out)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    st.rerun()
        else:
            st.info("Tidak ada tamu aktif.")

# --- TAB 2: EDIT & HAPUS ---
with tab_manage:
    st.subheader("🛠️ Manajemen Database")
    search_edit = st.text_input("Cari Nama/KTP untuk Edit atau Hapus:")
    
    if search_edit:
        df_edit = df[df['Nama'].str.contains(search_edit, case=False) | df['No KTP'].astype(str).str.contains(search_edit)]
        if not df_edit.empty:
            for index, row in df_edit.iterrows():
                with st.expander(f"Edit: {row['Nama']} ({row['Tanggal']})"):
                    c1, c2 = st.columns(2)
                    en = c1.text_input("Nama", value=row['Nama'], key=f"nm_{index}")
                    ek = c1.text_input("KTP", value=row['No KTP'], key=f"ktp_{index}")
                    ep = c2.text_input("Keperluan", value=row['Keperluan'], key=f"prl_{index}")
                    es = c2.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1, key=f"st_{index}")
                    
                    if st.button("💾 Simpan Perubahan", key=f"save_{index}"):
                        df.at[index, 'Nama'] = en
                        df.at[index, 'No KTP'] = ek
                        df.at[index, 'Keperluan'] = ep
                        df.at[index, 'Status'] = es
                        sync_data(df)
                        st.rerun()
                    
                    if st.button("🗑️ Hapus Data", key=f"del_{index}"):
                        df = df.drop(index).reset_index(drop=True)
                        sync_data(df)
                        st.rerun()