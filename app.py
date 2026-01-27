import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import pytz 

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Tablero Lavadero", layout="wide")

# --- ESTILOS ---
st.markdown("""
<style>
    .fila-tabla { padding: 8px 0; border-bottom: 1px solid #e0e0e0; }
    .hora-grande { font-size: 1.3em; font-weight: bold; color: #d32f2f; }
    .patente { font-size: 1.2em; font-weight: bold; color: #1976d2; }
    .asesor { font-size: 0.9em; color: #555; font-style: italic; }
    .modelo { font-weight: 500; }
    div[data-testid="stExpander"] details { border: 1px solid #eee; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN PARA LIMPIAR HORAS ---
def limpiar_hora(valor):
    """Limpia cualquier formato raro que venga del Excel"""
    if not valor: return ""
    v = str(valor).strip()
    if v == "": return ""
    # Si viene fecha completa "2026-01-27 15:00:00"
    if " " in v: return v.split(" ")[-1][:5]
    # Si viene con segundos "15:00:00"
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
    st.title("🚿 Programación del Día")

    try:
        hoja = conectar_sheet()
        # Leemos TODO el contenido
        raw_data = hoja.get_all_values()
        
        # --- MAPEO MANUAL DE COLUMNAS (Indice 0 = Columna A) ---
        IDX_FECHA = 0      # Col A
        IDX_ASESOR = 2     # Col C
        IDX_DOMINIO = 3    # Col D
        IDX_MODELO = 4     # Col E
        IDX_PROMETIDO = 7  # Col H
        
        # ASUMIMOS ESTAS DOS (Si están mal, cámbialas aquí)
        IDX_INICIO = 8     # Col I
        IDX_FIN = 9        # Col J

        # --- FILTRADO DE FECHA ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy_dt = datetime.now(tz_ar).date()
        
        # Listas para guardar los datos procesados
        lista_pendientes = []
        lista_terminados = []

        # Recorremos fila por fila (Saltamos las primeras 3 de títulos)
        for i, fila in enumerate(raw_data):
            if i < 3: continue # Ignoramos encabezados
            
            # Seguridad: Si la fila está vacía o muy corta, la saltamos
            if len(fila) <= IDX_PROMETIDO: continue

            # 1. Leer FECHA (Columna A)
            fecha_txt = fila[IDX_FECHA]
            
            # Si la fecha está vacía, usamos un truco: miramos la fila anterior (Relleno)
            # (Simplificación: Por ahora exigimos que tenga fecha, o usamos lógica de "hoy")
            
            # Normalizamos fecha
            try:
                # Intenta convertir el texto a fecha
                fecha_fila = pd.to_datetime(fecha_txt, dayfirst=True, errors='coerce').date()
            except:
                continue # Si no es fecha, saltar

            # 2. SI LA FECHA ES HOY, PROCESAMOS
            if fecha_fila == hoy_dt:
                
                # Extraemos datos usando los ÍNDICES FIJOS
                datos = {
                    "fila_excel": i + 1, # +1 porque gspread empieza en 1
                    "dominio": fila[IDX_DOMINIO],
                    "modelo": fila[IDX_MODELO],
                    "asesor": fila[IDX_ASESOR],
                    "prometido": limpiar_hora(fila[IDX_PROMETIDO]),
                    "inicio": limpiar_hora(fila[IDX_INICIO]) if len(fila) > IDX_INICIO else "",
                    "fin": limpiar_hora(fila[IDX_FIN]) if len(fila) > IDX_FIN else ""
                }

                # Clasificar: Terminado o Pendiente
                if datos["fin"]:
                    lista_terminados.append(datos)
                else:
                    # Lógica de ordenamiento para pendientes
                    # Si no tiene hora prometida, le ponemos "23:59" para que vaya al fondo
                    datos["orden"] = datos["prometido"] if datos["prometido"] else "23:59"
                    lista_pendientes.append(datos)

        # --- MOSTRAR PENDIENTES ---
        st.subheader(f"📋 A Lavar ({len(lista_pendientes)}) - {hoy_dt.strftime('%d/%m')}")

        if not lista_pendientes:
            st.info("✅ No hay vehículos pendientes para hoy.")
        else:
            # Ordenar por horario
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
                
                with c1: st.markdown(f"<span class='hora-grande'>{auto['prometido']}</span>", unsafe_allow_html=True)
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
                            st.rerun() # Recarga rapida
                
                st.markdown("<div class='fila-tabla'></div>", unsafe_allow_html=True)

        # --- MOSTRAR TERMINADOS ---
        if lista_terminados:
            st.write("---")
            with st.expander(f"✅ Lavados Terminados ({len(lista_terminados)})"):
                # Creamos un dataframe simple solo para mostrar
                df_term = pd.DataFrame(lista_terminados)
                # Seleccionamos y renombramos columnas para que se vea lindo
                if not df_term.empty:
                    df_term = df_term[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]]
                    st.dataframe(df_term, hide_index=True, use_container_width=True)

    except Exception as e:
        st.error("Ocurrió un error:")
        st.write(e)
        st.info("Revisa si las columnas I y J existen en tu Excel para Inicio y Fin.")

if __name__ == "__main__":
    main()
