import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Lavadero Postventa", layout="wide")

# --- LOGO PEUGEOT EN CÓDIGO (BASE64) - NO REQUIERE INTERNET ---
LOGO_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAMAAAAp4XiDAAAAhFBMVEUAAAAA//8AzMwA/wAAzP8A//8MzMwMzP8AmZkAmf8zMzMAZmYAzMwz/zMA/8wz//8z/MwzAABmZgBm/2Zm//9m/5lm/2YzM2YzM5lmZswzM8wzM/8zMzMzAAAAmcwAmf8AmZkAZswAZpkAZgAAZjMAZswAMzMAM2YAMwAAM8wAM/8AMwBmZma2AAAAxnRSTlMAu4vC/vC3j/7+/v7+8q+Z/v7+q4uL/v7+u/7+tI/+/v7+i/7+s5n+tP7+i4v+/v7+3/v7+i/7+8v7+/v7+tP7+8ov+/v7+q4v+/v7+q/7+/v6L/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v63/v7+i/7+/v7+/v7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+q/7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+8r7r3wAAAfdJREFUSMe1lU1rwlAQx08T32qsFxF8W6u26sVaD1ZBqCCFInioQvHQAwqeexD8f9+kE81LFl1P3eG3CNnN/Oad5M2E4J9A6LgO05iWwzAMg9gO05QG/xLItw7bSiaTrm3fOiyCDeR7j+tUq9Vut0/53uclhEB+DLhOvV4fDAbD4ZB9DDgR+Tng5vP5YDAajUbD4Xg8Ho3H48F87uZE5NeIm8/n0+l0Op3NZrPZbDabz6fT+dzLi8ivCTefz2ez2Ww2m81ms9lsNpvNZtP53MuLyK8JN5/PZ7PZbDabzWaz2Ww2m81m0/ncy4vIrwk3n89ns9lsNpvNZrO5d1y31+s5/wEivybcfD6fTqfT6XQ2m81ms9lsPp9O53MvLyK/Btx8Ph8MRqPRaDgcXl9fX11djcfjwXzu5kTkx4Dr1Ov1wWAwHA7ZxwD7I0gI5FuP61Sr1W63T/neZyVEIP86bCuZTLq2fessgQzDMI1p2QzDMAx7J7bDNKXBP4FwHIdpDMuwDMvYDtM49k8gXNdhGtNyGIZhENthmtLgXwL51mFbyWTS9X91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3WI/zrEfx3ivw7xX4f4r0P81yH+6xD/dYj/OsR/HeK/DvFfh/ivQ/zXIf7rEP91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3XIf/0G26wW10u4R5gAAAAASUVORK5CYII="

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    /* 1. MARGEN SUPERIOR AJUSTADO */
    .block-container {
        padding-top: 3.5rem !important; 
        padding-bottom: 1rem !important;
    }
    
    /* 2. HEADER */
    .header-div {
        display: flex; 
        align-items: center; 
        gap: 15px;
        padding-bottom: 10px; 
        border-bottom: 2px solid #00235d; 
        margin-bottom: 10px;
    }
    .main-title { 
        font-size: 26px !important; 
        font-weight: bold; 
        color: #00235d; 
        margin: 0 !important; 
        line-height: 1.1; 
    }
    .sub-title { font-size: 14px; color: #666; margin: 0 !important; }
    
    /* 3. FILAS COMPACTAS */
    .row-container { 
        padding: 3px 0 !important; 
        border-bottom: 1px solid #ddd; 
        align-items: center; 
        height: 36px !important;
    }
    
    /* 4. BOTONES */
    .stButton button { 
        height: 28px !important; 
        font-size: 12px !important; 
        padding: 0px 5px !important; 
        margin-top: 2px !important;
    }
    
    /* 5. TEXTOS Y ESPACIOS */
    p { margin-bottom: 0px !important; }
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 14px; }
    .txt-patente { color: #004488; font-weight: bold; font-size: 14px; }
    .txt-modelo { color: #222; font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .txt-asesor { color: #555; font-size: 12px; }

</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
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
    # --- HEADER CON IMAGEN BLINDADA (BASE64) ---
    st.markdown(f"""
    <div class="header-div">
        <img src="{LOGO_B64}" width="50" style="border-radius: 4px;">
        <div>
            <div class="main-title">CONTROL DE LAVADERO</div>
            <div class="sub-title">Gestión de Tiempos y Calidad</div>
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
        st.header("Filtros")
        fecha_sel = st.date_input("Fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    pendientes = []
    terminados_hoy = []
    tiempos_hoy = []
    historial_data = []

    for i, fila in enumerate(raw_data[1:], start=2):
        if len(fila) < 14: fila += [""] * (14 - len(fila))
        
        dom = fila[IDX_DOMINIO]
        pro_raw = fila[IDX_PROMETIDO].upper()
        if not dom or "NO SE LAVA" in pro_raw or "NO VINO" in pro_raw: continue

        fecha_celda = fila[IDX_FECHA]
        ini1, fin1 = fila[IDX_INICIO], fila[IDX_FIN]
        ini2, fin2 = fila[IDX_INI2], fila[IDX_FIN2]
        estado = fila[IDX_ESTADO].strip().upper()
        control_ok = fila[IDX_CONTROL].strip().upper()

        es_finalizado = (estado == "FINALIZADO") or (fin1 and not estado) or fin2
        
        es_hoy_filtro = (f_str in fecha_celda) or (f_str_cero in fecha_celda) or (f_str in pro_raw)
        
        es_atrasado = False
        if not es_finalizado:
            try:
                f_dt = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                if f_dt < fecha_sel: es_atrasado = True
            except: pass

        if es_hoy_filtro or es_atrasado:
            item = {
                "fila": i,
                "dom": dom, "mod": fila[IDX_MODELO],
                "ase": limpiar_asesor(fila[IDX_ASESOR]),
                "pro": fila[IDX_PROMETIDO],
                "ini": ini1, "fin": fin1, "ini2": ini2, "fin2": fin2,
                "est": estado, "atr": es_atrasado, "ok": (control_ok == "OK"),
                "orden_pend": normalizar_hora(fila[IDX_PROMETIDO]),
                "orden_term": obtener_minutos_orden(ini1)
            }
            if es_finalizado:
                terminados_hoy.append(item)
                if es_hoy_filtro:
                    t = calcular_minutos(ini1, fin1)
                    if ini2 and fin2: t += calcular_minutos(ini2, fin2)
                    if t > 0: tiempos_hoy.append(t)
            else:
                pendientes.append(item)

        if es_finalizado:
            try:
                fecha_clean = fecha_celda.split()[0]
                t_total = calcular_minutos(ini1, fin1)
                if ini2 and fin2: t_total += calcular_minutos(ini2, fin2)
                if t_total > 0 and t_total < 300: 
                    historial_data.append({"Fecha": fecha_clean, "Tiempo": t_total, "Auto": 1})
            except: pass

    tab_op, tab_hoy, tab_hist = st.tabs(["🚗 OPERACIÓN", "📊 HOY", "📅 HISTORIAL"])

    with tab_op:
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
                            if st.button("▶️", key=f"g{p['fila']}", type="primary"):
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
                    st.markdown("<div class='row-container'></div>", unsafe_allow_html=True)
        else:
            st.info("Sin pendientes.")

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(f"**Finalizados ({len(terminados_hoy)})**")
        if terminados_hoy:
            terminados_hoy.sort(key=lambda x: x["orden_term"])
            c_t = st.columns([0.6, 0.6, 0.8, 2.5, 0.8, 0.5])
            c_t[0].caption("INI")
            c_t[1].caption("FIN")
            c_t[2].caption("DOM")
            c_t[3].caption("MODELO")
            c_t[4].caption("ASE")
            c_t[5].caption("OK")
            
            for t in terminados_hoy:
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

    with tab_hoy:
        st.markdown("##### Rendimiento de Hoy")
        k1, k2, k3 = st.columns(3)
        avg = int(sum(tiempos_hoy)/len(tiempos_hoy)) if tiempos_hoy else 0
        with k1: st.metric("Lavados Hoy", len(terminados_hoy))
        with k2: st.metric("Promedio Hoy", f"{avg} min")
        with k3: st.metric("Pico Máximo", f"{max(tiempos_hoy) if tiempos_hoy else 0} min")
        
        st.divider()
        if tiempos_hoy:
            st.bar_chart(tiempos_hoy)
        else:
            st.info("Esperando primeros autos...")

    with tab_hist:
        st.markdown("##### Historial General")
        if historial_data:
            df_hist = pd.DataFrame(historial_data)
            df_hist['Fecha_DT'] = pd.to_datetime(df_hist['Fecha'], format="%d/%m/%Y", errors='coerce')
            df_hist = df_hist.dropna(subset=['Fecha_DT']).sort_values('Fecha_DT')

            st.markdown("📊 **Autos lavados por día**")
            df_counts = df_hist.groupby("Fecha", sort=False)["Auto"].sum().reset_index()
            st.bar_chart(df_counts.set_index("Fecha"))
            
            st.divider()

            st.markdown("⏱️ **Tiempo promedio (min)**")
            df_avg = df_hist.groupby("Fecha", sort=False)["Tiempo"].mean().reset_index()
            st.line_chart(df_avg.set_index("Fecha"))
        else:
            st.info("Sin historial suficiente.")

if __name__ == "__main__":
    main()
