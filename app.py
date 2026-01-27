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
    .fila-tabla { padding: 10px 0; border-bottom: 1px solid #eee; }
    .hora-grande { font-size: 1.3em; font-weight: bold; color: #d32f2f; }
    .patente { font-size: 1.3em; font-weight: bold; color: #1565c0; }
    .asesor { font-size: 0.95em; color: #555; }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).worksheet("PLAN GENERAL")

def main():
    st.title("🚿 Gestión de Lavadero")

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Índices exactos (Basado en A, B, C...)
        IDX_FECHA = 0      # Col A
        IDX_ASESOR = 2     # Col C
        IDX_DOMINIO = 3    # Col D
        IDX_MODELO = 4     # Col E
        IDX_PROMETIDO = 7  # Col H
        IDX_INICIO = 8     # Col I
        IDX_FIN = 9        # Col J

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_str = datetime.now(tz_ar).strftime("%d/%m/%Y")

        # --- FILTROS EN BARRA LATERAL ---
        with st.sidebar:
            st.header("🔍 Filtros")
            fecha_buscada = st.text_input("Fecha (dd/mm/aaaa)", value=hoy_str)
            busqueda = st.text_input("Buscar Patente").upper()
            ver_todo = st.checkbox("Ver todos los registros")

        pendientes = []
        terminados = []

        # Procesar filas (desde la 2 para evitar encabezados)
        for i, fila in enumerate(raw_data[1:], start=2):
            if len(fila) < 10: fila += [""] * (10 - len(fila))
            
            fecha_celda = fila[IDX_FECHA].strip()
            dominio = fila[IDX_DOMINIO].strip().upper()
            prometido = fila[IDX_PROMETIDO].strip()

            # Lógica de filtrado
            if not dominio or prometido.upper() == "NO SE LAVA": continue
            if not ver_todo and (fecha_buscada not in fecha_celda): continue
            if busqueda and (busqueda not in dominio): continue

            item = {
                "fila": i,
                "dominio": dominio,
                "modelo": fila[IDX_MODELO],
                "asesor": fila[IDX_ASESOR],
                "prometido": prometido,
                "inicio": fila[IDX_INICIO],
                "fin": fila[IDX_FIN]
            }

            if item["fin"]:
                terminados.append(item)
            else:
                pendientes.append(item)

        # --- MOSTRAR PENDIENTES ---
        st.subheader(f"📋 Pendientes ({len(pendientes)})")
        if pendientes:
            c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1.5])
            c1.bold("Prometido"); c2.bold("Patente"); c3.bold("Modelo"); c4.bold("Asesor"); c5.bold("Estado")
            
            for p in pendientes:
                col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1.5])
                col1.markdown(f"<span class='hora-grande'>{p['prometido']}</span>", unsafe_allow_html=True)
                col2.markdown(f"<span class='patente'>{p['dominio']}</span>", unsafe_allow_html=True)
                col3.write(p['modelo'])
                col4.write(p['asesor'])
                with col5:
                    if not p['inicio']:
                        if st.button("INICIAR", key=f"ini_{p['fila']}"):
                            hoja.update_cell(p['fila'], IDX_INICIO + 1, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                    else:
                        if st.button("TERMINAR", key=f"fin_{p['fila']}", type="primary"):
                            hoja.update_cell(p['fila'], IDX_FIN + 1, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)
        else:
            st.info("No hay autos pendientes para esta selección.")

        # --- MOSTRAR TERMINADOS ---
        if terminados:
            st.divider()
            with st.expander(f"✅ Finalizados ({len(terminados)})"):
                st.table(pd.DataFrame(terminados)[["prometido", "dominio", "modelo", "inicio", "fin"]])

    except Exception as e:
        st.error(f"Error de conexión: {e}")

if __name__ == "__main__":
    main()
