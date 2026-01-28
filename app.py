import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Lavadero", layout="wide")

# --- 2. ESTILOS CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px;
    }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 2px 0; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-size: 12px; }
    .stButton button { height: 26px !important; font-size: 12px !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. CONEXIÓN ---
def conectar_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        key_dict = json.loads(st.secrets["service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
        return client.open_by_url(url).worksheet("PLAN GENERAL")
    except Exception as e:
        st.error(f"Error conectando: {e}"); return None

# --- 4. FUNCIONES AUXILIARES ---
def calcular_tiempo_total(h_ini1, h_fin1, h_ini2, h_fin2):
    total = 0
    fmt = "%H:%M"
    try:
        if h_ini1 and h_fin1:
            total += (datetime.strptime(h_fin1, fmt) - datetime.strptime(h_ini1, fmt)).total_seconds() / 60
    except: pass
    try:
        if h_ini2 and h_fin2:
            total += (datetime.strptime(h_fin2, fmt) - datetime.strptime(h_ini2, fmt)).total_seconds() / 60
    except: pass
    return int(total)

def obtener_minutos_orden(hora_str):
    if not hora_str or ":" not in str(hora_str): return 99999
    try:
        h, m = map(int, str(hora_str).split(':'))
        return h * 60 + m
    except: return 99999

def limpiar_asesor(nombre):
    if not nombre: return ""
    partes = nombre.split()
    return partes[1] if len(partes) > 1 and partes[0].isdigit() else partes[0]

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # MAPEO DE COLUMNAS SEGÚN TU PEDIDO
    # I=8, J=9, K=10, L=11, M=12, N=13
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_PRO = 0, 2, 3, 4, 7
    IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2 = 8, 9, 10, 11
    IDX_EST, IDX_CTRL = 12, 13

    with st.sidebar:
        st.markdown("### ⚙️ Filtros")
        busqueda = st.text_input("Patente:", "").upper()
        fecha_sel = st.date_input("Fecha Operación:", hoy_date)
        mes_sel = st.selectbox("Mes Historial:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=hoy_date.month-1)

    f_str = fecha_sel.strftime("%-d/%-m/%Y")
    f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    st.markdown(f'<div class="header-box"><div class="header-title">LAVADERO | PANEL DE CONTROL</div><div style="text-align: right;"><b>{fecha_sel.strftime("%d/%m/%Y")}</b><br>{hora_actual} hs</div></div>', unsafe_allow_html=True)

    pendientes, terminados_hoy, historico_mes = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        
        f_celda = fila[IDX_FECHA]
        dom = fila[IDX_DOM].upper()
        estado = fila[IDX_EST].strip().upper()
        
        if not dom or any(x in fila[IDX_PRO].upper() for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue

        # Cálculo con las nuevas columnas I, J, K, L
        tiempo_lavado = calcular_tiempo_total(fila[IDX_INI1], fila[IDX_FIN1], fila[IDX_INI2], fila[IDX_FIN2])

        item = {
            "fila": i, "fecha": f_celda, "dom": dom, "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1], 
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2],
            "est": estado, "ok": (fila[IDX_CTRL].upper() == "OK"), "min_lavado": tiempo_lavado
        }

        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        es_atrasado = False
        try:
            f_dt = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").date()
            if f_dt < fecha_sel: es_atrasado = True
        except: pass

        if (busqueda == "" or busqueda in dom):
            if estado == "FINALIZADO":
                if es_de_fecha or (es_atrasado and fecha_sel == hoy_date):
                    terminados_hoy.append(item)
            elif es_de_fecha or es_atrasado:
                pendientes.append(item)

        try:
            meses_dic = {"Enero":1,"Febrero":2,"Marzo":3,"Abril":4,"Mayo":5,"Junio":6,"Julio":7,"Agosto":8,"Septiembre":9,"Octubre":10,"Noviembre":11,"Diciembre":12}
            f_dt_hist = datetime.strptime(f_celda.split()[0], "%d/%m/%Y")
            if f_dt_hist.month == meses_dic[mes_sel] and f_dt_hist.year == hoy_date.year and estado == "FINALIZADO":
                historico_mes.append(item)
        except: pass

    tab1, tab2, tab3 = st.tabs(["🚗 Operación", "📊 KPIs", "📅 Historial"])

    with tab1:
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        for p in pendientes:
            with st.container():
                c = st.columns([1, 1, 2, 1, 1.5])
                c[0].write(p['pro'])
                c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                c[3].write(p['ase'])
                with c[4]:
                    # Lógica de botones con índices corregidos
                    if not p['ini']:
                        if st.button("▶️", key=f"s{p['fila']}", type="primary"):
                            hoja.update_cell(p['fila'], IDX_INI1+1, hora_actual)
                            hoja.update_cell(p['fila'], IDX_EST+1, "LAVANDO"); st.rerun()
                    elif p['ini'] and not p['fin']:
                        cb = st.columns(2)
                        if cb[0].button("🏁", key=f"f{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN1+1, hora_actual)
                            hoja.update_cell(p['fila'], IDX_EST+1, "FINALIZADO"); st.rerun()
                        if cb[1].button("⏸️", key=f"p{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN1+1, hora_actual)
                            hoja.update_cell(p['fila'], IDX_EST+1, "PAUSA"); st.rerun()
                    elif p['est'] == "PAUSA":
                        if st.button("🔄", key=f"r{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI2+1, hora_actual)
                            hoja.update_cell(p['fila'], IDX_EST+1, "REPASO"); st.rerun()
                    elif p['est'] == "REPASO":
                         if st.button("🏁 ", key=f"f2{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN2+1, hora_actual)
                            hoja.update_cell(p['fila'], IDX_EST+1, "FINALIZADO"); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)
        
        st.markdown(f"<br>**Finalizados ({len(terminados_hoy)})**", unsafe_allow_html=True)
        for t in terminados_hoy:
            with st.container():
                r = st.columns([1, 1, 1, 2, 1])
                r[0].write(t['ini'])
                r[1].write(t['fin2'] if t['fin2'] else t['fin'])
                r[2].write(t['dom']); r[3].write(t['mod']); r[4].write("✅" if t['ok'] else "⏳")
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        if terminados_hoy:
            df_kpi = pd.DataFrame(terminados_hoy)
            avg_time = int(df_kpi['min_lavado'].mean())
            k1, k2, k3 = st.columns(3)
            k1.metric("Autos Lavados", len(df_kpi))
            k2.metric("Tiempo Promedio Total", f"{avg_time} min")
            k3.metric("Control OK", f"{len(df_kpi[df_kpi['ok'] == True])}")
            
            st.plotly_chart(px.bar(df_kpi['ase'].value_counts(), title="Lavados por Asesor"), use_container_width=True)
        else:
            st.info("Sin datos para KPIs hoy.")

    with tab3:
        if historico_mes:
            df_hist = pd.DataFrame(historico_mes)
            df_hist['Día'] = df_hist['fecha'].apply(lambda x: x.split()[0])
            resumen = df_hist.groupby('Día').agg(Cantidad=('dom', 'count'), Promedio=('min_lavado', 'mean')).reset_index()
            st.dataframe(resumen, use_container_width=True)
            st.plotly_chart(px.line(resumen, x='Día', y='Cantidad', title="Evolución Mensual"), use_container_width=True)

if __name__ == "__main__":
    main()
