import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Programación Lavadero", layout="wide")

# --- ESTILOS CSS PARA QUE QUEDE TIPO TABLA COMPACTA ---
st.markdown("""
<style>
    .fila-tabla { padding: 8px 0; border-bottom: 1px solid #eee; align-items: center; }
    .texto-hora { font-weight: bold; color: #d32f2f; font-size: 1.1em; }
    .texto-patente { font-weight: bold; font-size: 1.1em; color: #1565c0; }
    .encabezado { background-color: #f0f2f6; padding: 10px 0; font-weight: bold; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN LIMPIADORA DE HORAS (SOLUCIÓN AL BUG) ---
def limpiar_hora(valor):
    """Convierte cualquier cosa que venga del Excel a formato HH:MM string"""
    if not valor: return ""
    v_str = str(valor).strip()
    
    # Si viene vacía
    if v_str == "": return ""
    
    # Si viene fecha completa "2026-01-27 15:00:00" nos quedamos con la hora
    if " " in v_str:
        parte_hora = v_str.split(" ")[-1] # Toma lo que está después del espacio
        return parte_hora[:5] # Toma los primeros 5 caracteres (15:00)
    
    # Si viene "15:00:00" tomamos solo 15:00
    if len(v_str) > 5:
        return v_str[:5]
        
    return v_str

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    # TU URL
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).sheet1

def main():
    st.title("🚿 Programación del Día")

    try:
        hoja = conectar_sheet()
        data = hoja.get_values("A1:Z150") # Leemos bloque grande
        
        # --- BUSCADOR DE TÍTULOS ---
        fila_titulos = -1
        for i, fila in enumerate(data[:10]):
            fila_mayus = [str(celda).strip().upper() for celda in fila]
            if "DOMINIO" in fila_mayus:
                fila_titulos = i
                break
        
        if fila_titulos == -1:
            st.error("🚨 Error: No encuentro la columna 'DOMINIO'.")
            st.stop()
            
        headers = [h.strip() for h in data[fila_titulos]] 
        df = pd.DataFrame(data[fila_titulos+1:], columns=headers)

        # --- TUS COLUMNAS (Ajustar si cambian nombres) ---
        COL_PATENTE = "DOMINIO"
        COL_MODELO = "Modelo"
        COL_ASESOR = "Asesor"           # <--- Agregamos esta
        COL_PROMETIDO = "Horario Prometido" 
        COL_INICIO = "INICIO"   
        COL_FIN = "FIN"      

        # --- FILTRO FECHA DE HOY ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()
        col_fecha = df.columns[0]
        
        # Limpieza y filtrado
        df = df[df[col_fecha] != ""] 
        df['Fecha_Norm'] = pd.to_datetime(df[col_fecha], dayfirst=True, errors='coerce').dt.date
        df_hoy = df[df['Fecha_Norm'] == hoy].copy()
        
        # --- LIMPIEZA DE HORAS ---
        # Aplicamos la función limpiadora a la columna de prometido
        if COL_PROMETIDO in df_hoy.columns:
            df_hoy[COL_PROMETIDO] = df_hoy[COL_PROMETIDO].apply(limpiar_hora)

        # --- SEPARAR: PENDIENTES vs TERMINADOS ---
        # Terminados: Tienen algo en la columna FIN
        df_terminados = df_hoy[df_hoy[COL_FIN].str.strip() != ""].copy()
        
        # Pendientes: Columna FIN vacía
        df_pendientes = df_hoy[df_hoy[COL_FIN].str.strip() == ""].copy()

        # --- TABLA 1: PENDIENTES (ARRIBA) ---
        st.subheader(f"📋 A Lavar ({len(df_pendientes)}) - {hoy.strftime('%d/%m')}")
        
        if df_pendientes.empty:
            st.info("✅ No hay vehículos pendientes.")
        else:
            # Ordenar
            df_pendientes['orden'] = df_pendientes[COL_PROMETIDO].replace("", "23:59")
            df_pendientes = df_pendientes.sort_values('orden')

            # ENCABEZADOS DE LA TABLA
            c1, c2, c3, c4, c5 = st.columns([1, 1.5, 2, 2, 1.5])
            c1.markdown("**HORA**")
            c2.markdown("**DOMINIO**")
            c3.markdown("**MODELO**")
            c4.markdown("**ASESOR**")
            c5.markdown("**ACCIÓN**")
            st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

            # FILAS
            for i, row in df_pendientes.iterrows():
                # Buscamos la fila real para el botón
                patente_buscada = row[COL_PATENTE]
                fila_excel = -1
                
                # Buscador de fila segura
                for idx_raw, linea in enumerate(data):
                    if idx_raw > fila_titulos:
                        if linea[headers.index(COL_PATENTE)] == patente_buscada:
                             # Verificamos modelo por seguridad
                            if row[COL_MODELO] in linea: 
                                fila_excel = idx_raw + 1
                                break
                
                if fila_excel == -1: continue

                # Datos
                prometido = row.get(COL_PROMETIDO, "")
                dominio = row.get(COL_PATENTE, "")
                modelo = row.get(COL_MODELO, "")
                asesor = row.get(COL_ASESOR, "") # Leemos Asesor
                inicio = str(row.get(COL_INICIO, "")).strip()

                # Visualización Fila
                c1, c2, c3, c4, c5 = st.columns([1, 1.5, 2, 2, 1.5])
                
                with c1: st.markdown(f"<span class='texto-hora'>{prometido}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span class='texto-patente'>{dominio}</span>", unsafe_allow_html=True)
                with c3: st.write(modelo)
                with c4: st.write(asesor)
                with c5:
                    col_idx_inicio = headers.index(COL_INICIO) + 1
                    col_idx_fin = headers.index(COL_FIN) + 1

                    if not inicio:
                        # Botón PLAY
                        if st.button("▶️ Iniciar", key=f"start_{fila_excel}", type="secondary"):
                            hora = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila_excel, col_idx_inicio, hora)
                            st.rerun()
                    else:
                        # Botón STOP (Ya inició, falta terminar)
                        st.markdown(f"<span style='color:grey; font-size:0.8em'>Inició: {inicio}</span>", unsafe_allow_html=True)
                        if st.button("🏁 Listo", key=f"end_{fila_excel}", type="primary"):
                            hora = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila_excel, col_idx_fin, hora)
                            st.balloons()
                            st.rerun()
                
                st.markdown("<div style='border-bottom:1px solid #eee; margin-bottom:5px'></div>", unsafe_allow_html=True)

        # --- TABLA 2: TERMINADOS (ABAJO) ---
        st.write("---")
        st.subheader(f"✅ Listos ({len(df_terminados)})")
        
        if not df_terminados.empty:
            # Seleccionamos solo las columnas útiles para mostrar
            cols_mostrar = [COL_PATENTE, COL_MODELO, COL_ASESOR, COL_INICIO, COL_FIN]
            
            # Verificamos que existan todas antes de mostrar
            cols_finales = [c for c in cols_mostrar if c in df_terminados.columns]
            
            df_show = df_terminados[cols_finales].copy()
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no se finalizaron lavados hoy.")

    except Exception as e:
        st.error("Error en la aplicación:")
        st.write(e)

if __name__ == "__main__":
    main()
