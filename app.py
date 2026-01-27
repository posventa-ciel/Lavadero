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
    .modelo { font-weight: 500; color: #333; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---
def limpiar_hora(valor):
    if not valor: return ""
    v = str(valor).strip()
    if len(v) > 5: return v[:5] # Cortar segundos
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
        
        # --- ÍNDICES DE COLUMNAS (A=0, B=1, C=2...) ---
        IDX_FECHA = 0      # Columna A
        IDX_ASESOR = 2     # Columna C
        IDX_DOMINIO = 3    # Columna D
        IDX_MODELO = 4     # Columna E
        IDX_PROMETIDO = 7  # Columna H
        IDX_INICIO = 8     # Columna I
        IDX_FIN = 9        # Columna J

        # --- FECHA DE HOY (TEXTO) ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora = datetime.now(tz_ar)
        
        # Generamos las variantes de texto posibles para "hoy"
        # Ejemplo: "27/1", "27/01", "27/1/2026", "27-01"
        hoy_dia = str(ahora.day)
        hoy_mes = str(ahora.month)
        
        # Texto clave: "27/1" (Sin ceros adelante es lo más común en tu excel)
        texto_busqueda_1 = f"{hoy_dia}/{hoy_mes}"       # 27/1
        texto_busqueda_2 = f"{hoy_dia:02d}/{hoy_mes:02d}" # 27/01
        
        # --- BARRA LATERAL (DEBUG) ---
        with st.sidebar:
            st.header("🔧 Controles")
            ver_todo = st.checkbox("⚠️ Ver TODO (Ignorar fecha)", value=False)
            st.write(f"Buscando fecha que contenga: **'{texto_busqueda_1}'**")

        lista_pendientes = []
        lista_terminados = []

        # --- BARRIDO DE DATOS ---
        for i, fila in enumerate(raw_data):
            if i < 1: continue # Saltamos títulos
            
            # Relleno de seguridad por si la fila es corta
            while len(fila) < 12: fila.append("")

            # 1. LEER FECHA COMO TEXTO
            fecha_celda = str(fila[IDX_FECHA]).strip()
            
            # 2. FILTRO INTELIGENTE
            # Si "Ver Todo" está apagado, aplicamos el filtro de fecha
            es_de_hoy = False
            if ver_todo:
                es_de_hoy = True
            else:
                # Si la celda contiene "27/1" o "27/01" -> ES DE HOY
                if texto_busqueda_1 in fecha_celda or texto_busqueda_2 in fecha_celda:
                    es_de_hoy = True
            
            if es_de_hoy:
                # Capturamos datos
                dom = str(fila[IDX_DOMINIO]).strip()
                if not dom: continue # Si no hay dominio, es fila vacía

                datos = {
                    "fila": i + 1,
                    "dominio": dom,
                    "modelo": str(fila[IDX_MODELO]).strip(),
                    "asesor": str(fila[IDX_ASESOR]).strip(),
                    "prometido": limpiar_hora(fila[IDX_PROMETIDO]),
                    "inicio": limpiar_hora(fila[IDX_INICIO]),
                    "fin": limpiar_hora(fila[IDX_FIN])
                }

                # Clasificar
                if datos["fin"]:
                    lista_terminados.append(datos)
                else:
                    # Orden: Si no tiene hora, "23:59"
                    h = datos["prometido"]
                    if not h: h = "23:59"
                    datos["orden"] = h
                    lista_pendientes.append(datos)

        # --- VISUALIZACIÓN ---
        st.subheader(f"📋 A Lavar ({len(lista_pendientes)})")
        
        if not lista_pendientes:
            st.warning(f"No encontré autos que digan '{texto_busqueda_1}' en la primera columna.")
            st.info("Prueba activando la casilla '⚠️ Ver TODO' en el menú de la izquierda.")
        else:
            # Ordenar
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
                            # ESCRIBIR HORA ACTUAL
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(f, IDX_INICIO + 1, h_act)
                            st.rerun()
                    else:
                        st.caption(f"Inició: {auto['inicio']}")
                        if st.button("🏁 Listo", key=f"e_{f}", type="primary"):
                            # ESCRIBIR HORA FIN
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(f, IDX_FIN + 1, h_act)
                            st.rerun()
                
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        # Terminados
        if lista_terminados:
            st.write("---")
            with st.expander(f"✅ Lavados Terminados ({len(lista_terminados)})"):
                df_t = pd.DataFrame(lista_terminados)
                if not df_t.empty:
                    st.dataframe(df_t[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]], hide_index=True)

    except Exception as e:
        st.error("Error:")
        st.write(e)

if __name__ == "__main__":
    main()
