import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

# --- 2. ESTILOS CSS (Fiel a tu diseño original) ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px 20px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px;
    }
    .header-title { font-size: 24px; font-weight: bold; text-transform: uppercase; margin: 0; }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 5px 0; margin-bottom: 5px; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 15px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 13px; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-normal { color: #333; font-weight: bold; }
    .stButton button { width: 100%; height: 28px; font-size: 12px; padding: 0; }
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
        st.error(f"Error de conexión: {e}"); return None

# --- 4. FUNCIONES AUXILIARES ---
def obtener_minutos_orden(hora_str):
    if not hora_str or ":" not in str(hora_str): return 99999
    try:
        h, m = map(int, str(hora_str).split(':'))
        return h * 60 + m
    except: return 99999

def limpiar_asesor(nombre):
    if not nombre: return ""
    partes = str(nombre).split()
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

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # Columnas: A=0(Fecha), C=2(Asesor), D=3(Dom), E=4(Mod), H=7(Prom), I=8(Ini1), J=9(Fin1), K=10(Ini2), L=11(Fin2), M=12(Est), N=13(Ctrl)
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13

    with st.sidebar:
        st.markdown("### Filtros")
        busqueda = st.text_input("Buscar Patente:").upper()
        fecha_sel = st.date_input("Fecha de trabajo:", hoy_date)
        # Formatos posibles de fecha en tu Sheet
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")
        if st.button("🔄 Actualizar"): st.rerun()

    st.markdown(f'<div class="header-box"><div class="header-title">LAVADERO: {fecha_sel.strftime("%d/%m/%Y")}</div><div>{hora_actual} hs</div></div>', unsafe_allow_html=True)

    pendientes, terminados = [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        
        f_celda = fila[IDX_FECHA]
        dom = fila[IDX_DOM].upper()
        pro_raw = fila[IDX_PRO].upper()
        estado = fila[IDX_EST].strip().upper()

        # 1. FILTRO DE SEGURIDAD: Solo lo que tenga patente y no sea una exclusión
        if not dom or any(x in pro_raw for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue
        
        # 2. FILTRO DE FECHA ESTRICTO: Solo mostrar lo del día seleccionado
        if not (f_str in f_celda or f_str_cero in f_celda): continue
        
        # 3. FILTRO DE BÚSQUEDA
        if busqueda and busqueda not in dom: continue

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado,
            "ok": (fila[IDX_CTRL].strip().upper() == "OK"),
            "min_orden": obtener_minutos_orden(fila[IDX_PRO])
        }

        if estado == "FINALIZADO" or item["fin2"] != "":
            terminados.append(item)
        else:
            pendientes.append(item)

    tab1, tab2 = st.tabs(["🚗 Operación", "📊 Resumen"])

    with tab1:
        st.write(f"**Pendientes de hoy: {len(pendientes)}**")
        if pendientes:
            pendientes.sort(key=lambda x: x["min_orden"])
            for p in pendientes:
                with st.container():
                    c = st.columns([0.8, 0.8, 2, 0.8, 1.2])
                    c[0].markdown(generar_badge_alerta(p['pro'], now_dt), unsafe_allow_html=True)
                    c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span><br><span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    
                    with c[4]:
                        # Lógica de botones por estado
                        if not p['ini']:
                            if st.button("▶️ Iniciar", key=f"s{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INI1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                        elif p['ini'] and not p['fin']:
                            cb = st.columns(2)
                            if cb[0].button("⏸️", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                            if cb[1].button("🏁", key=f"f{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                        elif p['est'] == "PAUSA":
                            if st.button("🔄 Repaso", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                        elif p['est'] == "REPASO":
                            if st.button("✅ Terminar", key=f"t{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.write(f"**Finalizados: {len(terminados)}**")
        for t in terminados:
            with st.container():
                r = st.columns([1, 1, 2, 1, 1])
                r[0].caption(f"FIN: {t['fin2'] if t['fin2'] else t['fin']}")
                r[1].markdown(f"**{t['dom']}**")
                r[2].markdown(f"{t['mod']} ({t['ase']})")
                with r[4]:
                    if st.checkbox("OK", value=t['ok'], key=f"ck{t['fila']}"):
                        if not t['ok']: 
                            hoja.update_cell(t['fila'], IDX_CTRL + 1, "OK"); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
