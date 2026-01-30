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
st.set_page_config(page_title="Gestión Lavadero y Taller", layout="wide")

# --- ESTILOS CSS ---
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
    .status-badge { padding: 3px 8px; border-radius: 5px; font-weight: bold; font-size: 12px; }
    .bg-danger { background-color: #f8d7da; color: #721c24; }
    .badge-ok { background-color: #2e7d32; color: white; font-weight: bold; font-size: 11px; padding: 3px 6px; border-radius: 4px; }
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
        st.error(f"Error conectando: {e}"); return None

# --- 3. FUNCIONES AUXILIARES ---
def limpiar_asesor(nombre):
    if not nombre: return ""
    partes = nombre.split()
    return partes[1] if len(partes) > 1 and partes[0].isdigit() else partes[0]

def calcular_tiempo_neto(item):
    try:
        fmt = "%H:%M"
        t1 = 0
        if item['ini'] and item['fin']:
            t1 = (datetime.strptime(item['fin'], fmt) - datetime.strptime(item['ini'], fmt)).total_seconds() / 60
        t2 = 0
        if item['ini2'] and item['fin2']:
            t2 = (datetime.strptime(item['fin2'], fmt) - datetime.strptime(item['ini2'], fmt)).total_seconds() / 60
        return max(0, int(t1 + t2))
    except: return 0

def generar_badge_alerta(hora_prometida, now_dt):
    if not hora_prometida or ":" not in str(hora_prometida): return f"<span>{hora_prometida}</span>"
    try:
        h, m = map(int, str(hora_prometida).split(':'))
        prometida_dt = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = (prometida_dt - now_dt).total_seconds() / 60
        if diff < 0: return f"<div class='badge' style='background-color:#d32f2f;color:white;padding:3px;border-radius:4px;'>{hora_prometida}<br>DEMORADO</div>"
        elif diff <= 30: return f"<div class='badge' style='background-color:#d32f2f;color:white;padding:3px;border-radius:4px;'>{hora_prometida}<br>YA!</div>"
        elif diff <= 60: return f"<div class='badge' style='background-color:#fbc02d;color:black;padding:3px;border-radius:4px;'>{hora_prometida}<br>ATENCIÓN</div>"
        return f"<b>{hora_prometida}</b>"
    except: return f"<span>{hora_prometida}</span>"

# --- 4. MAIN ---
def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    now_dt = datetime.now(tz_ar)
    hora_actual = now_dt.strftime("%H:%M")
    hoy_date = now_dt.date()
    hoy_str = hoy_date.strftime("%d/%m/%Y")

    st.markdown(f'<div class="header-box"><div class="header-title">CONTROL DE EFICIENCIA TALLER</div><div style="text-align: right;"><div style="font-size: 16px; font-weight: 700;">{hoy_date.strftime("%d/%m/%Y")}</div><div style="font-size: 14px; opacity: 0.8;">{hora_actual} hs</div></div></div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return
    raw_data = hoja.get_all_values()

    # ÍNDICES
    # 0:Fecha, 1:Ingreso_DMS (Col B), 2:Asesor, 3:Dom, 4:Modelo, 5:Cliente, 7:Prometido, 12:Estado, 13:OK (Col N), 14:Fecha_Fin (Col O), 15:Recuperado (Col P)
    IDX_FECHA, IDX_ING_DMS, IDX_ASE, IDX_DOM, IDX_MOD, IDX_CLI, IDX_PRO, IDX_INI1, IDX_FIN1, IDX_INI2, IDX_FIN2, IDX_EST, IDX_CTRL, IDX_FECHA_FIN, IDX_RECUPERO = 0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15

    with st.sidebar:
        st.title("⚙️ Filtros")
        fecha_sel = st.date_input("Fecha a consultar:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")
        st.markdown("---")
        busqueda = st.text_input("Buscar Patente:").upper()

    pendientes, finalizados_ver, turnos_eficiencia = [], [], []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 16: fila += [""] * (16 - len(fila))
        
        f_celda = fila[IDX_FECHA]
        es_de_fecha = (f_str in f_celda) or (f_str_cero in f_celda)
        if not es_de_fecha: continue

        dom = fila[IDX_DOM].upper()
        if not dom: continue
        if busqueda and busqueda not in dom: continue

        # --- LÓGICA DE TURNOS ---
        hora_b = fila[IDX_ING_DMS].strip()
        prometido = fila[IDX_PRO].upper()
        modelo = fila[IDX_MOD].upper()
        
        # Solo sumamos a la estadística si Columna B tiene algo
        if hora_b != "":
            es_paracaidista = (hora_b == "13:00")
            es_dms = not es_paracaidista
            vino = not ("NO VINO" in prometido or "NO VINO" in modelo)
            es_mantenimiento = any(x in modelo for x in ["SERV", "10K", "20K", "30K", "40K", "50K", "60K", "70K", "80K", "90K", "100K"])

            turnos_eficiencia.append({
                "fila": i, "dom": dom, "asesor": limpiar_asesor(fila[IDX_ASE]),
                "programado": es_dms, "adicional": es_paracaidista, "vino": vino, 
                "mantenimiento": es_mantenimiento, "recuperado": fila[IDX_RECUPERO].strip().upper() == "SI"
            })

        # --- LÓGICA LAVADERO ---
        estado = fila[IDX_EST].strip().upper()
        tiene_hora_fin = fila[IDX_FIN1].strip() != "" or fila[IDX_FIN2].strip() != ""
        item_lav = {
            "fila": i, "dom": dom, "mod": fila[IDX_MOD], "cli": fila[IDX_CLI], "ase": limpiar_asesor(fila[IDX_ASE]),
            "pro": fila[IDX_PRO], "ini": fila[IDX_INI1], "fin": fila[IDX_FIN1],
            "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2], "est": estado, 
            "ok": fila[IDX_CTRL].strip().upper() in ["SI", "OK"], "fecha_fin_real": fila[IDX_FECHA_FIN]
        }

        if not tiene_hora_fin or estado in ["PAUSA", "REPASO"]:
            pendientes.append(item_lav)
        else:
            if es_de_fecha or (fecha_sel == hoy_date and fila[IDX_FECHA_FIN] == hoy_str):
                finalizados_ver.append(item_lav)

    tab1, tab2, tab3 = st.tabs(["🚗 Operación Lavadero", "📊 Eficiencia de Turnos", "📅 Historial"])

    with tab1:
        # PENDIENTES
        st.subheader(f"Pendientes ({len(pendientes)})")
        if pendientes:
            cols_p = [0.8, 0.8, 1.4, 1.4, 0.8, 1.2]
            for p in pendientes:
                with st.container():
                    c = st.columns(cols_p)
                    c[0].markdown(generar_badge_alerta(p['pro'], now_dt), unsafe_allow_html=True)
                    c[1].write(f"**{p['dom']}**")
                    c[2].write(p['cli']); c[3].write(p['mod']); c[4].write(p['ase'])
                    with c[5]:
                        if not p['ini']:
                            if st.button("▶️", key=f"s{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI1 + 1, now_dt.strftime("%H:%M"))
                                hoja.update_cell(p['fila'], IDX_EST + 1, "LAVANDO"); st.rerun()
                        elif not p['fin']:
                            if st.button("🏁", key=f"f{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN1 + 1, now_dt.strftime("%H:%M"))
                                hoja.update_cell(p['fila'], IDX_EST + 1, "FINALIZADO")
                                hoja.update_cell(p['fila'], IDX_FECHA_FIN + 1, hoy_str); st.rerun()
                    st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

        # FINALIZADOS
        st.subheader(f"Finalizados ({len(finalizados_ver)})")
        for t in finalizados_ver:
            with st.container():
                r = st.columns([0.6, 0.6, 0.6, 0.8, 1.4, 1.4, 0.8, 1.2])
                r[0].write(t['ini']); r[1].write(t['fin']); r[2].write(f"{calcular_tiempo_neto(t)}'")
                r[3].write(f"**{t['dom']}**"); r[4].write(t['cli']); r[5].write(t['mod']); r[6].write(t['ase'])
                with r[7]:
                    c_chk, c_txt = st.columns([0.3, 0.7])
                    with c_chk:
                        nk = st.checkbox("", value=t['ok'], key=f"ck{t['fila']}", label_visibility="collapsed")
                        if nk != t['ok']:
                            hoja.update_cell(t['fila'], IDX_CTRL + 1, "SI" if nk else ""); st.rerun()
                    c_txt.markdown("<span class='badge-ok'>ENTREGADO</span>" if t['ok'] else "", unsafe_allow_html=True)
                st.markdown("<div class='compact-row'></div>", unsafe_allow_html=True)

    with tab2:
        st.header(f"KPI de Turnos Taller")
        if turnos_eficiencia:
            df = pd.DataFrame(turnos_eficiencia)
            prog = df[df['programado'] == True]
            aus = prog[prog['vino'] == False]
            adicionales = df[df['adicional'] == True]
            asistencia = (len(prog[prog['vino']==True]) / len(prog) * 100) if len(prog)>0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Agenda DMS", len(prog))
            c2.metric("Show-up (Asistencia)", f"{int(asistencia)}%")
            c3.metric("Adicionales (13:00hs)", len(adicionales))
            c4.metric("Servicios 10k-100k", len(df[df['mantenimiento']==True]))

            st.markdown("---")
            st.subheader("📞 Recupero de Turnos Ausentes")
            if len(aus) > 0:
                for _, a in aus.iterrows():
                    col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
                    col1.write(f"**{a['dom']}**")
                    col2.write(f"Asesor: {a['asesor']}")
                    col3.markdown("<span class='status-badge bg-danger'>NO VINO</span>", unsafe_allow_html=True)
                    if a['recuperado']:
                        col4.success("RECUPERADO ✅")
                    else:
                        if col4.button("Marcar Recuperado", key=f"recu_{a['fila']}"):
                            hoja.update_cell(a['fila'], IDX_RECUPERO + 1, "SI"); st.rerun()
            else:
                st.success("Sin ausentes registrados.")
        else:
            st.info("No hay datos en la Columna B para medir eficiencia hoy.")

    with tab3:
        st.write("Cargando historial...")
        # (Aquí puedes mantener el gráfico de barras que ya teníamos)

if __name__ == "__main__":
    main()
