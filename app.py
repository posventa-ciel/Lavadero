import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro", layout="wide")

# --- ESTILOS COMPACTOS (Más chicos para que entre todo) ---
st.markdown("""
<style>
    .main-title { font-size: 18px !important; font-weight: bold; color: #00235d; margin: 0; }
    .fila-tabla { padding: 2px 0; border-bottom: 1px solid #eee; font-size: 0.75em; line-height: 1.1; }
    .hora-txt { font-weight: bold; color: #d32f2f; font-size: 0.8em; }
    .patente-txt { font-weight: bold; color: #1565c0; font-size: 0.8em; }
    .small-font { font-size: 0.75em; color: #444; }
    .stButton button { height: 22px; font-size: 0.65em; padding: 0px 4px; margin: 0; }
    .header-container { display: flex; align-items: center; gap: 10px; margin-bottom: 5px; border-bottom: 2px solid #00235d; }
    caption { font-size: 0.7em !important; font-weight: bold; color: #333; }
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

def main():
    # --- IMAGEN DESDE GITHUB ---
    # REEMPLAZA ESTE LINK por el tuyo de GitHub (el link "Raw")
    url_imagen_github = "https://raw.githubusercontent.com/tunombre/turepo/main/peugeot_lavado.png"
    
    st.markdown(f"""
    <div class="header-container">
        <img src="{url_imagen_github}" width="80" onerror="this.src='https://img.icons8.com/fluency/48/car-wash.png'">
        <h1 class="main-title">LAVADERO POSTVENTA - CONTROL DE CALIDAD</h1>
    </div>
    """, unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo: A=0, C=2, D=3, E=4, H=7, I=8, J=9, K=10 (Calidad)
        IDX_FECHA, IDX_ASESOR, IDX_DOMINIO = 0, 2, 3
        IDX_MODELO, IDX_PROMETIDO, IDX_INICIO, IDX_FIN, IDX_CALIDAD = 4, 7, 8, 9, 10

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        with st.sidebar:
            st.header("⚙️ Filtros")
            fecha_sel = st.date_input("Día:", hoy_dt.date())
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación Diaria", "📊 KPIs"])

        pendientes, terminados = [], []
        tiempos_lavado = []

        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 11: fila += [""] * (11 - len(fila))
            
            p_val = fila[IDX_PROMETIDO].upper()
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in p_val or "NO VINO" in p_val:
                continue

            f_celda = fila[IDX_FECHA]
            es_dia = f_str in f_celda or f_str_cero in f_celda or f_str in p_val or f_str_cero in p_val
            
            if es_dia or (not fila[IDX_FIN] and "PENDIENTE"): # Lógica simplificada de arrastre
                item = {
                    "fila": i, "dom": fila[IDX_DOMINIO], "mod": fila[IDX_MODELO],
                    "ase": fila[IDX_ASESOR], "pro": p_val,
                    "ini": fila[IDX_INICIO], "fin": fila[IDX_FIN], "ok": fila[IDX_CALIDAD]
                }
                if item["fin"]:
                    terminados.append(item)
                    try:
                        t1 = datetime.strptime(item["ini"], "%H:%M")
                        t2 = datetime.strptime(item["fin"], "%H:%M")
                        tiempos_lavado.append(int((t2 - t1).total_seconds() / 60))
                    except: pass
                else:
                    pendientes.append(item)

        with tab1:
            # --- PENDIENTES ---
            st.write(f"**Pendientes ({len(pendientes)})**")
            if pendientes:
                c = st.columns([0.8, 1, 2, 1.2, 0.5])
                c[0].caption("PROMETIDO"); c[1].caption("DOMINIO"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACC")
                for p in pendientes:
                    r = st.columns([0.8, 1, 2, 1.2, 0.5])
                    r[0].markdown(f"<span class='hora-txt'>{p['pro']}</span>", unsafe_allow_html=True)
                    r[1].markdown(f"<span class='patente-txt'>{p['dom']}</span>", unsafe_allow_html=True)
                    r[2].markdown(f"<span class='small-font'>{p['mod']}</span>", unsafe_allow_html=True)
                    r[3].markdown(f"<span class='small-font'>{p['ase']}</span>", unsafe_allow_html=True)
                    with r[4]:
                        btn = "▶️" if not p['ini'] else "🏁"
                        if st.button(btn, key=f"p{p['fila']}"):
                            col = IDX_INICIO + 1 if not p['ini'] else IDX_FIN + 1
                            hoja.update_cell(p['fila'], col, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

            # --- TERMINADOS ---
            st.write(f"**Terminados ({len(terminados)})**")
            if terminados:
                t_sorted = sorted(terminados, key=lambda x: x["ini"])
                c_t = st.columns([0.6, 0.6, 0.8, 1.5, 1, 0.6])
                c_t[0].caption("INICIO"); c_t[1].caption("FIN"); c_t[2].caption("DOMINIO"); 
                c_t[3].caption("MODELO"); c_t[4].caption("ASESOR"); c_t[5].caption("CALIDAD")
                
                for t in t_sorted:
                    rt = st.columns([0.6, 0.6, 0.8, 1.5, 1, 0.6])
                    rt[0].write(t['ini']); rt[1].write(t['fin'])
                    rt[2].markdown(f"<span class='patente-txt'>{t['dom']}</span>", unsafe_allow_html=True)
                    rt[3].markdown(f"<span class='small-font'>{t['mod']}</span>", unsafe_allow_html=True)
                    rt[4].markdown(f"<span class='small-font'>{t['ase']}</span>", unsafe_allow_html=True)
                    with rt[5]:
                        if not t['ok']:
                            if st.button("OK", key=f"ok{t['fila']}"):
                                hoja.update_cell(t['fila'], IDX_CALIDAD + 1, "OK")
                                st.rerun()
                        else:
                            st.success("✅")
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        with tab2:
            st.subheader("KPI Lavadero")
            if tiempos_lavado:
                prom = sum(tiempos_lavado)/len(tiempos_lavado)
                st.metric("Promedio de Lavado", f"{int(prom)} min")
                st.line_chart(tiempos_lavado)

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
