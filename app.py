import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro Peugeot/Citroën", layout="wide")

# --- ESTILOS COMPACTOS ---
st.markdown("""
<style>
    .main-title { font-size: 22px !important; font-weight: bold; color: #00235d; margin-top: -10px; }
    .kpi-box { border: 1px solid #ddd; padding: 8px; border-radius: 5px; text-align: center; background-color: #f1f3f6; }
    .kpi-val { font-size: 18px; font-weight: bold; color: #00235d; }
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
    # Header con Imagen de Peugeot Lavándose
    col_img, col_tit = st.columns([1.2, 5])
    with col_img:
        # Imagen de Peugeot lavándose
        st.image("https://www.peugeot.com.ar/content/dam/peugeot/argentina/service/Peugeot_Service_Logo.png", width=140)
    with col_tit:
        st.markdown("<h1 class='main-title'>Gestión de Lavadero - Concesionario Oficial</h1>", unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo según tu Sheet
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN = 4, 7, 8, 9

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        # --- FILTRO DE FECHA ---
        with st.sidebar:
            st.header("📅 Control de Fecha")
            fecha_sel = st.date_input("Día de trabajo:", hoy_dt)
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación Diaria", "📊 KPIs y Tiempos"])

        pendientes, terminados = [], []
        tiempos_lavado = []

        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 10: fila += [""] * (10 - len(fila))
            
            estado_prometido = fila[IDX_PROMETIDO].upper()
            # FILTRO: Sacamos los que NO VINIERON o NO SE LAVAN
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in estado_prometido or "NO VINO" in estado_prometido:
                continue

            fecha_celda = fila[IDX_FECHA]
            es_fecha_sel = f_str in fecha_celda or f_str_cero in fecha_celda or f_str in estado_prometido or f_str_cero in estado_prometido
            
            # Pendientes de días anteriores
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
            st.markdown(f"**Programación ({len(pendientes)}) - {fecha_sel.strftime('%d/%m/%Y')}**")
            if pendientes:
                c = st.columns([1, 1, 2, 1.5, 1])
                c[0].caption("PROMETIDO"); c[1].caption("DOMINIO"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACCIÓN")
                
                for p in pendientes:
                    r = st.columns([1, 1, 2, 1.5, 1])
                    atraso_prefix = "⚠️ " if p['atrasado'] else ""
                    r[0].markdown(f"<span class='hora-txt'>{atraso_prefix}{p['prometido']}</span>", unsafe_allow_html=True)
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
                # Ordenamos cronológicamente por hora de inicio
                df_term = pd.DataFrame(terminados).sort_values(by="inicio")
                st.dataframe(df_term[["inicio", "fin", "dominio", "modelo", "asesor"]], 
                             hide_index=True, use_container_width=True)

        with tab2:
            st.markdown("### Indicadores de Eficiencia")
            k1, k2, k3 = st.columns(3)
            promedio = sum(tiempos_lavado)/len(tiempos_lavado) if tiempos_lavado else 0
            max_t = max(tiempos_lavado) if tiempos_lavado else 0
            
            with k1: st.markdown(f"<div class='kpi-box'>Lavados Totales<br><span class='kpi-val'>{len(terminados)}</span></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Promedio Lavado<br><span class='kpi-val'>{int(promedio)} min</span></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'>Lavado más largo<br><span class='kpi-val'>{max_t} min</span></div>", unsafe_allow_html=True)

            if tiempos_lavado:
                st.markdown("---")
                st.line_chart(tiempos_lavado)
                st.caption("Minutos por unidad lavada a lo largo del día.")

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
