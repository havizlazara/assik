import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import io

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Visitor Management TRAC", layout="wide")

# --- FUNGSI ZONA WAKTU WIB ---
def get_waktu_wib():
    return datetime.utcnow() + timedelta(hours=7)

# --- FUNGSI FORMAT JAM (HHMM -> HH:MM) ---
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

# --- FUNGSI DATA & RESET NOMOR ---
def fetch_data():
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])
        df = pd.DataFrame(data)
        df = df[df['Nama'] != ""]
        df = df.dropna(how='all')
        df['Tanggal_Filter'] = pd.to_datetime(df['Tanggal'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    if 'Tanggal_Filter' in df_baru.columns:
        df_baru = df_baru.drop(columns=['Tanggal_Filter'])
    df_baru = df_baru[df_baru['Nama'] != ""].reset_index(drop=True)
    df_baru['No'] = range(1, len(df_baru) + 1)
    cols = ['No'] + [c for c in df_baru.columns if c != 'No']
    df_baru = df_baru[cols].fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

# Load data awal
df = fetch_data()
waktu_wib = get_waktu_wib()
tgl_skrg = waktu_wib.strftime("%d-%m-%Y")

# --- HEADER ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    if os.path.exists("trac.png"):
        st.image("trac.png", width=150)
with col_text:
    st.title("Visitor Management - GRHA TRAC")
    st.subheader(f"🕒 {waktu_wib.strftime('%H:%M')} WIB")

st.markdown("---")

# --- SIDEBAR: PENCARIAN & DOWNLOAD ---
st.sidebar.title("📊 Menu Utama")

# 1. Pencarian Riwayat KTP
st.sidebar.subheader("Cek Riwayat KTP")
search_ktp = st.sidebar.text_input("Cari No KTP:")
if search_ktp:
    history = df[df['No KTP'].astype(str) == search_ktp].copy()
    if not history.empty:
        st.sidebar.success(f"Nama: {history['Nama'].iloc[-1]}")
        st.sidebar.info(f"Total Kunjungan: {len(history)} kali")
        st.sidebar.dataframe(history[['Tanggal', 'Keperluan']].sort_index(ascending=False), hide_index=True)
    else:
        st.sidebar.warning("KTP belum terdaftar.")

st.sidebar.markdown("---")

# 2. Filter Tabel Utama
st.sidebar.subheader("Filter & Ekspor")
view_opt = st.sidebar.selectbox("Filter Tampilan:", ["Hari Ini Saja", "Semua Riwayat"])

# --- PROSES DATA DOWNLOAD ---
# Data yang akan didownload menyesuaikan dengan filter view_opt
df_download = df[df['Tanggal'] == tgl_skrg].copy() if view_opt == "Hari Ini Saja" else df.copy()
df_download = df_download.drop(columns=['Tanggal_Filter'], errors='ignore')

# Tombol Download Excel
if not df_download.empty:
    # Buffer untuk Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_download.to_excel(writer, index=False, sheet_name='Data_Pengunjung')
        
    st.sidebar.download_button(
        label=f"📥 Download Excel ({view_opt})",
        data=buffer.getvalue(),
        file_name=f"Visitor_TRAC_{view_opt.replace(' ', '_')}_{tgl_skrg}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.sidebar.info("Tidak ada data untuk didownload.")

# --- UI UTAMA DENGAN TAB ---
tab_reg, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data"])

# TAB 1: REGISTRASI & DAFTAR
with tab_reg:
    st.subheader(f"📋 Tabel Pengunjung ({view_opt})")
    if df_download.empty:
        st.info("Belum ada data kunjungan.")
    else:
        st.dataframe(df_download, use_container_width=True, hide_index=True)

    st.markdown("---")
    
    col_in, col_out = st.columns(2)
    
    with col_in:
        st.subheader("➕ Check-In")
        with st.form("form_checkin", clear_on_submit=True):
            in_tgl = st.date_input("Tanggal", waktu_wib)
            in_nama = st.text_input("Nama Lengkap")
            in_ktp = st.text_input("No KTP")
            in_perlu = st.text_input("Keperluan")
            in_id = st.text_input("Visitor ID")
            in_jml = st.number_input("Jumlah Tamu", min_value=1, value=1)
            in_jam = st.text_input("Jam Masuk (Contoh: 0800)")
            
            if st.form_submit_button("💾 SIMPAN DATA", type="primary"):
                if in_nama and in_ktp:
                    new_data = {
                        "No": 0, "Tanggal": in_tgl.strftime("%d-%m-%Y"), "Nama": in_nama,
                        "No KTP": in_ktp, "Keperluan": in_perlu, "Jumlah Tamu": int(in_jml),
                        "Visitor Id": in_id, "Jam Masuk": format_jam(in_jam),
                        "Jam Keluar": "-", "Status": "IN"
                    }
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    sync_data(df)
                    st.rerun()
                else:
                    st.error("Nama & KTP wajib diisi!")

    with col_out:
        st.subheader("🚪 Check-Out")
        list_in = df[df['Status'] == 'IN']['Nama'].tolist()
        if list_in:
            with st.form("form_checkout", clear_on_submit=True):
                target = st.selectbox("Pilih Nama", list_in)
                out_jam = st.text_input("Jam Keluar (Contoh: 1700)")
                if st.form_submit_button("🚪 KONFIRMASI KELUAR"):
                    idx = df[df['Nama'] == target].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(out_jam)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    st.rerun()
        else:
            st.info("Tidak ada tamu aktif.")

# TAB 2: EDIT & HAPUS
with tab_manage:
    st.subheader("🛠️ Manajemen Database")
    q = st.text_input("Cari data:")
    if q:
        df_edit = df[df['Nama'].str.contains(q, case=False) | df['No KTP'].astype(str).str.contains(q)]
        for idx, row in df_edit.iterrows():
            with st.expander(f"Edit Baris {row['No']}: {row['Nama']}"):
                with st.form(f"edt_{idx}"):
                    c1, c2 = st.columns(2)
                    en = c1.text_input("Nama", value=row['Nama'])
                    ek = c1.text_input("KTP", value=str(row['No KTP']))
                    eid = c1.text_input("Visitor ID", value=row['Visitor Id'])
                    ep = c2.text_input("Keperluan", value=row['Keperluan'])
                    ejm = c2.text_input("Jam Masuk", value=row['Jam Masuk'])
                    ejk = c2.text_input("Jam Keluar", value=row['Jam Keluar'])
                    est = st.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1)
                    
                    if st.form_submit_button("💾 UPDATE"):
                        df.at[idx, 'Nama'], df.at[idx, 'No KTP'] = en, ek
                        df.at[idx, 'Keperluan'], df.at[idx, 'Visitor Id'] = ep, eid
                        df.at[idx, 'Jam Masuk'], df.at[idx, 'Jam Keluar'] = ejm, ejk
                        df.at[idx, 'Status'] = est
                        sync_data(df)
                        st.rerun()
                
                if st.button(f"🗑️ HAPUS DATA {idx}", key=f"del_{idx}"):
                    df = df.drop(idx)
                    sync_data(df)
                    st.rerun()