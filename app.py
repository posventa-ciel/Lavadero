import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
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
    # Tu URL
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

def main():
    st.title("🚿 Tablero de Lavadero")

    try:
        hoja = conectar_sheet()
        # Leemos las primeras 100 filas para no cargar todo si es gigante
        data = hoja.get_values("A1:Z100") 
        
        # --- BUSCADOR INTELIGENTE DE TÍTULOS ---
        fila_titulos = -1
        
        # Buscamos en las primeras 5 filas alguna que tenga la palabra "DOMINIO" o "Dominio"
        for i, fila in enumerate(data[:5]):
            # Convertimos toda la fila a mayúsculas para comparar fácil
            fila_mayus = [str(celda).strip().upper() for celda in fila]
            if "DOMINIO" in fila_mayus:
                fila_titulos = i
                break
        
        if fila_titulos == -1:
            st.error("🚨 Error: No encuentro la fila de títulos. Asegúrate de que haya una columna llamada 'DOMINIO'.")
            st.write("Esto es lo que veo en las primeras filas:", data[:3])
            st.stop()
            
        # Ahora sí, armamos la tabla usando la fila que encontramos
        headers = [h.strip() for h in data[fila_titulos]] # Quitamos espacios extra
        df = pd.DataFrame(data[fila_titulos+1:], columns=headers)

        # --- NOMBRES DE COLUMNAS ---
        # (El código buscará estos nombres EXACTOS en la fila que detectó)
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "Modelo"  
        COL_PROMETIDO = "Horario Prometido" 
        COL_INICIO = "INICIO"   
        COL_FIN = "FIN"      

        # --- FILTRO DE FECHA ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()
        
        # Asumimos que la FECHA es la primera columna (índice 0)
        col_fecha_nombre = df.columns[0]
        
        # Limpieza de datos vacíos
        df = df[df[col_fecha_nombre] != ""] 
        
        df['Fecha_Normalizada'] = pd.to_datetime(df[col_fecha_nombre], dayfirst=True, errors='coerce').dt.date
        df_hoy = df[df['Fecha_Normalizada'] == hoy].copy()

        if df_hoy.empty:
            st.info(f"📅 Hoy es **{hoy}**. No encontré autos cargados para esta fecha.")
            st.caption("Nota: Revisa que la fecha en el Excel sea correcta (ej: 27/1/2026).")
        else:
            if COL_PROMETIDO in df_hoy.columns:
                df_hoy = df_hoy.sort_values(by=COL_PROMETIDO)

            st.success(f"Turnos del día: **{hoy}**")
            
            # --- DIBUJAR TARJETAS ---
            for i, row in df_hoy.iterrows():
                # Calculamos la fila real en el Excel
                # i = índice del filtro, pero necesitamos el índice real del Dataframe original
                # Sumamos: fila_titulos (ej: 2) + 1 (base 1) + 1 (header) + index real
                
                # Forma segura de encontrar la fila original:
                idx_real_df = i # Esto es relativo al df_hoy, cuidado.
                # Mejor usamos el número de fila que guardamos implícitamente?
                # Simplificación: Recalculamos basándonos en la posición original
                # Truco: Gspread usa filas base 1.
                
                # Vamos a buscar la fila exacta comparando Patente y Modelo para no errarle
                try:
                    # Buscamos en qué columna están los botones
                    idx_col_inicio = headers.index(COL_INICIO) + 1
                    idx_col_fin = headers.index(COL_FIN) + 1
                    
                    # Fila real (Aproximación por orden de lista filtrada NO SIRVE si hay filtro)
                    # Necesitamos la fila absoluta.
                    # Vamos a buscar la fila en 'data' que coincida con la patente
                    patente_buscada = row[COL_PATENTE]
                    
                    fila_excel = -1
                    for idx_raw, linea in enumerate(data):
                        if idx_raw > fila_titulos and linea[headers.index(COL_PATENTE)] == patente_buscada:
                            # Encontramos la fila!
                            if linea[headers.index(COL_MODELO)] == row[COL_MODELO]: # Doble check
                                fila_excel = idx_raw + 1 # +1 porque Excel empieza en 1
                                break
                    
                    if fila_excel == -1: continue # Si no la encuentra, salta

                except Exception as e:
                    st.error(f"Error calculando filas: {e}")
                    st.stop()

                patente = row.get(COL_PATENTE, "S/D")
                modelo = row.get(COL_MODELO, "")
                prometido = row.get(COL_PROMETIDO, "--:--")
                inicio = row.get(COL_INICIO, "")
                fin = row.get(COL_FIN, "")

                # ESTADO VISUAL
                color_borde = "#ddd"
                icono = "⏳"
                if inicio: 
                    color_borde = "#2196F3" # Azul
                    icono = "💦 LAVANDO"
                if fin: 
                    color_borde = "#4CAF50" # Verde
                    icono = "✅ LISTO"

                with st.container():
                    st.markdown(f"""
                    <div style="border-left: 5px solid {color_borde}; padding: 10px; background: white; margin-bottom: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 style="margin:0">{patente}</h3>
                        <div style="color:grey">{modelo}</div>
                        <div style="font-weight:bold; color:#d9534f">Horario: {prometido}</div>
                        <div style="margin-top:5px; font-size:0.9em">{icono}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    
                    # BOTÓN INICIAR
                    with c1:
                        if not inicio:
                            if st.button(f"▶️ INICIAR", key=f"start_{fila_excel}"):
                                hora = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_excel, idx_col_inicio, hora)
                                st.rerun()
                    
                    # BOTÓN FINALIZAR
                    with c2:
                        if inicio and not fin:
                            if st.button(f"🏁 LISTO", key=f"end_{fila_excel}"):
                                hora = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_excel, idx_col_fin, hora)
                                st.balloons()
                                st.rerun()

    except Exception as e:
        st.error("Algo salió mal:")
        st.write(e)

if __name__ == "__main__":
    main()
