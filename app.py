import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN DE PÁGINA (Layout Wide) ---
st.set_page_config(page_title="Lavadero Postventa", layout="wide")

# --- LOGO PEUGEOT EN BASE64 (Para asegurar que se vea siempre) ---
LOGO_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAMAAAAp4XiDAAAAhFBMVEUAAAAA//8AzMwA/wAAzP8A//8MzMwMzP8AmZkAmf8zMzMAZmYAzMwz/zMA/8wz//8z/MwzAABmZgBm/2Zm//9m/5lm/2YzM2YzM5lmZswzM8wzM/8zMzMzAAAAmcwAmf8AmZkAZswAZpkAZgAAZjMAZswAMzMAM2YAMwAAM8wAM/8AMwBmZma2AAAAxnRSTlMAu4vC/vC3j/7+/v7+8q+Z/v7+q4uL/v7+u/7+tI/+/v7+i/7+s5n+tP7+i4v+/v7+3/v7+i/7+8v7+/v7+tP7+8ov+/v7+q4v+/v7+q/7+/v6L/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v63/v7+i/7+/v7+/v7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+q/7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+8r7r3wAAAfdJREFUSMe1lU1rwlAQx08T32qsFxF8W6u26sVaD1ZBqCCFInioQvHQAwqeexD8f9+kE81LFl1P3eG3CNnN/Oad5M2E4J9A6LgO05iWwzAMg9gO05QG/xLItw7bSiaTrm3fOiyCDeR7j+tUq9Vut0/53uclhEB+DLhOvV4fDAbD4ZB9DDgR+Tng5vP5YDAajUbD4Xg8Ho3H48F87uZE5NeIm8/n0+l0Op3NZrPZbDabz6fT+dzLi8ivCTefz2ez2Ww2m81ms9lsNpvNZtP53MuLyK8JN5/PZ7PZbDabzWaz2Ww2m81m0/ncy4vIrwk3n89ns9lsNpvNZrO5d1y31+s5/wEivybcfD6fTqfT6XQ2m81ms9lsPp9O53MvLyK/Btx8Ph8MRqPRaDgcXl9fX11djcfjwXzu5kTkx4Dr1Ov1wWAwHA7ZxwD7I0gI5FuP61Sr1W63T/neZyVEIP86bCuZTLq2fessgQzDMI1p2QzDMAx7J7bDNKXBP4FwHIdpDMuwDMvYDtM49k8gXNdhGtNyGIZhENthmtLgXwL51mFbyWTS9X91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3WI/zrEfx3ivw7xX4f4r0P81yH+6xD/dYj/OsR/HeK/DvFfh/ivQ/zXIf7rEP91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3XIf/0G26wW10u4R5gAAAAASUVORK5CYII="

# --- ESTILOS COMPACTOS (CSS) ---
st.markdown("""
<style>
    /* 1. Subir todo al techo (Eliminar padding superior) */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        margin-top: 0rem !important;
    }
    
    /* 2. Header compacto */
    .header-container {
        display: flex; 
        align-items: center; 
        gap: 10px; 
        padding-bottom: 5px; 
        border-bottom: 2px solid #00235d;
        margin-bottom: 5px;
    }
    .main-title { font-size: 20px !important; font-weight: bold; color: #00235d; margin: 0; }
    .sub-title { font-size: 12px; color: #666; margin: 0; }

    /* 3. Tablas compactas */
    .row-container { 
        padding: 2px 0 !important; 
        border-bottom: 1px solid #eee; 
        align-items: center; 
    }
    
    /* 4. Textos más chicos para ver más filas */
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 13px; }
    .txt-patente { color: #0056b3; font-weight: bold; font-size: 13px; }
    .txt-modelo { color: #333; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .txt-asesor { color: #666; font-size: 11px; }
    
    /* 5. Botones pequeños */
    .stButton button { 
        width: 100%; 
        border-radius: 4px; 
        font-size: 11px !important; 
        font-weight: bold; 
        padding: 2px !important; 
        height: 24px !important;
        min-height: 24px !important;
        margin-top: 0px !important;
    }
    
    /* KPI Cards compactas */
    .kpi-card { background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 5px; padding: 5px; text-align: center; }
    .kpi-val { font-size: 18px; font-weight: bold; color: #003366; }
    .kpi-lbl { font-size: 11px; color: #666; }
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
        st.error(f"Error: {e}")
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

def main():
    # --- HEADER COMPACTO CON IMAGEN BLINDADA ---
    st.markdown(f"""
    <div class="header-container">
        <img src="{LOGO_B64}" width="45" style="border-radius: 4px;">
        <div>
            <h1 class="main-title">POSTVENTA - LAVADERO</h1>
        </div>
    </div>
    """, unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return

    # --- LECTURA ---
    raw_data = hoja.get_all_values()
    
    # Índices
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

    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    # --- SIDEBAR COMPACTO ---
    with st.sidebar:
        st.markdown("**Filtros**") # Título más chico
        fecha_sel = st.date_input("Fecha:", hoy_date, label_visibility="collapsed")
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    # --- PROCESAMIENTO ---
    pendientes = []
    terminados = []
    tiempos_dia = []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 13: fila += [""] * (13 - len(fila))
        
        dom = fila[IDX_DOMINIO]
        pro_raw = fila[IDX_PROMETIDO].upper()
        
        if not dom: continue
        if "NO SE LAVA" in pro_raw or "NO VINO" in pro_raw: continue

        fecha_celda = fila[IDX_FECHA]
        ini1, fin1 = fila[IDX_INICIO], fila[IDX_FIN]
        ini2, fin2 = fila[IDX_INI2], fila[IDX_FIN2]
        estado = fila[IDX_ESTADO].strip().upper()

        # Determinar Finalizado
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
                "ase": fila[IDX_ASESOR], "pro": fila[IDX_PROMETIDO],
                "ini": ini1, "fin": fin1,
                "ini2": ini2, "fin2": fin2,
                "est": estado, "atr": es_atrasado,
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

    # --- INTERFAZ ---
    tab_op, tab_kpi = st.tabs(["🚗 Operación", "📈 KPIs"])

    with tab_op:
        # PENDIENTES
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        
        if pendientes:
            pendientes.sort(key=lambda x: (not x["atr"], x["orden_pend"]))
            
            # Columnas ajustadas para compactar
            # Reducimos espacio de Hora y Patente, damos más a Modelo
            c_h = st.columns([0.6, 0.8, 2.5, 1, 1.3])
            c_h[0].caption("HORA")
            c_h[1].caption("DOM")
            c_h[2].caption("MODELO")
            c_h[3].caption("ASESOR")
            c_h[4].caption("ACCIÓN")
            
            for p in pendientes:
                with st.container():
                    col = st.columns([0.6, 0.8, 2.5, 1, 1.3])
                    
                    # Datos
                    hora_txt = f"⚠️ {p['pro']}" if p['atr'] else p['pro']
                    col[0].markdown(f"<span class='txt-hora'>{hora_txt}</span>", unsafe_allow_html=True)
                    col[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    col[2].markdown(f"<span class='txt-modelo' title='{p['mod']}'>{p['mod']}</span>", unsafe_allow_html=True)
                    col[3].markdown(f"<span class='txt-asesor'>{p['ase'].split(' ')[0]}</span>", unsafe_allow_html=True) # Solo primer nombre asesor
                    
                    with col[4]:
                        if not p['ini']:
                            if st.button("▶️", key=f"go{p['fila']}", type="primary"):
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
                            if st.button("🔄", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "REPASO")
                                st.rerun()
                        elif p['ini2'] and not p['fin2']:
                            if st.button("🏁", key=f"f2{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                        else:
                            if st.button("Forzar", key=f"x{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()

                    st.markdown("<div class='row-container'></div>", unsafe_allow_html=True)
        else:
            st.info("Sin pendientes.")

        # TERMINADOS
        st.markdown(f"**Listos ({len(terminados)})**")
        if terminados:
            terminados.sort(key=lambda x: x["orden_term"])
            
            c_t = st.columns([0.6, 0.6, 0.8, 2.5, 1])
            c_t[0].caption("INI")
            c_t[1].caption("FIN")
            c_t[2].caption("DOM")
            c_t[3].caption("MODELO")
            c_t[4].caption("ASE")
            
            for t in terminados:
                r = st.columns([0.6, 0.6, 0.8, 2.5, 1])
                fin_s = t['fin2'] if t['fin2'] else t['fin']
                
                r[0].markdown(f"<span class='txt-asesor'>{t['ini']}</span>", unsafe_allow_html=True)
                r[1].markdown(f"<span class='txt-asesor'>{fin_s}</span>", unsafe_allow_html=True)
                r[2].markdown(f"<span class='txt-patente'>{t['dom']}</span>", unsafe_allow_html=True)
                r[3].markdown(f"<span class='txt-modelo'>{t['mod']}</span>", unsafe_allow_html=True)
                r[4].markdown(f"<span class='txt-asesor'>{t['ase'].split(' ')[0]}</span>", unsafe_allow_html=True)
                st.markdown("<div class='row-container'></div>", unsafe_allow_html=True)

    with tab_kpi:
        k1, k2, k3 = st.columns(3)
        avg = int(sum(tiempos_dia)/len(tiempos_dia)) if tiempos_dia else 0
        with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(terminados)}</div><div class='kpi-lbl'>Total</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{avg}'</div><div class='kpi-lbl'>Promedio</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{max(tiempos_dia) if tiempos_dia else 0}'</div><div class='kpi-lbl'>Máx</div></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
