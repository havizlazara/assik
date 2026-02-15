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

# Fungsi Format Jam Otomatis (HHMM -> HH:MM)
def format_jam(input_jam):
    if not input_jam or input_jam == "-": return "-"
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}:{digits[2:]}"
    elif len(digits) == 3:
        return f"0{digits[0]}:{digits[1:]}"
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
        # Bersihkan baris yang benar-benar kosong
        df = df[df['Nama'] != ""]
        df = df.dropna(how='all')
        df['Tanggal_Filter'] = pd.to_datetime(df['Tanggal'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    # 1. Buang kolom 'Tanggal_Filter' jika ada
    if 'Tanggal_Filter' in df_baru.columns:
        df_baru = df_baru.drop(columns=['Tanggal_Filter'])
    
    # 2. Hapus baris kosong
    df_baru = df_baru[df_baru['Nama'] != ""]
    df_baru = df_baru.dropna(subset=['Nama'])
    
    # 3. RESET TOTAL NOMOR URUT
    # Mengabaikan index lama dan membuat urutan 1, 2, 3... berdasarkan jumlah data yang ada sekarang
    df_baru = df_baru.reset_index(drop=True)
    df_baru['No'] = range(1, len(df_baru) + 1)
    
    # 4. Pastikan kolom 'No' ada di urutan pertama
    cols = ['No'] + [c for c in df_baru.columns if c != 'No']
    df_baru = df_baru[cols]
    
    # 5. Kirim ke Google Sheets
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
    st.markdown(f"**📅 Hari Ini:** {waktu_skrg.strftime('%A, %d %B %Y')}")

st.markdown("---")

# --- SIDEBAR ---
st.sidebar.title("🔍 Fitur Pencarian")
st.sidebar.subheader("Cek Riwayat KTP")
search_ktp = st.sidebar.text_input("Input No KTP Pengunjung:")
if search_ktp:
    history = df[df['No KTP'].astype(str) == search_ktp].copy()
    if not history.empty:
        st.sidebar.success(f"**Nama:** {history['Nama'].iloc[-1]}")
        st.sidebar.info(f"📋 Total Kunjungan: **{len(history)} kali**")
        st.sidebar.dataframe(history[['Tanggal', 'Keperluan']].sort_index(ascending=False), hide_index=True)
    else:
        st.sidebar.warning("KTP belum terdaftar.")

st.sidebar.markdown("---")
view_option = st.sidebar.selectbox("Lihat Daftar Utama:", ["Hari Ini Saja", "Semua Riwayat"])

# --- UI UTAMA ---
tab_reg, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data"])

with tab_reg:
    st.subheader(f"📋 List Pengunjung ({view_option})")
    df_display = df[df['Tanggal'] == tgl_str] if view_option == "Hari Ini Saja" else df.copy()

    if df_display.empty:
        st.info("Tidak ada data kunjungan.")
    else:
        # Menampilkan tabel dengan nomor urut yang sudah diperbaiki
        st.dataframe(
            df_display[["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"]], 
            use_container_width=True, 
            hide_index=True
        )

    st.markdown("---")
    
    col_in, col_out = st.columns(2)
    
    with col_in:
        st.subheader("➕ Check-In")
        with st.form("form_registrasi", clear_on_submit=True):
            in_tgl = st.date_input("Tanggal", waktu_skrg)
            in_nama = st.text_input("Nama Lengkap")
            in_ktp = st.text_input("Nomor KTP")
            in_perlu = st.text_input("Keperluan")
            in_id = st.text_input("Visitor ID")
            in_jml = st.number_input("Jumlah Tamu", min_value=1, value=1)
            in_jam = st.text_input("Jam Masuk (Contoh: 0800)")
            
            btn_simpan = st.form_submit_button("💾 SIMPAN DATA TAMU", type="primary")
            
            if btn_simpan:
                if in_nama and in_ktp:
                    jam_final = format_jam(in_jam)
                    new_row = {
                        "No": 0, # Placeholder, akan di-reset di sync_data
                        "Tanggal": in_tgl.strftime("%d-%m-%Y"),
                        "Nama": in_nama, "No KTP": in_ktp, "Keperluan": in_perlu,
                        "Jumlah Tamu": int(in_jml), "Visitor Id": in_id,
                        "Jam Masuk": jam_final, "Jam Keluar": "-", "Status": "IN"
                    }
                    df_upd = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    sync_data(df_upd)
                    st.rerun()
                else:
                    st.error("Nama dan KTP wajib diisi!")

    with col_out:
        st.subheader("🚪 Check-Out")
        list_aktif = df[df['Status'] == 'IN']['Nama'].tolist()
        if list_aktif:
            with st.form("form_checkout", clear_on_submit=True):
                t_out = st.selectbox("Pilih Nama", list_aktif)
                j_out = st.text_input("Jam Keluar (Contoh: 1700)")
                if st.form_submit_button("🚪 KONFIRMASI KELUAR"):
                    if t_out and j_out:
                        idx = df[df['Nama'] == t_out].index[-1]
                        df.at[idx, 'Jam Keluar'] = format_jam(j_out)
                        df.at[idx, 'Status'] = 'OUT'
                        sync_data(df)
                        st.rerun()
        else:
            st.info("Tidak ada tamu aktif.")

# --- TAB 2: MANAJEMEN ---
with tab_manage:
    st.subheader("🛠️ Manajemen Database")
    search_edit = st.text_input("Cari Nama/KTP:")
    if search_edit:
        df_edit = df[df['Nama'].str.contains(search_edit, case=False) | df['No KTP'].astype(str).str.contains(search_edit)]
        for index, row in df_edit.iterrows():
            with st.expander(f"Edit: {row['Nama']}"):
                with st.form(f"form_edit_{index}"):
                    en = st.text_input("Nama", value=row['Nama'])
                    ek = st.text_input("KTP", value=str(row['No KTP']))
                    if st.form_submit_button("SIMPAN PERUBAHAN"):
                        df.at[index, 'Nama'] = en
                        df.at[index, 'No KTP'] = ek
                        sync_data(df)
                        st.rerun()
                if st.button("🗑️ Hapus Data", key=f"del_{index}"):
                    # Menghapus secara fisik dari dataframe
                    df = df.drop(index)
                    sync_data(df)
                    st.rerun()