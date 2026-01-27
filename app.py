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
        
        # --- NUEVO MAPEO SEGÚN TU IMAGEN ---
        # A=0 (Fecha), B=1 (Hora Recep), C=2 (Asesor), D=3 (Dominio), 
        # E=4 (Modelo), H=7 (Prometido), I=8 (Inicio), J=9 (Fin)
        IDX_FECHA = 0      
        IDX_ASESOR = 2     
        IDX_DOMINIO = 3    
        IDX_MODELO = 4     
        IDX_PROMETIDO = 7  
        IDX_INICIO = 8     
        IDX_FIN = 9        

        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora = datetime.now(tz_ar)
        
        # Formatos de fecha para filtrar
        f1 = f"{ahora.day}/{ahora.month}/{ahora.year}"
        f2 = f"{ahora.day}/{ahora.month}" # Por si acaso el formato es corto

        with st.sidebar:
            st.header("⚙️ Configuración")
            ver_todo = st.checkbox("Ver todos los registros", value=False)

        lista_pendientes = []
        lista_terminados = []

        # Recorremos desde la fila 2 (índice 1) para saltar el encabezado azul
        for i, fila in enumerate(raw_data):
            if i < 1: continue 
            
            # Asegurar que la fila tenga suficientes columnas
            while len(fila) < 10: fila.append("")

            fecha_celda = str(fila[IDX_FECHA]).strip()
            prometido_valor = str(fila[IDX_PROMETIDO]).strip().upper()

            # Filtramos por fecha de hoy o "Ver todo"
            if ver_todo or (f1 in fecha_celda or f2 in fecha_celda):
                
                # Ignorar si no hay dominio o si dice "NO SE LAVA"
                dom = str(fila[IDX_DOMINIO]).strip()
                if not dom or prometido_valor == "NO SE LAVA": 
                    continue

                datos = {
                    "fila": i + 1,
                    "dominio": dom,
                    "modelo": str(fila[IDX_MODELO]).strip(),
                    "asesor": str(fila[IDX_ASESOR]).strip(),
                    "prometido": prometido_valor,
                    "inicio": limpiar_hora(fila[IDX_INICIO]),
                    "fin": limpiar_hora(fila[IDX_FIN])
                }

                if datos["fin"] and datos["fin"] != "":
                    lista_terminados.append(datos)
                else:
                    # Usamos el horario para ordenar, si no tiene va al final
                    datos["orden"] = datos["prometido"] if ":" in datos["prometido"] else "23:59"
                    lista_pendientes.append(datos)

        # --- CUADRO 1: PENDIENTES ---
        st.subheader(f"📋 Pendientes de Lavar ({len(lista_pendientes)})")
        if not lista_pendientes:
            st.info("No hay autos pendientes para lavar en esta fecha.")
        else:
            # Ordenar por horario prometido
            lista_pendientes.sort(key=lambda x: x["orden"])
            
            c1, c2, c3, c4, c5 = st.columns([1, 1.2, 2, 1.5, 1.5])
            c1.markdown("**PROMETIDO**"); c2.markdown("**DOMINIO**"); c3.markdown("**MODELO**"); c4.markdown("**ASESOR**"); c5.markdown("**ACCIÓN**")
            st.divider()

            for auto in lista_pendientes:
                col1, col2, col3, col4, col5 = st.columns([1, 1.2, 2, 1.5, 1.5])
                with col1: st.markdown(f"<span class='hora-grande'>{auto['prometido']}</span>", unsafe_allow_html=True)
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

        # --- CUADRO 2: TERMINADOS ---
        if lista_terminados:
            st.write("---")
            st.subheader(f"✅ Lavados Finalizados ({len(lista_terminados)})")
            df_t = pd.DataFrame(lista_terminados)
            st.dataframe(df_t[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]], 
                         hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"Error detectado: {e}")

if __name__ == "__main__":
    main()
