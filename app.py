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
    .fila-tabla { padding: 8px 0; border-bottom: 1px solid #eee; }
    .hora-grande { font-size: 1.1em; font-weight: bold; color: #d32f2f; }
    .patente { font-size: 1.1em; font-weight: bold; color: #1565c0; }
    .asesor { font-size: 0.85em; color: #666; }
    .stButton button { width: 100%; height: 35px; padding: 0; }
</style>
""", unsafe_allow_html=True)

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
        
        # --- 1. BUSCAR FILA DE TÍTULOS ---
        idx_fila_titulos = -1
        for i, fila in enumerate(raw_data[:15]):
            fila_clean = [str(c).strip().upper() for c in fila]
            if "DOMINIO" in fila_clean:
                idx_fila_titulos = i
                titulos_reales = [str(c).strip() for c in fila]
                break
        
        if idx_fila_titulos == -1:
            st.error("No se encontró la columna 'DOMINIO'. Revisa los títulos del Excel.")
            st.stop()

        # --- 2. MAPEO DE COLUMNAS POR NOMBRE ---
        # Buscamos en qué posición está cada cosa según lo que vos escribiste
        def buscar_idx(nombre_buscado):
            for i, t in enumerate(titulos_reales):
                if nombre_buscado.upper() in t.upper():
                    return i
            return -1

        # Mapeamos según tus datos: FECHA(A), ASESOR(C), DOMINIO(D), MODELO(E), PROMETIDO(H)
        idx_fecha = buscar_idx("FECHA")
        idx_asesor = buscar_idx("ASESOR")
        idx_dominio = buscar_idx("DOMINIO")
        idx_modelo = buscar_idx("MODELO")
        idx_prometido = buscar_idx("PROMETIDO")
        idx_inicio = buscar_idx("INICIO")
        idx_fin = buscar_idx("FIN")

        # --- 3. PROCESAR DATOS ---
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz_ar).date()

        pendientes = []
        terminados = []

        for i, fila in enumerate(raw_data):
            if i <= idx_fila_titulos: continue
            
            # Rellenar fila si es corta
            while len(fila) < len(titulos_reales): fila.append("")

            # --- LIMPIEZA DE FECHA ---
            fecha_raw = fila[idx_fecha].strip()
            if not fecha_raw: continue
            
            # Intentamos convertir la fecha del Excel a algo que Python entienda
            fecha_celda = pd.to_datetime(fecha_raw, dayfirst=True, errors='coerce').date()

            if fecha_celda == hoy:
                # Si tiene FIN, va a la lista de abajo
                h_fin = str(fila[idx_fin]).strip()
                
                item = {
                    "fila": i + 1,
                    "prometido": str(fila[idx_prometido]).strip()[:5],
                    "dominio": str(fila[idx_dominio]).strip(),
                    "modelo": str(fila[idx_modelo]).strip(),
                    "asesor": str(fila[idx_asesor]).strip(),
                    "inicio": str(fila[idx_inicio]).strip()[:5],
                    "fin": h_fin[:5]
                }

                if h_fin:
                    terminados.append(item)
                else:
                    # Valor para ordenar (si no hay hora, va al final)
                    item["orden"] = item["prometido"] if item["prometido"] else "23:59"
                    pendientes.append(item)

        # --- 4. MOSTRAR INTERFAZ ---
        # TABLA PENDIENTES
        st.subheader(f"📋 Pendientes ({len(pendientes)})")
        if not pendientes:
            st.info("No hay autos pendientes.")
        else:
            pendientes.sort(key=lambda x: x["orden"])
            
            # Encabezados compactos
            cols = st.columns([1, 1.2, 2, 1.5, 1.2])
            cols[0].caption("PROMETIDO")
            cols[1].caption("DOMINIO")
            cols[2].caption("MODELO")
            cols[3].caption("ASESOR")
            cols[4].caption("ACCIÓN")
            st.markdown("---")

            for auto in pendientes:
                c = st.columns([1, 1.2, 2, 1.5, 1.2])
                c[0].markdown(f"<span class='hora-grande'>{auto['prometido']}</span>", unsafe_allow_html=True)
                c[1].markdown(f"<span class='patente'>{auto['dominio']}</span>", unsafe_allow_html=True)
                c[2].write(auto['modelo'])
                c[3].markdown(f"<span class='asesor'>{auto['asesor']}</span>", unsafe_allow_html=True)
                
                with c[4]:
                    if not auto['inicio']:
                        if st.button("▶️ Iniciar", key=f"s_{auto['fila']}"):
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(auto['fila'], idx_inicio + 1, h_act)
                            st.rerun()
                    else:
                        if st.button("🏁 Listo", key=f"e_{auto['fila']}", type="primary"):
                            h_act = datetime.now(tz_ar).strftime("%H:%M")
                            hoja.update_cell(auto['fila'], idx_fin + 1, h_act)
                            st.balloons()
                            st.rerun()

        # TABLA TERMINADOS
        if terminados:
            st.write("---")
            with st.expander(f"✅ Lavados Finalizados ({len(terminados)})"):
                st.table(pd.DataFrame(terminados)[["prometido", "dominio", "modelo", "asesor", "inicio", "fin"]])

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
