import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro", layout="wide")

# --- ESTILOS COMPACTOS Y LOGO ---
st.markdown("""
<style>
    .main-title { font-size: 24px !important; font-weight: bold; color: #333; margin-bottom: 0px; }
    .kpi-box { border: 1px solid #ddd; padding: 10px; border-radius: 5px; text-align: center; background-color: #f9f9f9; }
    .kpi-val { font-size: 20px; font-weight: bold; color: #1565c0; }
    .fila-tabla { padding: 4px 0; border-bottom: 1px solid #eee; font-size: 0.9em; }
    .hora-txt { font-weight: bold; color: #d32f2f; font-size: 1em; }
    .patente-txt { font-weight: bold; color: #1565c0; font-size: 1em; }
    .small-font { font-size: 0.85em; color: #555; }
    div[data-testid="stExpander"] { border: none !important; }
    .stButton button { height: 32px; font-size: 0.8em; padding: 0px; }
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
    # Header con logo sugerido (Peugeot/Citroen)
    col_logo, col_tit = st.columns([1, 6])
    with col_logo:
        # Imagen genérica de lavado profesional (puedes cambiar la URL por una de Peugeot si prefieres)
        st.image("https://www.peugeot.com.ar/content/dam/peugeot/argentina/service/Peugeot_Service_Logo.png", width=120)
    with col_tit:
        st.markdown("<h1 class='main-title'>Gestión de Lavadero - Postventa</h1>", unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN = 4, 7, 8, 9

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_str = datetime.now(tz_ar).strftime("%-d/%-m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación Diaria", "📊 KPIs y Rendimiento"])

        # Procesamiento de datos
        pendientes, terminados = [], []
        tiempos_lavado = []

        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 10: fila += [""] * (10 - len(fila))
            if not fila[IDX_DOMINIO] or fila[IDX_PROMETIDO].upper() == "NO SE LAVA": continue
            if hoy_str not in fila[IDX_FECHA] and hoy_str not in fila[IDX_PROMETIDO]: continue

            item = {
                "fila": i, "dominio": fila[IDX_DOMINIO], "modelo": fila[IDX_MODELO],
                "asesor": fila[IDX_ASESOR], "prometido": fila[IDX_PROMETIDO],
                "inicio": fila[IDX_INICIO], "fin": fila[IDX_FIN]
            }

            if item["fin"]:
                terminados.append(item)
                mins = calcular_minutos(item["inicio"], item["fin"])
                if mins > 0: tiempos_lavado.append(mins)
            else:
                pendientes.append(item)

        with tab1:
            # PENDIENTES
            st.markdown(f"**Pendientes de hoy ({len(pendientes)})**")
            if pendientes:
                c = st.columns([1, 1, 2, 1.5, 1])
                c[0].caption("PROMETIDO"); c[1].caption("DOMINIO"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACCIÓN")
                
                for p in pendientes:
                    r = st.columns([1, 1, 2, 1.5, 1])
                    r[0].markdown(f"<span class='hora-txt'>{p['prometido']}</span>", unsafe_allow_html=True)
                    r[1].markdown(f"<span class='patente-txt'>{p['dominio']}</span>", unsafe_allow_html=True)
                    r[2].markdown(f"<span class='small-font'>{p['modelo']}</span>", unsafe_allow_html=True)
                    r[3].markdown(f"<span class='small-font'>{p['asesor']}</span>", unsafe_allow_html=True)
                    with r[4]:
                        if not p['inicio']:
                            if st.button("▶️", key=f"i{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INICIO + 1, datetime.now(tz_ar).strftime("%H:%M"))
                                st.rerun()
                        else:
                            if st.button("🏁", key=f"f{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, datetime.now(tz_ar).strftime("%H:%M"))
                                st.rerun()
            
            st.markdown("---")
            
            # TERMINADOS (Ordenados por Inicio)
            st.markdown(f"**Lavados Finalizados ({len(terminados)})**")
            if terminados:
                df_term = pd.DataFrame(terminados).sort_values(by="inicio")
                st.dataframe(df_term[["inicio", "fin", "dominio", "modelo", "asesor"]], 
                             hide_index=True, use_container_width=True)

        with tab2:
            st.markdown("### Indicadores de Eficiencia (KPI)")
            k1, k2, k3, k4 = st.columns(4)
            
            promedio = sum(tiempos_lavado)/len(tiempos_lavado) if tiempos_lavado else 0
            max_tiempo = max(tiempos_lavado) if tiempos_lavado else 0
            
            with k1: st.markdown(f"<div class='kpi-box'>Total Lavados<br><span class='kpi-val'>{len(terminados)}</span></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Tiempo Promedio<br><span class='kpi-val'>{int(promedio)} min</span></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'>Tiempo Máximo<br><span class='kpi-val'>{max_tiempo} min</span></div>", unsafe_allow_html=True)
            with k4: 
                pend_porc = (len(pendientes)/(len(pendientes)+len(terminados))*100) if (len(pendientes)+len(terminados)) > 0 else 0
                st.markdown(f"<div class='kpi-box'>% Pendiente<br><span class='kpi-val'>{int(pend_porc)}%</span></div>", unsafe_allow_html=True)

            if tiempos_lavado:
                st.markdown("---")
                st.line_chart(tiempos_lavado)
                st.caption("Evolución de tiempos de lavado (en minutos) durante el día.")

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
