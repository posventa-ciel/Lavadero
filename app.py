import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

# --- 2. ESTILOS CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px 20px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .header-title { font-size: 24px; font-weight: bold; text-transform: uppercase; margin: 0; }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 2px 0 !important; margin: 0 !important; line-height: 1.2 !important; }
    p { margin: 0 !important; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 13px; }
    .txt-truncado { color: #333; font-weight: 500; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; width: 100%; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; min-width: 70px; display: inline-block; line-height: 1.1; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-ok { background-color: #2e7d32; color: white; font-weight: bold; font-size: 11px; }
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

def calcular_tiempo_neto(item):
    try:
        fmt = "%H:%M"
        t1 = 0
        if item['ini'] and item['fin']:
            t1 = (datetime.strptime(item['fin'], fmt) - datetime.strptime(item['ini'], fmt)).total_seconds() / 60
        t2 = 0
        if item['ini2'] and item['fin2']:
            t2 = (datetime.strptime(item['fin2'], fmt) - datetime.strptime(item['ini2'], fmt)).total_seconds() / 60
        return max(0, int(t1 + t2))
    except: return 0

def generar_badge_alerta(hora_prometida, now_dt):
    if not hora_prometida or ":" not in str(hora_prometida): return f"<span>{hora_prometida}</span>"
    try:
        h, m = map(int, str(hora_prometida).split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prometida}<br>DEMORADO</div>"
        elif diff <= 30: return f"<div class='badge badge-red'>{hora_prometida}<br>YA!</div>"
        elif diff <= 60: return f"<div class='badge badge-yellow'>{hora_prometida}<br>ATENCIÓN</div>"
        return f"<b>{hora_prometida}</b>"
    except: return f"<span>{hora_prometida}</span>"

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()
    hoy_str = hoy_date.strftime("%d/%m/%Y")

    st.markdown(f'<div class="header-box"><div class="header-title">PROGRAMACIÓN LAVADERO</div><div style="text-align: right;"><div style="font-size: 16px; font-weight: 700;">{hoy_date.strftime("%d/%m/%Y")}</div><div style="font-size: 14px; opacity: 0.8;">{hora_actual} hs</div></div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # IDX_FECHA_FIN es la columna O (Indice 14)
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_CLI, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL, IDX_FECHA_FIN = 0, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14

    with st.sidebar:
        st.markdown("### 🔍 Buscar Patente")
        busqueda = st.text_input("", placeholder="Ej: AB123CD", label_visibility="collapsed").upper()
        st.markdown("---")
        fecha_sel = st.date_input("Ver fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes, finalizados_ver = [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 15: fila += [""] * (15 - len(fila))
        dom = fila[IDX_DOM].upper()
        pro_raw = fila[IDX_PRO].upper()
        
        if not dom or any(x in pro_raw for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue
        if busqueda and busqueda not in dom: continue

        f_celda = fila[IDX_FECHA]
        f_fin_celda = fila[IDX_FECHA_FIN]
        estado = fila[IDX_EST].strip().upper()
        es_de_fecha_seleccionada = (f_str in f_celda) or (f_str_cero in f_celda)
        tiene_hora_fin = fila[IDX_FIN1].strip() != "" or fila[IDX_FIN2].strip() != ""

        es_atrasado = False
        try:
            f_dt = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").date()
            if f_dt < fecha_sel: es_atrasado = True
        except: pass

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "cli": fila[IDX_CLI], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado, 
            "ok": fila[IDX_CTRL].strip().upper() in ["SI", "OK"], "atr": es_atrasado,
            "min_orden": obtener_minutos_orden(fila[IDX_PRO]), "fecha": f_celda, "fecha_fin_real": f_fin_celda
        }

        # --- CLASIFICACIÓN CON FILTRO DE FECHA DE FINALIZACIÓN ---
        if not tiene_hora_fin or estado in ["PAUSA", "REPASO"]:
            if es_de_fecha_seleccionada or es_atrasado:
                pendientes.append(item)
        else:
            if es_de_fecha_seleccionada:
                finalizados_ver.append(item)
            elif fecha_sel == hoy_date and f_fin_celda == hoy_str:
                finalizados_ver.append(item)

    tab1, tab2, tab3 = st.tabs(["🚗 Operación", "📊 Métricas Hoy", "📅 Historial"])

    with tab1:
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        if pendientes:
            pendientes.sort(key=lambda x: (not x["atr"], x["min_orden"]))
            cols_p = [0.8, 0.8, 1.4, 1.4, 0.8, 1.2]
            h_p = st.columns(cols_p)
            h_p[0].caption("ESTADO"); h_p[1].caption("DOMINIO"); h_p[2].caption("CLIENTE"); h_p[3].caption("MODELO"); h_p[4].caption("ASESOR"); h_p[5].caption("ACCIONES")

            for p in pendientes:
                with st.container():
                    c = st.columns(cols_p)
                    if p['est'] == "PAUSA":
                        badge = f"<div class='badge' style='background-color: #6c757d; color: white;'>{p['pro']}<br>PAUSADO</div>"
                    elif p['est'] == "REPASO":
                        badge = f"<div class='badge' style='background-color: #17a2b8; color: white;'>{p['pro']}<br>REPASO</div>"
                    else:
                        badge = f"<div class='badge badge-red'>{p['pro']}<br>ATRASADO</div>" if p['atr'] else generar_badge_alerta(p['pro'], now_dt)
                    
                    c[0].markdown(badge, unsafe_allow_html=True)
                    c[1].markdown(f"<b>{p['dom']}</b>", unsafe_allow_html=True)
                    c[2].markdown(f"<span class='txt-truncado'>{p['cli']}</span>", unsafe_allow_html=True)
                    c[3].markdown(f"<span class='txt-truncado'>{p['mod']}</span>", unsafe_allow_html=True)
                    c[4].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    with c[5]:
                        if not p['ini']:
                            if st.button("▶️", key=f"s{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INI1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                        elif p['ini'] and (p['est'] not in ["PAUSA", "REPASO", "FINALIZADO"]):
                            cb = st.columns(2)
                            if cb[0].button("⏸️", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                            if cb[1].button("🏁", key=f"f{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO")
                                hoja.update_cell(p['fila'], IDX_FECHA_FIN + 1, hoy_str); st.rerun()
                        elif p['est'] == "PAUSA":
                            if st.button("🔄", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                        elif p['est'] == "REPASO":
                            if st.button("🏁", key=f"f2{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO")
                                hoja.update_cell(p['fila'], IDX_FECHA_FIN + 1, hoy_str); st.rerun()
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        st.markdown(f"**Finalizados ({len(finalizados_ver)})**")
        if finalizados_ver:
            finalizados_ver.sort(key=lambda x: obtener_minutos_orden(x['ini']))
            cols_f = [0.5, 0.5, 0.5, 0.8, 1.4, 1.4, 0.7, 1.2]
            h_f = st.columns(cols_f)
            h_f[0].caption("INI"); h_f[1].caption("FIN"); h_f[2].caption("T."); h_f[3].caption("DOM"); h_f[4].caption("CLIENTE"); h_f[5].caption("MODELO"); h_f[6].caption("ASESOR"); h_f[7].caption("ESTADO")
            for t in finalizados_ver:
                t['min_total'] = calcular_tiempo_neto(t)
                with st.container():
                    r = st.columns(cols_f)
                    r[0].write(t['ini']); r[1].write(t['fin2'] if t['fin2'] else t['fin']); r[2].write(f"{t['min_total']}'")
                    r[3].markdown(f"<b>{t['dom']}</b>", unsafe_allow_html=True)
                    r[4].markdown(f"<span class='txt-truncado'>{t['cli']}</span>", unsafe_allow_html=True)
                    r[5].markdown(f"<span class='txt-truncado'>{t['mod']}</span>", unsafe_allow_html=True)
                    r[6].markdown(f"<span class='txt-asesor'>{t['ase']}</span>", unsafe_allow_html=True)
                    with r[7]:
                        c_chk, c_txt = st.columns([0.3, 0.7])
                        with c_chk:
                            nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                            if nk != t['ok']:
                                hoja.update_cell(t['fila'], IDX_CTRL + 1, "SI" if nk else ""); st.rerun()
                        with c_txt:
                            if t['ok']: st.markdown("<span class='badge badge-ok'>ENTREGADO</span>", unsafe_allow_html=True)
                            else: st.markdown(generar_badge_alerta(t['pro'], now_dt), unsafe_allow_html=True)
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        st.subheader("Resumen de Hoy")
        if finalizados_ver:
            df_hoy = pd.DataFrame(finalizados_ver)
            df_hoy['minutos'] = df_hoy.apply(calcular_tiempo_neto, axis=1)
            c1, c2, c3 = st.columns(3)
            c1.metric("Lavados", len(df_hoy))
            c2.metric("Promedio Real", f"{int(df_hoy['minutos'].mean())} min")
            c3.metric("Max Lavado", f"{df_hoy['minutos'].max()} min")
            col_g1, col_g2 = st.columns(2)
            with col_g1: st.plotly_chart(px.bar(df_hoy, x='dom', y='minutos', color='minutos', title="Tiempo Neto (min)"), use_container_width=True)
            with col_g2: st.plotly_chart(px.pie(df_hoy, names='ase', title="Lavados por Asesor"), use_container_width=True)
        else: st.info("Sin datos de hoy.")

    with tab3:
        st.subheader("📅 Historial Mensual")
        hist_list = []
        for f in raw_data[1:]:
            if len(f) >= 12 and f[IDX_FIN1] and f[IDX_INI1]:
                try:
                    f_dt = datetime.strptime(f[IDX_FECHA].split()[0], "%d/%m/%Y")
                    item_h = {'ini': f[IDX_INI1], 'fin': f[IDX_FIN1], 'ini2': f[IDX_INI2], 'fin2': f[IDX_FIN2]}
                    m = calcular_tiempo_neto(item_h)
                    hist_list.append({"Fecha": f_dt, "Mes": f_dt.strftime("%Y-%m"), "Mins": max(0, int(m))})
                except: continue
        if hist_list:
            df_h = pd.DataFrame(hist_list)
            m_sel = st.selectbox("Seleccionar Mes:", sorted(df_h['Mes'].unique(), reverse=True))
            df_m = df_h[df_h['Mes'] == m_sel].groupby('Fecha').agg(Lavados=('Fecha','count'), Promedio=('Mins','mean')).reset_index()
            df_m['Fecha_str'] = df_m['Fecha'].dt.strftime('%d/%m')
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Bar(x=df_m['Fecha_str'], y=df_m['Lavados'], name='Autos', marker_color='#00235d', yaxis='y'))
            fig_hist.add_trace(go.Scatter(x=df_m['Fecha_str'], y=df_m['Promedio'], name='Promedio', line=dict(color='#fbc02d', width=4), yaxis='y2'))
            fig_hist.update_layout(yaxis=dict(title="Autos"), yaxis2=dict(title="Minutos", overlaying="y", side="right"), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_hist, use_container_width=True)
            st.dataframe(df_m.sort_values('Fecha', ascending=False).assign(Fecha=lambda x: x['Fecha'].dt.strftime('%d/%m/%Y'), Promedio=lambda x: x['Promedio'].round(1).astype(str)+" min")[['Fecha', 'Lavados', 'Promedio']], hide_index=True, use_container_width=True)

if __name__ == "__main__":
    main()
