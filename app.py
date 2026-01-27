import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import pytz # Librería para zonas horarias

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero", layout="wide")

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    
    # TU PLANILLA
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

# --- APP ---
def main():
    st.title("🚿 Tablero de Lavadero")

    try:
        hoja = conectar_sheet()
        data = hoja.get_all_values()
        
        # --- NOMBRES DE COLUMNAS (AJUSTADOS A TU FOTO) ---
        # Fila 1 del Excel parece ser la de títulos (según tu foto es la fila 1, no la 3)
        # Si tus títulos "FECHA, HORA, DOMINIO..." están en la Fila 1, usa FILA_TITULOS = 0
        FILA_TITULOS = 0 
        
        headers = data[FILA_TITULOS] 
        df = pd.DataFrame(data[FILA_TITULOS+1:], columns=headers)
        
        # AJUSTA ESTOS NOMBRES SI NO TE APARECEN DATOS:
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "Modelo"       # En tu foto se ve "Modelo" (con M mayúscula y el resto minúscula)
        COL_PROMETIDO = "HORA PROM" # Verifica que esta columna exista a la derecha
        COL_INICIO = "INICIO LAV"   # Verifica que esta columna exista
        COL_FIN = "FIN LAVADO"      # Verifica que esta columna exista
        
        # --- FILTRO DE FECHA INTELIGENTE ---
        # 1. Obtenemos la fecha actual en Argentina
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()
        
        # 2. Convertimos la columna FECHA del Excel (Columna A) a objetos de fecha reales
        # Esto soluciona el problema de "27/1" vs "27/01"
        col_fecha_nombre = df.columns[0] # Asumimos que FECHA es la primera columna
        df['Fecha_Normalizada'] = pd.to_datetime(df[col_fecha_nombre], dayfirst=True, errors='coerce').dt.date

        # 3. Filtramos
        df_hoy = df[df['Fecha_Normalizada'] == hoy].copy()

        if df_hoy.empty:
            st.warning(f"No encontré autos para la fecha: {hoy}")
            st.info("Consejo: Revisa que la columna A tenga la fecha correcta.")
        else:
            # Ordenar si existe la columna
            if COL_PROMETIDO in df_hoy.columns:
                df_hoy = df_hoy.sort_values(by=COL_PROMETIDO)

            st.success(f"📅 Mostrando turnos del: **{hoy}**")
            
            for i, row in df_hoy.iterrows():
                # Índices para escribir en el Excel
                try:
                    idx_inicio = headers.index(COL_INICIO) + 1
                    idx_fin = headers.index(COL_FIN) + 1
                    # Calculamos fila real: índice del loop + filas headers + corrección base 1
                    fila_real = i + FILA_TITULOS + 2 
                except:
                    st.error(f"⚠️ Error: No encuentro las columnas '{COL_INICIO}' o '{COL_FIN}' en el Excel. ¿Están escritas igual?")
                    st.stop()

                patente = row.get(COL_PATENTE, "S/D")
                modelo = row.get(COL_MODELO, "")
                prometido = row.get(COL_PROMETIDO, "--:--")
                inicio = row.get(COL_INICIO, "")
                fin = row.get(COL_FIN, "")

                # LÓGICA DE ESTADO VISUAL
                estado_emoji = "⏳"
                estado_color = "grey"
                
                if inicio and not fin:
                    estado_emoji = "💦 LAVANDO"
                    estado_color = "blue"
                elif fin:
                    estado_emoji = "✅ LISTO"
                    estado_color = "green"

                # TARJETA
                with st.container():
                    st.markdown(f"""
                    <div style="padding:10px; border-radius:10px; border:1px solid #ddd; margin-bottom:10px; background-color:#f9f9f9">
                        <h3 style="margin:0; color:{estado_color}">{estado_emoji} {patente}</h3>
                        <p style="margin:0"><b>{modelo}</b> | Prometido: <span style="color:red">{prometido}</span></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    
                    # Botón INICIAR
                    with c1:
                        if not inicio:
                            if st.button(f"▶️ INICIAR {patente}", key=f"ini_{i}"):
                                hora = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_real, idx_inicio, hora)
                                st.rerun()
                    
                    # Botón TERMINAR
                    with c2:
                        if inicio and not fin:
                            if st.button(f"🏁 TERMINAR {patente}", key=f"fin_{i}"):
                                hora = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_real, idx_fin, hora)
                                st.balloons()
                                st.rerun()

    except Exception as e:
        st.error("Hubo un error en la aplicación:")
        st.write(e)

if __name__ == "__main__":
    main()
