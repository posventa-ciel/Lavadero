import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero", layout="wide")

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

# --- APP ---
def main():
    st.title("🚿 Tablero de Lavadero")

    try:
        hoja = conectar_sheet()
        data = hoja.get_all_values()
        
        # FILA 0 = La primera fila del Excel (donde están los títulos)
        FILA_TITULOS = 0 
        
        headers = data[FILA_TITULOS] 
        df = pd.DataFrame(data[FILA_TITULOS+1:], columns=headers)
        
        # --- AQUÍ ESTABA EL ERROR: CORREGIMOS LOS NOMBRES EXACTOS ---
        # (Tal cual se ven en tus fotos)
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "Modelo"            # En tu foto está con 'M' mayúscula y resto minúscula
        COL_PROMETIDO = "Horario Prometido" # Columna H (Fondo verde)
        COL_INICIO = "INICIO"            # Columna I (Fondo blanco)
        COL_FIN = "FIN"                  # Columna J (Fondo blanco)
        
        # --- FILTRO DE FECHA ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()
        
        col_fecha_nombre = df.columns[0] # Asumimos columna A (FECHA)
        
        # Normalizamos la fecha para que "27/1" sea igual a "27/01"
        df['Fecha_Normalizada'] = pd.to_datetime(df[col_fecha_nombre], dayfirst=True, errors='coerce').dt.date

        df_hoy = df[df['Fecha_Normalizada'] == hoy].copy()

        if df_hoy.empty:
            st.warning(f"No encontré autos para la fecha de hoy: {hoy}")
            st.info("Revisa que la columna 'FECHA' tenga el día correcto (ej: 27/1/2026).")
        else:
            # Ordenar por Horario Prometido si existe
            if COL_PROMETIDO in df_hoy.columns:
                df_hoy = df_hoy.sort_values(by=COL_PROMETIDO)

            st.success(f"📅 Turnos del día: **{hoy}**")
            
            for i, row in df_hoy.iterrows():
                try:
                    # Buscamos en qué número de columna están los títulos (para escribir)
                    idx_inicio = headers.index(COL_INICIO) + 1
                    idx_fin = headers.index(COL_FIN) + 1
                    
                    # Calculamos la fila real (+1 por empezar en 0, +1 por header)
                    fila_real = i + FILA_TITULOS + 2 
                except:
                    st.error(f"⚠️ Error Crítico: No encuentro las columnas '{COL_INICIO}' o '{COL_FIN}' en la fila 1 del Excel.")
                    st.stop()

                patente = row.get(COL_PATENTE, "S/D")
                modelo = row.get(COL_MODELO, "")
                prometido = row.get(COL_PROMETIDO, "--:--")
                inicio = row.get(COL_INICIO, "")
                fin = row.get(COL_FIN, "")

                # LÓGICA VISUAL (EMOJIS Y COLORES)
                estado_emoji = "⏳"
                estado_color = "grey"
                bg_color = "#f9f9f9" # Gris clarito por defecto
                
                if inicio and not fin:
                    estado_emoji = "💦 LAVANDO"
                    estado_color = "#0068c9" # Azul
                    bg_color = "#e6f2ff" # Fondo azulado
                elif fin:
                    estado_emoji = "✅ LISTO"
                    estado_color = "#2e7d32" # Verde
                    bg_color = "#e8f5e9" # Fondo verdoso

                # TARJETA
                with st.container():
                    st.markdown(f"""
                    <div style="padding:15px; border-radius:10px; border:1px solid #ddd; margin-bottom:15px; background-color:{bg_color}">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h2 style="margin:0; color:{estado_color}; font-weight:bold;">{patente}</h2>
                            <span style="font-size:1.2em; background-color:white; padding:5px 10px; border-radius:5px; border:1px solid #ccc">
                                ⏰ {prometido}
                            </span>
                        </div>
                        <p style="margin:5px 0 0 0; font-size:1.1em;">🚘 {modelo}</p>
                        <p style="margin:0; color:grey; font-size:0.9em;">Estado: {estado_emoji}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    
                    # Botón INICIAR
                    with c1:
                        if not inicio:
                            if st.button(f"▶️ INICIAR", key=f"ini_{i}", use_container_width=True):
                                hora = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_real, idx_inicio, hora)
                                st.rerun()
                    
                    # Botón TERMINAR
                    with c2:
                        if inicio and not fin:
                            if st.button(f"🏁 TERMINAR", key=f"fin_{i}", type="primary", use_container_width=True):
                                hora = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_real, idx_fin, hora)
                                st.balloons()
                                st.rerun()

    except Exception as e:
        st.error("Hubo un error en la aplicación:")
        st.write(e)

if __name__ == "__main__":
    main()
