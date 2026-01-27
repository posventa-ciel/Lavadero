import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro", layout="wide")

# --- ESTILOS COMPACTOS ---
st.markdown("""
<style>
    .main-title { font-size: 22px !important; font-weight: bold; color: #333; margin-top: -10px; }
    .kpi-box { border: 1px solid #ddd; padding: 8px; border-radius: 5px; text-align: center; background-color: #f9f9f9; }
    .kpi-val { font-size: 18px; font-weight: bold; color: #1565c0; }
    .fila-tabla { padding: 4px 0; border-bottom: 1px solid #eee; font-size: 0.85em; }
    .hora-txt { font-weight: bold; color: #d32f2f; font-size: 0.95em; }
    .patente-txt { font-weight: bold; color: #1565c0; font-size: 0.95em; }
    .small-font { font-size: 0.85em; color: #555; }
    .stButton button { height: 28px; font-size: 0.75em; padding: 0px 10px; }
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
    # Header con Imagen (Usando una imagen estable de lavado)
    col_img, col_tit = st.columns([1, 5])
    with col_img:
        # Imagen de un auto siendo lavado para Peugeot/Citroen
        st.image("https://cdn-icons-png.flaticon.com/512/2311/2311438.png", width=70)
    with col_tit:
        st.markdown("<h1 class='main-title'>Gestión de Lavadero - Postventa</h1>", unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo según tu Sheet
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN = 4, 7, 8, 9

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        # --- FILTRO DE FECHA EN SIDEBAR ---
        with st.sidebar:
            st.header("📅 Calendario")
            fecha_sel = st.date_input("Consultar día:", hoy_dt)
            # Formatos de fecha para buscar en el Excel
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación Diaria", "📊 KPIs y Rendimiento"])

        pendientes, terminados = [], []
        tiempos_lavado = []

        # Procesamiento
        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 10: fila += [""] * (10 - len(fila))
            
            # FILTRO: Sacamos "NO SE LAVA" y "NO VINO"
            estado_prometido = fila[IDX_PROMETIDO].upper()
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in estado_prometido or "NO VINO" in estado_prometido:
                continue

            fecha_celda = fila[IDX_FECHA]
            # Detectar si es de la fecha seleccionada o si es un pendiente viejo
            es_fecha_sel = f_str in fecha_celda or f_str_cero in fecha_celda or f_str in estado_prometido or f_str_cero in estado_prometido
            
            # Arrastre de pendientes sin terminar de días anteriores
            es_pendiente_viejo = False
            if not fila[IDX_FIN]:
                try:
                    fecha_dt_celda = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                    if fecha_dt_celda < fecha_sel:
                        es_pendiente_viejo = True
                except: pass

            if es_fecha_sel or es_pendiente_viejo:
                item = {
                    "fila": i, "dominio": fila[IDX_DOMINIO], "modelo": fila[IDX_MODELO],
                    "asesor": fila[IDX_ASESOR], "prometido": fila[IDX_PROMETIDO],
                    "inicio": fila[IDX_INICIO], "fin": fila[IDX_FIN], "atrasado": es_pendiente_viejo
                }

                if item["fin"]:
                    terminados.append(item)
                    mins = calcular_minutos(item["inicio"], item["fin"])
                    if mins > 0: tiempos_lavado.append(mins)
                else:
                    pendientes.append(item)

        with tab1:
            st.markdown(f"**Pendientes ({len(pendientes)}) - {fecha_sel.strftime('%d/%m')}**")
            if pendientes:
                c = st.columns([1, 1, 2, 1.5, 1])
                c[0].caption("PROMETIDO"); c[1].caption("DOMINIO"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACCIÓN")
                
                for p in pendientes:
                    r = st.columns([1, 1, 2, 1.5, 1])
                    atraso_tag = "⚠️ " if p['atrasado'] else ""
                    r[0].markdown(f"<span class='hora-txt'>{atraso_tag}{p['prometido']}</span>", unsafe_allow_html=True)
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
            st.markdown(f"**Unidades Terminadas ({len(terminados)})**")
            if terminados:
                df_term = pd.DataFrame(terminados).sort_values(by="inicio")
                st.dataframe(df_term[["inicio", "fin", "dominio", "modelo", "asesor"]], 
                             hide_index=True, use_container_width=True)

        with tab2:
            st.markdown("### Rendimiento del Día")
            k1, k2, k3 = st.columns(3)
            promedio = sum(tiempos_lavado)/len(tiempos_lavado) if tiempos_lavado else 0
            
            with k1: st.markdown(f"<div class='kpi-box'>Lavados Realizados<br><span class='kpi-val'>{len(terminados)}</span></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Promedio por Auto<br><span class='kpi-val'>{int(promedio)} min</span></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'>Pendientes de Lavar<br><span class='kpi-val'>{len(pendientes)}</span></div>", unsafe_allow_html=True)

            if tiempos_lavado:
                st.markdown("---")
                st.line_chart(tiempos_lavado)

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
