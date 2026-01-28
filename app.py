import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

# --- 2. ESTILOS CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px;
    }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 2px 0; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 12px; }
    .badge { padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; min-width: 70px; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-yellow { background-color: #fbc02d; color: black; }
    .badge-ok { color: #2e7d32; font-weight: bold; }
    .stButton button { height: 24px !important; font-size: 11px !important; }
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
        st.error(f"Error: {e}"); return None

# --- 4. FUNCIONES ---
def generar_badge_alerta(hora_prometida, now_dt):
    if not hora_prometida or ":" not in hora_prometida: return f"<span>{hora_prometida}</span>"
    try:
        h, m = map(int, hora_prometida.split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge badge-red'>{hora_prometida}<br>DEMORADO</div>"
        if diff <= 30: return f"<div class='badge badge-red'>{hora_prometida}<br>YA!</div>"
        if diff <= 60: return f"<div class='badge badge-yellow'>{hora_prometida}<br>ATENCIÓN</div>"
        return f"<span>{hora_prometida}</span>"
    except: return f"<span>{hora_prometida}</span>"

# --- 5. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()

    st.markdown(f'<div class="header-box"><div><h2 style="margin:0;">LAVADERO</h2></div><div style="text-align:right;">{hoy_date.strftime("%d/%m/%Y")}<br>{hora_actual} hs</div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    IDX = {"FECHA": 0, "ASE": 2, "DOM": 3, "MOD": 4, "PRO": 7, "INI1": 8, "FIN1": 9, "INI2": 10, "FIN2": 11, "EST": 12, "CTRL": 13}

    with st.sidebar:
        busqueda = st.text_input("🔍 Buscar Patente:").upper()
        fecha_sel = st.date_input("Ver día:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes = []
    finalizados = []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        dom = fila[IDX["DOM"]].upper()
        if not dom or "NO VINO" in fila[IDX["PRO"]].upper(): continue
        if busqueda and busqueda not in dom: continue

        f_ingreso = fila[IDX["FECHA"]]
        estado = fila[IDX["EST"]].strip().upper()
        es_de_hoy = (f_str in f_ingreso) or (f_str_cero in f_ingreso)
        
        # Filtro estricto: ¿Está terminado?
        esta_terminado = (estado == "FINALIZADO") or (fila[IDX["FIN1"]] != "")

        item = {
            "fila": i, "dom": dom, "mod": fila[IDX["MOD"]], "pro": fila[IDX["PRO"]],
            "ini": fila[IDX["INI1"]], "fin": fila[IDX["FIN1"]], "est": estado,
            "ok": (fila[IDX["CTRL"]].strip().upper() == "OK")
        }

        if esta_terminado:
            # SOLO mostramos si el ingreso fue en la fecha que estamos viendo
            if es_de_hoy:
                finalizados.append(item)
        else:
            # PENDIENTES: Mostramos si es de hoy o de días anteriores (atrasados)
            try:
                f_dt = datetime.strptime(f_ingreso.split()[0], "%d/%m/%Y").date()
                if f_dt <= fecha_sel:
                    item["atrasado"] = f_dt < fecha_sel
                    pendientes.append(item)
            except:
                if es_de_hoy: pendientes.append(item)

    # --- RENDER ---
    st.subheader(f"🚗 Pendientes ({len(pendientes)})")
    for p in pendientes:
        cols = st.columns([1, 1, 2, 1.5])
        badge_html = f"<b style='color:red;'>ATRASADO</b><br>{p['pro']}" if p.get("atrasado") else generar_badge_alerta(p['pro'], now_dt)
        cols[0].markdown(badge_html, unsafe_allow_html=True)
        cols[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
        cols[2].write(p['mod'])
        with cols[3]:
            if not p['ini']:
                if st.button("▶️ Iniciar", key=f"s{p['fila']}"):
                    hoja.update_cell(p['fila'], IDX["INI1"]+1, hora_actual)
                    hoja.update_cell(p['fila'], IDX["EST"]+1, "LAVANDO"); st.rerun()
            else:
                if st.button("🏁 Finalizar", key=f"f{p['fila']}"):
                    hoja.update_cell(p['fila'], IDX["FIN1"]+1, hora_actual)
                    hoja.update_cell(p['fila'], IDX["EST"]+1, "FINALIZADO"); st.rerun()
        st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"✅ Finalizados ({len(finalizados)})")
    for f in finalizados:
        cols = st.columns([1, 1, 2, 1.5])
        cols[0].write(f"Fin: {f['fin']}")
        cols[1].markdown(f"<span class='txt-patente'>{f['dom']}</span>", unsafe_allow_html=True)
        cols[2].write(f['mod'])
        with cols[3]:
            check = st.checkbox("Control OK", value=f['ok'], key=f"ck{f['fila']}")
            if check != f['ok']:
                hoja.update_cell(f['fila'], IDX["CTRL"]+1, "OK" if check else ""); st.rerun()
        st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
