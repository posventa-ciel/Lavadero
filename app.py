import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Lavadero Postventa", layout="wide")

# --- ESTILOS VISUALES MEJORADOS (NO TAN COMPACTOS) ---
st.markdown("""
<style>
    /* Ajuste para ganar espacio arriba sin pegar el título al borde */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Títulos */
    .main-header { font-size: 26px; font-weight: bold; color: #003366; margin: 0; }
    .sub-header { font-size: 14px; color: #666; margin-bottom: 10px; }
    
    /* Filas de la tabla con mejor espaciado */
    .row-container { 
        padding: 6px 0; 
        border-bottom: 1px solid #e0e0e0; 
        align-items: center; 
        min-height: 40px;
    }
    
    /* Textos Legibles */
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 15px; }
    .txt-patente { color: #004488; font-weight: bold; font-size: 15px; }
    .txt-modelo { color: #333; font-size: 14px; font-weight: 500; }
    .txt-asesor { color: #555; font-size: 13px; font-style: italic; }
    
    /* Botones más funcionales */
    .stButton button { 
        width: 100%; 
        border-radius: 4px; 
        font-weight: 600; 
        font-size: 13px;
        height: 32px;
    }

    /* KPI Cards */
    .kpi-card { 
        background-color: white; 
        border: 1px solid #ddd; 
        border-radius: 8px; 
        padding: 10px; 
        text-align: center; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .kpi-val { font-size: 22px; font-weight: bold; color: #003366; }
    .kpi-lbl { font-size: 12px; color: #666; text-transform: uppercase; }
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
    # Lógica: Si "21 JAVIER...", toma "JAVIER". Si "BELEN...", toma "BELEN".
    if not nombre_completo: return ""
    partes = nombre_completo.split()
    if len(partes) > 1 and partes[0].isdigit():
        return partes[1] # Devuelve el segundo elemento si el primero es numero
    return partes[0] # Devuelve el primero si no es numero

def main():
    # --- HEADER ---
    col_img, col_txt = st.columns([0.15, 0.85])
    with col_img:
        st.image("https://upload.wikimedia.org/wikipedia/commons/f/f7/Peugeot_Logo_2021.svg", use_container_width=True)
    with col_txt:
        st.markdown('<h1 class="main-header">CONTROL DE LAVADERO - POSTVENTA</h1>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Gestión de calidad y tiempos</div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return

    raw_data = hoja.get_all_values()
    
    # INDICES (Agregamos la Columna N para CONTROL)
    # A=0 ... M=12 ... N=13 (CONTROL)
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
    IDX_CONTROL = 13 # NUEVA COLUMNA

    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    with st.sidebar:
        st.markdown("### 📅 Filtros")
        fecha_sel = st.date_input("Fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes = []
    terminados = []
    tiempos_dia = []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila)) # Rellenar hasta Col N
        
        dom = fila[IDX_DOMINIO]
        pro_raw = fila[IDX_PROMETIDO].upper()
        
        if not dom: continue
        if "NO SE LAVA" in pro_raw or "NO VINO" in pro_raw: continue

        fecha_celda = fila[IDX_FECHA]
        ini1, fin1 = fila[IDX_INICIO], fila[IDX_FIN]
        ini2, fin2 = fila[IDX_INI2], fila[IDX_FIN2]
        estado = fila[IDX_ESTADO].strip().upper()
        control_ok = fila[IDX_CONTROL].strip().upper() # Valor de la celda OK

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
                "ase": limpiar_asesor(fila[IDX_ASESOR]), # Limpiamos el nombre aquí
                "pro": fila[IDX_PROMETIDO],
                "ini": ini1, "fin": fin1,
                "ini2": ini2, "fin2": fin2,
                "est": estado, "atr": es_atrasado,
                "ok": (control_ok == "OK"), # Boolean para el checkbox
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

    tab_op, tab_kpi = st.tabs(["🚗 Operación", "📈 Indicadores"])

    with tab_op:
        # --- PENDIENTES ---
        st.markdown(f"### 📋 Pendientes ({len(pendientes)})")
        if pendientes:
            pendientes.sort(key=lambda x: (not x["atr"], x["orden_pend"]))
            
            # Encabezados
            c_h = st.columns([0.8, 1, 2.2, 1, 1.2])
            c_h[0].caption("HORA")
            c_h[1].caption("PATENTE")
            c_h[2].caption("MODELO")
            c_h[3].caption("ASESOR")
            c_h[4].caption("ACCIÓN")
            
            for p in pendientes:
                with st.container():
                    col = st.columns([0.8, 1, 2.2, 1, 1.2])
                    
                    hora_txt = f"⚠️ {p['pro']}" if p['atr'] else p['pro']
                    col[0].markdown(f"<span class='txt-hora'>{hora_txt}</span>", unsafe_allow_html=True)
                    col[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    col[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                    col[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    
                    with col[4]:
                        if not p['ini']:
                            if st.button("▶️ INICIAR", key=f"g{p['fila']}", type="primary"):
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
            st.info("No hay vehículos pendientes.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- FINALIZADOS CON CONTROL ---
        st.markdown(f"### ✅ Finalizados ({len(terminados)})")
        if terminados:
            terminados.sort(key=lambda x: x["orden_term"])
            
            c_t = st.columns([0.8, 0.8, 1, 2.5, 1, 0.8])
            c_t[0].caption("INICIO")
            c_t[1].caption("FIN")
            c_t[2].caption("PATENTE")
            c_t[3].caption("MODELO")
            c_t[4].caption("ASESOR")
            c_t[5].caption("CONTROL") # Nueva columna
            
            for t in terminados:
                r = st.columns([0.8, 0.8, 1, 2.5, 1, 0.8])
                fin_s = t['fin2'] if t['fin2'] else t['fin']
                
                r[0].write(t['ini'])
                r[1].write(fin_s)
                r[2].markdown(f"<span class='txt-patente'>{t['dom']}</span>", unsafe_allow_html=True)
                r[3].markdown(f"<span class='txt-modelo'>{t['mod']}</span>", unsafe_allow_html=True)
                r[4].markdown(f"<span class='txt-asesor'>{t['ase']}</span>", unsafe_allow_html=True)
                
                # Checkbox para el Control de Calidad
                with r[5]:
                    # Si ya estaba OK, aparece marcado. Si el usuario lo cambia, se actualiza el sheet.
                    nuevo_ok = st.checkbox("OK", value=t['ok'], key=f"chk_{t['fila']}", label_visibility="collapsed")
                    if nuevo_ok != t['ok']:
                        valor_sheet = "OK" if nuevo_ok else ""
                        hoja.update_cell(t['fila'], IDX_CONTROL + 1, valor_sheet)
                        st.rerun()
                
                st.markdown("<div class='row-container'></div>", unsafe_allow_html=True)

    with tab_kpi:
        k1, k2, k3 = st.columns(3)
        avg = int(sum(tiempos_dia)/len(tiempos_dia)) if tiempos_dia else 0
        with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(terminados)}</div><div class='kpi-lbl'>Total Lavados</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{avg}'</div><div class='kpi-lbl'>Promedio Taller</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{max(tiempos_dia) if tiempos_dia else 0}'</div><div class='kpi-lbl'>Pico Máximo</div></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
