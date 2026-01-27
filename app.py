import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
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
    .pendiente-viejo { color: #ff9800; font-weight: bold; font-size: 0.8em; }
    .stButton button { width: 100%; height: 45px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def limpiar_hora(valor):
    if not valor: return ""
    v = str(valor).strip()
    return v[:5] if len(v) > 5 else v

# --- CONEXIÓN ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = json.loads(st.secrets["service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    url = "https://docs.google.com/spreadsheets/d/1zw3qrKmdK_gmGL8k_nDyC2ugWb_hMINDxNvqzE2Japo/edit"
    return client.open_by_url(url).worksheet("PLAN GENERAL")

def main():
    st.title("🚿 Programación Lavadero")

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # Mapeo de columnas
        IDX_FECHA = 0      
        IDX_ASESOR = 2     
        IDX_DOMINIO = 3    
        IDX_MODELO = 4     
        IDX_PROMETIDO = 7  
        IDX_INICIO = 8     
        IDX_FIN = 9        

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar)

        # --- BARRA LATERAL CON FILTROS ---
        with st.sidebar:
            st.header("🔍 Filtros y Fecha")
            # Selector de fecha (Calendario)
            fecha_consulta = st.date_input("Consultar programación del día:", hoy_dt)
            ver_todo = st.checkbox("Ver historial completo", value=False)
            arrastrar_pendientes = st.checkbox("Incluir pendientes de días anteriores", value=True)

        # Formatear fecha seleccionada para comparar con el Excel
        f_str = fecha_consulta.strftime("%-d/%-m/%Y") # Formato 27/1/2026
        f_str_cero = fecha_consulta.strftime("%d/%m/%Y") # Formato 27/01/2026

        lista_pendientes = []
        lista_terminados = []

        for i, fila in enumerate(raw_data):
            if i < 1: continue 
            while len(fila) < 10: fila.append("")

            fecha_celda = str(fila[IDX_FECHA]).strip()
            prometido_valor = str(fila[IDX_PROMETIDO]).strip().upper()
            dom = str(fila[IDX_DOMINIO]).strip()
            fin_hora = limpiar_hora(fila[IDX_FIN])

            if not dom or prometido_valor == "NO SE LAVA": 
                continue

            es_de_hoy = f_str in fecha_celda or f_str_cero in fecha_celda or f_str in prometido_valor or f_str_cero in prometido_valor
            
            # Lógica para arrastrar pendientes viejos
            es_pendiente_viejo = False
            if arrastrar_pendientes and not fin_hora:
                try:
                    fecha_dt_celda = datetime.strptime(fecha_celda.split()[0], "%d/%m/%Y").date()
                    if fecha_dt_celda < fecha_consulta:
                        es_pendiente_viejo = True
                except:
                    pass

            # Criterio de inclusión
            if ver_todo or es_de_hoy or es_pendiente_viejo:
                datos = {
                    "fila": i + 1,
                    "dominio": dom,
                    "modelo": str(fila[IDX_MODELO]).strip(),
                    "asesor": str(fila[IDX_ASESOR]).strip(),
                    "prometido": prometido_valor,
                    "inicio": limpiar_hora(fila[IDX_INICIO]),
                    "fin": fin_hora,
                    "es_viejo": es_pendiente_viejo
                }

                if datos["fin"]:
                    lista_terminados.append(datos)
                else:
                    datos["orden"] = datos["prometido"] if ":" in datos["prometido"] else "23:59"
                    lista_pendientes.append(datos)

        # --- MOSTRAR PENDIENTES ---
        st.subheader(f"📋 Pendientes ({len(lista_pendientes)}) - {fecha_consulta.strftime('%d/%m/%Y')}")
        
        if not lista_pendientes:
            st.info("No hay autos pendientes.")
        else:
            lista_pendientes.sort(key=lambda x: x["orden"])
            c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
            c1.markdown("**PROMETIDO**"); c2.markdown("**DOMINIO**"); c3.markdown("**MODELO**"); c4.markdown("**ASESOR**"); c5.markdown("**ACCIÓN**")
            st.divider()

            for auto in lista_pendientes:
                col1, col2, col3, col4, col5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                with col1: 
                    st.markdown(f"<span class='hora-grande'>{auto['prometido']}</span>", unsafe_allow_html=True)
                    if auto['es_viejo']:
                        st.markdown("<span class='pendiente-viejo'>⚠️ ATRASADO</span>", unsafe_allow_html=True)
                with col2: st.markdown(f"<span class='patente'>{auto['dominio']}</span>", unsafe_allow_html=True)
                with col3: st.write(auto['modelo'])
                with col4: st.markdown(f"<span class='asesor'>{auto['asesor']}</span>", unsafe_allow_html=True)
                with col5:
                    f_idx = auto['fila']
                    if not auto['inicio']:
                        if st.button("▶️ INICIAR", key=f"btn_start_{f_idx}"):
                            hoja.update_cell(f_idx, IDX_INICIO + 1, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                    else:
                        if st.button("🏁 LISTO", key=f"btn_end_{f_idx}", type="primary"):
                            hoja.update_cell(f_idx, IDX_FIN + 1, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        # --- MOSTRAR TERMINADOS ---
        if lista_terminados:
            st.write("---")
            with st.expander(f"✅ Lavados Finalizados ({len(lista_terminados)})"):
                df_t = pd.DataFrame(lista_terminados)
                st.dataframe(df_t[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]], 
                             hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"Error detectado: {e}")

if __name__ == "__main__":
    main()
