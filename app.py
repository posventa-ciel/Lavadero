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
    # Header con logo estable
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
        <img src="https://www.peugeot.com.ar/content/dam/peugeot/argentina/service/Peugeot_Service_Logo.png" width="90">
        <h1 class="main-title">Gestión de Lavadero - Postventa</h1>
    </div>
    """, unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo de columnas (Incluyendo Inicio 2 y Fin 2 en K y L)
        # A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10 (INI 2), L=11 (FIN 2)
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN = 4, 7, 8, 9
        IDX_INI2, IDX_FIN2 = 10, 11

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        with st.sidebar:
            st.header("📅 Filtros")
            fecha_sel = st.date_input("Consultar día:", hoy_dt.date())
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación Diaria", "📊 KPIs y Rendimiento"])

        operacion_lista, historial_kpi = [], []
        tiempos_dia = []

        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 12: fila += [""] * (12 - len(fila))
            
            estado_h = fila[IDX_PROMETIDO].upper()
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in estado_h or "NO VINO" in estado_h:
                continue

            fecha_celda = fila[IDX_FECHA]
            es_fecha_sel = f_str in fecha_celda or f_str_cero in fecha_celda or f_str in estado_h or f_str_cero in estado_h
            
            # Arrastre de pendientes de ayer
            es_atrasado = False
            finalizado_real = fila[IDX_FIN2] if fila[IDX_FIN2] else (fila[IDX_FIN] if not fila[IDX_INI2] else "")

            if not finalizado_real:
                try:
                    fecha_dt = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                    if fecha_dt < fecha_sel: es_atrasado = True
                except: pass

            if es_fecha_sel or es_atrasado:
                item = {
                    "fila": i, "dom": fila[IDX_DOMINIO], "mod": fila[IDX_MODELO],
                    "ase": fila[IDX_ASESOR], "pro": fila[IDX_PROMETIDO],
                    "ini": fila[IDX_INICIO], "fin": fila[IDX_FIN],
                    "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2],
                    "atr": es_atrasado,
                    "orden": fila[IDX_PROMETIDO] if ":" in fila[IDX_PROMETIDO] else "23:59"
                }
                operacion_lista.append(item)
                
                # Datos para KPIs del día
                if finalizado_real:
                    t1 = calcular_minutos(item["ini"], item["fin"])
                    t2 = calcular_minutos(item["ini2"], item["fin2"]) if item["fin2"] else 0
                    tiempos_dia.append(t1 + t2)

        with tab1:
            pendientes = [x for x in operacion_lista if not (x["fin2"] or (x["fin"] and not x["ini2"]))]
            terminados = [x for x in operacion_lista if x not in pendientes]

            st.write(f"**Pendientes ({len(pendientes)})**")
            if pendientes:
                # ORDEN: 1. Atrasados, 2. Por horario prometido
                pendientes.sort(key=lambda x: (not x["atr"], x["orden"]))
                
                c = st.columns([1, 1, 2, 1.5, 1.5])
                c[0].caption("PROMETIDO"); c[1].caption("DOMINIO"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACCIÓN")
                
                for p in pendientes:
                    r = st.columns([1, 1, 2, 1.5, 1.5])
                    r[0].markdown(f"<span class='hora-txt'>{'⚠️' if p['atr'] else ''}{p['pro']}</span>", unsafe_allow_html=True)
                    r[1].markdown(f"<span class='patente-txt'>{p['dom']}</span>", unsafe_allow_html=True)
                    r[2].markdown(f"<span class='small-font'>{p['mod']}</span>", unsafe_allow_html=True)
                    r[3].markdown(f"<span class='small-font'>{p['ase']}</span>", unsafe_allow_html=True)
                    with r[4]:
                        # Lógica de botones Pausa/Play
                        hora_actual = datetime.now(tz_ar).strftime("%H:%M")
                        if not p['ini']:
                            if st.button("▶️ Iniciar", key=f"play_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INICIO + 1, hora_actual)
                                st.rerun()
                        elif p['ini'] and not p['fin']:
                            col1, col2 = st.columns(2)
                            if col1.button("🏁 Fin", key=f"fin1_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                st.rerun()
                            if col2.button("⏸️ Pausa", key=f"pau_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                st.rerun()
                        elif p['fin'] and not p['ini2']:
                            if st.button("🔄 Reiniciar", key=f"re_{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                st.rerun()
                        elif p['ini2'] and not p['fin2']:
                            if st.button("🏁 Finalizar", key=f"fin2_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                st.rerun()
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

            st.write(f"**Terminados ({len(terminados)})**")
            if terminados:
                t_sorted = sorted(terminados, key=lambda x: x["ini"])
                c_t = st.columns([1, 1, 1, 2, 1.5])
                c_t[0].caption("INICIO"); c_t[1].caption("FIN"); c_t[2].caption("DOMINIO"); c_t[3].caption("MODELO"); c_t[4].caption("ASESOR")
                for t in t_sorted:
                    rt = st.columns([1, 1, 1, 2, 1.5])
                    f_h = t['fin2'] if t['fin2'] else t['fin']
                    rt[0].write(t['ini']); rt[1].write(f_h)
                    rt[2].markdown(f"<span class='patente-txt'>{t['dom']}</span>", unsafe_allow_html=True)
                    rt[3].markdown(f"<span class='small-font'>{t['mod']}</span>", unsafe_allow_html=True)
                    rt[4].markdown(f"<span class='small-font'>{t['ase']}</span>", unsafe_allow_html=True)
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("### Indicadores del Día")
            k1, k2, k3, k4 = st.columns(4)
            prom = sum(tiempos_dia)/len(tiempos_dia) if tiempos_dia else 0
            max_t = max(tiempos_dia) if tiempos_dia else 0
            eficiencia = (len(terminados) / (len(operacion_lista)) * 100) if operacion_lista else 0
            
            with k1: st.markdown(f"<div class='kpi-box'>Lavados<br><span class='kpi-val'>{len(terminados)}</span></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Promedio<br><span class='kpi-val'>{int(prom)} min</span></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'>Máximo<br><span class='kpi-val'>{max_t} min</span></div>", unsafe_allow_html=True)
            with k4: st.markdown(f"<div class='kpi-box'>Eficiencia<br><span class='kpi-val'>{int(eficiencia)}%</span></div>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### Producción Histórica Diaria")
            # Simulación de historial (en un caso real, esto filtraría todas las fechas del sheet)
            hist_data = pd.DataFrame({"Día": ["26/01", "27/01", "28/01"], "Lavados": [12, 18, len(terminados)]})
            st.bar_chart(hist_data.set_index("Día"))

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
