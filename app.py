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
    # URL de tu Sheet
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

def main():
    st.title("🚿 Tablero de Lavadero")

    try:
        hoja = conectar_sheet()
        data = hoja.get_values("A1:Z150") # Leemos hasta 150 filas
        
        # --- BUSCADOR INTELIGENTE DE TÍTULOS ---
        fila_titulos = -1
        for i, fila in enumerate(data[:10]): # Buscamos en las primeras 10 filas
            fila_mayus = [str(celda).strip().upper() for celda in fila]
            if "DOMINIO" in fila_mayus:
                fila_titulos = i
                break
        
        if fila_titulos == -1:
            st.error("🚨 No encuentro la columna 'DOMINIO'.")
            st.stop()
            
        headers = [h.strip() for h in data[fila_titulos]] 
        df = pd.DataFrame(data[fila_titulos+1:], columns=headers)

        # --- TUS COLUMNAS ---
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "Modelo"
        COL_PROMETIDO = "Horario Prometido" 
        COL_INICIO = "INICIO"   
        COL_FIN = "FIN"      

        # --- FILTRO 1: FECHA DE HOY ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()
        col_fecha = df.columns[0]
        
        df = df[df[col_fecha] != ""] 
        df['Fecha_Norm'] = pd.to_datetime(df[col_fecha], dayfirst=True, errors='coerce').dt.date
        df_hoy = df[df['Fecha_Norm'] == hoy].copy()

        # --- FILTRO 2: OCULTAR TERMINADOS ---
        # Solo nos quedamos con los que tienen la columna FIN vacía
        if COL_FIN in df_hoy.columns:
            df_hoy = df_hoy[df_hoy[COL_FIN].str.strip() == ""]

        if df_hoy.empty:
            st.info(f"✅ ¡Todo limpio! No hay autos pendientes para hoy ({hoy}).")
        else:
            # --- ORDENAMIENTO (LOGICA NUEVA) ---
            # Creamos una columna temporal para ordenar
            def valor_orden(hora):
                h = str(hora).strip()
                if not h or h == "":
                    return "23:59" # Si está vacía, la mandamos al final del día
                return h # Si tiene hora, usamos esa
            
            df_hoy['orden_temp'] = df_hoy[COL_PROMETIDO].apply(valor_orden)
            
            # Ordenamos: De temprano a tarde (y los vacíos al final)
            df_hoy = df_hoy.sort_values(by='orden_temp', ascending=True)

            st.write(f"Pendientes para hoy: **{hoy}**")
            
            # --- MOSTRAR LISTA ---
            for i, row in df_hoy.iterrows():
                # Lógica para encontrar fila real
                patente_buscada = row[COL_PATENTE]
                modelo_buscado = row[COL_MODELO]
                
                fila_excel = -1
                for idx_raw, linea in enumerate(data):
                    if idx_raw > fila_titulos: # Solo buscamos abajo de los títulos
                        # Chequeamos Patente y Modelo para estar seguros
                        try:
                           if (linea[headers.index(COL_PATENTE)] == patente_buscada and 
                               linea[headers.index(COL_MODELO)] == modelo_buscado):
                               fila_excel = idx_raw + 1
                               break
                        except:
                            continue

                if fila_excel == -1: continue # Seguridad

                # Datos para mostrar
                patente = row.get(COL_PATENTE, "S/D")
                modelo = row.get(COL_MODELO, "")
                prometido = row.get(COL_PROMETIDO, "")
                inicio = row.get(COL_INICIO, "")
                
                # Diseño
                prom_texto = prometido if prometido else "Sin horario"
                color_prom = "red" if prometido else "grey"
                
                bg = "white"
                estado_txt = "⏳ Pendiente"
                
                if inicio:
                    bg = "#e3f2fd" # Azulito claro
                    estado_txt = "💦 LAVANDO..."
                
                with st.container():
                    st.markdown(f"""
                    <div style="background-color:{bg}; padding:15px; border-radius:10px; border:1px solid #ccc; margin-bottom:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                        <div style="display:flex; justify-content:space-between;">
                            <h3 style="margin:0; color:#333">{patente}</h3>
                            <span style="font-weight:bold; color:{color_prom}">⏰ {prom_texto}</span>
                        </div>
                        <div style="color:#555; margin-top:5px;">{modelo}</div>
                        <div style="font-size:0.8em; color:#888; margin-top:5px;">{estado_txt}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # SOLO MOSTRAMOS LOS BOTONES NECESARIOS
                    col_btn_inicio = headers.index(COL_INICIO) + 1
                    col_btn_fin = headers.index(COL_FIN) + 1
                    
                    if not inicio:
                        if st.button(f"▶️ INICIAR LAVADO", key=f"btn_ini_{fila_excel}", use_container_width=True):
                            hora = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila_excel, col_btn_inicio, hora)
                            st.rerun()
                    else:
                        # Si ya inició, mostramos botón terminar (verde)
                        if st.button(f"🏁 FINALIZAR LAVADO", key=f"btn_fin_{fila_excel}", type="primary", use_container_width=True):
                            hora = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila_excel, col_btn_fin, hora)
                            st.balloons()
                            st.rerun()

    except Exception as e:
        st.error("Error:")
        st.write(e)

if __name__ == "__main__":
    main()
