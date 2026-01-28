import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

# --- 2. ESTILOS CSS (ESTILO COMPACTO ORIGINAL) ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px 20px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .header-title { font-size: 24px; font-weight: bold; text-transform: uppercase; margin: 0; }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 2px 0 !important; margin: 0 !important; line-height: 1 !important; }
    p { margin: 0 !important; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; min-width: 70px; display: inline-block; line-height: 1.1; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-blue { background-color: #007bff; color: white; }
    .badge-normal { color: #333; font-weight: bold; font-size: 13px; }
    .badge-ok { color: #2e7d32; font-weight: bold; font-size: 12px; }
    .stButton button { height: 24px !important; min-height: 24px !important; font-size: 11px !important; padding: 0 8px !important; margin: 1px 0 !important; }
    div[data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    div[data-testid="column"] { padding: 0 !important; }
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

def generar_badge_alerta(hora_prometida, now_dt, estado):
    if estado == "PAUSA": return f"<div class='badge badge-blue'>{hora_prometida}<br>PAUSA</div>"
    if not hora_prometida or ":" not in str(hora_prometida): return f"<span class='badge-normal'>{hora_prometida}</span>"
    try:
        h, m = map(int, str(hora_prometida).split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prometida}<br>DEMORADO</div>"
        elif diff <= 30: return f"<div class='badge badge-red'>{hora_prometida}<br>YA!</div>"
        elif diff <= 60: return f"<div class='badge badge-yellow'>{hora_prometida}<br>ATENCIÓN</div>"
        return f"<span class='badge-normal'>{hora_prometida}</span>"
    except: return f"<span class='badge-normal'>{hora_prometida}</span>"

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()

    st.markdown(f'<div class="header-box"><div class="header-title">PROGRAMACIÓN LAVADERO</div><div style="text-align: right;"><div style="font-size: 16px; font-weight: 700;">{hoy_date.strftime("%d/%m/%Y")}</div><div style="font-size: 14px; opacity: 0.8;">{hora_actual} hs</div></div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # ÍNDICES SEGÚN TU PLANILLA: H=7, I=8, J=9, K=10, L=11, M=12, N=13
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_PRO, IDX_INI, IDX_FIN, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13

    with st.sidebar:
        st.markdown("### 🔍 Filtros")
        busqueda = st.text_input("Patente:", placeholder="Ej: AB123CD").upper()
        fecha_sel = st.date_input("Ver fecha:", hoy_date)
        mes_historial = st.selectbox("Mes Historial:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=hoy_date.month-1)

    pendientes, terminados_hoy, historico_mes = [], [], []
    f_str = fecha_sel.strftime("%-d/%-m/%Y")
    f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        
        dom = fila[IDX_DOM].upper()
        if not dom or "NO SE LAVA" in fila[IDX_PRO].upper(): continue
        if busqueda and busqueda not in dom: continue

        f_celda = fila[IDX_FECHA]
        estado = fila[IDX_EST].strip().upper()
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        
        # CLAVE: Un auto solo se considera finalizado si el estado dice FINALIZADO
        es_finalizado = (estado == "FINALIZADO")

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI], "fin": fila[IDX_FIN],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado, 
            "ok": (fila[IDX_CTRL].strip().upper() == "OK"),
            "min_orden": obtener_minutos_orden(fila[IDX_PRO]),
            "tiempo": calcular_minutos_totales(fila[IDX_INI], fila[IDX_FIN], fila[IDX_INI2], fila[IDX_FIN2]),
            "fecha": f_celda
        }

        if es_finalizado:
            if es_de_fecha: terminados_hoy.append(item)
            try:
                mes_num = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").month
                meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                if meses[mes_num-1] == mes_historial: historico_mes.append(item)
            except: pass
        else:
            if es_de_fecha or "202" in f_celda: pendientes.append(item)

    tab1, tab2, tab3 = st.tabs(["🚗 Operación", "📊 KPIs", "📅 Historial"])

    with tab1:
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        cols_tit_p = [0.8, 0.8, 2, 0.8, 1.4]
        tp = st.columns(cols_tit_p)
        tp[0].caption("PROMETIDO"); tp[1].caption("DOMINIO"); tp[2].caption("MODELO"); tp[3].caption("ASESOR"); tp[4].caption("ACCIONES")
        
        if pendientes:
            pendientes.sort(key=lambda x: x["min_orden"])
            for p in pendientes:
                with st.container():
                    c = st.columns(cols_tit_p)
                    c[0].markdown(generar_badge_alerta(p['pro'], now_dt, p['est']), unsafe_allow_html=True)
                    c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                    c[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    
                    with c[4]:
                        if not p['ini']:
                            if st.button("▶️", key=f"s{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INI + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                        elif p['ini'] and not p['fin']:
                            cb = st.columns(2)
                            if cb[0].button("⏸️", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                            if cb[1].button("🏁", key=f"f{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                        elif p['est'] == "PAUSA":
                            if st.button("🔄", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                        elif p['est'] == "REPASO":
                            if st.button("🏁", key=f"f2{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("<br>**Finalizados del día**", unsafe_allow_html=True)
        if terminados_hoy:
            cols_f = [0.6, 0.6, 0.8, 1.5, 0.8, 1.2]
            tf = st.columns(cols_f)
            tf[0].caption("INI"); tf[1].caption("FIN"); tf[2].caption("DOM"); tf[3].caption("MODELO"); tf[4].caption("ASESOR"); tf[5].caption("CONTROL")
            for t in terminados_hoy:
                r = st.columns(cols_f)
                r[0].write(t['ini'])
                r[1].write(t['fin2'] if t['fin2'] else t['fin'])
                r[2].markdown(f"<span class='txt-patente'>{t['dom']}</span>", unsafe_allow_html=True)
                r[3].markdown(f"<span class='txt-modelo'>{t['mod']}</span>", unsafe_allow_html=True)
                r[4].markdown(f"<span class='txt-asesor'>{t['ase']}</span>", unsafe_allow_html=True)
                with r[5]:
                    c_chk, c_txt = st.columns([0.3, 0.7])
                    with c_chk:
                        nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                        if nk != t['ok']:
                            hoja.update_cell(t['fila'], IDX_CTRL + 1, "OK" if nk else ""); st.rerun()
                    with c_txt:
                        st.markdown("<span class='badge-ok'>OK</span>" if t['ok'] else "—", unsafe_allow_html=True)
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        if terminados_hoy:
            df_k = pd.DataFrame(terminados_hoy)
            m1, m2, m3 = st.columns(3)
            m1.metric("Lavados", len(df_k))
            m2.metric("Promedio", f"{int(df_k['tiempo'].mean())} min")
            m3.metric("Calidad OK", len(df_k[df_k['ok']]))
            st.plotly_chart(px.bar(df_k['ase'].value_counts(), title="Lavados por Asesor"), use_container_width=True)
        else: st.info("Sin datos para KPIs hoy.")

    with tab3:
        if historico_mes:
            df_h = pd.DataFrame(historico_mes)
            st.dataframe(df_h[['fecha', 'dom', 'mod', 'ase', 'tiempo']], use_container_width=True)
            st.plotly_chart(px.line(df_h.groupby('fecha').size().reset_index(name='Cant'), x='fecha', y='Cant', title="Evolución"), use_container_width=True)
        else: st.info(f"Sin historial para {mes_historial}.")

if __name__ == "__main__":
    main()
