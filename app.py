import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro", layout="wide")

# --- ESTILOS ---
st.markdown("""
<style>
    .fila-tabla { padding: 8px 0; border-bottom: 1px solid #e0e0e0; }
    .hora-grande { font-size: 1.2em; font-weight: bold; color: #d32f2f; }
    .patente { font-size: 1.2em; font-weight: bold; color: #1565c0; text-transform: uppercase; }
    .asesor { font-size: 0.9em; color: #666; font-style: italic; }
    .stButton button { width: 100%; height: 45px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- LIMPIEZA DE HORA ---
def limpiar_hora(valor):
    if not valor: return ""
    v = str(valor).strip()
    if len(v) > 5: return v[:5]
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
    st.title("🚿 Programación Lavadero")

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # --- MAPEO POR LETRAS DE EXCEL (A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9) ---
        IDX_FECHA = 0      # Columna A
        IDX_ASESOR = 2     # Columna C
        IDX_DOMINIO = 3    # Columna D
        IDX_MODELO = 4     # Columna E
        IDX_PROMETIDO = 7  # Columna H
        IDX_INICIO = 8     # Columna I
        IDX_FIN = 9        # Columna J

        # --- FECHA DE HOY ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora = datetime.now(tz_ar)
        
        # Formatos de texto para hoy (ej: 27/1 y 27/01)
        f1 = f"{ahora.day}/{ahora.month}"
        f2 = f"{ahora.day:02d}/{ahora.month:02d}"

        with st.sidebar:
            st.header("⚙️ Configuración")
            st.info(f"Buscando fecha: {f1} o {f2}")
            ver_todo = st.checkbox("Ver todo el listado", value=False)

        lista_pendientes = []
        lista_terminados = []

        # Recorremos los datos (saltando la fila de títulos)
        for i, fila in enumerate(raw_data):
            if i < 1: continue 
            
            # Rellenar si la fila es corta
            while len(fila) < 10: fila.append("")

            # Chequeo de Fecha
            fecha_celda = str(fila[IDX_FECHA]).strip()
            
            if ver_todo or (f1 in fecha_celda or f2 in fecha_celda):
                dom = str(fila[IDX_DOMINIO]).strip()
                if not dom: continue # Saltear si no hay patente

                datos = {
                    "fila": i + 1,
                    "dominio": dom,
                    "modelo": str(fila[IDX_MODELO]).strip(),
                    "asesor": str(fila[IDX_ASESOR]).strip(),
                    "prometido": limpiar_hora(fila[IDX_PROMETIDO]),
                    "inicio": limpiar_hora(fila[IDX_INICIO]),
                    "fin": limpiar_hora(fila[IDX_FIN])
                }

                if datos["fin"]:
                    lista_terminados.append(datos)
                else:
                    # Si no hay horario, mandarlo al final
                    datos["orden"] = datos["prometido"] if datos["prometido"] else "23:59"
                    lista_pendientes.append(datos)

        # --- TABLA PENDIENTES ---
        st.subheader(f"📋 Pendientes ({len(lista_pendientes)})")
        
        if not lista_pendientes:
            st.warning("No hay autos pendientes para hoy.")
        else:
            # ORDENAR DE MÁS TEMPRANO A MÁS TARDE
            lista_pendientes.sort(key=lambda x: x["orden"])

            # Encabezados
            c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
            c1.markdown("**PROMETIDO**")
            c2.markdown("**DOMINIO**")
            c3.markdown("**MODELO**")
            c4.markdown("**ASESOR**")
            c5.markdown("**ESTADO / ACCIÓN**")
            st.markdown("<hr style='margin:2px 0'>", unsafe_allow_html=True)

            for auto in lista_pendientes:
                c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                
                h_show = auto['prometido'] if auto['prometido'] else "--:--"
                
                with c1: st.markdown(f"<span class='hora-grande'>{h_show}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span class='patente'>{auto['dominio']}</span>", unsafe_allow_html=True)
                with c3: st.write(auto['modelo'])
                with c4: st.markdown(f"<span class='asesor'>{auto['asesor']}</span>", unsafe_allow_html=True)
                with c5:
                    num_fila = auto['fila']
                    if not auto['inicio']:
                        if st.button("▶️ INICIAR", key=f"s_{num_fila}"):
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(num_fila, IDX_INICIO + 1, h_act)
                            st.rerun()
                    else:
                        st.caption(f"En proceso ({auto['inicio']})")
                        if st.button("🏁 LISTO", key=f"e_{num_fila}", type="primary"):
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(num_fila, IDX_FIN + 1, h_act)
                            st.rerun()
                
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        # --- TABLA TERMINADOS ---
        if lista_terminados:
            st.write("---")
            with st.expander(f"✅ Lavados Finalizados Hoy ({len(lista_terminados)})"):
                df_t = pd.DataFrame(lista_terminados)
                st.dataframe(df_t[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]], hide_index=True, use_container_width=True)

    except Exception as e:
        st.error("Error inesperado:")
        st.write(e)

if __name__ == "__main__":
    main()
