import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1rem !important; }
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    }
    .compact-row { border-bottom: 1px solid #e0e0e0; padding: 5px 0; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; text-align: center; display: inline-block; }
    .badge-red { background-color: #d32f2f; color: white; }
    .badge-blue { background-color: #007bff; color: white; }
    .stButton button { height: 24px !important; font-size: 11px !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
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

# --- 3. MAIN ---
def main():
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    now = datetime.now(tz)
    h_act = now.strftime("%H:%M")
    
    hoja = conectar_sheet()
    if not hoja: return
    data = hoja.get_all_values()
    
    # ÍNDICES SEGÚN TU SHEET: I=8(PROMETIDO), J=9(INI), K=10(FIN), L=11(INI2), M=12(FIN2), N=13(ESTADO), O=14(CONTROL)
    IDX_FECHA, IDX_ASE, IDX_DOM, IDX_MOD = 0, 2, 3, 4
    IDX_PRO, IDX_INI, IDX_FIN, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL = 8, 9, 10, 11, 12, 13, 14

    with st.sidebar:
        fecha_sel = st.date_input("Fecha:", now.date())
        busqueda = st.text_input("Patente:").upper()

    f_str = fecha_sel.strftime("%-d/%-m/%Y")
    f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes, terminados = [], []
    patentes_procesadas = set() # Para evitar duplicados

    for i, fila in enumerate(data[1:], start=2):
        if len(fila) < 15: fila += [""] * (15 - len(fila))
        
        dom = fila[IDX_DOM].strip().upper()
        f_fila = fila[IDX_FECHA].strip()
        
        # FILTRO CRÍTICO: Solo si hay patente y es de la fecha seleccionada
        if not dom or not ((f_str in f_fila) or (f_str_cero in f_fila)):
            continue
            
        # Evitar duplicados por si hay filas repetidas en el Sheet
        if dom in patentes_procesadas:
            continue
        patentes_procesadas.add(dom)

        if busqueda and busqueda not in dom: continue
        if any(x in fila[IDX_PRO].upper() for x in ["NO SE LAVA", "NO VINO", "SIN TURNO"]): continue

        estado = fila[IDX_EST].strip().upper()
        item = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "ase": fila[IDX_ASE],
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI], "fin": fila[IDX_FIN],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado,
            "ok": (fila[IDX_CTRL].upper() == "OK")
        }

        if estado == "FINALIZADO":
            terminados.append(item)
        else:
            pendientes.append(item)

    # --- INTERFAZ ---
    st.markdown(f'<div class="header-box"><div class="header-title">LAVADERO</div><div>{f_str} | {h_act} hs</div></div>', unsafe_allow_html=True)

    t1, t2 = st.tabs(["🚗 Operación", "📊 Métricas"])

    with t1:
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        cols_p = st.columns([1, 1, 2, 1, 1.5])
        cols_p[0].caption("PROMETIDO"); cols_p[1].caption("DOMINIO"); cols_p[2].caption("MODELO"); cols_p[3].caption("ASESOR"); cols_p[4].caption("ACCIONES")
        
        for p in pendientes:
            with st.container():
                c = st.columns([1, 1, 2, 1, 1.5])
                b_color = "badge-blue" if p['est'] == "PAUSA" else "badge-red"
                c[0].markdown(f"<div class='badge {b_color}'>{p['pro']}<br>{p['est'] if p['est'] else 'ESPERA'}</div>", unsafe_allow_html=True)
                c[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                c[2].write(p['mod'])
                c[3].write(p['ase'])
                
                with c[4]:
                    # LÓGICA DE BOTONES ÚNICA
                    if not p['ini'] or p['ini'].strip() == "":
                        if st.button("▶️ Iniciar", key=f"btn_s{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                    
                    elif p['est'] == "LAVANDO" or (p['ini'] and not p['fin']):
                        cb = st.columns(2)
                        if cb[0].button("⏸️", key=f"btn_p{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "PAUSA"); st.rerun()
                        if cb[1].button("🏁", key=f"btn_f{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
                    
                    elif p['est'] == "PAUSA":
                        if st.button("🔄 Reanudar", key=f"btn_r{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INI2 + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "REPASO"); st.rerun()
                    
                    elif p['est'] == "REPASO":
                        if st.button("🏁 Finalizar", key=f"btn_f2{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_FIN2 + 1, h_act)
                            hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO"); st.rerun()
            st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        st.markdown(f"<br>**Finalizados ({len(terminados)})**", unsafe_allow_html=True)
        if terminados:
            df_t = pd.DataFrame(terminados)
            st.table(df_t[['ini', 'dom', 'mod', 'ase']])

if __name__ == "__main__":
    main()
