import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import json 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero", layout="wide")

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # ACÁ ES DONDE LA APP VA A LEER LA LLAVE QUE DESCARGASTE
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    
    # TU PLANILLA - Verifica que este link sea el correcto
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

# --- APP ---
def main():
    st.title("🚿 Tablero de Lavadero")

    try:
        hoja = conectar_sheet()
        data = hoja.get_all_values()
        
        # --- ATENCIÓN: REVISA QUE ESTOS NOMBRES SEAN IGUALES A TU EXCEL (FILA 3) ---
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "MODELO"
        COL_PROMETIDO = "HORA PROM" # Columna G
        COL_INICIO = "INICIO LAV"   # Columna H
        COL_FIN = "FIN LAVADO"      # Columna I
        
        # Asumimos títulos en fila 3 (índice 2)
        FILA_TITULOS = 2
        headers = data[FILA_TITULOS] 
        df = pd.DataFrame(data[FILA_TITULOS+1:], columns=headers)
        
        # Filtro de HOY
        hoy = datetime.now().strftime("%d/%m/%Y")
        col_fecha = df.columns[0] # Asumimos fecha en columna A
        
        # Filtrar
        df_hoy = df[df[col_fecha].astype(str).str.contains(hoy, na=False)].copy()

        if df_hoy.empty:
            st.info(f"No hay autos para hoy ({hoy}) o revisa el formato de fecha en el Excel.")
        else:
            # Ordenar por Hora Prometida
            if COL_PROMETIDO in df_hoy.columns:
                df_hoy = df_hoy.sort_values(by=COL_PROMETIDO)

            st.write(f"Mostrando turnos del: **{hoy}**")
            
            for i, row in df_hoy.iterrows():
                # Índices para escribir
                try:
                    idx_inicio = headers.index(COL_INICIO) + 1
                    idx_fin = headers.index(COL_FIN) + 1
                    # Calculamos fila real: índice del loop + filas headers + corrección base 1
                    fila_real = i + FILA_TITULOS + 2 
                except:
                    st.error(f"Error: No encuentro las columnas '{COL_INICIO}' o '{COL_FIN}'. Revisa los nombres.")
                    st.stop()

                patente = row.get(COL_PATENTE, "S/D")
                modelo = row.get(COL_MODELO, "")
                prometido = row.get(COL_PROMETIDO, "")
                inicio = row.get(COL_INICIO, "")
                fin = row.get(COL_FIN, "")

                # TARJETA VISUAL
                # Color del borde según estado
                estado = "⏳ Pendiente"
                if inicio: estado = "💦 Lavando"
                if fin: estado = "✅ Listo"

                with st.expander(f"[{estado}] {patente} - {modelo}", expanded=True):
                    st.caption(f"Prometido: {prometido}")
                    c1, c2 = st.columns(2)
                    
                    # Botón INICIAR
                    with c1:
                        if not inicio:
                            if st.button("▶️ INICIAR", key=f"ini_{i}"):
                                hora = datetime.now().strftime("%H:%M")
                                hoja.update_cell(fila_real, idx_inicio, hora)
                                st.success("Iniciado")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.write(f"Inicio: {inicio}")

                    # Botón FINALIZAR
                    with c2:
                        if inicio and not fin:
                            if st.button("🏁 TERMINAR", key=f"fin_{i}"):
                                hora = datetime.now().strftime("%H:%M")
                                hoja.update_cell(fila_real, idx_fin, hora)
                                st.balloons()
                                time.sleep(1)
                                st.rerun()
                        elif fin:
                            st.write(f"Fin: {fin}")

    except Exception as e:
        st.error("Error de conexión. Revisa los Secrets.")
        st.write(e)

if __name__ == "__main__":
    main()
