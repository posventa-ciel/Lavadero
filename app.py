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
    .fila-tabla { padding: 8px 0; border-bottom: 1px solid #e0e0e0; }
    .hora-grande { font-size: 1.2em; font-weight: bold; color: #d32f2f; }
    .patente { font-size: 1.2em; font-weight: bold; color: #1565c0; text-transform: uppercase; }
    .asesor { font-size: 0.9em; color: #666; font-style: italic; }
    .stButton button { width: 100%; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---
def limpiar_hora(valor):
    if not valor: return ""
    v = str(valor).strip()
    if len(v) > 5: return v[:5]
    return v

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
        raw_data = hoja.get_all_values()
        
        # --- 1. BUSCADOR DE ENCABEZADOS (EL SABUESO) ---
        fila_headers = -1
        # Buscamos la fila que tenga "DOMINIO" y "FECHA"
        for i, fila in enumerate(raw_data[:10]):
            fila_upper = [str(c).strip().upper() for c in fila]
            if "DOMINIO" in fila_upper:
                fila_headers = i
                headers = fila_upper # Guardamos los nombres en mayúsculas
                break
        
        if fila_headers == -1:
            st.error("🚨 Error Crítico: No encuentro la columna 'DOMINIO'.")
            st.stop()

        # --- 2. MAPEO DINÁMICO ---
        # Buscamos en qué número de columna cayó cada título
        def get_idx(posibles_nombres):
            for nombre in posibles_nombres:
                if nombre in headers:
                    return headers.index(nombre)
            return -1

        IDX_FECHA = get_idx(["FECHA", "DIA"])
        IDX_DOMINIO = get_idx(["DOMINIO", "PATENTE"])
        IDX_MODELO = get_idx(["MODELO", "VEHICULO"])
        IDX_ASESOR = get_idx(["ASESOR", "ASESOR DE SERVICIO"])
        IDX_PROMETIDO = get_idx(["HORARIO PROMETIDO", "HORA PROM", "PROMESA", "HORA"])
        IDX_INICIO = get_idx(["INICIO", "HORA INICIO"])
        IDX_FIN = get_idx(["FIN", "HORA FIN", "TERMINADO"])

        # Debug para vos (Te muestra qué encontró)
        with st.sidebar:
            st.header("🕵️ Detector de Columnas")
            st.success(f"Dominio: Columna {IDX_DOMINIO+1}")
            st.success(f"Horario: Columna {IDX_PROMETIDO+1}")
            st.info(f"Asesor: Columna {IDX_ASESOR+1}")
            st.write("---")
            ver_todo = st.checkbox("Ignorar Fecha (Ver Todo)", value=False)

        # Si alguna columna clave falta, avisamos
        if IDX_DOMINIO == -1 or IDX_PROMETIDO == -1:
            st.error("⚠️ Faltan columnas clave (Dominio o Horario Prometido). Revisa los nombres en el Excel.")
            st.write("Columnas encontradas:", headers)
            st.stop()

        # --- 3. PROCESAMIENTO ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora = datetime.now(tz_ar)
        hoy_dia = ahora.day
        hoy_mes = ahora.month
        
        # Filtros de texto (27/1 y 27/01)
        filtro_1 = f"{hoy_dia}/{hoy_mes}"
        filtro_2 = f"{hoy_dia:02d}/{hoy_mes:02d}"

        lista_pendientes = []
        lista_terminados = []

        for i, fila in enumerate(raw_data):
            if i <= fila_headers: continue # Saltamos títulos
            
            # Relleno de seguridad
            while len(fila) < max(IDX_FIN, IDX_PROMETIDO) + 1: fila.append("")

            # Chequeo de Fecha
            fecha_celda = str(fila[IDX_FECHA]).strip()
            
            es_de_hoy = False
            if ver_todo:
                es_de_hoy = True
            else:
                # Si contiene 27/1 o 27/01
                if filtro_1 in fecha_celda or filtro_2 in fecha_celda:
                    es_de_hoy = True
            
            if es_de_hoy:
                dom = str(fila[IDX_DOMINIO]).strip()
                if not dom: continue # Fila vacía

                datos = {
                    "fila": i + 1,
                    "dominio": dom,
                    "modelo": str(fila[IDX_MODELO]).strip() if IDX_MODELO != -1 else "",
                    "asesor": str(fila[IDX_ASESOR]).strip() if IDX_ASESOR != -1 else "",
                    "prometido": limpiar_hora(fila[IDX_PROMETIDO]),
                    "inicio": limpiar_hora(fila[IDX_INICIO]) if IDX_INICIO != -1 else "",
                    "fin": limpiar_hora(fila[IDX_FIN]) if IDX_FIN != -1 else ""
                }

                if datos["fin"]:
                    lista_terminados.append(datos)
                else:
                    h = datos["prometido"]
                    if not h: h = "23:59"
                    datos["orden"] = h
                    lista_pendientes.append(datos)

        # --- VISUALIZACIÓN ---
        st.subheader(f"📋 A Lavar ({len(lista_pendientes)})")
        
        if not lista_pendientes:
            st.info("No hay vehículos pendientes. (Prueba activar 'Ignorar Fecha' en el menú lateral)")
        else:
            lista_pendientes.sort(key=lambda x: x["orden"])

            # Encabezados
            c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
            c1.markdown("**HORA**")
            c2.markdown("**DOMINIO**")
            c3.markdown("**MODELO**")
            c4.markdown("**ASESOR**")
            c5.markdown("**ACCIÓN**")
            st.markdown("<hr style='margin:5px 0'>", unsafe_allow_html=True)

            for auto in lista_pendientes:
                c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                
                h_show = auto['prometido'] if auto['prometido'] else "--:--"
                
                with c1: st.markdown(f"<span class='hora-grande'>{h_show}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span class='patente'>{auto['dominio']}</span>", unsafe_allow_html=True)
                with c3: st.write(auto['modelo'])
                with c4: st.markdown(f"<span class='asesor'>{auto['asesor']}</span>", unsafe_allow_html=True)
                with c5:
                    f = auto['fila']
                    if not auto['inicio']:
                        if st.button("▶️ Iniciar", key=f"s_{f}", type="secondary"):
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(f, IDX_INICIO + 1, h_act)
                            st.rerun()
                    else:
                        st.caption(f"Inició: {auto['inicio']}")
                        if st.button("🏁 Listo", key=f"e_{f}", type="primary"):
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(f, IDX_FIN + 1, h_act)
                            st.rerun()
                
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        if lista_terminados:
            st.write("---")
            with st.expander(f"✅ Terminados ({len(lista_terminados)})"):
                df_t = pd.DataFrame(lista_terminados)
                if not df_t.empty:
                    st.dataframe(df_t[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]], hide_index=True)

    except Exception as e:
        st.error("Error:")
        st.write(e)

if __name__ == "__main__":
    main()
