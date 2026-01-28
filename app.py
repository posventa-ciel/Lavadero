import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Lavadero Postventa", layout="wide")

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    .main-header { font-size: 24px; font-weight: bold; color: #003366; margin-bottom: 5px; }
    .sub-header { font-size: 14px; color: #666; margin-bottom: 15px; }
    .kpi-card { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 10px; text-align: center; }
    .kpi-val { font-size: 20px; font-weight: bold; color: #003366; }
    .kpi-lbl { font-size: 12px; color: #666; text-transform: uppercase; }
    .stButton button { width: 100%; border-radius: 4px; font-size: 12px; font-weight: 600; padding: 4px; }
    .row-container { padding: 8px 0; border-bottom: 1px solid #eee; align-items: center; }
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 14px; }
    .txt-patente { color: #0056b3; font-weight: bold; font-size: 14px; }
    .txt-modelo { color: #444; font-size: 13px; }
    .txt-asesor { color: #777; font-size: 12px; }
    .status-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
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
        st.error(f"Error conectando a Google Sheets: {e}")
        return None

# --- FUNCIONES AUXILIARES ---
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
    # Función clave para ordenar cronológicamente
    if not hora_str: return 99999
    try:
        h, m = map(int, hora_str.split(':'))
        return h * 60 + m
    except: return 99999

def main():
    # --- HEADER ---
    col_logo, col_titulo = st.columns([0.5, 4])
    with col_logo:
        # Logo estable desde Wikimedia
        st.image("https://upload.wikimedia.org/wikipedia/commons/f/f7/Peugeot_Logo_2021.svg", width=50)
    with col_titulo:
        st.markdown('<div class="main-header">CONTROL DE LAVADERO</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Gestión de tiempos y productividad</div>', unsafe_allow_html=True)

    hoja = conectar_sheet()
    if not hoja: return

    # --- LECTURA DE DATOS ---
    raw_data = hoja.get_all_values()
    
    # Índices de Columnas (0-based)
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

    # Fecha actual
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Filtros")
        fecha_sel = st.date_input("Fecha a visualizar:", hoy_date)
        
        f_str = fecha_sel.strftime("%-d/%-m/%Y")     # 28/1/2026
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")  # 28/01/2026

    # --- PROCESAMIENTO ---
    pendientes = []
    terminados = []
    tiempos_dia = []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 13: fila += [""] * (13 - len(fila))
        
        dom = fila[IDX_DOMINIO]
        prometido_raw = fila[IDX_PROMETIDO].upper()
        
        if not dom: continue
        if "NO SE LAVA" in prometido_raw or "NO VINO" in prometido_raw: continue

        fecha_celda = fila[IDX_FECHA]
        ini1 = fila[IDX_INICIO]
        fin1 = fila[IDX_FIN]
        ini2 = fila[IDX_INI2]
        fin2 = fila[IDX_FIN2]
        estado = fila[IDX_ESTADO].strip().upper()

        # Lógica de Finalizado
        es_finalizado = False
        if estado == "FINALIZADO":
            es_finalizado = True
        elif fin1 and not estado: 
            es_finalizado = True 
        elif fin2: 
            es_finalizado = True

        es_hoy = (f_str in fecha_celda) or (f_str_cero in fecha_celda) or (f_str in prometido_raw)
        
        es_atrasado = False
        if not es_finalizado:
            try:
                f_dt = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                if f_dt < fecha_sel:
                    es_atrasado = True
            except: pass

        if es_hoy or es_atrasado:
            item = {
                "fila": i,
                "dom": dom,
                "mod": fila[IDX_MODELO],
                "ase": fila[IDX_ASESOR],
                "pro": fila[IDX_PROMETIDO],
                "ini": ini1, "fin": fin1,
                "ini2": ini2, "fin2": fin2,
                "est": estado,
                "atr": es_atrasado,
                "orden_pend": normalizar_hora(fila[IDX_PROMETIDO])
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
    tab_op, tab_kpi = st.tabs(["🚗 Operación", "📈 Estadísticas"])

    with tab_op:
        # --- SECCIÓN PENDIENTES ---
        st.markdown(f"#### Pendientes ({len(pendientes)})")
        
        if pendientes:
            # Ordenar: 1. Atrasados primero, 2. Por hora prometida
            pendientes.sort(key=lambda x: (not x["atr"], x["orden_pend"]))
            
            c_h = st.columns([0.8, 1, 1.8, 1.2, 1.5])
            c_h[0].markdown("**HORA**")
            c_h[1].markdown("**PATENTE**")
            c_h[2].markdown("**MODELO**")
            c_h[3].markdown("**ASESOR**")
            c_h[4].markdown("**ACCIÓN**")
            
            for p in pendientes:
                with st.container():
                    col = st.columns([0.8, 1, 1.8, 1.2, 1.5])
                    
                    hora_txt = p['pro']
                    if p['atr']: hora_txt = f"⚠️ {hora_txt}"
                    col[0].markdown(f"<span class='txt-hora'>{hora_txt}</span>", unsafe_allow_html=True)
                    col[1].markdown(f"<span class='txt-patente'>{p['dom']}</span>", unsafe_allow_html=True)
                    col[2].markdown(f"<span class='txt-modelo'>{p['mod']}</span>", unsafe_allow_html=True)
                    col[3].markdown(f"<span class='txt-asesor'>{p['ase']}</span>", unsafe_allow_html=True)
                    
                    with col[4]:
                        # Botones
                        if not p['ini']:
                            if st.button("▶️ INICIAR", key=f"start_{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INICIO + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "LAVANDO")
                                st.rerun()
                        elif p['ini'] and not p['fin']:
                            c_b = st.columns(2)
                            if c_b[0].button("⏸️", key=f"pau_{p['fila']}", help="Pausar"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "PAUSA")
                                st.rerun()
                            if c_b[1].button("🏁", key=f"fin1_{p['fila']}", help="Finalizar"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                        elif p['est'] == "PAUSA" and not p['ini2']:
                            st.warning("En Pausa")
                            if st.button("🔄 REANUDAR", key=f"res_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "REPASO")
                                st.rerun()
                        elif p['ini2'] and not p['fin2']:
                            if st.button("🏁 FIN", key=f"fin2_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                        else:
                            if st.button("Forzar Fin", key=f"force_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                    st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
        else:
            st.success("🎉 No hay vehículos pendientes por lavar.")

        # --- SECCIÓN TERMINADOS ---
        st.markdown(f"#### Terminados ({len(terminados)})")
        if terminados:
            # CORRECCIÓN DE ORDEN: Usamos la función matemática obtener_minutos_orden
            terminados.sort(key=lambda x: obtener_minutos_orden(x["ini"]))
            
            cols_show = st.columns([1, 1, 1, 2, 1.5])
            cols_show[0].caption("INICIO")
            cols_show[1].caption("FIN")
            cols_show[2].caption("PATENTE")
            cols_show[3].caption("MODELO")
            cols_show[4].caption("ASESOR")
            
            for t in terminados:
                cols = st.columns([1, 1, 1, 2, 1.5])
                fin_show = t['fin2'] if t['fin2'] else t['fin']
                
                cols[0].write(t['ini'])
                cols[1].write(fin_show)
                cols[2].markdown(f"**{t['dom']}**")
                cols[3].write(t['mod'])
                cols[4].write(t['ase'])

    with tab_kpi:
        st.markdown("### Rendimiento Diario")
        k1, k2, k3 = st.columns(3)
        
        avg = int(sum(tiempos_dia)/len(tiempos_dia)) if tiempos_dia else 0
        
        with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(terminados)}</div><div class='kpi-lbl'>Autos Lavados</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{avg} min</div><div class='kpi-lbl'>Tiempo Promedio</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='kpi-card'><div class='kpi-val'>{max(tiempos_dia) if tiempos_dia else 0} min</div><div class='kpi-lbl'>Tiempo Máximo</div></div>", unsafe_allow_html=True)

        if tiempos_dia:
            st.write("---")
            st.bar_chart(tiempos_dia)

if __name__ == "__main__":
    main()
