import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import io

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Visitor Management TRAC", layout="wide")

# --- 2. SISTEM KEAMANAN (LOGIN) ---
# Silakan ganti password sesuai keinginan Anda
ADMIN_PASSWORD = "tracadmin123" 

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- 3. FUNGSI ZONA WAKTU WIB ---
def get_waktu_wib():
    return datetime.utcnow() + timedelta(hours=7)

waktu_wib = get_waktu_wib()
tgl_skrg = waktu_wib.strftime("%d-%m-%Y")

# --- 4. FUNGSI FORMAT JAM (HHMM -> HH:MM) ---
def format_jam(input_jam):
    if not input_jam or input_jam == "-": return "-"
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}:{digits[2:]}"
    elif len(digits) == 3:
        return f"0{digits[0]}:{digits[1:]}"
    return input_jam

# --- 5. KONEKSI GOOGLE SHEETS ---
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

# --- 6. FUNGSI DATA ---
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

# --- 7. HEADER ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    if os.path.exists("trac.png"):
        st.image("trac.png", width=150)
with col_text:
    st.title("Visitor Management - GRHA TRAC")
    st.subheader(f"📅 {waktu_wib.strftime('%d %B %Y')}")

st.markdown("---")

# --- 8. SIDEBAR (LOGIN, PENCARIAN & DOWNLOAD) ---
st.sidebar.title("📊 Menu Utama")

# Login Section
if not st.session_state.authenticated:
    pwd_input = st.sidebar.text_input("🔑 Admin Login", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.sidebar.error("Password Salah!")
else:
    st.sidebar.success("✅ Mode Admin Aktif")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

st.sidebar.markdown("---")

# FITUR PENCARIAN NO KTP (Dimunculkan Kembali)
st.sidebar.subheader("🔍 Cek Riwayat Tamu")
search_ktp = st.sidebar.text_input("Masukkan No KTP:")
if search_ktp:
    # Filter data berdasarkan KTP
    history = df[df['No KTP'].astype(str) == search_ktp].copy()
    if not history.empty:
        nama_tamu = history['Nama'].iloc[-1]
        st.sidebar.success(f"**Nama:** {nama_tamu}")
        st.sidebar.info(f"📋 Total Kunjungan: **{len(history)} kali**")
        st.sidebar.write("**Daftar Keperluan:**")
        # Menampilkan tabel ringkas riwayat
        st.sidebar.dataframe(
            history[['Tanggal', 'Keperluan', 'Status']].sort_index(ascending=False), 
            hide_index=True
        )
    else:
        st.sidebar.warning("Data KTP belum pernah terdaftar.")

st.sidebar.markdown("---")

# Filter Tampilan & Download
view_opt = st.sidebar.selectbox("Filter Tampilan Tabel:", ["Hari Ini Saja", "Semua Riwayat"])
df_filtered = df[df['Tanggal'] == tgl_skrg].copy() if view_opt == "Hari Ini Saja" else df.copy()

if not df_filtered.empty:
    df_filtered['No'] = range(1, len(df_filtered) + 1)
    
    # Download Button (Hanya Admin)
    if st.session_state.authenticated:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_filtered.to_excel(writer, index=False, sheet_name='Data_Visitor')
        st.sidebar.download_button(
            label="📥 Download Excel", 
            data=buffer.getvalue(), 
            file_name=f"Visitor_TRAC_{tgl_skrg}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- 9. UI UTAMA ---
if st.session_state.authenticated:
    tab_reg, tab_manage = st.tabs(["📝 Registrasi & Daftar", "⚙️ Kelola Data"])
else:
    st.info("💡 Mode **VIEWER**. Login di sidebar untuk menambah atau mengedit data.")
    tab_reg = st.container()

with tab_reg:
    st.subheader(f"📋 Tabel Pengunjung ({view_opt})")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)
    
    if st.session_state.authenticated:
        st.markdown("---")
        col_in, col_out = st.columns(2)
        
        with col_in:
            st.subheader("➕ Check-In")
            if "form_id" not in st.session_state: st.session_state.form_id = 0
            suffix = str(st.session_state.form_id)
            
            in_nama = st.text_input("Nama Lengkap", key="n"+suffix)
            in_ktp = st.text_input("No KTP", key="k"+suffix)
            in_perlu = st.text_input("Keperluan", key="p"+suffix)
            in_id = st.text_input("Visitor ID", key="id"+suffix)
            in_jml = st.number_input("Jumlah Tamu", min_value=1, value=1, key="j"+suffix)
            in_jam = st.text_input("Jam Masuk (Contoh: 0800)", key="jam"+suffix)
            
            # Button manual (Tanpa st.form untuk cegah Enter-submit)
            if st.button("💾 SIMPAN DATA", type="primary"):
                if in_nama and in_ktp:
                    new_row = {"No": 0, "Tanggal": tgl_skrg, "Nama": in_nama, "No KTP": in_ktp, "Keperluan": in_perlu, "Jumlah Tamu": int(in_jml), "Visitor Id": in_id, "Jam Masuk": format_jam(in_jam), "Jam Keluar": "-", "Status": "IN"}
                    sync_data(pd.concat([df, pd.DataFrame([new_row])], ignore_index=True))
                    st.session_state.form_id += 1 # Reset form via key change
                    st.rerun()
                else:
                    st.error("Nama & KTP wajib diisi!")

        with col_out:
            st.subheader("🚪 Check-Out")
            list_in = df[df['Status'] == 'IN']['Nama'].tolist()
            if list_in:
                target = st.selectbox("Pilih Nama", list_in, key="t"+suffix)
                out_jam = st.text_input("Jam Keluar (Contoh: 1700)", key="out"+suffix)
                if st.button("🚪 KONFIRMASI KELUAR"):
                    if out_jam:
                        idx = df[df['Nama'] == target].index[-1]
                        df.at[idx, 'Jam Keluar'] = format_jam(out_jam)
                        df.at[idx, 'Status'] = 'OUT'
                        sync_data(df)
                        st.session_state.form_id += 1
                        st.rerun()
                    else:
                        st.warning("Isi jam keluar dahulu.")
            else:
                st.info("Tidak ada tamu aktif.")

if st.session_state.authenticated:
    with tab_manage:
        st.subheader("🛠️ Manajemen Database")
        q = st.text_input("Cari Nama/KTP:")
        if q:
            df_edit = df[df['Nama'].str.contains(q, case=False) | df['No KTP'].astype(str).str.contains(q)]
            for idx, row in df_edit.iterrows():
                with st.expander(f"Edit: {row['Nama']}"):
                    with st.form(f"edt_{idx}"):
                        en = st.text_input("Nama", value=row['Nama'])
                        ek = st.text_input("KTP", value=str(row['No KTP']))
                        est = st.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1)
                        if st.form_submit_button("💾 UPDATE"):
                            df.at[idx, 'Nama'], df.at[idx, 'No KTP'], df.at[idx, 'Status'] = en, ek, est
                            sync_data(df)
                            st.rerun()
                    if st.button(f"🗑️ HAPUS", key=f"del_{idx}"):
                        sync_data(df.drop(idx))
                        st.rerun()