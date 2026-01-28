import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz
import plotly.express as px  # Agregamos Plotly para gráficos estilo pro

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Lavadero", layout="wide")

# --- ESTILOS CSS (ADAPTADOS DE TU REFERENCIA) ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* ENCABEZADO AZUL (Igual a tu referencia) */
    .portada-container { 
        background: linear-gradient(90deg, #00235d 0%, #004080 100%); 
        color: white; 
        padding: 1rem 1.5rem; 
        border-radius: 10px; 
        margin-bottom: 1.5rem; 
        display: flex; 
        justify-content: space-between; 
        align-items: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* TARJETAS DE MÉTRICAS (Igual a tu referencia) */
    .metric-card { 
        background-color: white; 
        border: 1px solid #dee2e6; 
        padding: 15px; 
        border-radius: 8px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
        text-align: center; 
        height: 100%; 
        display: flex; 
        flex-direction: column; 
        justify-content: center; 
    }
    
    /* ESTILOS DE TABLA PERSONALIZADA */
    .row-card {
        background-color: white;
        border-bottom: 1px solid #eee;
        padding: 8px 10px;
        display: flex;
        align-items: center;
        transition: background-color 0.2s;
    }
    .row-card:hover { background-color: #f8f9fa; }
    
    /* TEXTOS */
    .txt-hora { color: #d32f2f; font-weight: bold; font-size: 15px; }
    .txt-patente { color: #00235d; font-weight: bold; font-size: 15px; }
    .txt-modelo { color: #444; font-size: 13px; font-weight: 500; }
    .txt-asesor { color: #666; font-size: 12px; font-style: italic; }
    
    /* BOTONES ESTILIZADOS */
    .stButton button {
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        height: 32px;
        border: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- LOGO EN BASE64 (HTML PURO) ---
LOGO_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAMAAAAp4XiDAAAAhFBMVEUAAAAA//8AzMwA/wAAzP8A//8MzMwMzP8AmZkAmf8zMzMAZmYAzMwz/zMA/8wz//8z/MwzAABmZgBm/2Zm//9m/5lm/2YzM2YzM5lmZswzM8wzM/8zMzMzAAAAmcwAmf8AmZkAZswAZpkAZgAAZjMAZswAMzMAM2YAMwAAM8wAM/8AMwBmZma2AAAAxnRSTlMAu4vC/vC3j/7+/v7+8q+Z/v7+q4uL/v7+u/7+tI/+/v7+i/7+s5n+tP7+i4v+/v7+3/v7+i/7+8v7+/v7+tP7+8ov+/v7+q4v+/v7+q/7+/v6L/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v63/v7+i/7+/v7+/v7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+/v7+i/7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+q/7+/v7+/v7+tP7+/v7+/v7+/v7+/v7+/v7+8r7r3wAAAfdJREFUSMe1lU1rwlAQx08T32qsFxF8W6u26sVaD1ZBqCCFInioQvHQAwqeexD8f9+kE81LFl1P3eG3CNnN/Oad5M2E4J9A6LgO05iWwzAMg9gO05QG/xLItw7bSiaTrm3fOiyCDeR7j+tUq9Vut0/53uclhEB+DLhOvV4fDAbD4ZB9DDgR+Tng5vP5YDAajUbD4Xg8Ho3H48F87uZE5NeIm8/n0+l0Op3NZrPZbDabz6fT+dzLi8ivCTefz2ez2Ww2m81ms9lsNpvNZtP53MuLyK8JN5/PZ7PZbDabzWaz2Ww2m81m0/ncy4vIrwk3n89ns9lsNpvNZrO5d1y31+s5/wEivybcfD6fTqfT6XQ2m81ms9lsPp9O53MvLyK/Btx8Ph8MRqPRaDgcXl9fX11djcfjwXzu5kTkx4Dr1Ov1wWAwHA7ZxwD7I0gI5FuP61Sr1W63T/neZyVEIP86bCuZTLq2fessgQzDMI1p2QzDMAx7J7bDNKXBP4FwHIdpDMuwDMvYDtM49k8gXNdhGtNyGIZhENthmtLgXwL51mFbyWTS9X91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3WI/zrEfx3ivw7xX4f4r0P81yH+6xD/dYj/OsR/HeK/DvFfh/ivQ/zXIf7rEP91iP86xH8d4r8O8V+H+K9D/Nch/usQ/3XIf/0G26wW10u4R5gAAAAASUVORK5CYII="

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
    # --- PROCESAMIENTO FECHAS ---
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    # --- PORTADA TIPO "GRUPO CENOA" ---
    st.markdown(f'''
    <div class="portada-container">
        <div style="display: flex; align-items: center; gap: 15px;">
             <img src="{LOGO_B64}" width="50" style="border-radius: 5px;">
             <div>
                <h1 style="margin:0; font-size: 1.8rem;">Control de Lavadero</h1>
                <h3 style="margin:0; font-size: 1rem; opacity: 0.9;">Gestión Operativa Postventa</h3>
             </div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 1.2rem; font-weight: bold;">{hoy_date.strftime("%d/%m/%Y")}</div>
            <div style="font-size: 0.9rem;">{datetime.now(tz_ar).strftime("%H:%M")} hs</div>
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

    # --- SIDEBAR (FILTROS) ---
    with st.sidebar:
        st.header("🔍 Filtros")
        fecha_sel = st.date_input("Fecha:", hoy_date)
        f_str = fecha_sel.strftime("%-d/%-m/%Y")
        f_str_cero = fecha_sel.strftime("%d/%m/%Y")

    # --- PROCESAMIENTO DE DATOS ---
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

        # OPERATIVO
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

        # HISTORICO
        if es_finalizado:
            try:
                fecha_clean = fecha_celda.split()[0]
                t_total = calcular_minutos(ini1, fin1)
                if ini2 and fin2: t_total += calcular_minutos(ini2, fin2)
                if t_total > 0 and t_total < 300: 
                    historial_data.append({"Fecha": fecha_clean, "Tiempo": t_total, "Auto": 1})
            except: pass

    # --- PESTAÑAS ESTILO GRUPO CENOA ---
    menu_opts = ["🏠 Operación", "📊 Métricas Hoy", "📈 Histórico"]
    selected_tab = st.radio("", menu_opts, horizontal=True, label_visibility="collapsed")
    st.markdown("---")

    # ==========================
    # PESTAÑA 1: OPERACIÓN
    # ==========================
    if selected_tab == "🏠 Operación":
        
        # --- SECCIÓN PENDIENTES ---
        st.subheader(f"🚗 Pendientes de Lavado ({len(pendientes)})")
        
        if pendientes:
            pendientes.sort(key=lambda x: (not x["atr"], x["orden_pend"]))
            
            # CABECERA DE TABLA
            c1, c2, c3, c4, c5 = st.columns([0.8, 1, 2, 1, 1.5])
            c1.markdown("**Hora**")
            c2.markdown("**Patente**")
            c3.markdown("**Modelo**")
            c4.markdown("**Asesor**")
            c5.markdown("**Acción**")
            
            for p in pendientes:
                with st.container():
                    # Usamos HTML para simular la "Card" de fila
                    st.markdown('<div class="row-card">', unsafe_allow_html=True)
                    col = st.columns([0.8, 1, 2, 1, 1.5])
                    
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
                            if st.button("🔄 RETOMAR", key=f"r{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_INI2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "REPASO")
                                st.rerun()
                        elif p['ini2'] and not p['fin2']:
                            if st.button("🏁 FIN", key=f"f2{p['fila']}"):
                                hoja.update_cell(p['fila'], IDX_FIN2 + 1, hora_actual)
                                hoja.update_cell(p['fila'], IDX_ESTADO + 1, "FINALIZADO")
                                st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.success("✅ ¡Todo al día! No hay vehículos pendientes.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECCIÓN FINALIZADOS ---
        st.subheader(f"✅ Finalizados ({len(terminados_hoy)})")
        
        if terminados_hoy:
            terminados_hoy.sort(key=lambda x: x["orden_term"])
            
            # CABECERA TABLA
            t1, t2, t3, t4, t5, t6 = st.columns([0.6, 0.6, 1, 2, 0.8, 0.5])
            t1.caption("INICIO")
            t2.caption("FIN")
            t3.caption("DOMINIO")
            t4.caption("MODELO")
            t5.caption("ASESOR")
            t6.caption("OK")
            
            for t in terminados_hoy:
                with st.container():
                     st.markdown('<div class="row-card" style="padding: 4px 10px;">', unsafe_allow_html=True)
                     r = st.columns([0.6, 0.6, 1, 2, 0.8, 0.5])
                     fin_s = t['fin2'] if t['fin2'] else t['fin']
                     
                     r[0].write(t['ini'])
                     r[1].write(fin_s)
                     r[2].markdown(f"**{t['dom']}**")
                     r[3].markdown(f"<span style='font-size:12px'>{t['mod']}</span>", unsafe_allow_html=True)
                     r[4].write(t['ase'])
                     
                     with r[5]:
                        nk = st.checkbox("", value=t['ok'], key=f"chk_{t['fila']}")
                        if nk != t['ok']:
                            hoja.update_cell(t['fila'], IDX_CONTROL + 1, "OK" if nk else "")
                            st.rerun()
                     st.markdown('</div>', unsafe_allow_html=True)

    # ==========================
    # PESTAÑA 2: MÉTRICAS HOY
    # ==========================
    elif selected_tab == "📊 Métricas Hoy":
        avg_hoy = int(sum(tiempos_hoy)/len(tiempos_hoy)) if tiempos_hoy else 0
        max_hoy = max(tiempos_hoy) if tiempos_hoy else 0
        
        # KPI CARDS Estilo Reference
        k1, k2, k3 = st.columns(3)
        with k1: st.markdown(f'<div class="metric-card"><p style="color:#666; font-size:0.9rem;">Autos Lavados</p><h2 style="color:#00235d;">{len(terminados_hoy)}</h2><div style="font-size:0.8rem; color:#28a745;">Hoy</div></div>', unsafe_allow_html=True)
        with k2: st.markdown(f'<div class="metric-card"><p style="color:#666; font-size:0.9rem;">Tiempo Promedio</p><h2 style="color:#00235d;">{avg_hoy} min</h2><div style="font-size:0.8rem; color:#888;">Objetivo: 45 min</div></div>', unsafe_allow_html=True)
        with k3: st.markdown(f'<div class="metric-card"><p style="color:#666; font-size:0.9rem;">Tiempo Máximo</p><h2 style="color:#dc3545;">{max_hoy} min</h2><div style="font-size:0.8rem; color:#888;">Pico del día</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if tiempos_hoy:
            st.markdown("##### ⏱️ Distribución de Tiempos (Hoy)")
            fig = px.histogram(x=tiempos_hoy, nbins=10, labels={'x':'Minutos', 'y':'Cantidad'}, color_discrete_sequence=['#00235d'])
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Esperando datos de lavados finalizados para graficar...")

    # ==========================
    # PESTAÑA 3: HISTÓRICO
    # ==========================
    elif selected_tab == "📈 Histórico":
        if historial_data:
            df_hist = pd.DataFrame(historial_data)
            df_hist['Fecha_DT'] = pd.to_datetime(df_hist['Fecha'], format="%d/%m/%Y", errors='coerce')
            df_hist = df_hist.dropna(subset=['Fecha_DT']).sort_values('Fecha_DT')
            
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("##### 📊 Cantidad de Autos por Día")
                df_counts = df_hist.groupby("Fecha_DT")["Auto"].sum().reset_index()
                fig_bar = px.bar(df_counts, x='Fecha_DT', y='Auto', text='Auto', color_discrete_sequence=['#00235d'])
                fig_bar.update_layout(xaxis_title="Fecha", yaxis_title="Cantidad", height=350)
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with col_g2:
                st.markdown("##### ⏱️ Tiempo Promedio por Día")
                df_avg = df_hist.groupby("Fecha_DT")["Tiempo"].mean().reset_index()
                fig_line = px.line(df_avg, x='Fecha_DT', y='Tiempo', markers=True, color_discrete_sequence=['#28a745'])
                fig_line.add_hline(y=45, line_dash="dot", annotation_text="Obj (45m)", line_color="gray")
                fig_line.update_layout(xaxis_title="Fecha", yaxis_title="Minutos", height=350)
                st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay suficiente historial para generar reportes.")

if __name__ == "__main__":
    main()
