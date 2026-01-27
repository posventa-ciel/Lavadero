import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro Peugeot", layout="wide")

# --- ESTILOS COMPACTOS ---
st.markdown("""
<style>
    .main-title { font-size: 20px !important; font-weight: bold; color: #00235d; margin-top: -15px; }
    .kpi-box { border: 1px solid #ddd; padding: 5px; border-radius: 5px; text-align: center; background-color: #f1f3f6; }
    .kpi-val { font-size: 16px; font-weight: bold; color: #00235d; }
    .fila-tabla { padding: 4px 0; border-bottom: 1px solid #eee; font-size: 0.82em; }
    .hora-txt { font-weight: bold; color: #d32f2f; font-size: 0.9em; }
    .patente-txt { font-weight: bold; color: #1565c0; font-size: 0.9em; }
    .small-font { font-size: 0.82em; color: #555; }
    .stButton button { height: 26px; font-size: 0.72em; padding: 0px 8px; }
    .header-container { display: flex; align-items: center; gap: 15px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).worksheet("PLAN GENERAL")

def calcular_minutos(h1, h2):
    try:
        fmt = "%H:%M"
        t1 = datetime.strptime(h1, fmt)
        t2 = datetime.strptime(h2, fmt)
        return int((t2 - t1).total_seconds() / 60)
    except: return 0

def main():
    # Header compacto con imagen estable
    st.markdown(f"""
    <div class="header-container">
        <img src="https://www.peugeot.com.ar/content/dam/peugeot/argentina/service/Peugeot_Service_Logo.png" width="90">
        <h1 class="main-title">Gestión de Lavadero - Postventa</h1>
    </div>
    """, unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN = 4, 7, 8, 9

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        with st.sidebar:
            st.header("📅 Control")
            fecha_sel = st.date_input("Consultar día:", hoy_dt.date())
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación Diaria", "📊 KPIs"])

        pendientes, terminados = [], []
        tiempos_lavado = []

        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 10: fila += [""] * (10 - len(fila))
            
            estado_h = fila[IDX_PROMETIDO].upper()
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in estado_h or "NO VINO" in estado_h:
                continue

            fecha_celda = fila[IDX_FECHA]
            es_fecha_sel = f_str in fecha_celda or f_str_cero in fecha_celda or f_str in estado_h or f_str_cero in estado_h
            
            es_atrasado = False
            if not fila[IDX_FIN]:
                try:
                    fecha_dt = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                    if fecha_dt < fecha_sel: es_atrasado = True
                except: pass

            if es_fecha_sel or es_atrasado:
                item = {
                    "fila": i, "dominio": fila[IDX_DOMINIO], "modelo": fila[IDX_MODELO],
                    "asesor": fila[IDX_ASESOR], "prometido": fila[IDX_PROMETIDO],
                    "inicio": fila[IDX_INICIO], "fin": fila[IDX_FIN], "atrasado": es_atrasado
                }
                if item["fin"]:
                    terminados.append(item)
                    m = calcular_minutos(item["inicio"], item["fin"])
                    if m > 0: tiempos_lavado.append(m)
                else:
                    pendientes.append(item)

        with tab1:
            st.markdown(f"**Pendientes ({len(pendientes)}) - {fecha_sel.strftime('%d/%m')}**")
            if pendientes:
                c = st.columns([1, 1, 2, 1.5, 0.8])
                c[0].caption("PROMETIDO"); c[1].caption("DOMINIO"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACCIÓN")
                
                for p in pendientes:
                    r = st.columns([1, 1, 2, 1.5, 0.8])
                    txt_atraso = "⚠️ " if p['atrasado'] else ""
                    r[0].markdown(f"<span class='hora-txt'>{txt_atraso}{p['prometido']}</span>", unsafe_allow_html=True)
                    r[1].markdown(f"<span class='patente-txt'>{p['dominio']}</span>", unsafe_allow_html=True)
                    r[2].markdown(f"<span class='small-font'>{p['modelo']}</span>", unsafe_allow_html=True)
                    r[3].markdown(f"<span class='small-font'>{p['asesor']}</span>", unsafe_allow_html=True)
                    with r[4]:
                        btn_label = "▶️" if not p['inicio'] else "🏁"
                        if st.button(btn_label, key=f"btn{p['fila']}"):
                            col_upd = IDX_INICIO + 1 if not p['inicio'] else IDX_FIN + 1
                            hoja.update_cell(p['fila'], col_upd, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"**Unidades Terminadas ({len(terminados)})**")
            if terminados:
                # ORDENAR: De más temprano a más tarde por hora de INICIO
                terminados_sorted = sorted(terminados, key=lambda x: x["inicio"])
                
                c_t = st.columns([1, 1, 1.2, 2, 1.5])
                c_t[0].caption("INICIO"); c_t[1].caption("FIN"); c_t[2].caption("DOMINIO"); c_t[3].caption("MODELO"); c_t[4].caption("ASESOR")
                
                for t in terminados_sorted:
                    r_t = st.columns([1, 1, 1.2, 2, 1.5])
                    r_t[0].markdown(f"<span class='small-font'>{t['inicio']}</span>", unsafe_allow_html=True)
                    r_t[1].markdown(f"<span class='small-font'>{t['fin']}</span>", unsafe_allow_html=True)
                    r_t[2].markdown(f"<span class='patente-txt'>{t['dominio']}</span>", unsafe_allow_html=True)
                    r_t[3].markdown(f"<span class='small-font'>{t['modelo']}</span>", unsafe_allow_html=True)
                    r_t[4].markdown(f"<span class='small-font'>{t['asesor']}</span>", unsafe_allow_html=True)
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("### Rendimiento")
            k1, k2, k3 = st.columns(3)
            avg = sum(tiempos_lavado)/len(tiempos_lavado) if tiempos_lavado else 0
            with k1: st.markdown(f"<div class='kpi-box'>Lavados<br><span class='kpi-val'>{len(terminados)}</span></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Promedio<br><span class='kpi-val'>{int(avg)} min</span></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'>Máximo<br><span class='kpi-val'>{max(tiempos_lavado) if tiempos_lavado else 0} min</span></div>", unsafe_allow_html=True)
            if tiempos_lavado: st.line_chart(tiempos_lavado)

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
