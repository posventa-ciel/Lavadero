import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Tablero Lavadero", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .fila-tabla { padding: 8px 0; border-bottom: 1px solid #e0e0e0; }
    .hora-grande { font-size: 1.2em; font-weight: bold; color: #d32f2f; }
    .patente { font-size: 1.2em; font-weight: bold; color: #1976d2; }
    .asesor { font-size: 0.9em; color: #666; font-style: italic; }
    .modelo { font-weight: 500; color: #333; }
    .stButton button { width: 100%; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---
def limpiar_hora(valor):
    if not valor: return ""
    v = str(valor).strip()
    if v == "": return ""
    if " " in v: return v.split(" ")[-1][:5]
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
        
        # --- INDICES FIJOS (Columna A = 0) ---
        IDX_FECHA = 0      # A
        IDX_ASESOR = 2     # C
        IDX_DOMINIO = 3    # D
        IDX_MODELO = 4     # E
        IDX_PROMETIDO = 7  # H
        IDX_INICIO = 8     # I
        IDX_FIN = 9        # J

        # --- FILTRO FECHA ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar).date()
        
        lista_pendientes = []
        lista_terminados = []

        # Recorremos saltando encabezados (Fila 1 a 3 aprox)
        for i, fila in enumerate(raw_data):
            if i < 1: continue # Ajustar si tus títulos están en la fila 1
            
            # --- CORRECCIÓN IMPORTANTE: RELLENO DE FILAS CORTAS ---
            # Si la fila tiene menos columnas de las que necesitamos (ej: 10), le agregamos espacios vacíos
            # para que al buscar fila[9] no de error.
            while len(fila) < 12:
                fila.append("")

            # Leemos la fecha. Si falla, pasamos.
            fecha_txt = fila[IDX_FECHA]
            try:
                fecha_fila = pd.to_datetime(fecha_txt, dayfirst=True, errors='coerce').date()
            except:
                continue 

            # PROCESAMOS SOLO SI ES HOY
            if fecha_fila == hoy_dt:
                
                # Leemos datos con seguridad
                dom = fila[IDX_DOMINIO]
                # Si no tiene dominio, no lo mostramos (basura)
                if not dom or dom.strip() == "": continue
                
                datos = {
                    "fila_excel": i + 1,
                    "dominio": dom,
                    "modelo": fila[IDX_MODELO],
                    "asesor": fila[IDX_ASESOR],
                    "prometido": limpiar_hora(fila[IDX_PROMETIDO]),
                    "inicio": limpiar_hora(fila[IDX_INICIO]),
                    "fin": limpiar_hora(fila[IDX_FIN])
                }

                # Lógica de Ordenamiento:
                # Si tiene fin, va a terminados
                if datos["fin"]:
                    lista_terminados.append(datos)
                else:
                    # Si no tiene prometido, le ponemos "23:59" para que vaya al fondo
                    # PERO si tiene "NO SE LAVA" o similar, también va al fondo.
                    hora_orden = datos["prometido"]
                    if not hora_orden: hora_orden = "23:59"
                    
                    datos["orden"] = hora_orden
                    lista_pendientes.append(datos)

        # --- VISUALIZACIÓN ---
        st.subheader(f"📋 A Lavar ({len(lista_pendientes)}) - {hoy_dt.strftime('%d/%m')}")

        if not lista_pendientes:
            st.info(f"No hay pendientes para hoy ({hoy_dt}).")
        else:
            # Ordenamos
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
                
                # Si no tiene hora prometida, mostramos "--:--"
                hora_show = auto['prometido'] if auto['prometido'] else "--:--"
                
                with c1: st.markdown(f"<span class='hora-grande'>{hora_show}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span class='patente'>{auto['dominio']}</span>", unsafe_allow_html=True)
                with c3: st.write(auto['modelo'])
                with c4: st.markdown(f"<span class='asesor'>{auto['asesor']}</span>", unsafe_allow_html=True)
                with c5:
                    fila = auto['fila_excel']
                    if not auto['inicio']:
                        if st.button("▶️ Iniciar", key=f"s_{fila}", type="secondary"):
                            h = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila, IDX_INICIO + 1, h)
                            st.rerun()
                    else:
                        st.caption(f"Inició: {auto['inicio']}")
                        if st.button("🏁 Listo", key=f"e_{fila}", type="primary"):
                            h = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(fila, IDX_FIN + 1, h)
                            st.rerun()
                
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        # Terminados
        if lista_terminados:
            st.write("---")
            with st.expander(f"✅ Lavados Terminados ({len(lista_terminados)})"):
                df_term = pd.DataFrame(lista_terminados)
                if not df_term.empty:
                    df_term = df_term[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]]
                    st.dataframe(df_term, hide_index=True, use_container_width=True)

    except Exception as e:
        st.error("Error:")
        st.write(e)

if __name__ == "__main__":
    main()
