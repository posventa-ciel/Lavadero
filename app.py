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
    .block-container { padding-top: 2rem !important; }
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
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-blue { background-color: #007bff; color: white; }
    .stButton button { height: 26px !important; font-size: 11px !important; }
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

def generar_badge(hora_prom, now_dt, estado):
    if estado == "PAUSA": return f"<div class='badge badge-blue'>{hora_prom}<br>PAUSA</div>"
    if not hora_prom or ":" not in str(hora_prom): return f"<span>{hora_prom}</span>"
    try:
        h, m = map(int, str(hora_prom).split(':'))
        prom_dt = now_dt.replace(hour=h, minute=m, second=0)
        diff = (prom_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prom}<br>ATRASADO</div>"
        if diff <= 30: return f"<div class='badge badge-red'>{hora_prom}<br>YA!</div>"
        if diff <= 60: return f"<div class='badge badge-yellow'>{hora_prom}<br>ALERTA</div>"
        return f"<span>{hora_prom}</span>"
    except: return f"<span>{hora_prom}</span>"

# --- 4. MAIN ---
def main():
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    now = datetime.now(tz)
    
    hoja = conectar_sheet()
    if not hoja: return
    data = hoja.get_all_values()
    
    # ÍNDICES SEGÚN TU IMAGEN
    # A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11, M=12, N=13
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD = 0, 2, 3, 4
    IDX_PRO, IDX_INI, IDX_FIN, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 7, 8, 9, 10, 11, 12, 13

    with st.sidebar:
        st.header("Filtros")
        busqueda = st.text_input("Patente:").upper()
        fecha_sel = st.date_input("Fecha:", now.date())
        mes_hist = st.selectbox("Mes Historial:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=now.month-1)

    pendientes, terminados, historial = [], [], []

    for i, fila in enumerate(data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        
        estado = fila[IDX_EST].strip().upper()
        fecha_fila = fila[IDX_FECHA]
        dom = fila[IDX_DOM].upper()
        
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

        # Lógica de clasificación
        es_hoy = fecha_sel.strftime("%-d/%-m/%Y") in fecha_fila or fecha_sel.strftime("%d/%m/%Y") in fecha_fila
        
        if estado == "FINALIZADO":
            if es_hoy: terminados.append(item)
            # Para el historial mensual
            try:
                f_dt = datetime.strptime(fecha_fila.split()[0], "%d/%m/%Y")
                if f_dt.month == ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_hist) + 1:
                    historial.append(item)
            except: pass
        else:
            if es_hoy or (not tiene_fecha_futura and "202" in fecha_fila): # Simplificado para mostrar pendientes
                pendientes.append(item)

    # --- TABS ---
    t1, t2, t3 = st.tabs(["🚗 Operación", "📊 KPIs", "📅 Historial"])

    with t1:
        st.subheader(f"Pendientes ({len(pendientes)})")
        cols = st.columns([1, 1, 2, 1, 1.5])
        cols[0].caption("PROMETIDO"); cols[1].caption("DOMINIO"); cols[2].caption("MODELO"); cols[3].caption("ASESOR"); cols[4].caption("ACCIONES")
        
        for p in pendientes:
            with st.container():
                c = st.columns([1, 1, 2, 1, 1.5])
                c[0].markdown(generar_badge(p['pro'], now, p['est']), unsafe_allow_html=True)
                c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                c[3].write(p['ase'])
                
                with c[4]:
                    h_act = now.strftime("%H:%M")
                    if not p['ini']:
                        if st.button("▶️ Iniciar", key=f"s{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                    elif p['ini'] and not p['fin']:
                        btn_c = st.columns(2)
                        if btn_c[0].button("⏸️", key=f"p{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                        if btn_c[1].button("🏁", key=f"f{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                    elif p['est'] == "PAUSA":
                        if st.button("🔄 Reanudar", key=f"r{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI2 + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                    elif p['est'] == "REPASO":
                        if st.button("🏁 Finalizar", key=f"f2{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN2 + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader(f"Finalizados Hoy ({len(terminados)})")
        if terminados:
            df_t = pd.DataFrame(terminados)
            st.dataframe(df_t[['ini', 'fin2', 'dom', 'mod', 'ase', 'tiempo']], use_container_width=True)

    with t2:
        st.subheader("Indicadores del Día")
        if terminados:
            df_kpi = pd.DataFrame(terminados)
            m1, m2, m3 = st.columns(3)
            m1.metric("Autos Lavados", len(df_kpi))
            m2.metric("Tiempo Promedio", f"{int(df_kpi['tiempo'].mean())} min")
            m3.metric("Controles OK", len(df_kpi[df_kpi['ok']]))
            
            fig = px.bar(df_kpi['ase'].value_counts(), title="Lavados por Asesor")
            st.plotly_chart(fig)
        else: st.info("Sin datos hoy.")

    with t3:
        st.subheader(f"Histórico {mes_hist}")
        if historial:
            df_h = pd.DataFrame(historial)
            st.write(df_h[['fecha', 'dom', 'mod', 'tiempo']])
            fig_evol = px.line(df_h.groupby('fecha').size().reset_index(name='Cantidad'), x='fecha', y='Cantidad', title="Evolución Mensual")
            st.plotly_chart(fig_evol)
        else: st.info("No hay datos para este mes.")

if __name__ == "__main__":
    main()
