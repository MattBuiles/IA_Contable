from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool
from langchain.agents import create_agent
from typing import Optional
import json

from src.ai.client import get_chat_model, get_embeddings
from src.ai.vectorstore import get_retriever
from src.ai.accounting_tasks import AVAILABLE_TASKS
from src.db.database import DB_PATH, get_connection
from src.utils.logger import log_info



# HERRAMIENTAS DEL AGENTE

@tool
def check_database_status() -> dict:
    """
    Verifica el estado actual de la base de datos contable.
    Retorna cantidad de documentos, transacciones, asientos y cuentas.
    Úsala SIEMPRE PRIMERO para saber si hay datos disponibles.
    """
    try:
        log_info("🔍 Tool: check_database_status")
        with get_connection() as conn:
            cursor = conn.cursor()
            
            tx_count = cursor.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            je_count = cursor.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
            doc_count = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            acc_count = cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            
            status = {
                "documents": doc_count,
                "transactions": tx_count,
                "journal_entries": je_count,
                "accounts": acc_count,
                "is_empty": tx_count == 0 and je_count == 0,
                "has_data": tx_count > 0 or je_count > 0
            }
            
            log_info(f"✅ Estado: {status}")
            return status
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e), "is_empty": True, "has_data": False}


@tool
def generate_balance_sheet(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Genera el Balance General (Estado de Situación Financiera).
    Muestra Activos, Pasivos y Patrimonio con la ecuación contable validada.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: generate_balance_sheet (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["balance_sheet"](start_date, end_date)
        log_info(f"✅ Balance generado: {len(result.get('assets', []))} activos")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def generate_income_statement(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Genera el Estado de Resultados (P&L).
    Muestra Ingresos, Costos, Gastos y Utilidad Neta.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: generate_income_statement (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["income_statement"](start_date, end_date)
        log_info(f"✅ Estado generado: Utilidad {result.get('net_income', 0)}")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def get_sales_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Obtiene resumen detallado de ventas.
    Incluye total, IVA, productos más vendidos, clientes top.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: get_sales_summary (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["sales_summary"](start_date, end_date)
        log_info(f"✅ Ventas: {result.get('total_sales', 0)}")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def get_purchase_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Obtiene resumen detallado de compras.
    Incluye total, IVA, proveedores principales.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: get_purchase_summary (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["purchase_summary"](start_date, end_date)
        log_info(f"✅ Compras: {result.get('total_purchases', 0)}")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def get_expenses_by_category(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Analiza gastos organizados por categoría.
    Útil para control presupuestario y análisis de costos.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: get_expenses_by_category (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["expenses_by_category"](start_date, end_date)
        log_info(f"✅ Gastos: {len(result.get('categories', []))} categorías")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def get_cash_flow(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Genera análisis de Flujo de Caja.
    Muestra entradas, salidas y saldo neto de efectivo.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: get_cash_flow (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["cash_flow"](start_date, end_date)
        log_info(f"✅ Flujo: {result.get('net_cash_flow', 0)}")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def get_tax_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Calcula resumen de impuestos (IVA).
    Muestra IVA cobrado, pagado y saldo a favor/contra.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: get_tax_summary (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["tax_summary"](start_date, end_date)
        log_info(f"✅ IVA: {result.get('net_vat', 0)}")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def calculate_profit_margin(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    Calcula márgenes de rentabilidad.
    Incluye margen bruto, operacional y neto.
    
    Args:
        start_date: Fecha inicio (YYYY-MM-DD), opcional
        end_date: Fecha fin (YYYY-MM-DD), opcional
    """
    try:
        log_info(f"🔍 Tool: calculate_profit_margin (fechas: {start_date} - {end_date})")
        result = AVAILABLE_TASKS["profit_margin"](start_date, end_date)
        log_info(f"✅ Margen neto: {result.get('net_margin', 0)}%")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def analyze_aging(account_type: str = "receivable") -> dict:
    """
    Analiza antigüedad de cuentas por cobrar o pagar.
    Útil para gestión de cobranzas y pagos.
    
    Args:
        account_type: "receivable" (por cobrar) o "payable" (por pagar)
    """
    try:
        log_info(f"🔍 Tool: analyze_aging (tipo: {account_type})")
        result = AVAILABLE_TASKS["aging_analysis"](account_type)
        log_info(f"✅ Antigüedad: {len(result.get('aging_buckets', []))} rangos")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def analyze_trends(metric: str, period: str = "monthly") -> dict:
    """
    Analiza tendencias temporales de métricas.
    
    Args:
        metric: "sales", "expenses", "profit", etc.
        period: "daily", "weekly", "monthly", "yearly"
    """
    try:
        log_info(f"🔍 Tool: analyze_trends (métrica: {metric}, período: {period})")
        result = AVAILABLE_TASKS["trend_analysis"](metric, period)
        log_info(f"✅ Tendencia: {len(result.get('data_points', []))} puntos")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return {"error": str(e)}


@tool
def run_custom_sql(query: str) -> str:
    """
    Ejecuta una consulta SQL personalizada en la base de datos contable.
    ÚSALA SOLO si las otras herramientas no son suficientes.
    
    Tablas disponibles:
    - transactions: transacciones individuales
    - journal_entries: asientos contables
    - accounts: plan de cuentas
    - documents: documentos fuente
    
    Args:
        query: Consulta SQL (SELECT únicamente, no modificaciones)
    """
    try:
        log_info(f"🔍 Tool: run_custom_sql")
        log_info(f"Query: {query}")
        
        # Validación básica de seguridad
        query_lower = query.lower().strip()
        if not query_lower.startswith("select"):
            return "❌ Error: Solo se permiten consultas SELECT"
        
        forbidden = ["drop", "delete", "update", "insert", "alter", "create"]
        if any(word in query_lower for word in forbidden):
            return "❌ Error: Operaciones de modificación no permitidas"
        
        db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")
        result = db.run(query)
        log_info(f"✅ Query ejecutada: {len(str(result))} chars")
        return result
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return f"❌ Error ejecutando SQL: {str(e)}"


@tool
def search_documents(query: str) -> str:
    """
    Busca en documentos contables cargados usando búsqueda semántica.
    Útil para encontrar políticas, normativas o información contextual.
    
    Args:
        query: Texto a buscar (ej: "política de depreciación", "retención IVA")
    """
    try:
        log_info(f"🔍 Tool: search_documents (query: {query})")
        embedder = get_embeddings()
        retriever = get_retriever(embedder)
        docs = retriever.invoke(query)
        
        if not docs:
            log_info("⚠️ No se encontraron documentos")
            return "No se encontraron documentos relevantes."
        
        # Combinar los 3 documentos más relevantes
        content = "\n\n---\n\n".join([d.page_content for d in docs[:3]])
        log_info(f"✅ Encontrados {len(docs)} documentos")
        return content
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return f"Error buscando documentos: {str(e)}"


# ============================================================================
# AGENTE CONTABLE
# ============================================================================

def create_accounting_agent():
    """Crea el agente contable con todas las herramientas."""
    
    llm = get_chat_model()
    
    # Lista de herramientas disponibles
    tools = [
        check_database_status,
        generate_balance_sheet,
        generate_income_statement,
        get_sales_summary,
        get_purchase_summary,
        get_expenses_by_category,
        get_cash_flow,
        get_tax_summary,
        calculate_profit_margin,
        analyze_aging,
        analyze_trends,
        run_custom_sql,
        search_documents
    ]
    
    # Prompt del sistema para el agente
    system_prompt = """Eres un experto contador y asesor financiero con 20+ años de experiencia.

Tu misión es responder preguntas contables usando las herramientas disponibles de forma inteligente.

PROTOCOLO OBLIGATORIO:
1. **SIEMPRE** usa check_database_status() PRIMERO
   - Si is_empty=true, informa al usuario que debe cargar datos
   - Si has_data=true, continúa con el análisis

2. Usa las herramientas específicas según la pregunta:
   - Balance/Situación financiera → generate_balance_sheet()
   - Estado de resultados/P&L → generate_income_statement()
   - Ventas → get_sales_summary()
   - Compras → get_purchase_summary()
   - Gastos → get_expenses_by_category()
   - Flujo de caja → get_cash_flow()
   - Impuestos/IVA → get_tax_summary()
   - Rentabilidad → calculate_profit_margin()
   - Antigüedad → analyze_aging()
   - Tendencias → analyze_trends()
   - SQL personalizado → run_custom_sql() (último recurso)
   - Documentos/Políticas → search_documents()

3. Puedes usar MÚLTIPLES herramientas en una sola pregunta
   Ejemplo: "¿Cuál es mi situación financiera?"
   → check_database_status() + generate_balance_sheet() + generate_income_statement()

4. FORMATO DE RESPUESTA:
   - Respuesta directa y clara
   - Datos precisos con COP ($)
   - Interpretación profesional
   - Recomendaciones accionables
   - Sin repetir información de las herramientas

5. SI LA BD ESTÁ VACÍA:
   - Explica que necesita cargar datos
   - Menciona formatos aceptados (Excel, PDF)
   - Da ejemplo de estructura de datos
   - No uses herramientas de análisis

IMPORTANTE:
- Moneda: COP (pesos colombianos)
- Fechas: formato YYYY-MM-DD
- Sé preciso y profesional
- Valida datos antes de interpretarlos
- Sugiere acciones concretas

Fecha actual: 2025-11-13"""

    # Crear el agente usando la nueva API de LangChain 1.0.5
    agent_executor = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        debug=True
    )
    
    return agent_executor


def answer_question(question: str) -> str:
    """
    Responde preguntas contables usando el agente con tool calling.
    
    El agente decidirá automáticamente qué herramientas usar y en qué orden.
    """
    log_info(f"=== NUEVA PREGUNTA (AGENTE) ===")
    log_info(f"Pregunta: {question}")
    
    try:
        agent_executor = create_accounting_agent()
        
        # Ejecutar agente - create_agent devuelve un CompiledStateGraph
        # que se invoca con un mensaje directamente
        result = agent_executor.invoke({"messages": [{"role": "user", "content": question}]})
        
        # Extraer la respuesta del estado final
        if "messages" in result and len(result["messages"]) > 0:
            last_message = result["messages"][-1]
            # last_message es un objeto AIMessage, no un dict
            if hasattr(last_message, 'content'):
                # Si content es una lista de objetos (como en Gemini con extras)
                if isinstance(last_message.content, list):
                    # Buscar el texto en la lista
                    text_parts = [part.get('text', '') if isinstance(part, dict) else str(part) 
                                 for part in last_message.content]
                    response = '\n'.join(text_parts)
                else:
                    response = last_message.content
            else:
                response = str(last_message)
        else:
            response = str(result)
        
        log_info(f"=== RESPUESTA GENERADA ===")
        return response
        
    except Exception as e:
        log_info(f"❌ Error en agente: {e}")
        import traceback
        log_info(traceback.format_exc())
        return f"""❌ Error procesando la pregunta:

{str(e)}

Por favor, intenta reformular tu pregunta o contacta soporte."""