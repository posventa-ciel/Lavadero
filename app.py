import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Lavadero Postventa", layout="wide")

# --- ESTILOS "MAXIMIZE ROWS" ---
st.markdown("""
<style>
    /* 1. PEGAR AL TECHO: Padding mínimo arriba */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
        margin-top: 0 !important;
    }
    
    /* 2. HEADER ULTRA COMPACTO */
    .header-div {
        display: flex;
        align-items: center;
        gap: 10px;
        padding-bottom: 5px;
        margin-bottom: 5px;
        border-bottom: 2px solid #00235d;
    }
    .main-title { 
        font-size: 18px !important; /* Título más chico */
        font-weight: bold; 
        color: #00235d; 
        margin: 0 !important; 
        line-height: 1.2;
    }
    .sub-title { 
        font-size: 12px; 
        color: #666; 
        margin: 0 !important; 
    }
    
    /* 3. FILAS DELGADAS (Para ganar esa fila extra) */
    .row-container { 
        padding: 2px 0 !important; 
        border-bottom: 1px solid #eee; 
        align-items: center; 
        min-height: 30px !important;
    }
    
    /* 4. FUENTES AJUSTADAS */
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 13px; }
    .txt-patente { color: #004488; font-weight: bold; font-size: 13px; }
    .txt-modelo { color: #333; font-size: 12px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .txt-asesor { color: #666; font-size: 11px; font-style: italic; }
    
    /* 5. BOTONES SLIM */
    .stButton button { 
        width: 100%; 
        border-radius: 4px; 
        font-weight: 600; 
        font-size: 11px !important;
        height: 26px !important; /* Botón bien bajito */
        padding: 0px !important;
        line-height: 1 !important;
    }

    /* KPI Cards */
    .kpi-card { 
        background-color: white; 
        border: 1px solid #ddd; 
        border-radius: 6px; 
        padding: 5px; 
        text-align: center; 
    }
    .kpi-val { font-size: 18px; font-weight: bold; color: #003366; }
    .kpi-lbl { font-size: 10px; color: #666; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN GOOGLE SHEETS ---
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

# --- FUNCIONES ---
def calcular_minutos(h1, h2):
    try:
        fmt = "%H:%M"
        t1 = datetime.strptime(h1, fmt)
        t2 = datetime.strptime(h2, fmt)
        return int((t2 - t1).total_seconds() / 60)
    except: return 0

def normalizar_hora(hora_str):
    if not hora_str: return "99:99"
    if ":" in hora_str:
        try:
            h, m = hora_str.split(":")
            return f"{int(h):02d}:{m}"
        except: return hora_str
    return hora_str

def obtener_minutos_orden(hora_str):
    if not hora_str: return 99999
    try:
        h, m = map(int, hora_str.split(':'))
        return h * 60 + m
    except: return 99999

def limpiar_asesor(nombre_completo):
    if not nombre_completo: return ""
    partes = nombre_completo.split()
    if len(partes) > 1 and partes[0].isdigit():
        return partes[1]
    return partes[0]

def main():
    # --- HEADER MANUAL (Para control total del tamaño) ---
    st.markdown("""
    <div class="header-div">
        <img src="https://upload.wikimedia.org/wikipedia/commons/f/f7/Peugeot_Logo_2021.svg" width="35">
        <div>
            <p class="main-title">CONTROL LAVADERO</p>
            <p class="sub-title">Gestión Postventa</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return

    raw_data = hoja.get_all_values()
    
    # INDICES
    IDX_FECHA = 0
    IDX_ASESOR = 2
    IDX_DOMINIO = 3
    IDX_MODELO = 4
    IDX_PROMETIDO = 7
    IDX_INICIO = 8
    IDX_FIN = 9
    IDX_INI2 = 10
    IDX_FIN2 = 11
    IDX_ESTADO = 12
    IDX_CONTROL = 13 

    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    with st.sidebar:
        st.markdown("**Filtros**")
        fecha_sel = st.date_input("Fecha:", hoy_date, label_visibility="collapsed")
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes = []
    terminados = []
    tiempos_dia = []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        
        dom = fila[IDX_DOMINIO]
        pro_raw = fila[IDX_PROMETIDO].upper()
        
        if not dom: continue
        if "NO SE LAVA" in pro_raw or "NO VINO" in pro_raw: continue

        fecha_celda = fila[IDX_FECHA]
        ini1, fin1 = fila[IDX_INICIO], fila[IDX_FIN]
        ini2, fin2 = fila[IDX_INI2], fila[IDX_FIN2]
        estado = fila[IDX_ESTADO].strip().upper()
        control_ok = fila[IDX_CONTROL].strip().upper()

        es_finalizado = (estado == "FINALIZADO") or (fin1 and not estado) or fin2
        es_hoy = (f_str in fecha_celda) or (f_str_cero in fecha_celda) or (f_str in pro_raw)
        
        es_atrasado = False
        if not es_finalizado:
            try:
                f_dt = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                if f_dt < fecha_sel: es_atrasado = True
            except: pass

        if es_hoy or es_atrasado:
            item = {
                "fila": i,
                "dom": dom, "mod": fila[IDX_MODELO],
                "ase": limpiar_asesor(fila[IDX_ASESOR]),
                "pro": fila[IDX_PROMETIDO],
                "ini": ini1, "fin": fin1,
                "ini2": ini2, "fin2": fin2,
                "est": estado, "atr": es_atrasado,
                "ok": (control_ok == "OK"),
                "orden_pend": normalizar_hora(fila[IDX_PROMETIDO]),
                "orden_term": obtener_minutos_orden(ini1)
            }

            if es_finalizado:
                terminados.append(item)
                if es_hoy:
                    t = calcular_minutos(ini1, fin1)
                    if ini2 and fin2: t += calcular_minutos(ini2, fin2)
                    if t > 0: tiempos_dia.append(t)
            else:
                pendientes.append(item)

    tab_op, tab_kpi = st.tabs(["🚗 Operación", "📈 KPIs"])

    with tab_op:
        # --- PENDIENTES ---
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        if pendientes:
            pendientes.sort(key=lambda x: (not x["atr"], x["orden_pend"]))
            
            c_h = st.columns([0.6, 0.8, 2.5, 0.8, 1.3])
            c_h[0].caption("HORA")
            c_h[1].caption("DOMINIO")
            c_h[2].caption("MODELO")
            c_h[3].caption("ASESOR")
            c_h[4].caption("ACCION")
            
            for p in pendientes:
                with st.container():
                    col = st.columns([0.6, 0.8, 2.5, 0.8, 1.3])
                    
                    hora_txt = f"⚠️ {p['pro']}" if p['atr'] else p['pro']
                    col[0].markdown(f"<span class='txt-hora'>{hora_txt}</span>", unsafe_allow_html=True)
                    col[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    col[2].markdown(f"<span class='txt-modelo' title='{p['mod']}'>{p['mod']}</span>", unsafe_allow_html=True)
                    col[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    
                    with col[4]:
                        if not p['ini']:
                            if st.button("▶️ INICIO", key=f"g{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INICIO + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "LAVANDO")
                                st.rerun()
                        elif p['ini'] and not p['fin']:
                            c_b = st.columns(2)
                            if c_b[0].button("⏸️", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "PAUSA")
                                st.rerun()
                            if c_b[1].button("🏁", key=f"f1{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                        elif p['est'] == "PAUSA" and not p['ini2']:
                            if st.button("🔄 RETOMAR", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "REPASO")
                                st.rerun()
                        elif p['ini2'] and not p['fin2']:
                            if st.button("🏁 FIN", key=f"f2{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                    st.markdown("<div class='row-container'></div>", unsafe_allow_html=True)
        else:
            st.info("Sin pendientes.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- FINALIZADOS ---
        st.markdown(f"**Finalizados ({len(terminados)})**")
        if terminados:
            terminados.sort(key=lambda x: x["orden_term"])
            
            c_t = st.columns([0.6, 0.6, 0.8, 2.5, 0.8, 0.5])
            c_t[0].caption("INI")
            c_t[1].caption("FIN")
            c_t[2].caption("DOM")
            c_t[3].caption("MODELO")
            c_t[4].caption("ASE")
            c_t[5].caption("OK")
            
            for t in terminados:
                r = st.columns([0.6, 0.6, 0.8, 2.5, 0.8, 0.5])
                fin_s = t['fin2'] if t['fin2'] else t['fin']
                
                r[0].write(t['ini'])
                r[1].write(fin_s)
                r[2].markdown(f"<span class='txt-patente'>{t['dom']}</span>", unsafe_allow_html=True)
                r[3].markdown(f"<span class='txt-modelo'>{t['mod']}</span>", unsafe_allow_html=True)
                r[4].markdown(f"<span class='txt-asesor'>{t['ase']}</span>", unsafe_allow_html=True)
                
                with r[5]:
                    nuevo_ok = st.checkbox("OK", value=t['ok'], key=f"chk_{t['fila']}", label_visibility="collapsed")
                    if nuevo_ok != t['ok']:
                        valor_sheet = "OK" if nuevo_ok else ""
                        hoja.update_cell(t['fila'], IDX_CONTROL + 1, valor_sheet)
                        st.rerun()
                
                st.markdown("<div class='row-container'></div>", unsafe_allow_html=True)

    with tab_kpi:
        k1, k2, k3 = st.columns(3)
        avg = int(sum(tiempos_dia)/len(tiempos_dia)) if tiempos_dia else 0
        with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(terminados)}</div><div class='kpi-lbl'>Total</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{avg}'</div><div class='kpi-lbl'>Promedio</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{max(tiempos_dia) if tiempos_dia else 0}'</div><div class='kpi-lbl'>Máx</div></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
