import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Fungsi Helper untuk Format Jam Otomatis
def format_jam(input_jam):
    digits = "".join(filter(str.isdigit, str(input_jam)))
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:]}"
    return input_jam

# 1. Konfigurasi Halaman
st.set_page_config(page_title="Visitor Management GRHA Trac Condet", layout="wide")

# PAKSA KE WAKTU INDONESIA (WIB: UTC+7)
hari_ini_wib = datetime.utcnow() + timedelta(hours=7)

# 2. Header dengan Logo
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("trac.png"):
        st.image("trac.png", width=200)
    else:
        st.write("### TRAC")

with col_title:
    st.title("Visitor Management GRHA Trac Condet")
    st.success(f"🇮🇩 **Sistem Aktif (WIB) | Hari Ini: {hari_ini_wib.strftime('%d %B %Y')}**")

st.markdown("---")

# 3. Inisialisasi Session State
if 'visitor_data' not in st.session_state:
    st.session_state.visitor_data = pd.DataFrame(columns=[
        "No", "Tanggal", "Nama", "No KTP", "Keperluan", "Jumlah Tamu", "Visitor Id", "Jam Masuk", "Jam Keluar", "Status"
    ])

if "form_tick" not in st.session_state:
    st.session_state.form_tick = 0

# 4. Sidebar: Filter KTP & Filter Tanggal
st.sidebar.header("🔍 Filter & Riwayat")
search_ktp = st.sidebar.text_input("Cari Nomor KTP:")
filter_date = st.sidebar.date_input("Filter Berdasarkan Tanggal:", value=hari_ini_wib)
date_str = filter_date.strftime("%d-%b")

df = st.session_state.visitor_data

# Logika Filter
df_filtered = df.copy()
if search_ktp:
    df_filtered = df_filtered[df_filtered['No KTP'].astype(str).str.contains(search_ktp)]
    count_ktp = len(df_filtered)
    if count_ktp > 0:
        st.sidebar.success(f"Tamu: {df_filtered.iloc[0]['Nama']}\n\nTotal Kunjungan: {count_ktp} kali")

total_tgl = len(df[df['Tanggal'] == date_str])
st.sidebar.markdown(f"**Ringkasan {date_str}:**")
st.sidebar.write(f"Total Pengunjung: {total_tgl} orang")

# 5. Ringkasan Statistik
col1, col2, col3 = st.columns(3)
col1.metric("Tamu di Dalam (IN)", len(df[df['Status'] == 'IN']))
col2.metric("Tamu Keluar (OUT)", len(df[df['Status'] == 'OUT']))
col3.metric("Total Database", len(df))

# 6. Tabel & Kelola Data (Edit/Hapus)
tab1, tab2 = st.tabs(["📊 Data Pengunjung", "⚙️ Kelola / Edit / Hapus Data"])
with tab1:
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

with tab2:
    if not df.empty:
        for index, row in df.iterrows():
            with st.expander(f"📝 Edit: {row['Nama']} (ID: {row['Visitor Id']})"):
                c_ed1, c_ed2 = st.columns(2)
                en = c_ed1.text_input("Nama", value=row['Nama'], key=f"en_{index}")
                ek = c_ed2.text_input("KTP", value=row['No KTP'], key=f"ek_{index}")
                ej = c_ed1.text_input("Jam Masuk", value=row['Jam Masuk'], key=f"ej_{index}")
                es = c_ed2.selectbox("Status", ["IN", "OUT"], index=0 if row['Status']=="IN" else 1, key=f"es_{index}")
                if st.button("Simpan Perubahan", key=f"sv_{index}"):
                    st.session_state.visitor_data.at[index, 'Nama'] = en
                    st.session_state.visitor_data.at[index, 'No KTP'] = ek
                    st.session_state.visitor_data.at[index, 'Jam Masuk'] = format_jam(ej)
                    st.session_state.visitor_data.at[index, 'Status'] = es
                    st.rerun()
                if st.button("Hapus", key=f"dl_{index}"):
                    st.session_state.visitor_data = df.drop(index).reset_index(drop=True)
                    st.session_state.visitor_data['No'] = range(1, len(st.session_state.visitor_data) + 1)
                    st.rerun()
    else:
        st.write("Belum ada data.")

st.markdown("---")

# 7. Area Input (Check-In & Check-Out)
col_add, col_out = st.columns(2)

with col_add:
    st.subheader("➕ Check In (Tamu Baru)")
    tick = st.session_state.form_tick
    
    v_date = st.date_input("Tanggal Kunjungan", value=hari_ini_wib, key=f"date_{tick}")
    v_name = st.text_input("Nama Lengkap", key=f"nama_{tick}")
    v_ktp = st.text_input("Nomor KTP", key=f"ktp_{tick}")
    v_need = st.text_input("Keperluan", key=f"need_{tick}")
    
    c1, c2 = st.columns(2)
    v_count = c1.number_input("Jumlah Tamu", min_value=1, value=1, key=f"count_{tick}")
    
    # VISITOR ID & JAM MASUK: Benar-benar kosong tanpa petunjuk (placeholder)
    v_id = c2.text_input("Visitor ID", value="", placeholder="", key=f"id_{tick}")
    v_in_raw = st.text_input("Jam Masuk", value="", placeholder="", key=f"jam_in_{tick}")
    
    if st.button("Simpan Check In", type="primary"):
        if v_name and v_ktp and v_in_raw and v_id:
            v_in_formatted = format_jam(v_in_raw)
            new_row = {
                "No": len(df) + 1, "Tanggal": v_date.strftime("%d-%b"),
                "Nama": v_name, "No KTP": v_ktp, "Keperluan": v_need,
                "Jumlah Tamu": v_count, "Visitor Id": v_id,
                "Jam Masuk": v_in_formatted, "Jam Keluar": "-", "Status": "IN"
            }
            st.session_state.visitor_data = pd.concat([st.session_state.visitor_data, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state.form_tick += 1
            st.rerun()
        else:
            st.error("Mohon isi semua kolom (Nama, KTP, ID, dan Jam Masuk)!")

with col_out:
    st.subheader("🚪 Check Out (Tamu Pulang)")
    visitors_in = df[df['Status'] == 'IN']['Nama'].tolist()
    if not visitors_in:
        st.info("Tidak ada tamu aktif.")
    else:
        target_name = st.selectbox("Pilih Nama:", ["-- Pilih --"] + visitors_in, key=f"sel_{tick}")
        v_out_raw = st.text_input("Jam Keluar", value="", placeholder="", key=f"jam_out_{tick}")
        if st.button("Konfirmasi Keluar"):
            if target_name != "-- Pilih --" and v_out_raw:
                v_out_formatted = format_jam(v_out_raw)
                idx = df[df['Nama'] == target_name].index[-1]
                st.session_state.visitor_data.at[idx, 'Jam Keluar'] = v_out_formatted
                st.session_state.visitor_data.at[idx, 'Status'] = 'OUT'
                st.session_state.form_tick += 1
                st.rerun()
            else:
                st.error("Pilih nama dan isi jam keluar!")