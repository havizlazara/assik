import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import io

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Visitor Management TRAC", layout="wide")

# --- 2. FUNGSI ZONA WAKTU WIB ---
def get_waktu_wib():
    return datetime.utcnow() + timedelta(hours=7)

waktu_wib = get_waktu_wib()
tgl_skrg = waktu_wib.strftime("%d-%m-%Y")

# --- 3. FUNGSI FORMAT JAM (HHMM -> HH:MM) ---
def format_jam(input_jam):
    if not input_jam or input_jam == "-": return "-"
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}:{digits[2:]}"
    elif len(digits) == 3:
        return f"0{digits[0]}:{digits[1:]}"
    return input_jam

# --- 4. KONEKSI GOOGLE SHEETS ---
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

# --- 5. FUNGSI DATA & SYNC ---
def fetch_data():
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])
        df = pd.DataFrame(data)
        df = df[df['Nama'] != ""].dropna(how='all')
        return df
    except:
        return pd.DataFrame(columns=["No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"])

def sync_data(df_baru):
    df_baru = df_baru[df_baru['Nama'] != ""].reset_index(drop=True)
    df_baru['No'] = range(1, len(df_baru) + 1)
    cols = ['No', 'Tanggal', 'Nama', 'No KTP', 'Keperluan', 'Jumlah Tamu', 'Visitor Id', 'Jam Masuk', 'Jam Keluar', 'Status']
    df_baru = df_baru[cols].fillna("-")
    sheet.clear()
    sheet.update([df_baru.columns.values.tolist()] + df_baru.values.tolist())

df = fetch_data()

# --- 6. HEADER ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    if os.path.exists("trac.png"):
        st.image("trac.png", width=150)
with col_text:
    st.title("Visitor Management - GRHA TRAC")
    st.subheader(f"📅 {waktu_wib.strftime('%d %B %Y')}")

st.markdown("---")

# --- 7. SIDEBAR (PENCARIAN, FILTER & DOWNLOAD) ---
st.sidebar.title("📊 Menu Utama")
search_ktp = st.sidebar.text_input("Cari No KTP untuk Riwayat:")
if search_ktp:
    history = df[df['No KTP'].astype(str) == search_ktp].copy()
    if not history.empty:
        st.sidebar.success(f"Nama: {history['Nama'].iloc[-1]}")
        st.sidebar.dataframe(history[['Tanggal', 'Keperluan']].sort_index(ascending=False), hide_index=True)

st.sidebar.markdown("---")
view_opt = st.sidebar.selectbox("Filter Tampilan:", ["Hari Ini Saja", "Semua Riwayat"])

if view_opt == "Hari Ini Saja":
    df_filtered = df[df['Tanggal'] == tgl_skrg].copy()
else:
    df_filtered = df.copy()

if not df_filtered.empty:
    df_filtered['No'] = range(1, len(df_filtered) + 1)

# TOMBOL DOWNLOAD EXCEL
if not df_filtered.empty:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_filtered.to_excel(writer, index=False, sheet_name='Data_Visitor')
    st.sidebar.download_button(
        label=f"📥 Download Excel ({view_opt})",
        data=buffer.getvalue(),
        file_name=f"Visitor_TRAC_{tgl_skrg}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- 8. UI UTAMA ---
tab_reg, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data"])

with tab_reg:
    st.subheader(f"📋 Tabel Pengunjung ({view_opt})")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)
    st.markdown("---")
    
    col_in, col_out = st.columns(2)
    
    with col_in:
        st.subheader("➕ Check-In")
        # --- LOGIKA FORM RESET ---
        # Kita gunakan key yang berubah setiap kali rerun untuk memaksa widget reset total
        if "form_id" not in st.session_state:
            st.session_state.form_id = 0

        # Semua input menggunakan key dinamis berdasarkan form_id
        suffix = str(st.session_state.form_id)
        in_nama = st.text_input("Nama Lengkap", key="nama"+suffix)
        in_ktp = st.text_input("No KTP", key="ktp"+suffix)
        in_perlu = st.text_input("Keperluan", key="perlu"+suffix)
        in_id = st.text_input("Visitor ID", key="id"+suffix)
        in_jml = st.number_input("Jumlah Tamu", min_value=1, value=1, key="jml"+suffix)
        in_jam = st.text_input("Jam Masuk (Contoh: 0800)", key="jam"+suffix)
        
        # Tombol Simpan
        if st.button("💾 SIMPAN DATA", type="primary"):
            if in_nama and in_ktp:
                new_row = {
                    "No": 0, "Tanggal": tgl_skrg, "Nama": in_nama, "No KTP": in_ktp,
                    "Keperluan": in_perlu, "Jumlah Tamu": int(in_jml),
                    "Visitor Id": in_id, "Jam Masuk": format_jam(in_jam),
                    "Jam Keluar": "-", "Status": "IN"
                }
                sync_data(pd.concat([df, pd.DataFrame([new_row])], ignore_index=True))
                
                # UPDATE FORM_ID: Ini akan memaksa semua widget dengan key baru (kosong)
                st.session_state.form_id += 1
                st.success(f"Data {in_nama} berhasil disimpan!")
                st.rerun()
            else:
                st.error("Nama dan KTP wajib diisi!")

    with col_out:
        st.subheader("🚪 Check-Out")
        list_in = df[df['Status'] == 'IN']['Nama'].tolist()
        if list_in:
            # Gunakan key dinamis juga untuk checkout agar dropdown reset
            target = st.selectbox("Pilih Nama", list_in, key="target"+suffix)
            out_jam = st.text_input("Jam Keluar (Contoh: 1700)", key="outjam"+suffix)
            
            if st.button("🚪 KONFIRMASI KELUAR"):
                if out_jam:
                    idx = df[df['Nama'] == target].index[-1]
                    df.at[idx, 'Jam Keluar'] = format_jam(out_jam)
                    df.at[idx, 'Status'] = 'OUT'
                    sync_data(df)
                    
                    st.session_state.form_id += 1
                    st.success(f"{target} berhasil Check-Out.")
                    st.rerun()
                else:
                    st.warning("Isi jam keluar dahulu.")
        else:
            st.info("Tidak ada tamu aktif.")

with tab_manage:
    st.subheader("🛠️ Manajemen Database")
    q = st.text_input("Cari Nama/KTP:")
    if q:
        df_edit = df[df['Nama'].str.contains(q, case=False) | df['No KTP'].astype(str).str.contains(q)]
        for idx, row in df_edit.iterrows():
            with st.expander(f"Edit: {row['Nama']}"):
                with st.form(f"edt_form_{idx}"):
                    en = st.text_input("Nama", value=row['Nama'])
                    ek = st.text_input("KTP", value=str(row['No KTP']))
                    est = st.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1)
                    if st.form_submit_button("💾 UPDATE"):
                        df.at[idx, 'Nama'], df.at[idx, 'No KTP'], df.at[idx, 'Status'] = en, ek, est
                        sync_data(df)
                        st.rerun()
                if st.button("🗑️ HAPUS", key=f"del_{idx}"):
                    sync_data(df.drop(idx))
                    st.rerun()