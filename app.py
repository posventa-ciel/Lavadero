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

# --- 2. ESTILOS CSS ---
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
    .badge-normal { color: #333; font-weight: bold; font-size: 13px; }
    .badge-ok { color: #2e7d32; font-weight: bold; font-size: 12px; }
    .stButton button { height: 26px !important; min-height: 26px !important; font-size: 11px !important; padding: 0 8px !important; margin: 1px 0 !important; width: 100%;}
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
def calcular_minutos(h1, h2):
    try:
        fmt = "%H:%M"
        t1 = datetime.strptime(h1, fmt)
        t2 = datetime.strptime(h2, fmt)
        return int((t2 - t1).total_seconds() / 60)
    except: return 0

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

def generar_badge_alerta(hora_prometida, now_dt):
    if not hora_prometida or ":" not in str(hora_prometida): return f"<span class='badge-normal'>{hora_prometida}</span>"
    try:
        h, m = map(int, str(hora_prometida).split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prometida}<br>ATRASADO</div>"
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

    # Estructura estricta de variables
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13

    with st.sidebar:
        st.markdown("### 🔍 Buscar Patente")
        busqueda = st.text_input("", placeholder="Ej: AB123CD", label_visibility="collapsed").upper()
        st.markdown("---")
        fecha_sel = st.date_input("Ver fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes, terminados_vista, historial_raw = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        dom = fila[IDX_DOM].upper()
        if not dom: continue
        
        pro_raw = fila[IDX_PRO].upper()
        if any(x in pro_raw for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue

        f_celda = fila[IDX_FECHA]
        estado = fila[IDX_EST].strip().upper()
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        
        # Lógica estricta de 'Finalizado'
        es_finalizado = (estado == "FINALIZADO")

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado, 
            "ok": (fila[IDX_CTRL].strip().upper() == "OK"),
            "min_orden": obtener_minutos_orden(fila[IDX_PRO]),
            "fecha_str": f_celda.split()[0]
        }

        # Para Historial (todos los FINALIZADO)
        if es_finalizado:
            historial_raw.append(item)

        if busqueda and busqueda not in dom: continue

        if es_finalizado:
            if es_de_fecha: terminados_vista.append(item)
        else:
            # Solución 36 vs 8: Filtrar basura histórica. Solo mostrar si es hoy o está activo.
            es_atrasado = False
            try:
                f_dt = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").date()
                if f_dt < fecha_sel: es_atrasado = True
            except: pass
            
            if es_de_fecha or (es_atrasado and (estado in ["PAUSA", "REPASO", "LAVANDO"] or item['ini'])):
                item["atr"] = es_atrasado
                pendientes.append(item)

    tab1, tab2, tab3 = st.tabs(["🚗 Operación", "📊 Métricas", "📜 Historial"])

    with tab1:
        # --- PENDIENTES ---
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        if pendientes:
            pendientes.sort(key=lambda x: (not x.get("atr", False), x["min_orden"]))
            cols_p = [0.8, 0.8, 2, 0.8, 1.4]
            # Títulos de columnas (Punto 1)
            h = st.columns(cols_p)
            h[0].caption("PROMETIDO"); h[1].caption("DOMINIO"); h[2].caption("MODELO"); h[3].caption("ASESOR"); h[4].caption("ACCIONES")
            
            for p in pendientes:
                with st.container():
                    c = st.columns(cols_p)
                    badge = f"<div class='badge badge-red'>{p['pro']}<br>ATRASADO</div>" if p.get("atr") else generar_badge_alerta(p['pro'], now_dt)
                    c[0].markdown(badge, unsafe_allow_html=True)
                    c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                    c[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    with c[4]:
                        # Lógica de Botones Corregida (Punto 2)
                        if not p['ini']:
                            if st.button("▶️ Iniciar", key=f"s{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INI1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                        elif p['est'] == "PAUSA":
                            if st.button("🔄 Reanudar", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                        elif p['est'] in ["LAVANDO", "REPASO", ""]:
                            cb = st.columns(2)
                            if cb[0].button("⏸️ Pausa", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                            if cb[1].button("🏁 Fin", key=f"f{p['fila']}"):
                                col_target = IDX_FIN2 + 1 if p['est'] == "REPASO" else IDX_FIN1 + 1
                                hoja.update_cell(p['fila'], col_target, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # --- TERMINADOS ---
        st.markdown(f"**Finalizados ({len(terminados_vista)})**")
        if terminados_vista:
            terminados_vista.sort(key=lambda x: obtener_minutos_orden(x['ini']))
            cols_f = [0.6, 0.6, 0.8, 1.5, 0.8, 1.2]
            hf = st.columns(cols_f)
            hf[0].caption("INI"); hf[1].caption("FIN"); hf[2].caption("DOM"); hf[3].caption("MODELO"); hf[4].caption("ASESOR"); hf[5].caption("CONTROL")
            for t in terminados_vista:
                with st.container():
                    r = st.columns(cols_f)
                    r[0].write(t['ini']); r[1].write(t['fin2'] if t['fin2'] else t['fin'])
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
                            st.markdown("<span class='badge-ok'>ENTREGADO</span>" if t['ok'] else generar_badge_alerta(t['pro'], now_dt), unsafe_allow_html=True)
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        # --- MÉTRICAS (Punto 3) ---
        st.subheader(f"Resumen de hoy ({hoy_date.strftime('%d/%m/%Y')})")
        tiempos = [calcular_minutos(t['ini'], t['fin2'] if t['fin2'] else t['fin']) for t in terminados_vista if t['ini']]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Autos Hoy", len(terminados_vista))
        m2.metric("Tiempo Promedio", f"{int(sum(tiempos)/len(tiempos)) if tiempos else 0} min")
        m3.metric("Tiempo Máximo", f"{max(tiempos) if tiempos else 0} min")
        
        if terminados_vista:
            df_hoy = pd.DataFrame(terminados_vista)
            fig_ase = px.bar(df_hoy.groupby('ase').size().reset_index(name='Cant'), x='ase', y='Cant', title="Autos por Asesor", color_discrete_sequence=['#00235d'])
            st.plotly_chart(fig_ase, use_container_width=True)

    with tab3:
        # --- HISTORIAL (Punto 4) ---
        st.subheader("Historial de Lavados FINALIZADOS")
        if historial_raw:
            df_hist = pd.DataFrame(historial_raw)
            df_resumen = df_hist.groupby('fecha_str').size().reset_index(name='Cantidad')
            
            st.plotly_chart(px.line(df_resumen, x='fecha_str', y='Cantidad', title="Evolución de Lavados", markers=True), use_container_width=True)
            st.markdown("**Resumen diario**")
            st.dataframe(df_resumen.sort_values('fecha_str', ascending=False), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
