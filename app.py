import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import json
import pytz
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN DE PÁGINA ---
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
    p { margin: 0 !important; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 13px; }
    .txt-truncado { color: #333; font-weight: 500; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; width: 100%; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; min-width: 70px; display: inline-block; line-height: 1.1; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-ok { background-color: #2e7d32; color: white; }
    .badge-blue { background-color: #00235d; color: white; }
    .badge-gray { background-color: #6c757d; color: white; } 
    .badge-teal { background-color: #17a2b8; color: white; }
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
# MODIFICADO: Ahora recibe fecha_base (fecha de ingreso del auto)
def procesar_fecha_flexible(val, hoy, tz, fecha_base=None):
    val = str(val).strip().replace("-", "/")
    if not val: return tz.localize(datetime(2099, 12, 31))
    
    # Si solo hay hora (ej: "17:00"), usamos la fecha de ingreso (fecha_base) en vez de HOY
    if ":" in val and len(val) <= 5:
        try:
            h, m = map(int, val.split(':'))
            base = fecha_base if fecha_base else hoy # Si por algo no hay fecha base, usa hoy
            return tz.localize(datetime(base.year, base.month, base.day, h, m))
        except: pass
        
    formatos = ["%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d/%m %H:%M", "%d/%m/%Y", "%d/%m"]
    for fmt in formatos:
        try:
            dt = datetime.strptime(val, fmt)
            if "Y" not in fmt and "y" not in fmt: dt = dt.replace(year=hoy.year)
            return tz.localize(dt)
        except ValueError: continue
    return tz.localize(datetime(2099, 12, 31))

def formatear_fecha_corta(dt, now_dt):
    if dt.year == 2099: return "S/D"
    if dt.date() == now_dt.date(): return dt.strftime("%H:%M")
    return dt.strftime("%d/%m %H:%M") # Si es de otro dia, muestra fecha y hora

def generar_badge_alertas(prometido_dt, now_dt, estado_actual):
    texto = formatear_fecha_corta(prometido_dt, now_dt)
    if estado_actual == "PAUSA": return f"<div class='badge badge-gray'>{texto}<br>PAUSADO</div>"
    if estado_actual == "REPASO": return f"<div class='badge badge-teal'>{texto}<br>REPASO</div>"
    if prometido_dt.year == 2099: return f"<div class='badge badge-gray'>{texto}</div>"
    
    es_hoy = prometido_dt.date() <= now_dt.date() # Si es fecha pasada, entra aquí también
    
    diff = (prometido_dt - now_dt).total_seconds() / 60
    
    # Si diff es negativo, significa que ya pasó la hora -> DEMORADO
    if diff < 0: return f"<div class='badge badge-red'>{texto}<br>DEMORADO</div>"
    
    if not es_hoy: return f"<div class='badge badge-blue'>{texto}<br>PRÓXIMO</div>"
    
    if diff <= 30: return f"<div class='badge badge-red'>{texto}<br>YA!</div>"
    elif diff <= 60: return f"<div class='badge badge-yellow'>{texto}<br>ATENCIÓN</div>"
    return f"<b>{texto}</b>"

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

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()
    hoy_str = hoy_date.strftime("%d/%m/%Y")

    st.markdown(f'<div class="header-box"><div class="header-title">CONTROL INTEGRAL POSVENTA</div><div style="text-align: right;"><b>{hoy_str}</b><br>{hora_actual} hs</div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    IDX_FECHA, IDX_ING_DMS, IDX_ASE, IDX_DOM, IDX_MOD, IDX_CLI, IDX_TRABAJO, IDX_PRO = 0, 1, 2, 3, 4, 5, 6, 7
    IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL, IDX_FECHA_FIN, IDX_RECUPERO = 8, 9, 10, 11, 12, 13, 14, 15

    with st.sidebar:
        st.markdown("### 🔍 Buscar Patente")
        busqueda = st.text_input("", placeholder="Ej: AB123CD", label_visibility="collapsed").upper()
        st.markdown("---")
        fecha_sel = st.date_input("Ver fecha:", hoy_date)
        f_str, f_str_cero = fecha_sel.strftime("%-d/%-m/%Y"), fecha_sel.strftime("%d/%m/%Y")

    pendientes, finalizados_ver, turnos_eficiencia = [], [], []
    historial_global = [] 
    historial_taller = [] 

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 16: fila += [""] * (16 - len(fila))
        
        f_ingreso_raw = fila[IDX_FECHA].strip()
        hora_recep_raw = fila[IDX_ING_DMS].strip()

        # --- FILTRO MAESTRO ---
        if not f_ingreso_raw and not hora_recep_raw: continue

        dom_raw = fila[IDX_DOM].upper().strip()
        display_dom = dom_raw if dom_raw else "S/D"
        
        if busqueda and busqueda not in display_dom: continue

        pro_raw = fila[IDX_PRO].upper().strip()
        estado = fila[IDX_EST].strip().upper()
        f_fin_celda = fila[IDX_FECHA_FIN].strip()
        es_de_fecha = (f_str in f_ingreso_raw) or (f_str_cero in f_ingreso_raw)
        tiene_fin = fila[IDX_FIN1].strip() != "" or fila[IDX_FIN2].strip() != ""
        
        # --- PROCESAMIENTO FECHA INGRESO ---
        # Primero obtenemos la fecha real de ingreso para usarla de base
        f_dt_obj = None
        try:
            f_dt_obj = datetime.strptime(f_ingreso_raw.split()[0], "%d/%m/%Y")
        except: 
            try: f_dt_obj = datetime.strptime(f_ingreso_raw, "%d/%m/%Y")
            except: pass
        
        # Obtenemos string para display
        try:
            h_ing = f_ingreso_raw.split()[1] if len(f_ingreso_raw.split()) > 1 else ""
            f_ing_display = f"{f_dt_obj.strftime('%d/%m')} {h_ing}" if f_dt_obj else f_ingreso_raw
        except: f_ing_display = f_ingreso_raw

        # --- PROCESAMIENTO FECHA PROMETIDA (CORREGIDO) ---
        # Pasamos f_dt_obj como 'fecha_base'. Si el asesor puso "17:00", usará la fecha de ingreso, no HOY.
        dt_prometido = procesar_fecha_flexible(fila[IDX_PRO], hoy_date, tz_ar, fecha_base=f_dt_obj)

        item = {
            "fila": i, "dom": display_dom, "mod": fila[IDX_MOD], "cli": fila[IDX_CLI], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro_dt": dt_prometido, "pro_str": fila[IDX_PRO], "ingreso": f_ing_display,
            "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], 
            "est": estado, "ok": fila[IDX_CTRL].strip().upper() in ["SI", "OK"], 
            "f_fin_real": f_fin_celda, "trabajo": fila[IDX_TRABAJO].upper()
        }

        # --- 1. LAVADERO ---
        no_se_lava = any(x in pro_raw for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"])
        if not no_se_lava and f_ingreso_raw:
            if not tiene_fin or estado in ["PAUSA", "REPASO"]:
                pendientes.append(item)
            else:
                if es_de_fecha or (fecha_sel == hoy_date and f_fin_celda == hoy_str):
                    finalizados_ver.append(item)
                
                # Historial Lavadero
                if f_dt_obj:
                    t_n = calcular_tiempo_neto(item)
                    if t_n > 0: historial_global.append({"Fecha": f_dt_obj, "Mes": f_dt_obj.strftime("%Y-%m"), "Mins": t_n})

        # --- 2. TALLER ---
        if hora_recep_raw:
            vino_real = "NO VINO" not in pro_raw
            es_dms = (hora_recep_raw != "13:00")
            txt_t = item['trabajo']
            palabras_serv = ["SERV", "KM", "MANT", "10K", "20K", "30K", "40K", "50K", "60K", "70K", "80K", "90K", "100K"]
            es_servicio = any(x in txt_t for x in palabras_serv)
            es_recuperado = (fila[IDX_RECUPERO].upper() == "SI")
            
            if es_de_fecha:
                turnos_eficiencia.append({
                    "fila": i, "dom": display_dom, "cli": fila[IDX_CLI], "mod": fila[IDX_MOD], 
                    "ase": item['ase'], "dms": es_dms, "vino": vino_real, 
                    "serv": es_servicio, "rec": es_recuperado
                })

            if f_dt_obj:
                historial_taller.append({
                    "Mes": f_dt_obj.strftime("%Y-%m"),
                    "DMS": es_dms, "Vino": vino_real, "Serv": es_servicio, "Rec": es_recuperado
                })

    tab1, tab2, tab3, tab4 = st.tabs(["🧽 Lavadero", "📊 Métricas Hoy", "📅 Historial", "📈 Eficiencia Turnos"])

    with tab1:
        st.subheader(f"Pendientes ({len(pendientes)})")
        if pendientes:
            pendientes.sort(key=lambda x: x["pro_dt"])
            cols_p = [0.8, 1.0, 0.8, 1.4, 1.4, 0.8, 1.2]
            h_p = st.columns(cols_p); h_p[0].caption("HS. ENTREGA"); h_p[1].caption("INGRESO"); h_p[2].caption("DOMINIO"); h_p[3].caption("CLIENTE"); h_p[4].caption("MODELO"); h_p[5].caption("ASESOR"); h_p[6].caption("ACCIONES")
            for p in pendientes:
                with st.container():
                    c = st.columns(cols_p)
                    c[0].markdown(generar_badge_alertas(p['pro_dt'], now_dt, p['est']), unsafe_allow_html=True)
                    c[1].write(f"<small>{p['ingreso']}</small>", unsafe_allow_html=True)
                    c[2].write(f"**{p['dom']}**")
                    c[3].markdown(f"<span class='txt-truncado'>{p['cli']}</span>", unsafe_allow_html=True)
                    c[4].markdown(f"<span class='txt-truncado'>{p['mod']}</span>", unsafe_allow_html=True)
                    c[5].write(p['ase'])
                    with c[6]:
                        if not p['ini']:
                            if st.button("▶️", key=f"s{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INI1+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "LAVANDO"); st.rerun()
                        elif not (p['fin'] or p['fin2']):
                            cb = st.columns(2)
                            if cb[0].button("⏸️", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "PAUSA"); st.rerun()
                            if cb[1].button("🏁", key=f"f{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "FINALIZADO"); hoja.update_cell(p['fila'], IDX_FECHA_FIN+1, hoy_str); st.rerun()
                        elif p['est'] == "PAUSA":
                            if st.button("🔄", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "REPASO"); st.rerun()
                        elif p['est'] == "REPASO":
                            if st.button("🏁", key=f"f2{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2+1, now_dt.strftime("%H:%M")); hoja.update_cell(p['fila'], IDX_EST+1, "FINALIZADO"); hoja.update_cell(p['fila'], IDX_FECHA_FIN+1, hoy_str); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader(f"Finalizados ({len(finalizados_ver)})")
        if finalizados_ver:
            finalizados_ver.sort(key=lambda x: (x['ok'], x['pro_dt']))
            cols_f = [0.8, 1.0, 0.5, 0.5, 0.5, 0.8, 1.4, 0.7, 1.2]
            h_f = st.columns(cols_f); h_f[0].caption("HS. ENTREGA"); h_f[1].caption("INGRESO"); h_f[2].caption("INI"); h_f[3].caption("FIN"); h_f[4].caption("T."); h_f[5].caption("DOM"); h_f[6].caption("CLIENTE"); h_f[7].caption("ASESOR"); h_f[8].caption("CONTROL")
            for t in finalizados_ver:
                t['min_total'] = calcular_tiempo_neto(t)
                with st.container():
                    r = st.columns(cols_f)
                    r[0].write(f"<small>{t['pro_str']}</small>", unsafe_allow_html=True)
                    r[1].write(f"<small>{t['ingreso']}</small>", unsafe_allow_html=True)
                    r[2].write(t['ini']); r[3].write(t['fin2'] if t['fin2'] else t['fin']); r[4].write(f"{t['min_total']}'")
                    r[5].markdown(f"<b>{t['dom']}</b>", unsafe_allow_html=True)
                    r[6].markdown(f"<span class='txt-truncado'>{t['cli']}</span>", unsafe_allow_html=True)
                    r[7].write(t['ase'])
                    with r[8]:
                        c_chk, c_txt = st.columns([0.2, 0.8])
                        with c_chk:
                            nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                            if nk != t['ok']: hoja.update_cell(t['fila'], IDX_CTRL+1, "SI" if nk else ""); st.rerun()
                        with c_txt:
                            if t['ok']: st.markdown("<span class='badge-ok'>CONTROLADO</span>", unsafe_allow_html=True)
                            else: st.markdown(generar_badge_alertas(t['pro_dt'], now_dt, "FINALIZADO"), unsafe_allow_html=True)
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        st.subheader("Resumen de Hoy")
        if finalizados_ver:
            df_hoy = pd.DataFrame(finalizados_ver); df_hoy['minutos'] = df_hoy.apply(calcular_tiempo_neto, axis=1)
            c1, c2, c3 = st.columns(3); c1.metric("Lavados", len(df_hoy)); c2.metric("Promedio Real", f"{int(df_hoy['minutos'].mean())} min"); c3.metric("Máximo", f"{df_hoy['minutos'].max()} min")
            col_g1, col_g2 = st.columns(2)
            with col_g1: st.plotly_chart(px.bar(df_hoy, x='dom', y='minutos', color='minutos', title="Tiempo por Patente"), use_container_width=True)
            with col_g2: st.plotly_chart(px.pie(df_hoy, names='ase', title="Lavados por Asesor"), use_container_width=True)
        else: st.info("Sin datos de hoy.")

    with tab3:
        st.subheader("📅 Historial Mensual")
        meses_lav = [x['Mes'] for x in historial_global]
        meses_tal = [x['Mes'] for x in historial_taller]
        meses_disp = sorted(list(set(meses_lav + meses_tal)), reverse=True)

        if meses_disp:
            col_sel, _ = st.columns([1, 4])
            with col_sel: m_sel = st.selectbox("Seleccionar Mes:", meses_disp)
            
            df_h_lav = pd.DataFrame(historial_global)
            if not df_h_lav.empty:
                df_m = df_h_lav[df_h_lav['Mes'] == m_sel].groupby('Fecha').agg(Lavados=('Fecha','count'), Promedio=('Mins','mean')).reset_index()
                if not df_m.empty:
                    fig_hist = go.Figure()
                    fig_hist.add_trace(go.Bar(x=df_m['Fecha'].dt.strftime('%d/%m'), y=df_m['Lavados'], name='Autos', marker_color='#00235d', yaxis='y'))
                    fig_hist.add_trace(go.Scatter(x=df_m['Fecha'].dt.strftime('%d/%m'), y=df_m['Promedio'], name='Promedio', line=dict(color='#fbc02d', width=4), yaxis='y2'))
                    fig_hist.update_layout(yaxis=dict(title="Autos"), yaxis2=dict(title="Minutos", overlaying="y", side="right"), legend=dict(orientation="h", y=1.1))
                    st.plotly_chart(fig_hist, use_container_width=True)
            
            st.markdown("---")
            st.subheader(f"🔧 Indicadores Taller - {m_sel}")
            df_h_taller = pd.DataFrame(historial_taller)
            
            if not df_h_taller.empty:
                df_mt = df_h_taller[df_h_taller['Mes'] == m_sel]
                if not df_mt.empty:
                    total_turnos = len(df_mt)
                    vinieron = df_mt['Vino'].sum()
                    ausentes = total_turnos - vinieron
                    recuperados = df_mt['Rec'].sum()
                    sobreturnos = len(df_mt[~df_mt['DMS']])
                    servicios = df_mt['Serv'].sum()

                    tasa_asistencia = (vinieron / total_turnos * 100) if total_turnos > 0 else 0
                    tasa_recupero = (recuperados / ausentes * 100) if ausentes > 0 else 0
                    mix_servicios = (servicios / vinieron * 100) if vinieron > 0 else 0

                    k1, k2, k3, k4, k5 = st.columns(5)
                    k1.metric("Asistencia", f"{int(tasa_asistencia)}%", f"{vinieron}/{total_turnos}")
                    k2.metric("Tasa Recupero", f"{int(tasa_recupero)}%", f"{recuperados} de {ausentes}")
                    k3.metric("Sobreturnos", sobreturnos, "Adicionales")
                    k4.metric("Servicios", servicios)
                    k5.metric("Mix Servicios", f"{int(mix_servicios)}%", "s/Ingresos")
                else: st.info("No hay datos de taller para este mes.")
        else: st.warning("No hay datos históricos registrados.")

    with tab4:
        st.subheader(f"Gestión de Turnos - {fecha_sel.strftime('%d/%m/%Y')}")
        if turnos_eficiencia:
            df_t = pd.DataFrame(turnos_eficiencia)
            aus_df = df_t[df_t['vino'] == False]
            vin_df = df_t[df_t['vino'] == True]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Turnos Taller", len(df_t))
            c2.metric("Vinieron", len(vin_df))
            c3.metric("No Vinieron", len(aus_df), delta_color="inverse")
            c4.metric("Show-up Rate", f"{int(len(vin_df)/len(df_t)*100)}%" if len(df_t)>0 else "0%")

            st.markdown("---")
            col_list1, col_list2 = st.columns(2)
            with col_list1:
                st.markdown("### ❌ Clientes Ausentes")
                for _, a in aus_df.iterrows():
                    with st.container():
                        r = st.columns([1, 2, 1])
                        r[0].write(f"**{a['dom']}**")
                        r[1].write(f"<small>{a['cli']}</small>", unsafe_allow_html=True)
                        if not a['rec'] and st.button("Recuperar", key=f"r_{a['fila']}"):
                            hoja.update_cell(a['fila'], IDX_RECUPERO+1, "SI"); st.rerun()
                        elif a['rec']: r[2].write("✅")
            with col_list2:
                st.markdown("### 📋 Resumen por Tipo")
                st.write(f"DMS Programados: {len(df_t[df_t['dms']])}")
                st.write(f"Adicionales (13:00): {len(df_t[~df_t['dms']])}")
                st.write(f"Servicios Realizados: {len(vin_df[vin_df['serv'] == True])}")
            
            st.markdown("---")
            g1, g2 = st.columns(2)
            with g1: st.plotly_chart(px.pie(df_t, names='vino', title="Presentes vs Ausentes", color_discrete_sequence=['#2e7d32', '#d32f2f']), use_container_width=True)
            with g2: st.plotly_chart(px.pie(df_t, names='serv', title="Servicios vs Otros", color_discrete_sequence=['#00235d', '#fbc02d']), use_container_width=True)
        else: st.info("Sin datos de taller para esta fecha.")

if __name__ == "__main__":
    main()
