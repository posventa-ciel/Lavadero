import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Tablero Lavadero", layout="wide")

# --- ESTILOS VISUALES (Compactos) ---
st.markdown("""
<style>
    .fila { border-bottom: 1px solid #eee; padding: 8px 0; align-items: center; }
    .hora-roja { color: #d32f2f; font-weight: bold; font-size: 1.1em; }
    .patente-azul { color: #1565c0; font-weight: bold; font-size: 1.2em; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN: LIMPIAR HORAS ---
def limpiar_hora(valor):
    """Deja limpio el formato HH:MM"""
    if not valor: return ""
    v = str(valor).strip()
    if v == "": return ""
    if " " in v: return v.split(" ")[-1][:5] # Si es fecha larga
    if len(v) > 5: return v[:5] # Si es 15:00:00
    return v

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

def main():
    st.title("🚿 Programación del Día")

    try:
        hoja = conectar_sheet()
        
        # CAMBIO CLAVE: Leemos TODO, sin límite de filas
        data = hoja.get_all_values() 
        
        # --- BUSCADOR INTELIGENTE DE ENCABEZADOS ---
        fila_titulos = -1
        for i, fila in enumerate(data[:15]): # Buscamos en las primeras 15 filas
            fila_mayus = [str(celda).strip().upper() for celda in fila]
            if "DOMINIO" in fila_mayus:
                fila_titulos = i
                break
        
        if fila_titulos == -1:
            st.error("🚨 Error Crítico: No encuentro una columna llamada 'DOMINIO'. Revisa los títulos.")
            st.stop()
            
        headers = [h.strip() for h in data[fila_titulos]] 
        df = pd.DataFrame(data[fila_titulos+1:], columns=headers)

        # --- TUS COLUMNAS EXACTAS ---
        # Asegurate que en el Excel se llamen ASÍ (respetando mayúsculas/minúsculas)
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "Modelo"
        COL_ASESOR = "ASESOR"            # Columna C
        COL_PROMETIDO = "Horario Prometido" # Columna H
        COL_INICIO = "INICIO"
        COL_FIN = "FIN"      

        # --- FILTRO DE FECHA ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()
        
        # Asumimos que la FECHA está en la primera columna (Índice 0)
        col_fecha = df.columns[0]
        
        # 1. Quitamos filas vacías
        df = df[df[col_fecha] != ""]
        
        # 2. Convertimos fecha (Maneja 27/1 y 27/01 igual)
        df['Fecha_Norm'] = pd.to_datetime(df[col_fecha], dayfirst=True, errors='coerce').dt.date
        
        # 3. Filtramos por HOY
        df_hoy = df[df['Fecha_Norm'] == hoy].copy()

        # --- HERRAMIENTA DE DIAGNÓSTICO (En el menú lateral) ---
        with st.sidebar:
            st.header("🔧 Diagnóstico")
            st.write(f"Fecha buscada: **{hoy}**")
            st.write(f"Total filas leídas: **{len(data)}**")
            st.write(f"Filas con fecha de hoy: **{len(df_hoy)}**")
            if st.checkbox("Ver tabla cruda"):
                st.dataframe(df_hoy)

        # --- PROCESAMIENTO ---
        if df_hoy.empty:
            st.info(f"No se encontraron vehículos para la fecha {hoy}.")
        else:
            # Limpiar hora prometida
            if COL_PROMETIDO in df_hoy.columns:
                df_hoy[COL_PROMETIDO] = df_hoy[COL_PROMETIDO].apply(limpiar_hora)
            
            # Separar PENDIENTES vs TERMINADOS
            df_terminados = df_hoy[df_hoy[COL_FIN].str.strip() != ""].copy()
            df_pendientes = df_hoy[df_hoy[COL_FIN].str.strip() == ""].copy()
            
            # --- TABLA PRINCIPAL: PENDIENTES ---
            st.subheader(f"📋 Pendientes ({len(df_pendientes)})")
            
            if not df_pendientes.empty:
                # Ordenar por hora (vacíos al final)
                df_pendientes['orden'] = df_pendientes[COL_PROMETIDO].replace("", "23:59")
                df_pendientes = df_pendientes.sort_values('orden')

                # Cabecera
                c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                c1.markdown("⏱ **HORA**")
                c2.markdown("🚘 **DOMINIO**")
                c3.markdown("📝 **MODELO**")
                c4.markdown("👤 **ASESOR**")
                c5.markdown("⚡ **ACCIÓN**")
                st.divider()

                for i, row in df_pendientes.iterrows():
                    # Búsqueda SEGURA de fila en Excel
                    patente = row[COL_PATENTE]
                    asesor = row.get(COL_ASESOR, "")
                    modelo = row.get(COL_MODELO, "")
                    prometido = row.get(COL_PROMETIDO, "")
                    inicio = str(row.get(COL_INICIO, "")).strip()

                    # Buscamos la fila original en 'data' para poder escribir
                    fila_excel = -1
                    for idx_raw, linea in enumerate(data):
                        if idx_raw > fila_titulos:
                            # Coincidencia por Patente Y Modelo (para evitar duplicados)
                            if (linea[headers.index(COL_PATENTE)] == patente and 
                                linea[headers.index(COL_MODELO)] == modelo):
                                fila_excel = idx_raw + 1
                                break
                    
                    if fila_excel == -1: continue

                    # DIBUJO DE LA FILA
                    c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                    
                    with c1: st.markdown(f"<span class='hora-roja'>{prometido}</span>", unsafe_allow_html=True)
                    with c2: st.markdown(f"<span class='patente-azul'>{patente}</span>", unsafe_allow_html=True)
                    with c3: st.write(modelo)
                    with c4: st.write(asesor)
                    with c5:
                        idx_col_ini = headers.index(COL_INICIO) + 1
                        idx_col_fin = headers.index(COL_FIN) + 1

                        if not inicio:
                            if st.button("▶️ Iniciar", key=f"start_{fila_excel}", type="secondary"):
                                h = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_excel, idx_col_ini, h)
                                st.rerun()
                        else:
                            # Ya inició
                            st.caption(f"Inició: {inicio}")
                            if st.button("🏁 Listo", key=f"end_{fila_excel}", type="primary"):
                                h = datetime.now(tz_ar).strftime("%H:%M")
                                hoja.update_cell(fila_excel, idx_col_fin, h)
                                st.rerun()
                    
                    st.markdown("<div style='margin-bottom:8px; border-bottom:1px solid #f0f0f0'></div>", unsafe_allow_html=True)

            # --- TABLA SECUNDARIA: TERMINADOS ---
            if not df_terminados.empty:
                st.write("")
                st.write("")
                with st.expander(f"✅ Ver Lavados Terminados ({len(df_terminados)})", expanded=False):
                    # Mostramos tabla limpia
                    cols_mostrar = [c for c in [COL_PROMETIDO, COL_PATENTE, COL_MODELO, COL_ASESOR, COL_INICIO, COL_FIN] if c in df_terminados.columns]
                    st.dataframe(df_terminados[cols_mostrar], hide_index=True, use_container_width=True)

    except Exception as e:
        st.error("Ocurrió un error:")
        st.code(e)

if __name__ == "__main__":
    main()
