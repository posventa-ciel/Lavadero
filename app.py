import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 5px 0; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-size: 12px; }
    .badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-blue { background-color: #007bff; color: white; }
    .stButton button { height: 26px !important; font-size: 11px !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
def conectar_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        key_dict = json.loads(st.secrets["service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
        return client.open_by_url(url).worksheet("PLAN GENERAL")
    except Exception as e:
        st.error(f"Error: {e}"); return None

# --- 3. FUNCIONES ---
def calcular_minutos_totales(h_ini, h_fin, h_ini2, h_fin2):
    total = 0
    fmt = "%H:%M"
    try:
        if h_ini and h_fin:
            total += (datetime.strptime(h_fin, fmt) - datetime.strptime(h_ini, fmt)).total_seconds() / 60
        if h_ini2 and h_fin2:
            total += (datetime.strptime(h_fin2, fmt) - datetime.strptime(h_ini2, fmt)).total_seconds() / 60
    except: pass
    return int(total)

# --- 4. MAIN ---
def main():
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    now = datetime.now(tz)
    h_actual = now.strftime("%H:%M")
    
    hoja = conectar_sheet()
    if not hoja: return
    data = hoja.get_all_values()
    
    # MAPEADO EXACTO SEGÚN TU IMAGEN (image_7a57bb.png):
    # A=0(FECHA), C=2(ASESOR), D=3(DOMINIO), E=4(MODELO), I=8(HORARIO PROM), J=9(INICIO), K=10(FIN), L=11(INICIO 2), M=12(FIN 2), N=13(ESTADO), O=14(CONTROL)
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD = 0, 2, 3, 4
    IDX_PRO, IDX_INI, IDX_FIN, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 8, 9, 10, 11, 12, 13, 14

    with st.sidebar:
        busqueda = st.text_input("Buscar Patente:").upper()
        fecha_sel = st.date_input("Fecha:", now.date())
        mes_hist = st.selectbox("Mes Historial:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=now.month-1)

    pendientes, terminados, historial = [], [], []
    f_str = fecha_sel.strftime("%-d/%-m/%Y")
    f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    for i, fila in enumerate(data[1:], start=2):
        if len(fila) < 15: fila += [""] * (15 - len(fila))
        
        estado = fila[IDX_EST].strip().upper()
        dom = fila[IDX_DOM].upper()
        fecha_fila = fila[IDX_FECHA]
        
        if not dom or "NO SE LAVA" in fila[IDX_PRO].upper(): continue
        if busqueda and busqueda not in dom: continue

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": fila[IDX_ASE],
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI], "fin": fila[IDX_FIN],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado,
            "ok": (fila[IDX_CTRL].upper() == "OK"),
            "tiempo": calcular_minutos_totales(fila[IDX_INI], fila[IDX_FIN], fila[IDX_INI2], fila[IDX_FIN2]),
            "fecha": fecha_fila
        }

        es_hoy = (f_str in fecha_fila) or (f_str_cero in fecha_fila)
        
        if estado == "FINALIZADO":
            if es_hoy: terminados.append(item)
            try:
                m_num = datetime.strptime(fecha_fila.split()[0], "%d/%m/%Y").month
                if m_num == (["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_hist) + 1):
                    historial.append(item)
            except: pass
        else:
            if es_hoy or ("202" in fecha_fila and estado != "FINALIZADO"):
                pendientes.append(item)

    t1, t2, t3 = st.tabs(["🚗 Operación", "📊 KPIs", "📅 Historial"])

    with t1:
        st.subheader(f"Pendientes ({len(pendientes)})")
        cols = st.columns([1, 1, 2, 1, 1.5])
        cols[0].caption("PROMETIDO"); cols[1].caption("DOMINIO"); cols[2].caption("MODELO"); cols[3].caption("ASESOR"); cols[4].caption("ACCIONES")
        
        for p in pendientes:
            with st.container():
                c = st.columns([1, 1, 2, 1, 1.5])
                # Badge de estado
                b_css = "badge-blue" if p['est'] == "PAUSA" else "badge-red"
                c[0].markdown(f"<div class='badge {b_css}'>{p['pro']}<br>{p['est'] if p['est'] else 'PENDIENTE'}</div>", unsafe_allow_html=True)
                c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                c[3].write(p['ase'])
                
                with c[4]:
                    if not p['ini']:
                        if st.button("▶️ Iniciar", key=f"s{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI + 1, h_actual)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                    elif p['ini'] and not p['fin']:
                        cb = st.columns(2)
                        if cb[0].button("⏸️", key=f"p{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, h_actual)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                        if cb[1].button("🏁", key=f"f{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, h_actual)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                    elif p['est'] == "PAUSA":
                        if st.button("🔄 Reanudar", key=f"r{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI2 + 1, h_actual)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                    elif p['est'] == "REPASO":
                        if st.button("🏁 Finalizar", key=f"f2{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN2 + 1, h_actual)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader(f"Finalizados ({len(terminados)})")
        if terminados:
            st.table(pd.DataFrame(terminados)[['ini', 'fin', 'dom', 'mod', 'ase']])

    with t2:
        if terminados:
            df = pd.DataFrame(terminados)
            m1, m2, m3 = st.columns(3)
            m1.metric("Lavados", len(df))
            m2.metric("Promedio", f"{int(df['tiempo'].mean())} min")
            m3.metric("Calidad OK", len(df[df['ok']]))
            st.plotly_chart(px.bar(df['ase'].value_counts(), title="Por Asesor"))

    with t3:
        if historial:
            st.dataframe(pd.DataFrame(historial)[['fecha', 'dom', 'mod', 'tiempo']], use_container_width=True)

if __name__ == "__main__":
    main()
