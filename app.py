import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import pytz
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

# --- 2. ESTILOS CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px 20px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .header-title { font-size: 24px; font-weight: bold; text-transform: uppercase; margin: 0; }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 4px 0 !important; margin: 0 !important; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 12px; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; min-width: 70px; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-normal { color: #333; font-weight: bold; font-size: 13px; }
    .stButton button { height: 28px !important; font-size: 12px !important; }
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

    st.markdown(f'<div class="header-box"><div class="header-title">LAVADERO CONTROL</div><div style="text-align: right;"><div style="font-size: 16px; font-weight: 700;">{hoy_date.strftime("%d/%m/%Y")}</div><div style="font-size: 14px; opacity: 0.8;">{hora_actual} hs</div></div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13

    with st.sidebar:
        st.markdown("### 🔍 Buscar Patente")
        busqueda = st.text_input("", placeholder="Ej: AB123CD", label_visibility="collapsed").upper()
        st.markdown("---")
        fecha_sel = st.date_input("Ver fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes, terminados_hoy, historia_data = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        dom = fila[IDX_DOM].upper().strip()
        pro_raw = fila[IDX_PRO].upper()
        if not dom or any(x in pro_raw for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue
        
        f_celda = fila[IDX_FECHA]
        estado = fila[IDX_EST].strip().upper()
        
        # --- CORRECCIÓN LÓGICA PAUSA (PUNTO 2) ---
        # Un auto SOLO se considera finalizado si el estado es FINALIZADO. 
        # Si tiene FIN1 pero el estado es PAUSA, sigue en pendientes.
        es_finalizado = (estado == "FINALIZADO")
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        
        es_atrasado = False
        try:
            f_dt = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").date()
            if f_dt < fecha_sel: es_atrasado = True
            # Recolectar para historia (Punto 4)
            if estado == "FINALIZADO":
                t_total = calcular_minutos(fila[IDX_INI1], fila[IDX_FIN1]) + calcular_minutos(fila[IDX_INI2], fila[IDX_FIN2])
                historia_data.append({"Fecha": f_dt, "Tiempo": t_total, "Asesor": limpiar_asesor(fila[IDX_ASE])})
        except: pass

        if busqueda and busqueda not in dom: continue

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado, 
            "ok": (fila[IDX_CTRL].strip().upper() == "OK"), "atr": es_atrasado,
            "min_orden": obtener_minutos_orden(fila[IDX_PRO])
        }

        if es_finalizado:
            if es_de_fecha or (es_atrasado and fecha_sel == hoy_date):
                terminados_hoy.append(item)
        else:
            if es_de_fecha or es_atrasado:
                pendientes.append(item)

    tab1, tab2, tab3 = st.tabs(["🚗 Operación", "📊 Métricas", "📅 Historial"])

    with tab1:
        # --- TÍTULOS DE COLUMNAS (PUNTO 1) ---
        cols_p = [0.8, 0.8, 2, 0.8, 1.4]
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        if pendientes:
            h = st.columns(cols_p)
            h[0].caption("PROMETIDO"); h[1].caption("PATENTE"); h[2].caption("MODELO"); h[3].caption("ASESOR"); h[4].caption("ACCIONES")
            pendientes.sort(key=lambda x: (not x["atr"], x["min_orden"]))
            for p in pendientes:
                with st.container():
                    c = st.columns(cols_p)
                    badge = f"<div class='badge badge-red'>{p['pro']}<br>ATRÁS</div>" if p['atr'] else generar_badge_alerta(p['pro'], now_dt)
                    c[0].markdown(badge, unsafe_allow_html=True)
                    c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                    c[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    with c[4]:
                        # Lógica de botones para el flujo: Inicio -> Pausa -> Reanudar -> Fin
                        if not p['ini']:
                            if st.button("▶️ Iniciar", key=f"s{p['fila']}", type="primary", use_container_width=True):
                                hoja.update_cell(p['fila'], IDX_INI1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                        elif p['est'] == "LAVANDO":
                            cb = st.columns(2)
                            if cb[0].button("⏸️", key=f"p{p['fila']}", help="Pausar"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                            if cb[1].button("🏁", key=f"f{p['fila']}", help="Finalizar"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                        elif p['est'] == "PAUSA":
                            if st.button("🔄 Reanudar", key=f"r{p['fila']}", use_container_width=True):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                        elif p['est'] == "REPASO":
                            if st.button("🏁 Finalizar", key=f"f2{p['fila']}", type="primary", use_container_width=True):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("<br>**Finalizados**", unsafe_allow_html=True)
        if terminados_hoy:
            cols_f = [0.6, 0.6, 0.8, 1.5, 0.8, 1.2]
            hf = st.columns(cols_f)
            hf[0].caption("INI"); hf[1].caption("FIN"); hf[2].caption("DOM"); hf[3].caption("MODELO"); hf[4].caption("ASESOR"); hf[5].caption("ESTADO")
            for t in terminados_hoy:
                r = st.columns(cols_f)
                r[0].write(t['ini']); r[1].write(t['fin2'] if t['fin2'] else t['fin'])
                r[2].markdown(f"**{t['dom']}**"); r[3].markdown(f"<small>{t['mod']}</small>", unsafe_allow_html=True)
                r[4].write(t['ase'])
                with r[5]:
                    nk = st.checkbox("OK", value=t['ok'], key=f"ck{t['fila']}")
                    if nk != t['ok']:
                        hoja.update_cell(t['fila'], IDX_CTRL + 1, "OK" if nk else ""); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        # --- PESTAÑA DE MÉTRICAS (PUNTO 3) ---
        if terminados_hoy:
            tiempos = [calcular_minutos(t['ini'], t['fin']) + calcular_minutos(t['ini2'], t['fin2']) for t in terminados_hoy if t['ini']]
            tiempos = [v for v in tiempos if v > 0]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Autos Lavados", len(terminados_hoy))
            m2.metric("Tiempo Promedio", f"{int(sum(tiempos)/len(tiempos))} min" if tiempos else "0 min")
            m3.metric("Tiempo Máximo", f"{max(tiempos)} min" if tiempos else "0 min")
            
            df_hoy = pd.DataFrame(terminados_hoy)
            fig = px.bar(df_hoy['ase'].value_counts(), title="Autos por Asesor", labels={'index':'Asesor', 'value':'Cantidad'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay autos finalizados para mostrar métricas hoy.")

    with tab3:
        # --- PESTAÑA DE HISTORIAL (PUNTO 4) ---
        if historia_data:
            df_hist = pd.DataFrame(historia_data)
            resumen = df_hist.groupby("Fecha").agg(Cantidad=("Asesor", "count"), Promedio_Min=("Tiempo", "mean")).reset_index()
            resumen["Promedio_Min"] = resumen["Promedio_Min"].round(1)
            
            st.markdown("### Resumen por Día")
            st.dataframe(resumen.sort_values("Fecha", ascending=False), use_container_width=True)
            
            fig_hist = px.line(resumen, x="Fecha", y="Cantidad", title="Tendencia de Lavados")
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No hay datos históricos suficientes.")

if __name__ == "__main__":
    main()
