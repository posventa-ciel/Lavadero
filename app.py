import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero", layout="wide")

# --- ESTILOS ---
st.markdown("""
<style>
    .fila-tabla { padding: 10px; border-bottom: 1px solid #eee; }
    .hora { color: #d32f2f; font-weight: bold; font-size: 1.2em; }
    .patente { color: #1565c0; font-weight: bold; font-size: 1.2em; }
    .modelo { font-weight: 500; color: #333; }
    .asesor { color: #666; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

# --- LIMPIEZA DE HORA ---
def limpiar_hora(valor):
    if not valor: return ""
    v = str(valor).strip()
    if len(v) > 5 and ":" in v: return v[:5] # Corta segundos
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
    st.title("🚿 Tablero de Lavadero")

    try:
        hoja = conectar_sheet()
        data = hoja.get_all_values()
        
        # --- BUSCADOR DE CABECERA ---
        fila_titulos = -1
        # Buscamos la fila que tenga "DOMINIO" (o "Dominio")
        for i, fila in enumerate(data[:20]):
            fila_upper = [str(c).strip().upper() for c in fila]
            if "DOMINIO" in fila_upper:
                fila_titulos = i
                break
        
        if fila_titulos == -1:
            st.error("🚨 No encuentro la columna 'DOMINIO'.")
            st.stop()

        # Armamos DataFrame
        headers = [str(h).strip() for h in data[fila_titulos]]
        df = pd.DataFrame(data[fila_titulos+1:], columns=headers)

        # --- DETECCIÓN DE COLUMNAS (Inteligente) ---
        # Buscamos el nombre real de la columna en el Excel parecida a lo que queremos
        def buscar_columna(posibles_nombres):
            for real in headers:
                if real.upper() in [p.upper() for p in posibles_nombres]:
                    return real
            return None

        col_fecha = df.columns[0] # Asumimos col A
        col_patente = buscar_columna(["DOMINIO", "PATENTE"])
        col_modelo = buscar_columna(["MODELO", "VEHICULO"])
        col_asesor = buscar_columna(["ASESOR", "ASESOR SERVICIO"])
        col_prometido = buscar_columna(["HORARIO PROMETIDO", "HORA PROM", "PROMESA"])
        col_inicio = buscar_columna(["INICIO", "HORA INICIO"])
        col_fin = buscar_columna(["FIN", "HORA FIN", "TERMINADO"])

        # --- LOGICA "ANTI-HUECOS" (Relleno hacia abajo) ---
        # Si la celda de fecha está vacía, repite la fecha de arriba
        df[col_fecha] = df[col_fecha].replace("", pd.NA).ffill()
        # Quitamos filas que sigan vacías después del relleno (filas en blanco reales)
        df = df.dropna(subset=[col_fecha])

        # --- SELECTOR DE FECHA (BARRA LATERAL) ---
        # Obtenemos todas las fechas únicas que hay en la planilla
        fechas_disponibles = df[col_fecha].unique().tolist()
        
        # Intentamos seleccionar la de HOY automáticamente
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_str_1 = datetime.now(tz_ar).strftime("%d/%m/%Y") # Formato 27/01/2026
        hoy_str_2 = datetime.now(tz_ar).strftime("%-d/%-m/%Y") # Formato 27/1/2026 (sin ceros)
        
        index_default = 0
        if fechas_disponibles:
            # Buscamos si hoy está en la lista (al final suele ser lo más reciente)
            for f in reversed(fechas_disponibles):
                if hoy_str_1 in str(f) or hoy_str_2 in str(f):
                    index_default = fechas_disponibles.index(f)
                    break
            else:
                index_default = len(fechas_disponibles) - 1 # Si no encuentra hoy, elige la última

        with st.sidebar:
            st.header("📅 Filtros")
            fecha_selec = st.selectbox("Elegir Fecha:", fechas_disponibles, index=index_default)
            
            st.divider()
            st.write("🔍 **Debug:**")
            st.write(f"Columnas detectadas:")
            st.code(f"Fecha: {col_fecha}\nPatente: {col_patente}\nAsesor: {col_asesor}\nHora: {col_prometido}")

        # --- FILTRADO ---
        df_hoy = df[df[col_fecha] == fecha_selec].copy()

        # Limpieza de hora prometida
        if col_prometido:
             df_hoy[col_prometido] = df_hoy[col_prometido].apply(limpiar_hora)

        # SEPARAR PENDIENTES / TERMINADOS
        pendientes = df_hoy[df_hoy[col_fin].fillna("").astype(str).str.strip() == ""].copy()
        terminados = df_hoy[df_hoy[col_fin].fillna("").astype(str).str.strip() != ""].copy()

        # --- TABLA PENDIENTES ---
        st.subheader(f"📋 Pendientes ({len(pendientes)})")
        
        if not pendientes.empty:
            # Ordenar
            if col_prometido:
                pendientes['orden'] = pendientes[col_prometido].replace("", "23:59")
                pendientes = pendientes.sort_values('orden')

            # Encabezados
            c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
            c1.markdown("**HORA**")
            c2.markdown("**PATENTE**")
            c3.markdown("**MODELO**")
            c4.markdown("**ASESOR**")
            c5.markdown("**ACCIÓN**")
            st.markdown("<hr style='margin:5px 0'>", unsafe_allow_html=True)

            for i, row in pendientes.iterrows():
                # Búsqueda de Fila Excel
                pat = row[col_patente]
                mod = row.get(col_modelo, "")
                
                # Buscamos coincidencia exacta en raw data
                fila_excel = -1
                for idx_raw, linea in enumerate(data):
                    if idx_raw > fila_titulos:
                        # Comparamos Patente
                        val_pat = str(linea[headers.index(col_patente)]).strip()
                        if val_pat == str(pat).strip():
                            # Comparamos Modelo (si existe) para desempatar
                            if col_modelo:
                                val_mod = str(linea[headers.index(col_modelo)]).strip()
                                if val_mod == str(mod).strip():
                                    fila_excel = idx_raw + 1
                                    break
                            else:
                                fila_excel = idx_raw + 1
                                break
                
                if fila_excel == -1: continue

                # Mostrar Fila
                prom = row.get(col_prometido, "")
                ases = row.get(col_asesor, "")
                ini = str(row.get(col_inicio, "")).strip()

                c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                
                with c1: st.markdown(f"<span class='hora'>{prom}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span class='patente'>{pat}</span>", unsafe_allow_html=True)
                with c3: st.markdown(f"<span class='modelo'>{mod}</span>", unsafe_allow_html=True)
                with c4: st.markdown(f"<span class='asesor'>{ases}</span>", unsafe_allow_html=True)
                with c5:
                    idx_ini = headers.index(col_inicio) + 1
                    idx_fin = headers.index(col_fin) + 1
                    
                    if not ini:
                        if st.button("▶️ Iniciar", key=f"s_{fila_excel}", type="secondary"):
                            h = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila_excel, idx_ini, h)
                            st.rerun()
                    else:
                        st.caption(f"Inició: {ini}")
                        if st.button("🏁 Listo", key=f"e_{fila_excel}", type="primary"):
                            h = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila_excel, idx_fin, h)
                            st.rerun()
                st.markdown("<div style='border-bottom:1px solid #f0f0f0; margin-bottom:5px'></div>", unsafe_allow_html=True)

        else:
            st.info("No hay pendientes para la fecha seleccionada.")

        # --- TABLA TERMINADOS ---
        if not terminados.empty:
            with st.expander(f"✅ Terminados ({len(terminados)})"):
                cols_ok = [c for c in [col_prometido, col_patente, col_modelo, col_asesor, col_inicio, col_fin] if c]
                st.dataframe(terminados[cols_ok], hide_index=True)

    except Exception as e:
        st.error("Error:")
        st.write(e)

if __name__ == "__main__":
    main()
