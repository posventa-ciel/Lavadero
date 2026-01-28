# --- ESTILOS CSS (CORREGIDO) ---
st.markdown("""
<style>
    /* 1. Ajuste del techo: Aumenté el padding-top para que no se corte arriba */
    .block-container {
        padding-top: 2rem !important; 
        padding-bottom: 2rem !important;
    }
    
    /* 2. Encabezado Azul: Flexible en altura */
    .header-box {
        background: linear-gradient(90deg, #00235d 0%, #001538 100%);
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        /* Quitamos height fija, usamos min-height */
        min-height: 70px; 
    }
    
    /* Título responsive */
    .header-title {
        font-size: 22px; 
        font-weight: bold; 
        letter-spacing: 0.5px; 
        text-transform: uppercase;
        line-height: 1.2;
    }

    /* 3. FILAS ULTRA COMPACTAS */
    .compact-row {
        border-bottom: 1px solid #e0e0e0;
        padding: 3px 0 !important;
        margin: 0 !important;
        line-height: 1 !important;
    }
    
    /* 4. Tipografía Ajustada */
    p { margin: 0 !important; }
    .txt-hora { color: #d32f2f; font-weight: 700; font-size: 14px; }
    .txt-patente { color: #00235d; font-weight: 700; font-size: 14px; }
    .txt-modelo { color: #333; font-weight: 500; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .txt-asesor { color: #666; font-style: italic; font-size: 11px; }
    
    /* 5. Botones Slim */
    .stButton button {
        height: 24px !important;
        min-height: 24px !important;
        font-size: 11px !important;
        padding: 0 10px !important;
        margin: 2px 0 !important;
        line-height: 1 !important;
    }
    
    /* 6. Eliminar huecos de Streamlit */
    div[data-testid="stVerticalBlock"] > div {
        gap: 0rem !important;
    }
    div[data-testid="column"] {
        padding: 0 !important;
    }
    
    /* Ajuste para móviles: si la pantalla es chica, achicar texto */
    @media (max-width: 600px) {
        .header-title { font-size: 16px; }
        .header-box { flex-direction: column; align-items: flex-start; gap: 10px; }
    }
</style>
""", unsafe_allow_html=True)

# ... (MANTENÉ TUS FUNCIONES DE CONEXIÓN Y LÓGICA AQUÍ: conectar_sheet, calcular_minutos, etc.) ...

def main():
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    hora_actual = datetime.now(tz_ar).strftime("%H:%M")
    hoy_date = datetime.now(tz_ar).date()

    # --- ENCABEZADO CORREGIDO Y MEJORADO ---
    # Usamos flexbox limpio para alinear Imagen - Título a la izquierda, y Fecha a la derecha
    st.markdown(f"""
    <div class="header-box">
        <div style="display: flex; align-items: center; gap: 15px;">
            <div style="background: white; border-radius: 50%; padding: 4px; display: flex; align-items: center; justify-content: center; width: 50px; height: 50px;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/f/f7/Peugeot_Logo_2021.svg" 
                     style="width: 35px; height: auto;" 
                     alt="Logo">
            </div>
            <div class="header-title">
                PROGRAMACIÓN<br>DEL LAVADERO
            </div>
        </div>
        
        <div style="text-align: right; min-width: 100px;">
            <div style="font-size: 16px; font-weight: bold;">{hoy_date.strftime("%d/%m/%Y")}</div>
            <div style="font-size: 14px; opacity: 0.9;">{datetime.now(tz_ar).strftime("%H:%M")} hs</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ... (RESTO DE TU CÓDIGO MAIN: hoja = conectar_sheet(), lógica de filtros, etc.) ...
