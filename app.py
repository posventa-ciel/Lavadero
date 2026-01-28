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
    .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 20px; border-radius: 8px; color: white;
        display: flex; flex-direction: row; justify-content: space-between; align-items: center;
        margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .header-title { font-size: 26px; font-weight: bold; text-transform: uppercase; margin: 0; }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 4px 0; display: flex; align-items: center; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 12px; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    .badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; text-align: center; min-width: 70px; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-normal { color: #333; font-weight: bold; }
    .badge-ok { color: #2e7d32; font-weight: bold; }
    .stButton button { height: 24px !important; font-size: 11px !important; padding: 0 10px !important; }
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
        st.error(f"Error conectando: {e}")
        return None

# --- 4. FUNCIONES AUXILIARES ---
def generar_badge_alerta(hora_prometida, now_dt):
    if not hora_prometida or ":" not in hora_prometida: return f"<span class='badge-normal'>{hora_prometida}</span>"
    try:
        h, m = map(int, hora_prometida.split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prometida}<br><small>DEMORADO</small></div>"
        elif diff <= 30: return f"<div class='badge badge-red'>{hora_prometida}<br><small>YA!</small></div>"
        elif diff <= 60: return f"<div class='badge badge-yellow'>{hora_prometida}<br><small>ATENCIÓN</small></div>"
        return f"<span class='badge-normal'>{hora_prometida}</span>"
    except: return f"<span class='badge-normal'>{hora_prometida}</span>"

def limpiar_asesor(nombre):
    if not nombre: return ""
    partes = nombre.split()
    return partes[1] if len(partes) > 1 and partes[0].isdigit() else partes[0]

# --- 5. FUNCIÓN PRINCIPAL ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()

    st.markdown(f'<div class="header-box"><div class="header-title">PROGRAMACIÓN LAVADERO</div><div style="text-align: right;"><div style="font-size: 18px; font-weight: 700;">{hoy_date.strftime("%d/%m/%Y")}</div><div>{hora_actual} hs</div></div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # Índices de columnas
    IDX = {"FECHA": 0, "ASESOR": 2, "DOMINIO": 3, "MODELO": 4, "PROMETIDO": 7, "INI1": 8, "FIN1": 9, "INI2": 10, "FIN2": 11, "ESTADO": 12, "CONTROL": 13}

    with st.sidebar:
        st.header("🔍 Búsqueda y Filtros")
        busqueda = st.text_input("Buscar por Dominio (Patente):", "").upper()
        fecha_sel = st.date_input("Fecha de visualización:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes, terminados = [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        dom = fila[IDX["DOMINIO"]].upper()
        if not dom or "NO SE LAVA" in fila[IDX["PROMETIDO"]].upper(): continue

        # Filtro de búsqueda (si hay algo escrito en la barra de búsqueda)
        if busqueda and busqueda not in dom: continue

        f_celda = fila[IDX["FECHA"]]
        f_fin = fila[IDX["FIN1"]] # Fecha/Hora de finalización
        estado = fila[IDX["ESTADO"]].strip().upper()
        
        es_finalizado = (estado == "FINALIZADO") or (fila[IDX["FIN1"]] and not estado) or fila[IDX["FIN2"]]
        
        # LÓGICA DE VISUALIZACIÓN CORREGIDA:
        # Pendientes: Los de hoy o los atrasados que NO estén finalizados.
        # Finalizados: Los que se terminaron HOY (según la fecha en la celda de FIN).
        es_de_hoy = (f_str in f_celda) or (f_str_cero in f_celda)
        
        item = {
            "fila": i, "dom": dom, "mod": fila[IDX["MODELO"]], "ase": limpiar_asesor(fila[IDX["ASESOR"]]),
            "pro": fila[IDX["PROMETIDO"]], "ini": fila[IDX["INI1"]], "fin": fila[IDX["FIN1"]],
            "ini2": fila[IDX["INI2"]], "fin2": fila[IDX["FIN2"]], "est": estado, "ok": (fila[IDX["CONTROL"]].strip().upper() == "OK")
        }

        if es_finalizado:
            # Aparece si se terminó en la fecha seleccionada
            # Nota: Asumimos que la fecha de fin está en la misma fila o es la del día de proceso
            if es_de_hoy: terminados.append(item)
        else:
            # Aparece si es de hoy o si es más viejo (atrasado)
            pendientes.append(item)

    t_op, t_met = st.tabs(["🚗 Operación", "📊 Métricas"])

    with t_op:
        st.subheader(f"Pendientes ({len(pendientes)})")
        cols_p = [0.8, 0.8, 2, 0.8, 1.4]
        for p in pendientes:
            with st.container():
                c = st.columns(cols_p)
                c[0].markdown(generar_badge_alerta(p['pro'], now_dt), unsafe_allow_html=True)
                c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                c[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                c[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                with c[4]:
                    if not p['ini']:
                        if st.button("▶️", key=f"start_{p['fila']}", type="primary"):
                            hoja.update_cell(p['fila'], IDX["INI1"] + 1, hora_actual)
                            hoja.update_cell(p['fila'], IDX["ESTADO"] + 1, "LAVANDO"); st.rerun()
                    elif p['ini'] and not p['fin']:
                        c_btn = st.columns(2)
                        if c_btn[0].button("⏸️", key=f"pause_{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX["FIN1"] + 1, hora_actual)
                            hoja.update_cell(p['fila'], IDX["ESTADO"] + 1, "PAUSA"); st.rerun()
                        if c_btn[1].button("🏁", key=f"fin1_{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX["FIN1"] + 1, hora_actual)
                            hoja.update_cell(p['fila'], IDX["ESTADO"] + 1, "FINALIZADO"); st.rerun()
                    elif p['est'] == "PAUSA":
                        if st.button("🔄", key=f"re_{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX["INI2"] + 1, hora_actual)
                            hoja.update_cell(p['fila'], IDX["ESTADO"] + 1, "REPASO"); st.rerun()
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader(f"Finalizados ({len(terminados)})")
        cols_f = [0.6, 0.6, 0.8, 1.5, 0.8, 1.2]
        for t in terminados:
            with st.container():
                r = st.columns(cols_f)
                r[0].write(t['ini']); r[1].write(t['fin2'] if t['fin2'] else t['fin'])
                r[2].markdown(f"<span class='txt-patente'>{t['dom']}</span>", unsafe_allow_html=True)
                r[3].markdown(f"<span class='txt-modelo'>{t['mod']}</span>", unsafe_allow_html=True)
                r[4].markdown(f"<span class='txt-asesor'>{t['ase']}</span>", unsafe_allow_html=True)
                with r[5]:
                    c_chk, c_txt = st.columns([0.3, 0.7])
                    with c_chk:
                        nk = st.checkbox("", value=t['ok'], key=f"chk_{t['fila']}", label_visibility="collapsed")
                        if nk != t['ok']:
                            hoja.update_cell(t['fila'], IDX["CONTROL"] + 1, "OK" if nk else ""); st.rerun()
                    with c_txt:
                        st.markdown("<span class='badge-ok'>ENTREGADO</span>" if t['ok'] else generar_badge_alerta(t['pro'], now_dt), unsafe_allow_html=True)
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
