import streamlit as st
from pathlib import Path
from src.db.database import init_db
from src.ingestion.pipeline import ingest_excel, ingest_pdf
from src.ai.agent import answer_question
from src.config import DB_PATH
from src.utils.logger import log_info, log_error
from src.ai.accounting_tasks import AVAILABLE_TASKS

# ===== Configuración de página =====
st.set_page_config(
    page_title="IA Contable",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Inicialización =====
init_db()

# ===== Estilos CSS =====
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .step-container {
        background-color: #e8f4f8;
        padding: 12px;
        border-left: 4px solid #0066cc;
        margin: 8px 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ===== Sidebar: Carga de documentos =====
with st.sidebar:
    st.header("Cargar Documentos")
    st.markdown("Sube facturas o extractos contables (PDF/Excel)")
    
    uploaded_file = st.file_uploader(
        "Selecciona un archivo",
        type=["pdf", "xlsx", "xls"],
        help="Formatos soportados: PDF, XLSX, XLS"
    )
    
    if uploaded_file is not None:
        temp_path = Path(f"data/{uploaded_file.name}")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(uploaded_file.getbuffer())
        
        with st.spinner("Procesando archivo..."):
            try:
                if uploaded_file.name.endswith(".pdf"):
                    doc_id = ingest_pdf(temp_path)
                    log_info(f"PDF cargado: {uploaded_file.name} (ID: {doc_id})")
                    st.success(f"PDF cargado correctamente (ID: {doc_id})")
                else:
                    doc_id = ingest_excel(temp_path)
                    log_info(f"Excel cargado: {uploaded_file.name} (ID: {doc_id})")
                    st.success(f"Excel procesado (ID: {doc_id})")
                st.balloons()
            except Exception as e:
                log_error(f"Error cargando archivo: {e}")
                st.error(f"Error: {str(e)}")

# ===== Área principal =====
st.title("Asistente Contable Inteligente")
st.markdown("""
Analiza tus facturas, extractos y documentos contables con IA.
El agente detecta automáticamente qué análisis necesitas y los ejecuta.
""")

st.divider()

# ===== Chat/Consultas =====
st.header("Haz tu Pregunta")
st.markdown("Ejemplos: *¿Cuál es mi balance?* | *¿Total vendido este mes?* | *¿Análisis de gastos?*")

# Sugerencias rápidas
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Balance General"):
        question = "Dame el balance general"
    else:
        question = None

with col2:
    if st.button("Ventas"):
        question = "¿Cuál fue el total vendido?"
    else:
        question = None if question is None else question

with col3:
    if st.button("Gastos"):
        question = "Muéstrame los gastos por categoría"
    else:
        question = None if question is None else question

# Input de pregunta custom
question = st.text_input(
    "O escribe tu pregunta aquí",
    value=question if question else "",
    placeholder="Escribe tu pregunta contable aquí...",
    label_visibility="collapsed"
)

if question:
    # Mostrar proceso paso a paso
    st.divider()
    st.markdown("### Procesando tu pregunta...")
    
    # Crear placeholders para cada paso
    step1_placeholder = st.empty()
    step2_placeholder = st.empty()
    step3_placeholder = st.empty()
    step4_placeholder = st.empty()
    step5_placeholder = st.empty()
    response_placeholder = st.empty()
    
    try:
        log_info(f"Pregunta recibida: {question}")
        # Procesar
        with st.spinner("Consultando IA..."):
            answer = answer_question(question)
        
        st.divider()
        
        # Mostrar respuesta con formato
        st.markdown("### Respuesta Completa")
        st.markdown(answer)
        
        # Opción para descargar
        st.download_button(
            label="Descargar respuesta",
            data=answer,
            file_name="respuesta_contable.txt",
            mime="text/plain"
        )
        
        # Opción para nuevas preguntas
        st.info("Puedes hacer más preguntas para profundizar en el análisis")
        
    except Exception as e:
        log_error(f"Error procesando pregunta: {e}")
        st.error(f"Error: {str(e)}")
        st.error(f"Detalles: {type(e).__name__}: {str(e)}")

st.caption("Tus datos se almacenan localmente | Potenciado por LangChain + Gemini")