import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Lavadero Postventa", layout="wide")

# --- LOGO SVG SIMPLIFICADO (Anti-Error) ---
LOGO_SVG = """
<svg width="40" height="40" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="50" height="50" rx="8" fill="white"/>
  <path d="M10 25 L20 25 L20 40" stroke="#00235d" stroke-width="4" fill="none"/>
  <path d="M10 10 L40 10 L40 25 L10 25" stroke="#00235d" stroke-width="4" fill="none"/>
</svg>
"""

# --- ESTILOS CSS (DISEÑO SLIM) ---
st.markdown("""
<style>
    /* 1. PEGAR AL TECHO */
    .block-container { 
        padding-top: 1rem !important; 
        padding-bottom: 1rem !important; 
    }
    
    /* 2. ENCABEZADO DELGADO */
    .portada-container { 
        background: linear-gradient(90deg, #00235d 0%, #004080 100%); 
        color: white; 
        padding: 8px 15px; /* Relleno mínimo */
        border-radius: 6px; 
        margin-bottom: 10px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center;
        box-shadow: 0 2px 3px rgba(0,0,0,0.1);
        height: 60px; /* Altura fija controlada */
    }
    
    /* 3. FILAS SUPER COMPACTAS */
    .row-card {
        background-color: white;
        border-bottom: 1px solid #eee;
        padding: 2px 5px !important; /* Casi sin espacio vertical */
        min-height: 30px !important;
        display: flex;
        align-items: center;
    }
    
    /* 4. TEXTOS DE TABLA */
    p { margin: 0 !important; }
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 13px; }
    .txt-patente { color: #00235d; font-weight: bold; font-size: 13px; }
    .txt-modelo { color: #333; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .txt-asesor { color: #666; font-size: 11px; }
    
    /* 5. BOTONES PEQUEÑOS */
    .stButton button {
        height: 24px !important;
        font-size: 10px !important;
        padding: 0px 10px !important;
        line-height: 1 !important;
        margin-top: 2px !important;
    }
    
    /* Quitar espacios extra de Streamlit */
    div[data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    
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
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    # --- PORTADA HTML SIMPLE Y SEGURA ---
    st.markdown(f'''
    <div class="portada-container">
        <div style="display: flex; align-items: center; gap: 15px;">
             {LOGO_SVG}
             <div>
                <div style="font-size: 1.4rem; font-weight: bold; line-height: 1;">CONTROL LAVADERO</div>
                <div style="font-size: 0.8rem; opacity: 0.8;">Postventa</div>
             </div>
        </div>
        <div style="text-align: right; line-height: 1.1;">
            <div style="font-size: 0.9rem; font-weight: bold;">{hoy_date.strftime("%d/%m/%Y")}</div>
            <div style="font-size: 0.8rem;">{datetime.now(tz_ar).strftime("%H:%M")} hs</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

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

    with st.sidebar:
        st.markdown("**Filtros**")
        fecha_sel = st.date_input("Fecha:", hoy_date, label_visibility="collapsed")
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

    tab_op, tab_hoy, tab_hist = st.tabs(["🚗 Operación", "📊 Métricas", "📈 Histórico"])

    with tab_op:
        # PENDIENTES
        st.markdown(f"**Pendientes ({len(pendientes)})**")
        if pendientes:
            pendientes.sort(key=lambda x: (not x["atr"], x["orden_pend"]))
            
            c1, c2, c3, c4, c5 = st.columns([0.6, 0.8, 2, 0.8, 1.5])
            c1.caption("HORA")
            c2.caption("PATENTE")
            c3.caption("MODELO")
            c4.caption("ASESOR")
            c5.caption("ACCION")
            
            for p in pendientes:
                with st.container():
                    st.markdown('<div class="row-card">', unsafe_allow_html=True)
                    col = st.columns([0.6, 0.8, 2, 0.8, 1.5])
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
                            cb = st.columns(2)
                            if cb[0].button("⏸️", key=f"p{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "PAUSA")
                                st.rerun()
                            if cb[1].button("🏁", key=f"f1{p['fila']}"):
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
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Sin pendientes.")

        st.markdown("<br>", unsafe_allow_html=True)

        # FINALIZADOS
        st.markdown(f"**Finalizados ({len(terminados_hoy)})**")
        if terminados_hoy:
            terminados_hoy.sort(key=lambda x: x["orden_term"])
            t1, t2, t3, t4, t5, t6 = st.columns([0.6, 0.6, 0.8, 2, 0.8, 0.5])
            t1.caption("INI")
            t2.caption("FIN")
            t3.caption("DOM")
            t4.caption("MODELO")
            t5.caption("ASE")
            t6.caption("OK")
            
            for t in terminados_hoy:
                with st.container():
                     st.markdown('<div class="row-card">', unsafe_allow_html=True)
                     r = st.columns([0.6, 0.6, 0.8, 2, 0.8, 0.5])
                     fin_s = t['fin2'] if t['fin2'] else t['fin']
                     r[0].write(t['ini'])
                     r[1].write(fin_s)
                     r[2].markdown(f"**{t['dom']}**")
                     r[3].markdown(f"<span style='font-size:12px'>{t['mod']}</span>", unsafe_allow_html=True)
                     r[4].write(t['ase'])
                     with r[5]:
                        nk = st.checkbox("", value=t['ok'], key=f"chk_{t['fila']}", label_visibility="collapsed")
                        if nk != t['ok']:
                            hoja.update_cell(t['fila'], IDX_CONTROL + 1, "OK" if nk else "")
                            st.rerun()
                     st.markdown('</div>', unsafe_allow_html=True)

    with tab_hoy:
        avg_hoy = int(sum(tiempos_hoy)/len(tiempos_hoy)) if tiempos_hoy else 0
        k1, k2, k3 = st.columns(3)
        with k1: st.metric("Lavados Hoy", len(terminados_hoy))
        with k2: st.metric("Promedio", f"{avg_hoy} min")
        with k3: st.metric("Máximo", f"{max(tiempos_hoy) if tiempos_hoy else 0} min")
        
        st.divider()
        if tiempos_hoy:
            fig = px.histogram(x=tiempos_hoy, nbins=10, labels={'x':'Minutos', 'y':'Autos'}, title="Distribución de Tiempos", color_discrete_sequence=['#00235d'])
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with tab_hist:
        if historial_data:
            df_hist = pd.DataFrame(historial_data)
            df_hist['Fecha_DT'] = pd.to_datetime(df_hist['Fecha'], format="%d/%m/%Y", errors='coerce')
            df_hist = df_hist.dropna(subset=['Fecha_DT']).sort_values('Fecha_DT')
            
            c1, c2 = st.columns(2)
            with c1:
                df_counts = df_hist.groupby("Fecha_DT")["Auto"].sum().reset_index()
                fig_bar = px.bar(df_counts, x='Fecha_DT', y='Auto', title="Autos por Día", color_discrete_sequence=['#00235d'])
                fig_bar.update_layout(height=300)
                st.plotly_chart(fig_bar, use_container_width=True)
            with c2:
                df_avg = df_hist.groupby("Fecha_DT")["Tiempo"].mean().reset_index()
                fig_line = px.line(df_avg, x='Fecha_DT', y='Tiempo', title="Tiempo Promedio", markers=True, color_discrete_sequence=['#28a745'])
                fig_line.update_layout(height=300)
                st.plotly_chart(fig_line, use_container_width=True)

if __name__ == "__main__":
    main()
