import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Lavadero Pro - Plan General", layout="wide")

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
    # Accedemos específicamente a "PLAN GENERAL"
    return client.open_by_url(url).worksheet("PLAN GENERAL")

def main():
    st.title("🚿 Programación Lavadero - PLAN GENERAL")

    try:
        hoja = conectar_sheet()
        raw_data = hoja.get_all_values()
        
        # --- MAPEO SEGÚN TU EXCEL REAL ---
        # A=0(Fecha), B=1(Asesor), C=2(Dominio), D=3(Modelo), E=4(Cliente), 
        # F=5(Trabajo), G=6(Prometido), H=7(Inicio), I=8(Fin)
        IDX_FECHA = 0      
        IDX_ASESOR = 1     
        IDX_DOMINIO = 2    
        IDX_MODELO = 3     
        IDX_PROMETIDO = 6  
        IDX_INICIO = 7     
        IDX_FIN = 8        

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora = datetime.now(tz_ar)
        f1 = f"{ahora.day}/{ahora.month}"
        f2 = f"{ahora.day:02d}/{ahora.month:02d}"

        with st.sidebar:
            st.header("⚙️ Configuración")
            st.info(f"Fecha de hoy: {f2}")
            ver_todo = st.checkbox("Ver todo el listado", value=False)

        lista_pendientes = []
        lista_terminados = []

        # Empezamos desde la fila 4 (índice 3) porque las primeras son títulos
        for i, fila in enumerate(raw_data):
            if i < 3: continue 
            
            while len(fila) < 10: fila.append("")

            fecha_celda = str(fila[IDX_FECHA]).strip()
            
            if ver_todo or (f1 in fecha_celda or f2 in fecha_celda):
                dom = str(fila[IDX_DOMINIO]).strip()
                if not dom or dom.lower() == "dominio": continue

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
                    datos["orden"] = datos["prometido"] if datos["prometido"] else "23:59"
                    lista_pendientes.append(datos)

        # --- CUADRO 1: PENDIENTES ---
        st.subheader(f"📋 Pendientes de Lavar ({len(lista_pendientes)})")
        if not lista_pendientes:
            st.success("¡No hay autos pendientes!")
        else:
            lista_pendientes.sort(key=lambda x: x["orden"])
            c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
            c1.write("**PROMETIDO**"); c2.write("**DOMINIO**"); c3.write("**MODELO**"); c4.write("**ASESOR**"); c5.write("**ACCIÓN**")
            
            for auto in lista_pendientes:
                col1, col2, col3, col4, col5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                with col1: st.markdown(f"<span class='hora-grande'>{auto['prometido'] or '--:--'}</span>", unsafe_allow_html=True)
                with col2: st.markdown(f"<span class='patente'>{auto['dominio']}</span>", unsafe_allow_html=True)
                with col3: st.write(auto['modelo'])
                with col4: st.markdown(f"<span class='asesor'>{auto['asesor']}</span>", unsafe_allow_html=True)
                with col5:
                    if not auto['inicio']:
                        if st.button("▶️ INICIAR", key=f"start_{auto['fila']}"):
                            hoja.update_cell(auto['fila'], IDX_INICIO + 1, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()
                    else:
                        if st.button("🏁 LISTO", key=f"end_{auto['fila']}", type="primary"):
                            hoja.update_cell(auto['fila'], IDX_FIN + 1, datetime.now(tz_ar).strftime("%H:%M"))
                            st.rerun()

        # --- CUADRO 2: LAVADOS DEL DÍA ---
        if lista_terminados:
            st.markdown("---")
            st.subheader(f"✅ Lavados Finalizados Hoy ({len(lista_terminados)})")
            df_t = pd.DataFrame(lista_terminados)
            st.dataframe(df_t[["prometido", "dominio", "modelo", "inicio", "fin"]], hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
