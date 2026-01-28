import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Peugeot Oficial", layout="wide")

# --- ESTILOS ---
st.markdown("""
<style>
    .main-title { font-size: 20px !important; font-weight: bold; color: #00235d; margin-top: -15px; }
    .kpi-box { border: 1px solid #ddd; padding: 5px; border-radius: 5px; text-align: center; background-color: #f1f3f6; }
    .kpi-val { font-size: 16px; font-weight: bold; color: #00235d; }
    .fila-tabla { padding: 4px 0; border-bottom: 1px solid #eee; font-size: 0.85em; }
    .hora-txt { font-weight: bold; color: #d32f2f; font-size: 0.9em; }
    .patente-txt { font-weight: bold; color: #1565c0; font-size: 0.9em; }
    .small-font { font-size: 0.82em; color: #555; }
    .stButton button { height: 28px; font-size: 0.75em; padding: 0px 8px; font-weight: bold; }
    /* Colores de botones específicos */
    div[data-testid="stColumn"] button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).worksheet("PLAN GENERAL")

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
        h, m = hora_str.split(":")
        return f"{int(h):02d}:{m}"
    return hora_str

def main():
    # Logo embebido (Base64) para seguridad
    LOGO_PEUGEOT = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAMAAAAp4XiDAAAAhFBMVEUAAAAA//8AzMwA/wAAzP8A//8MzMwMzP8AmZkAmf8zMzMAZmYAzMwz/zMA/8wz//8z/MwzAABmZgBm/2Zm//9m/5lm/2YzM2YzM5lmZswzM8wzM/8zMzMzAAAAmcwAmf8AmZkAZswAZpkAZgAAZjMAZswAMzMAM2YAMwAAM8wAM/8AMwBmZma2AAAAxnRSTlMAu4vC/vC3j/7+/v7+8q+Z/v7+q4uL/v7+u/7+tI/+/v7+i/7+s5n+tP7+i4v+/v7+3/v7+i/7+8v7+/v7+tP7+8ov+/v7+q4v+/v7+q/7+/v6L/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v63/v7+i/7+/v7+/v7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+q/7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+8r7r3wAAAfdJREFUSMe1lU1rwlAQx08T32qsFxF8W6u26sVaD1ZBqCCFInioQvHQAwqeexD8f9+kE81LFl1P3eG3CNnN/Oad5M2E4J9A6LgO05iWwzAMg9gO05QG/xLItw7bSiaTrm3fOiyCDeR7j+tUq9Vut0/53uclhEB+DLhOvV4fDAbD4ZB9DDgR+Tng5vP5YDAajUbD4Xg8Ho3H48F87uZE5NeIm8/n0+l0Op3NZrPZbDabz6fT+dzLi8ivCTefz2ez2Ww2m81ms9lsNpvNZtP53MuLyK8JN5/PZ7PZbDabzWaz2Ww2m81m0/ncy4vIrwk3n89ns9lsNpvNZrO5d1y31+s5/wEivybcfD6fTqfT6XQ2m81ms9lsPp9O53MvLyK/Btx8Ph8MRqPRaDgcXl9fX11djcfjwXzu5kTkx4Dr1Ov1wWAwHA7ZxwD7I0gI5FuP61Sr1W63T/neZyVEIP86bCuZTLq2fessgQzDMI1p2QzDMAx7J7bDNKXBP4FwHIdpDMuwDMvYDtM49k8gXNdhGtNyGIZhENthmtLgXwL51mFbyWTS9X91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3WI/zrEfx3ivw7xX4f4r0P81yH+6xD/dYj/OsR/HeK/DvFfh/ivQ/zXIf7rEP91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3XIf/0G26wW10u4R5gAAAAASUVORK5CYII="

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px; border-bottom: 2px solid #00235d; padding-bottom: 10px;">
        <img src="{LOGO_PEUGEOT}" width="50" style="border-radius: 4px;">
        <div>
            <h1 class="main-title">POSTVENTA JUJUY</h1>
            <span style="font-size: 0.8em; color: #666;">Sistema de Gestión de Lavadero</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # --- MAPEO DE COLUMNAS ---
        # A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11, M=12
        IDX_FECHA = 0
        IDX_ASESOR = 2
        IDX_DOMINIO = 3
        IDX_MODELO = 4
        IDX_PROMETIDO = 7
        IDX_INICIO = 8   # Columna I (Inicio 1)
        IDX_FIN = 9      # Columna J (Fin 1 / Pausa)
        IDX_INI2 = 10    # Columna K (Inicio 2 / Reinicio)
        IDX_FIN2 = 11    # Columna L (Fin 2 / Final)
        IDX_ESTADO = 12  # Columna M (Estado)

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        with st.sidebar:
            st.header("⚙️ Configuración")
            fecha_sel = st.date_input("Fecha:", hoy_dt.date())
            f_str = fecha_sel.strftime("%-d/%-m/%Y")
            f_str_cero = fecha_sel.strftime("%d/%m/%Y")

        tab1, tab2 = st.tabs(["🚀 Operación", "📊 Indicadores"])

        pendientes, terminados = [], []
        tiempos_dia = []

        # 1. PROCESAMIENTO DE DATOS
        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 13: fila += [""] * (13 - len(fila))
            
            estado_prometido = fila[IDX_PROMETIDO].upper()
            if not fila[IDX_DOMINIO] or "NO SE LAVA" in estado_prometido or "NO VINO" in estado_prometido:
                continue

            fecha_celda = fila[IDX_FECHA]
            es_hoy = f_str in fecha_celda or f_str_cero in fecha_celda or f_str in estado_prometido or f_str_cero in estado_prometido
            
            # Estado actual de la Columna M
            estado_lavado = fila[IDX_ESTADO].upper().strip()
            es_finalizado = (estado_lavado == "FINALIZADO")

            # Chequeo de atrasados
            es_atrasado = False
            if not es_finalizado:
                try:
                    fecha_dt = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                    if fecha_dt < fecha_sel: es_atrasado = True
                except: pass

            if es_hoy or es_atrasado:
                item = {
                    "fila": i, 
                    "dom": fila[IDX_DOMINIO], "mod": fila[IDX_MODELO],
                    "ase": fila[IDX_ASESOR], "pro": fila[IDX_PROMETIDO],
                    "ini": fila[IDX_INICIO], "fin": fila[IDX_FIN],
                    "ini2": fila[IDX_INI2], "fin2": fila[IDX_FIN2],
                    "est": estado_lavado,
                    "atr": es_atrasado,
                    "orden_hora": normalizar_hora(fila[IDX_PROMETIDO])
                }

                if es_finalizado:
                    terminados.append(item)
                    # Calculamos tiempo total (Tanda 1 + Tanda 2 si hubo pausa)
                    t1 = calcular_minutos(item["ini"], item["fin"])
                    t2 = calcular_minutos(item["ini2"], item["fin2"]) if item["fin2"] else 0
                    if t1 > 0: tiempos_dia.append(t1 + t2)
                else:
                    pendientes.append(item)

        # 2. PESTAÑA OPERACIÓN
        with tab1:
            st.write(f"**Pendientes ({len(pendientes)})**")
            
            if pendientes:
                # Orden: 1. Atrasados, 2. Hora normalizada
                pendientes.sort(key=lambda x: (not x["atr"], x["orden_hora"]))
                
                c = st.columns([0.8, 1, 1.8, 1.2, 1.5])
                c[0].caption("HORA"); c[1].caption("PATENTE"); c[2].caption("MODELO"); c[3].caption("ASESOR"); c[4].caption("ACCIONES")
                
                for p in pendientes:
                    r = st.columns([0.8, 1, 1.8, 1.2, 1.5])
                    
                    hora_show = f"⚠️ {p['pro']}" if p['atr'] else p['pro']
                    r[0].markdown(f"<span class='hora-txt'>{hora_show}</span>", unsafe_allow_html=True)
                    r[1].markdown(f"<span class='patente-txt'>{p['dom']}</span>", unsafe_allow_html=True)
                    r[2].markdown(f"<span class='small-font'>{p['mod']}</span>", unsafe_allow_html=True)
                    r[3].markdown(f"<span class='small-font'>{p['ase']}</span>", unsafe_allow_html=True)
                    
                    with r[4]:
                        hora_actual = datetime.now(tz_ar).strftime("%H:%M")
                        
                        # --- LÓGICA DE BOTONES ---
                        
                        # 1. No ha empezado -> INICIAR
                        if not p['ini']:
                            if st.button("▶️ INICIAR", key=f"start_{p['fila']}", type="primary"):
                                hoja.update_cell(p['fila'], IDX_INICIO + 1, hora_actual) # Llena I
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "LAVANDO")   # Llena M
                                st.rerun()

                        # 2. Está lavando (Tiene I, falta J) -> PAUSA o LISTO
                        elif p['ini'] and not p['fin']:
                            col_btns = st.columns(2)
                            # PAUSA: Llena J y pone M="PAUSA"
                            if col_btns[0].button("⏸️", key=f"pausa_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)    # Llena J
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "PAUSA")     # Llena M
                                st.rerun()
                            # LISTO: Llena J y pone M="FINALIZADO"
                            if col_btns[1].button("🏁", key=f"fin1_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)    # Llena J
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")# Llena M
                                st.rerun()
                        
                        # 3. Está Pausado (Tiene J y M="PAUSA") -> REINICIAR
                        elif p['est'] == "PAUSA" and not p['ini2']:
                            st.warning("Pausado")
                            if st.button("🔄 REANUDAR", key=f"reanudar_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)   # Llena K
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "REPASO")    # Llena M
                                st.rerun()

                        # 4. Está en Repaso (Tiene K, falta L) -> FINALIZAR
                        elif p['ini2'] and not p['fin2']:
                            if st.button("🏁 FIN FINAL", key=f"fin2_{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)   # Llena L
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")# Llena M
                                st.rerun()

                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)
            else:
                st.info("No hay vehículos pendientes.")

            st.write("---")
            st.write(f"**Terminados ({len(terminados)})**")
            
            if terminados:
                # Ordenar cronológicamente por inicio
                terminados.sort(key=lambda x: x["ini"])
                
                ct = st.columns([1, 1, 1, 1.8, 1.5])
                ct[0].caption("INICIO"); ct[1].caption("FIN"); ct[2].caption("PATENTE"); ct[3].caption("MODELO"); ct[4].caption("ASESOR")
                
                for t in terminados:
                    rt = st.columns([1, 1, 1, 1.8, 1.5])
                    # Si hubo pausa, el fin real es FIN 2 (L), sino es FIN 1 (J)
                    fin_real = t['fin2'] if t['fin2'] else t['fin']
                    
                    rt[0].write(t['ini'])
                    rt[1].write(fin_real)
                    rt[2].markdown(f"<span class='patente-txt'>{t['dom']}</span>", unsafe_allow_html=True)
                    rt[3].markdown(f"<span class='small-font'>{t['mod']}</span>", unsafe_allow_html=True)
                    rt[4].markdown(f"<span class='small-font'>{t['ase']}</span>", unsafe_allow_html=True)
                    st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        # 3. PESTAÑA KPIS
        with tab2:
            st.markdown("### Indicadores de Gestión")
            k1, k2, k3 = st.columns(3)
            
            promedio = int(sum(tiempos_dia)/len(tiempos_dia)) if tiempos_dia else 0
            maximo = max(tiempos_dia) if tiempos_dia else 0
            
            with k1: st.markdown(f"<div class='kpi-box'>Total Terminados<br><span class='kpi-val'>{len(terminados)}</span></div>", unsafe_allow_html=True)
            with k2: st.markdown(f"<div class='kpi-box'>Tiempo Promedio<br><span class='kpi-val'>{promedio} min</span></div>", unsafe_allow_html=True)
            with k3: st.markdown(f"<div class='kpi-box'>Pico Máximo<br><span class='kpi-val'>{maximo} min</span></div>", unsafe_allow_html=True)
            
            if tiempos_dia:
                st.write("---")
                st.caption("Distribución de tiempos de lavado (min)")
                st.bar_chart(tiempos_dia)

    except Exception as e:
        st.error(f"Error: {e}")
        st.warning("⚠️ Asegurate de haber creado la COLUMNA M con título 'ESTADO' en tu Excel.")

if __name__ == "__main__":
    main()
