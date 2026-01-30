import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Integral Lavadero y Taller", layout="wide")

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
    .badge-ok { background-color: #2e7d32; color: white; font-weight: bold; font-size: 11px; padding: 3px 6px; border-radius: 4px; }
    .status-badge { padding: 3px 8px; border-radius: 5px; font-weight: bold; font-size: 12px; }
    .bg-danger { background-color: #f8d7da; color: #721c24; }
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
def limpiar_asesor(nombre):
    if not nombre: return ""
    partes = nombre.split()
    return partes[1] if len(partes) > 1 and partes[0].isdigit() else partes[0]

def calcular_tiempo_neto(item):
    try:
        fmt = "%H:%M"
        t1 = (datetime.strptime(item['fin'], fmt) - datetime.strptime(item['ini'], fmt)).total_seconds() / 60 if item['ini'] and item['fin'] else 0
        t2 = (datetime.strptime(item['fin2'], fmt) - datetime.strptime(item['ini2'], fmt)).total_seconds() / 60 if item['ini2'] and item['fin2'] else 0
        return max(0, int(t1 + t2))
    except: return 0

def generar_badge_alerta(hora_prometida, now_dt):
    if not hora_prometida or ":" not in str(hora_prometida): return f"<span>{hora_prometida}</span>"
    try:
        h, m = map(int, str(hora_prometida).split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: color, txt = "#d32f2f", "DEMORADO"
        elif diff <= 30: color, txt = "#d32f2f", "YA!"
        elif diff <= 60: color, txt = "#fbc02d", "ATENCIÓN"
        else: return f"<b>{hora_prometida}</b>"
        return f"<div style='background-color:{color};color:white;padding:2px 5px;border-radius:4px;font-size:10px;text-align:center;'>{hora_prometida}<br>{txt}</div>"
    except: return f"<span>{hora_prometida}</span>"

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date, hoy_str = now_dt.date(), now_dt.strftime("%d/%m/%Y")

    st.markdown(f'<div class="header-box"><div class="header-title">CONTROL INTEGRAL TALLER</div><div style="text-align: right;"><div style="font-size: 16px; font-weight: 700;">{hoy_str}</div><div style="font-size: 14px; opacity: 0.8;">{hora_actual} hs</div></div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # ÍNDICES GLOBALES
    IDX_FECHA, IDX_ING_DMS, IDX_ASE, IDX_DOM, IDX_MOD, IDX_CLI, IDX_TRABAJO, IDX_PRO = 0, 1, 2, 3, 4, 5, 6, 7
    IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL, IDX_FECHA_FIN, IDX_RECUPERO = 8, 9, 10, 11, 12, 13, 14, 15

    with st.sidebar:
        st.markdown("### 🔍 Filtros")
        busqueda = st.text_input("Buscar Patente:").upper()
        fecha_sel = st.date_input("Fecha:", hoy_date)
        f_str, f_str_cero = fecha_sel.strftime("%-d/%-m/%Y"), fecha_sel.strftime("%d/%m/%Y")

    pendientes, finalizados_ver, turnos_hoy = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 16: fila += [""] * (16 - len(fila))
        f_celda = fila[IDX_FECHA]
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        if not es_de_fecha: continue
        dom = fila[IDX_DOM].upper()
        if not dom or (busqueda and busqueda not in dom): continue

        # --- PROCESAMIENTO TURNOS TALLER ---
        hora_b = fila[IDX_ING_DMS].strip()
        if hora_b != "":
            prometido, trabajo_g = fila[IDX_PRO].upper(), fila[IDX_TRABAJO].upper()
            vino = not ("NO VINO" in prometido or "NO VINO" in trabajo_g)
            palabras_serv = ["SERV", "KM", "10K", "20K", "30K", "40K", "50K", "60K", "70K", "80K", "90K", "100K", "MANT"]
            es_serv = any(x in trabajo_g for x in palabras_serv)
            turnos_hoy.append({"fila": i, "dom": dom, "cli": fila[IDX_CLI], "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]), "dms": (hora_b != "13:00"), "vino": vino, "serv": es_serv, "rec": (fila[IDX_RECUPERO].upper() == "SI")})

        # --- PROCESAMIENTO LAVADERO ---
        item_lav = {"fila": i, "dom": dom, "mod": fila[IDX_MOD], "cli": fila[IDX_CLI], "ase": limpiar_asesor(fila[IDX_ASE]), "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1], "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": fila[IDX_EST].upper(), "ok": fila[IDX_CTRL].upper() in ["SI", "OK"], "f_fin": fila[IDX_FECHA_FIN]}
        if not (fila[IDX_FIN1] or fila[IDX_FIN2]) or item_lav['est'] in ["PAUSA", "REPASO"]:
            pendientes.append(item_lav)
        elif es_de_fecha or (fecha_sel == hoy_date and item_lav['f_fin'] == hoy_str):
            finalizados_ver.append(item_lav)

    tab1, tab2, tab3, tab4 = st.tabs(["🚗 Operación", "📊 Métricas Hoy", "📅 Historial", "📈 Eficiencia Turnos"])

    with tab1:
        st.subheader(f"Pendientes ({len(pendientes)})")
        for p in pendientes:
            with st.container():
                c = st.columns([0.8, 0.8, 1.4, 1.4, 0.8, 1.2])
                c[0].markdown(generar_badge_alerta(p['pro'], now_dt), unsafe_allow_html=True)
                c[1].write(f"**{p['dom']}**")
                c[2].write(f"<small>{p['cli']}</small>", unsafe_allow_html=True); c[3].write(f"<small>{p['mod']}</small>", unsafe_allow_html=True); c[4].write(p['ase'])
                with c[5]:
                    if not p['ini']:
                        if st.button("▶️", key=f"s{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI1+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "LAVANDO"); st.rerun()
                    elif not (p['fin'] or p['fin2']):
                        if st.button("🏁", key=f"f{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN1+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "FINALIZADO"); hoja.update_cell(p['fila'], IDX_FECHA_FIN+1, hoy_str); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)
        st.subheader(f"Finalizados ({len(finalizados_ver)})")
        for t in finalizados_ver:
            with st.container():
                r = st.columns([0.6, 0.6, 0.6, 0.8, 1.4, 1.4, 0.8, 1.2])
                r[0].write(t['ini']); r[1].write(t['fin'] if t['fin'] else t['fin2']); r[2].write(f"{calcular_tiempo_neto(t)}'"); r[3].write(f"**{t['dom']}**")
                r[4].write(f"<small>{t['cli']}</small>", unsafe_allow_html=True); r[5].write(f"<small>{t['mod']}</small>", unsafe_allow_html=True); r[6].write(t['ase'])
                with r[7]:
                    c_chk, c_txt = st.columns([0.3, 0.7])
                    with c_chk:
                        nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                        if nk != t['ok']: hoja.update_cell(t['fila'], IDX_CTRL+1, "SI" if nk else ""); st.rerun()
                    c_txt.markdown("<span class='badge-ok'>ENTREGADO</span>" if t['ok'] else "", unsafe_allow_html=True)
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        if finalizados_ver:
            df_m = pd.DataFrame(finalizados_ver); df_m['minutos'] = df_m.apply(calcular_tiempo_neto, axis=1)
            c1, c2, c3 = st.columns(3); c1.metric("Lavados", len(df_m)); c2.metric("Promedio", f"{int(df_m['minutos'].mean())} min"); c3.metric("Max", f"{df_m['minutos'].max()} min")
            st.plotly_chart(px.bar(df_m, x='dom', y='minutos', title="Tiempo Neto por Patente"), use_container_width=True)

    with tab3:
        # Aquí procesamos el selector de mes y los datos históricos
        hist_list = []
        for f in raw_data[1:]:
            if len(f) >= 12 and f[IDX_FECHA]:
                try:
                    f_dt = datetime.strptime(f[IDX_FECHA].split()[0], "%d/%m/%Y")
                    hist_list.append({"Fecha": f_dt, "Mes": f_dt.strftime("%Y-%m"), "Mins": calcular_tiempo_neto({'ini':f[IDX_INI1],'fin':f[IDX_FIN1],'ini2':f[IDX_INI2],'fin2':f[IDX_FIN2]})})
                except: continue
        if hist_list:
            df_h = pd.DataFrame(hist_list); m_sel = st.selectbox("Mes:", sorted(df_h['Mes'].unique(), reverse=True))
            df_mh = df_h[df_h['Mes'] == m_sel].groupby('Fecha').size().reset_index(name='Autos')
            st.plotly_chart(px.line(df_mh, x='Fecha', y='Autos', title="Evolución Lavados"), use_container_width=True)
            # Resumen Taller Mensual
            st.markdown("---"); st.subheader("📊 Historial Taller")
            t_mes = []
            for f in raw_data[1:]:
                if len(f) >= 16 and m_sel in f[IDX_FECHA]:
                    try:
                        h_b = f[IDX_ING_DMS].strip()
                        if h_b != "":
                            v = not ("NO VINO" in f[IDX_PRO].upper() or "NO VINO" in f[IDX_TRABAJO].upper())
                            t_mes.append({"Fecha": f[IDX_FECHA].split()[0], "DMS": (h_b != "13:00"), "Vino": v, "Rec": (f[IDX_RECUPERO].upper() == "SI")})
                    except: continue
            if t_mes:
                df_tmes = pd.DataFrame(t_mes).groupby('Fecha').agg(Total=('DMS','sum'), Vino=('Vino','sum'), Rec=('Rec','sum')).reset_index()
                st.dataframe(df_tmes, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Gestión de Turnos y Recupero")
        if turnos_hoy:
            df_t = pd.DataFrame(turnos_hoy); dms = df_t[df_t['dms'] == True]; aus = dms[dms['vino'] == False]
            c1, c2, c3, c4 = st.columns(4); c1.metric("Turnos DMS", len(dms)); c2.metric("Show-up", f"{int(len(dms[dms['vino']])/len(dms)*100)}%" if len(dms)>0 else "0%")
            c3.metric("Adicionales", len(df_t[~df_t['dms']])); c4.metric("Servicios", len(df_t[df_t['serv']]))
            st.markdown("---"); st.subheader("📋 Recupero de Ausentes")
            for _, a in aus.iterrows():
                with st.container():
                    r = st.columns([0.8, 1.5, 1.5, 0.8, 1, 1.2])
                    r[0].write(f"**{a['dom']}**"); r[1].write(f"<small>{a['cli']}</small>", unsafe_allow_html=True); r[2].write(f"<small>{a['mod']}</small>", unsafe_allow_html=True); r[3].write(a['ase'])
                    r[4].markdown("<span class='status-badge bg-danger'>AUSENTE</span>" if not a['rec'] else "✅", unsafe_allow_html=True)
                    if not a['rec'] and r[5].button("Recuperar", key=f"rc_{a['fila']}"):
                        hoja.update_cell(a['fila'], IDX_RECUPERO+1, "SI"); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)
            col_p1, col_p2 = st.columns(2)
            col_p1.plotly_chart(px.pie(df_t, names='serv', title="Servicios vs Otros", color_discrete_sequence=['#00235d', '#fbc02d']), use_container_width=True)
            if len(aus)>0: col_p2.plotly_chart(px.bar(x=["Recuperados", "Pendientes"], y=[len(aus[aus['rec']]), len(aus[~aus['rec']])], title="Efectividad Recupero"), use_container_width=True)
        else: st.info("Sin turnos detectados.")

if __name__ == "__main__":
    main()
