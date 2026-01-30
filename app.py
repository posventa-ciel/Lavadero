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
    .txt-truncado { color: #333; font-weight: 500; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; width: 100%; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; min-width: 70px; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-ok { background-color: #2e7d32; color: white; }
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
    hoy_date, hoy_str = now_dt.date(), now_dt.strftime("%d/%m/%Y")

    st.markdown(f'<div class="header-box"><div class="header-title">CONTROL INTEGRAL POSVENTA</div><div style="text-align: right;"><b>{hoy_str}</b><br>{hora_actual} hs</div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # ÍNDICES GLOBALES (0-15)
    IDX_FECHA, IDX_ING_DMS, IDX_ASE, IDX_DOM, IDX_MOD, IDX_CLI, IDX_TRABAJO, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL, IDX_FECHA_FIN, IDX_RECUPERO = range(16)

    with st.sidebar:
        st.markdown("### 🔍 Filtros")
        busqueda = st.text_input("Patente:").upper()
        fecha_sel = st.date_input("Fecha:", hoy_date)
        f_str, f_str_cero = fecha_sel.strftime("%-d/%-m/%Y"), fecha_sel.strftime("%d/%m/%Y")

    pendientes, finalizados_ver, turnos_eficiencia = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 16: fila += [""] * (16 - len(fila))
        f_celda = fila[IDX_FECHA]
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        if not es_de_fecha: continue
        
        dom = fila[IDX_DOM].upper()
        if not dom or (busqueda and busqueda not in dom): continue

        estado = fila[IDX_EST].strip().upper()
        f_fin_real = fila[IDX_FECHA_FIN].strip()
        prometido = fila[IDX_PRO].upper()
        trabajo_g = fila[IDX_TRABAJO].upper()
        
        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "cli": fila[IDX_CLI], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1], "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2],
            "est": estado, "ok": fila[IDX_CTRL].strip().upper() in ["SI", "OK"], 
            "fecha": f_celda, "f_fin_real": f_fin_real, "trabajo": trabajo_g
        }

        # --- CLASIFICACIÓN LAVADERO ---
        tiene_fin = fila[IDX_FIN1].strip() != "" or fila[IDX_FIN2].strip() != ""
        if not tiene_fin or estado in ["PAUSA", "REPASO"]:
            pendientes.append(item)
        else:
            # Aquí unificamos: Si es la fecha del calendario o si se finalizó hoy (columna O)
            if es_de_fecha or (fecha_sel == hoy_date and f_fin_real == hoy_str):
                finalizados_ver.append(item)

        # --- CLASIFICACIÓN TURNOS ---
        hora_b = fila[IDX_ING_DMS].strip()
        if hora_b != "":
            vino = not ("NO VINO" in prometido or "NO VINO" in trabajo_g)
            p_serv = ["SERV", "KM", "10K", "20K", "30K", "40K", "50K", "60K", "70K", "80K", "90K", "100K", "MANT"]
            es_serv = any(x in trabajo_g for x in p_serv)
            turnos_eficiencia.append({
                "fila": i, "dom": dom, "cli": fila[IDX_CLI], "mod": fila[IDX_MOD], "ase": item['ase'],
                "dms": (hora_b != "13:00"), "vino": vino, "serv": es_serv, "rec": (fila[IDX_RECUPERO].upper() == "SI")
            })

    tab1, tab2, tab3, tab4 = st.tabs(["🚗 Operación", "📊 Métricas Hoy", "📅 Historial", "📈 Eficiencia Turnos"])

    with tab1:
        st.subheader(f"Pendientes ({len(pendientes)})")
        for p in pendientes:
            with st.container():
                c = st.columns([0.8, 0.8, 1.4, 1.4, 0.8, 1.2])
                c[0].markdown(generar_badge_alerta(p['pro'], now_dt), unsafe_allow_html=True)
                c[1].write(f"**{p['dom']}**")
                c[2].markdown(f"<span class='txt-truncado'>{p['cli']}</span>", unsafe_allow_html=True)
                c[3].markdown(f"<span class='txt-truncado'>{p['mod']}</span>", unsafe_allow_html=True)
                c[4].write(p['ase'])
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
                r = st.columns([0.5, 0.5, 0.5, 0.8, 1.4, 1.4, 0.7, 1.2])
                r[0].write(t['ini']); r[1].write(t['fin2'] if t['fin2'] else t['fin']); r[2].write(f"{calcular_tiempo_neto(t)}'")
                r[3].write(f"**{t['dom']}**"); r[4].write(t['cli']); r[5].write(t['mod']); r[6].write(t['ase'])
                with r[7]:
                    c_chk, c_txt = st.columns([0.3, 0.7])
                    with c_chk:
                        nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                        if nk != t['ok']: hoja.update_cell(t['fila'], IDX_CTRL+1, "SI" if nk else ""); st.rerun()
                    if t['ok']: c_txt.markdown("<span class='badge-ok'>ENTREGADO</span>", unsafe_allow_html=True)
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        if finalizados_ver:
            df_hoy = pd.DataFrame(finalizados_ver); df_hoy['minutos'] = df_hoy.apply(calcular_tiempo_neto, axis=1)
            c1, c2, c3 = st.columns(3); c1.metric("Lavados", len(df_hoy)); c2.metric("Promedio", f"{int(df_hoy['minutos'].mean())} min"); c3.metric("Máximo", f"{df_hoy['minutos'].max()} min")
            st.plotly_chart(px.bar(df_hoy, x='dom', y='minutos', title="Tiempo por Vehículo"), use_container_width=True)
            st.plotly_chart(px.pie(df_hoy, names='ase', title="Lavados por Asesor"), use_container_width=True)

    with tab3:
        st.subheader("📅 Historial")
        df_hist = pd.DataFrame(finalizados_ver)
        if not df_hist.empty:
            df_hist['minutos'] = df_hist.apply(calcular_tiempo_neto, axis=1)
            # Aquí unificamos la tabla con las métricas
            st.write(f"Resumen operativo para el día {fecha_sel.strftime('%d/%m/%Y')}:")
            st.dataframe(df_hist[['dom', 'cli', 'ase', 'minutos']].rename(columns={'dom':'Patente','cli':'Cliente','ase':'Asesor','minutos':'Minutos'}), use_container_width=True, hide_index=True)
            
            # --- TABLA MENSUAL TALLER ---
            st.markdown("---")
            st.subheader("📊 Historial Taller del Mes")
            t_mes = []
            mes_actual = fecha_sel.strftime("%Y-%m")
            for f in raw_data[1:]:
                if len(f) >= 16 and mes_actual in f[IDX_FECHA]:
                    try:
                        h_b = f[IDX_ING_DMS].strip()
                        if h_b != "":
                            v = not ("NO VINO" in f[IDX_PRO].upper() or "NO VINO" in f[IDX_TRABAJO].upper())
                            t_mes.append({"Fecha": f[IDX_FECHA].split()[0], "DMS": (h_b != "13:00"), "Vino": v, "Rec": (f[IDX_RECUPERO].upper() == "SI")})
                    except: continue
            if t_mes:
                df_res = pd.DataFrame(t_mes).groupby('Fecha').agg(Turnos=('DMS','sum'), Asistencia=('Vino','sum'), Recuperos=('Rec','sum')).reset_index()
                st.dataframe(df_res.sort_values('Fecha', ascending=False), use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Eficiencia de Agenda")
        if turnos_eficiencia:
            df_t = pd.DataFrame(turnos_eficiencia)
            prog = df_t[df_t['dms'] == True]; aus = prog[prog['vino'] == False]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Turnos DMS", len(prog))
            c2.metric("Show-up", f"{int(len(prog[prog['vino']])/len(prog)*100)}%" if len(prog)>0 else "0%")
            c3.metric("Adicionales", len(df_t[~df_t['dms']]))
            c4.metric("Servicios", len(df_t[df_t['serv']]))

            st.markdown("---")
            st.subheader("📞 Listado de Ausentes")
            if not aus.empty:
                for _, a in aus.iterrows():
                    with st.container():
                        r = st.columns([1, 1.5, 1.5, 1, 1, 1])
                        r[0].write(f"**{a['dom']}**"); r[1].write(a['cli']); r[2].write(a['mod']); r[3].write(a['ase'])
                        r[4].write("❌ PENDIENTE" if not a['rec'] else "✅ RECUPERADO")
                        if not a['rec'] and r[5].button("Recuperar", key=f"rc_{a['fila']}"):
                            hoja.update_cell(a['fila'], IDX_RECUPERO+1, "SI"); st.rerun()
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            g1, g2 = st.columns(2)
            with g1:
                st.plotly_chart(px.pie(df_t, names='serv', title="Servicios vs Otros", color_discrete_sequence=['#00235d', '#fbc02d']), use_container_width=True)
            with g2:
                # Gráfico de barras simple para el recupero
                rec_df = pd.DataFrame([{"Estado": "Recuperados", "Cant": len(aus[aus['rec']])}, {"Estado": "No Recuperados", "Cant": len(aus[~aus['rec']])}])
                st.plotly_chart(px.bar(rec_df, x="Estado", y="Cant", title="Gestión de Recupero de Ausentes", color="Estado", color_discrete_map={"Recuperados":"#2e7d32", "No Recuperados":"#d32f2f"}), use_container_width=True)
        else: st.info("Sin turnos detectados hoy.")

if __name__ == "__main__":
    main()
