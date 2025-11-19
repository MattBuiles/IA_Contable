import streamlit as st
from pathlib import Path
from src.db.database import init_db
from src.ingestion.pipeline import ingest_excel, ingest_pdf
from src.ai.agent_v2 import answer_question_v2
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
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("📊 Balance General"):
        question = "¿Cuál es mi balance general al 30 de noviembre de 2025? Muéstrame activos, pasivos y patrimonio con detalle."
    else:
        question = None

with col2:
    if st.button("💰 Estado de Resultados"):
        question = "¿Cuál fue mi utilidad neta en 2025? Muéstrame ingresos, costos y gastos."
    else:
        question = None if question is None else question

with col3:
    if st.button("📈 Top 5 Clientes"):
        question = "¿Quiénes son mis 5 mejores clientes por volumen de ventas? ¿Cuánto representa cada uno del total?"
    else:
        question = None if question is None else question

with col4:
    if st.button("🧾 Análisis de IVA"):
        question = "¿Cuánto IVA he cobrado y cuánto he pagado en 2025? ¿Tengo saldo a favor o en contra?"
    else:
        question = None if question is None else question

# Segunda fila de sugerencias
col5, col6, col7, col8 = st.columns(4)
with col5:
    if st.button("📅 Tendencias Mensuales"):
        question = "¿Cómo han evolucionado mis ventas mes a mes durante 2025? Muéstrame un análisis de tendencia."
    else:
        question = None if question is None else question

with col6:
    if st.button("⏰ Cartera Vencida"):
        question = "¿Cuáles son las facturas de venta pendientes de pago y cuántos días de mora tienen?"
    else:
        question = None if question is None else question

with col7:
    if st.button("💧 Ratio de Liquidez"):
        question = "¿Cuál es mi ratio de liquidez corriente y qué significa para mi empresa?"
    else:
        question = None if question is None else question

with col8:
    if st.button("🔢 Total Transacciones"):
        question = "¿Cuántas transacciones hay en total en la base de datos?"
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
            answer = answer_question_v2(question, thread_id=st.session_state.get("session_id", "default"))
        
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