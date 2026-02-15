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
        df = df.dropna(how='all')
        df['Tanggal_Filter'] = pd.to_datetime(df['Tanggal'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    if 'Tanggal_Filter' in df_baru.columns:
        df_baru = df_baru.drop(columns=['Tanggal_Filter'])
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
    st.markdown(f"**📅 Hari Ini:** {waktu_skrg.strftime('%A, %d %B %Y')}")

st.markdown("---")

# --- SIDEBAR (PENCARIAN KTP DENGAN INFO KEPERLUAN) ---
st.sidebar.title("🔍 Fitur Pencarian")

st.sidebar.subheader("Cek Riwayat KTP")
search_ktp = st.sidebar.text_input("Input No KTP Pengunjung:")
if search_ktp:
    # Cari riwayat berdasarkan No KTP
    history = df[df['No KTP'].astype(str) == search_ktp].copy()
    if not history.empty:
        nama_tamu = history['Nama'].iloc[-1]
        st.sidebar.success(f"**Nama:** {nama_tamu}")
        st.sidebar.info(f"📋 Total Kunjungan: **{len(history)} kali**")
        
        # MENAMPILKAN DAFTAR KEPERLUAN
        st.sidebar.write("**Daftar Keperluan Sebelumnya:**")
        # Mengambil riwayat tanggal dan keperluan, diurutkan dari yang terbaru
        history_summary = history[['Tanggal', 'Keperluan']].sort_index(ascending=False)
        st.sidebar.dataframe(history_summary, hide_index=True, use_container_width=True)
    else:
        st.sidebar.warning("Data KTP belum pernah terdaftar.")

st.sidebar.markdown("---")
view_option = st.sidebar.selectbox("Lihat Daftar Utama:", ["Hari Ini Saja", "Semua Riwayat"])

filter_tgl = st.sidebar.date_input("Total Tamu per Tanggal", waktu_skrg)
if not df.empty:
    df_rekap = df[df['Tanggal_Filter'].dt.date == filter_tgl]
    total_tamu_tgl = df_rekap['Jumlah Tamu'].apply(lambda x: int(x) if str(x).isdigit() else 0).sum()
    st.sidebar.metric(f"Total Tamu Terdata", f"{total_tamu_tgl} Orang")

# --- UI UTAMA ---
tab_reg, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data"])

with tab_reg:
    st.subheader(f"📋 List Pengunjung ({view_option})")
    df_display = df[df['Tanggal'] == tgl_str] if view_option == "Hari Ini Saja" else df.copy()

    if df_display.empty:
        st.info("Tidak ada data kunjungan.")
    else:
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
            in_jml = st.number_input("Jumlah Tamu", min_value=1, step=1, value=1)
            in_jam = st.text_input("Jam Masuk (Contoh: 0800)")
            
            btn_simpan = st.form_submit_button("💾 KLIK DI SINI UNTUK SIMPAN", type="primary")
            
            if btn_simpan:
                if in_nama and in_ktp:
                    jam_final = format_jam(in_jam)
                    new_row = {
                        "No": len(df) + 1,
                        "Tanggal": in_tgl.strftime("%d-%m-%Y"),
                        "Nama": in_nama, "No KTP": in_ktp, "Keperluan": in_perlu,
                        "Jumlah Tamu": int(in_jml), "Visitor Id": in_id,
                        "Jam Masuk": jam_final, "Jam Keluar": "-", "Status": "IN"
                    }
                    df_upd = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    sync_data(df_upd)
                    st.success(f"Berhasil menyimpan {in_nama}")
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
                btn_out = st.form_submit_button("🚪 KONFIRMASI KELUAR")
                
                if btn_out:
                    if t_out and j_out:
                        jam_out_final = format_jam(j_out)
                        idx = df[df['Nama'] == t_out].index[-1]
                        df.at[idx, 'Jam Keluar'] = jam_out_final
                        df.at[idx, 'Status'] = 'OUT'
                        sync_data(df)
                        st.rerun()
        else:
            st.info("Tidak ada tamu aktif.")

# --- TAB 2: MANAJEMEN ---
with tab_manage:
    st.subheader("🛠️ Manajemen Database")
    search_edit = st.text_input("Cari Nama/KTP untuk Edit/Hapus:")
    if search_edit:
        df_edit = df[df['Nama'].str.contains(search_edit, case=False) | df['No KTP'].astype(str).str.contains(search_edit)]
        for index, row in df_edit.iterrows():
            with st.expander(f"Edit: {row['Nama']}"):
                with st.form(f"form_edit_{index}"):
                    en = st.text_input("Nama", value=row['Nama'])
                    ek = st.text_input("KTP", value=str(row['No KTP']))
                    ep = st.text_input("Keperluan", value=row['Keperluan'])
                    es = st.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1)
                    if st.form_submit_button("SIMPAN PERUBAHAN"):
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