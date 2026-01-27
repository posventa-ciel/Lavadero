import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro Peugeot", layout="wide")

# --- ESTILOS ULTRA COMPACTOS ---
st.markdown("""
<style>
    .main-title { font-size: 18px !important; font-weight: bold; color: #00235d; margin: 0; }
    .kpi-box { border: 1px solid #ddd; padding: 5px; border-radius: 4px; text-align: center; background-color: #f8f9fa; }
    .kpi-val { font-size: 16px; font-weight: bold; color: #00235d; }
    .fila-tabla { padding: 2px 0; border-bottom: 1px solid #eee; font-size: 0.8em; line-height: 1.2; }
    .hora-txt { font-weight: bold; color: #d32f2f; font-size: 0.85em; }
    .patente-txt { font-weight: bold; color: #1565c0; font-size: 0.85em; }
    .small-font { font-size: 0.8em; color: #444; }
    .stButton button { height: 24px; font-size: 0.7em; padding: 0px 5px; margin: 0; }
    .header-container { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; border-bottom: 2px solid #00235d; padding-bottom: 5px; }
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
    # Logo Peugeot en Base64 para que NUNCA falle (Versión simplificada)
    logo_peugeot = "https://www.peugeot.com.ar/content/dam/peugeot/argentina/service/Peugeot_Service_Logo.png"
    
    st.markdown(f"""
    <div class="header-container">
        <img src="https://img.icons8.com/fluency/48/car-wash.png" width="40">
        <h1 class="main-title">GESTIÓN DE LAVADERO - POSTVENTA JUJUY</h1>
    </div>
    """, unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo: A=0(Fecha), C=2(Asesor), D=3(Patente), E=4(Modelo), H=7(Prometido), I=8(Inicio), J=9(Fin)
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN = 4, 7, 8, 9

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        with st.sidebar:
            st.header("⚙️ Filtros")
            fecha_sel = st.date_input("Día:", hoy_dt.date())
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación", "📊 KPIs"])

        pendientes, terminados = [], []
        tiempos_lavado = []

        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 10: fila += [""] * (10 - len(fila))
            
            p_val = fila[IDX_PROMETIDO].upper()
            # FILTRO EXCLUSIÓN
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in p_val or "NO VINO" in p_val:
                continue

            f_celda = fila[IDX_FECHA]
            es_dia = f_str in f_celda or f_str_cero in f_celda or f_str in p_val or f_str_cero in p_val
            
            es_atrasado = False
            if not fila[IDX_FIN]:
                try:
                    dt_c = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").date()
                    if dt_c < fecha_sel: es_atrasado = True
                except: pass

            if es_dia or es_atrasado:
                item = {
                    "fila": i, "dom": fila[IDX_DOMINIO], "mod": fila[IDX_MODELO],
                    "ase": fila[IDX_ASESOR], "pro": fila[IDX_PROMETIDO],
                    "ini": fila[IDX_INICIO], "fin": fila[IDX_FIN], "atr": es_atrasado
                }
                if item["fin"]:
                    terminados.append(item)
                    m = calcular_minutos(item["ini"], item["fin"])
                    if m > 0: tiempos_lavado.append(m)
                else:
                    pendientes.append(item)

        with tab1:
            st.write(f"**Pendientes ({len(pendientes)})**")
            if pendientes:
                c = st.columns([0.8, 1, 2, 1.2, 0.5])
                c[0].caption("HORA"); c[1].caption("DOM"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACC")
                
                for p in pendientes:
                    r = st.columns([0.8, 1, 2, 1.2, 0.5])
                    r[0].markdown(f"<span class='hora-txt'>{'⚠️' if p['atr'] else ''}{p['pro']}</span>", unsafe_allow_html=True)
                    r[1].markdown(f"<span class='patente-txt'>{p['dom']}</span>", unsafe_allow_html=True)
                    r[2].markdown(f"<span class='small-font'>{p['mod']}</span>", unsafe_allow_html=True)
                    r[3].markdown(f"<span class='small-font'>{p['ase']}</span>", unsafe_allow_html=True)
                    with r[4]:
                        btn = "▶️" if not p['ini'] else "🏁"
                        if st.button(btn, key=f"b{p['fila']}"):
                            col = IDX_INICIO + 1 if not p['ini'] else IDX_FIN + 1
                            hoja.update_cell(p['fila'], col, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

            st.write(f"**Terminados ({len(terminados)})**")
            if terminados:
                # ORDEN CRONOLÓGICO: Inicio más temprano primero
                t_sorted = sorted(terminados, key=lambda x: x["ini"])
                c_t = st.columns([0.7, 0.7, 1, 2, 1.2])
                c_t[0].caption("INI"); c_t[1].caption("FIN"); c_t[2].caption("DOM"); c_t[3].caption("MODELO"); c_t[4].caption("ASE")
                
                for t in t_sorted:
                    rt = st.columns([0.7, 0.7, 1, 2, 1.2])
                    rt[0].write(t['ini']); rt[1].write(t['fin'])
                    rt[2].markdown(f"<span class='patente-txt'>{t['dom']}</span>", unsafe_allow_html=True)
                    rt[3].markdown(f"<span class='small-font'>{t['mod']}</span>", unsafe_allow_html=True)
                    rt[4].markdown(f"<span class='small-font'>{t['ase']}</span>", unsafe_allow_html=True)
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        with tab2:
            st.subheader("Indicadores de Gestión")
            k1, k2 = st.columns(2)
            prom = sum(tiempos_lavado)/len(tiempos_lavado) if tiempos_lavado else 0
            with k1: st.markdown(f"<div class='kpi-box'>Lavados: <b>{len(terminados)}</b></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Promedio: <b>{int(prom)} min</b></div>", unsafe_allow_html=True)
            if tiempos_lavado: st.line_chart(tiempos_lavado)

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
