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

# --- 2. ESTILOS CSS (MANTENIDOS) ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px 20px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px;
    }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 4px 0; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 12px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .stButton button { height: 26px !important; font-size: 11px !important; width: 100%; }
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
    if not hora_prometida or ":" not in str(hora_prometida): return f"<span>{hora_prometida}</span>"
    try:
        h, m = map(int, str(hora_prometida).split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prometida}<br>DEMORADO</div>"
        elif diff <= 30: return f"<div class='badge badge-red'>{hora_prometida}<br>YA!</div>"
        elif diff <= 60: return f"<div class='badge badge-yellow'>{hora_prometida}<br>ATENCIÓN</div>"
        return f"<span>{hora_prometida}</span>"
    except: return f"<span>{hora_prometida}</span>"

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # Índices estrictos (No tocados)
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13

    with st.sidebar:
        busqueda = st.text_input("🔍 Patente").upper()
        fecha_sel = st.date_input("Ver fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes, terminados_hoy, historial_all = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        dom = fila[IDX_DOM].upper()
        if not dom: continue
        
        pro_raw = fila[IDX_PRO].upper()
        if any(x in pro_raw for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue

        f_celda = fila[IDX_FECHA]
        estado = fila[IDX_EST].strip().upper()
        
        # --- Lógica de Finalizado Estricta (Punto 2) ---
        es_finalizado = (estado == "FINALIZADO")
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado, 
            "ok": (fila[IDX_CTRL].strip().upper() == "OK"),
            "min_orden": obtener_minutos_orden(fila[IDX_PRO]),
            "fecha_orig": f_celda.split()[0]
        }

        # Guardamos todo lo finalizado para el Historial (Punto 4)
        if es_finalizado:
            historial_all.append(item)

        if busqueda and busqueda not in dom: continue

        if es_finalizado:
            if es_de_fecha: terminados_hoy.append(item)
        else:
            # --- SOLUCIÓN 8 AUTOS ---
            # Solo mostrar si es de hoy O si es un atrasado que está ACTIVO (Lavando, Pausa o Repaso)
            es_atrasado = False
            try:
                f_dt = datetime.strptime(f_celda.split()[0], "%d/%m/%Y").date()
                if f_dt < fecha_sel: es_atrasado = True
            except: pass
            
            if es_de_fecha or (es_atrasado and (estado in ["LAVANDO", "PAUSA", "REPASO"] or item['ini'])):
                item["atr"] = es_atrasado
                pendientes.append(item)

    st.markdown(f'<div class="header-box"><div style="font-size:20px; font-weight:bold;">PROGRAMACIÓN LAVADERO</div><div>{hoy_date.strftime("%d/%m/%Y")} - {hora_actual} hs</div></div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🚗 Operación", "📊 Métricas", "📜 Historial"])

    with tab1:
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        cols_p = [0.8, 0.9, 2, 0.8, 1.4]
        # Punto 1: Títulos de columnas
        h = st.columns(cols_p)
        h[0].caption("PROMETIDO"); h[1].caption("DOMINIO"); h[2].caption("MODELO"); h[3].caption("ASESOR"); h[4].caption("ACCIONES")
        
        for p in sorted(pendientes, key=lambda x: (not x.get('atr', False), x['min_orden'])):
            with st.container():
                c = st.columns(cols_p)
                badge = f"<div class='badge badge-red'>{p['pro']}<br>ATRASADO</div>" if p.get('atr') else generar_badge_alerta(p['pro'], now_dt)
                c[0].markdown(badge, unsafe_allow_html=True)
                c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                c[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                with c[4]:
                    # Punto 2: Corregir Pausa/Reanudar y que no desaparezca
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
                            col_f = IDX_FIN2 + 1 if p['est'] == "REPASO" else IDX_FIN1 + 1
                            hoja.update_cell(p['fila'], col_f, hora_actual)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"**Finalizados ({len(terminados_hoy)})**")
        if terminados_hoy:
            cols_f = [0.6, 0.6, 0.8, 1.5, 0.8, 1.2]
            hf = st.columns(cols_f)
            hf[0].caption("INI"); hf[1].caption("FIN"); hf[2].caption("DOM"); hf[3].caption("MODELO"); hf[4].caption("ASESOR"); hf[5].caption("CONTROL")
            for t in terminados_hoy:
                r = st.columns(cols_f)
                r[0].write(t['ini']); r[1].write(t['fin2'] if t['fin2'] else t['fin'])
                r[2].markdown(f"<span class='txt-patente'>{t['dom']}</span>", unsafe_allow_html=True)
                r[3].markdown(f"<span class='txt-modelo'>{t['mod']}</span>", unsafe_allow_html=True)
                r[4].markdown(f"<span class='txt-asesor'>{t['ase']}</span>", unsafe_allow_html=True)
                with r[5]:
                    nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                    if nk != t['ok']:
                        hoja.update_cell(t['fila'], IDX_CTRL + 1, "OK" if nk else ""); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        # Punto 3: Métricas
        st.subheader("Rendimiento de Hoy")
        tiempos = [calcular_minutos(t['ini'], t['fin2'] if t['fin2'] else t['fin']) for t in terminados_hoy if t['ini']]
        m1, m2, m3 = st.columns(3)
        m1.metric("Autos Hoy", len(terminados_hoy))
        m2.metric("Tiempo Promedio", f"{int(sum(tiempos)/len(tiempos)) if tiempos else 0} min")
        m3.metric("Tiempo Máximo", f"{max(tiempos) if tiempos else 0} min")
        if terminados_hoy:
            df_hoy = pd.DataFrame(terminados_hoy)
            st.plotly_chart(px.bar(df_hoy.groupby('ase').size().reset_index(name='Cant'), x='ase', y='Cant', title="Lavados por Asesor"), use_container_width=True)

    with tab3:
        # Punto 4: Historial
        st.subheader("Tendencia de Lavados")
        if historial_all:
            df_h = pd.DataFrame(historial_all)
            df_trend = df_h.groupby('fecha_orig').size().reset_index(name='Lavados')
            st.plotly_chart(px.line(df_trend, x='fecha_orig', y='Lavados', title="Lavados por Día", markers=True), use_container_width=True)
            st.dataframe(df_trend.sort_values('fecha_orig', ascending=False), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
