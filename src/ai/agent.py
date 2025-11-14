from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel
from langchain_community.utilities import SQLDatabase
import json

from src.ai.client import get_chat_model, get_embeddings
from src.ai.vectorstore import get_retriever
from src.ai.accounting_tasks import AVAILABLE_TASKS
from src.db.database import DB_PATH, get_connection
from src.utils.logger import log_info


def _understand_question(question: str, schema: str) -> dict:
    """
    Paso 1: LLM entiende la pregunta en profundidad.
    Analiza qué se solicita, qué contexto necesita, qué datos buscar.
    """
    llm = get_chat_model()
    
    understanding_prompt = ChatPromptTemplate.from_messages([
        ("system", """Eres un experto contable analizando preguntas de usuarios.
        
Tu tarea: Entender profundamente qué solicita el usuario.

Esquema disponible:
{schema}

Tareas automáticas disponibles:
- balance_sheet: Balance general (activos, pasivos, patrimonio)
- income_statement: Estado de resultados
- sales_summary: Resumen de ventas
- purchase_summary: Resumen de compras
- expenses_by_category: Gastos por categoría
- cash_flow: Flujo de caja
- aging_analysis: Antigüedad de cuentas
- tax_summary: Impuestos (IVA)
- profit_margin: Márgenes de ganancia
- trend_analysis: Análisis de tendencias

Responde en JSON con:
{{
    "intent": "descripción de qué quiere el usuario",
    "task": "nombre de tarea si aplica, o null",
    "data_needed": ["lista", "de", "datos"],
    "complexity": "simple|medium|complex",
    "requires_documents": true/false
}}"""),
        ("human", "Pregunta del usuario: {question}")
    ])
    
    chain = understanding_prompt | llm | StrOutputParser()
    response = chain.invoke({"schema": schema, "question": question})
    
    log_info(f"Entendimiento: {response}")
    
    try:
        return json.loads(response)
    except:
        return {"intent": question, "task": None, "data_needed": [], "complexity": "unknown"}


def _plan_analysis(question: str, understanding: dict, schema: str) -> dict:
    """
    Paso 2: LLM planifica cómo obtener la respuesta.
    Decide qué tareas ejecutar, qué SQL correr, qué documentos buscar.
    """
    llm = get_chat_model()
    
    planning_prompt = ChatPromptTemplate.from_messages([
        ("system", """Eres un estratega de análisis de datos contables.
        
Dado el entendimiento del usuario, planifica exactamente qué hacer.

TAREAS DISPONIBLES (usa el nombre exacto):
- balance_sheet
- income_statement
- sales_summary
- purchase_summary
- expenses_by_category
- cash_flow
- aging_analysis
- tax_summary
- profit_margin
- trend_analysis

IMPORTANTE: Si el usuario pide balance, usa "balance_sheet" (no "Generar Balance General").

Responde en JSON con:
{{
    "primary_task": "nombre EXACTO de tarea (ej: balance_sheet) o null",
    "additional_sql": "consulta SQL si es necesaria, o null",
    "search_keywords": ["palabra1", "palabra2"],
    "analysis_steps": ["paso1", "paso2"],
    "expected_metrics": ["métrica1", "métrica2"]
}}"""),
        ("human", """Usuario solicita: {question}
        
Entendimiento: {understanding}

Esquema: {schema}

Plan (usa nombres exactos de tareas):""")
    ])
    
    chain = planning_prompt | llm | StrOutputParser()
    response = chain.invoke({
        "question": question,
        "understanding": json.dumps(understanding),
        "schema": schema
    })
    
    log_info(f"Plan: {response}")
    
    try:
        return json.loads(response)
    except:
        return {"primary_task": None, "additional_sql": None}


def _execute_planned_analysis(plan: dict, understanding: dict) -> dict:
    """
    Paso 3: Ejecuta el plan (tareas, SQL, búsquedas).
    Retorna todos los datos obtenidos.
    """
    llm = get_chat_model()
    db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")
    embedder = get_embeddings()
    retriever = get_retriever(embedder)
    
    results = {
        "task_result": None,
        "sql_result": None,
        "document_context": None,
        "execution_notes": [],
        "database_status": {}
    }
    
    # PRIMERO: Verificar estado de la base de datos
    try:
        log_info("Verificando estado de la base de datos...")
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Contar datos en tablas principales
            tx_count = cursor.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            je_count = cursor.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
            doc_count = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            acc_count = cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            
            results["database_status"] = {
                "documents": doc_count,
                "transactions": tx_count,
                "journal_entries": je_count,
                "accounts": acc_count,
                "is_empty": tx_count == 0 and je_count == 0
            }
            
            log_info(f"Estado BD: {doc_count} docs, {tx_count} trans, {je_count} asientos")
            
            # Si la BD está vacía, alertar
            if results["database_status"]["is_empty"]:
                results["execution_notes"].append("⚠️ Base de datos vacía - No hay transacciones ni asientos contables")
                log_info("⚠️ ADVERTENCIA: Base de datos sin datos")
                return results  # Retornar temprano si no hay datos
            else:
                results["execution_notes"].append(f"✓ BD con datos: {tx_count} transacciones, {je_count} asientos")
                
    except Exception as e:
        results["execution_notes"].append(f"✗ Error verificando BD: {str(e)}")
        log_info(f"Error verificando BD: {e}")
    
    # Ejecutar tarea primaria
    primary_task = plan.get("primary_task")
    
    # Si el LLM inventó un nombre, intentar mapear a una tarea válida
    if primary_task and primary_task not in AVAILABLE_TASKS:
        log_info(f"Tarea '{primary_task}' no encontrada, intentando mapeo...")
        # Mapeo de nombres comunes a tareas válidas
        task_mapping = {
            "balance general": "balance_sheet",
            "generar balance general": "balance_sheet",
            "balance": "balance_sheet",
            "estado de resultados": "income_statement",
            "estado resultados": "income_statement",
            "ventas": "sales_summary",
            "resumen ventas": "sales_summary",
            "compras": "purchase_summary",
            "resumen compras": "purchase_summary",
            "gastos": "expenses_by_category",
            "flujo caja": "cash_flow",
            "impuestos": "tax_summary",
            "margen": "profit_margin",
            "tendencias": "trend_analysis"
        }
        
        # Buscar coincidencia (case-insensitive)
        for key, value in task_mapping.items():
            if key in primary_task.lower():
                primary_task = value
                log_info(f"Mapeado a: {primary_task}")
                break
    
    if primary_task and primary_task in AVAILABLE_TASKS:
        try:
            log_info(f"Ejecutando tarea: {primary_task}")
            task_func = AVAILABLE_TASKS[primary_task]
            task_data = task_func()
            results["task_result"] = task_data
            results["execution_notes"].append(f"✓ Tarea {primary_task} ejecutada")
            log_info(f"Resultado de tarea: {task_data}")
        except Exception as e:
            results["execution_notes"].append(f"✗ Error en tarea: {str(e)}")
            log_info(f"Error en tarea: {e}")
    elif primary_task:
        results["execution_notes"].append(f"⚠️ Tarea '{primary_task}' no reconocida")
        log_info(f"Tarea no reconocida: {primary_task}")
    
    # Ejecutar SQL adicional si es necesario
    if plan.get("additional_sql"):
        try:
            log_info(f"Ejecutando SQL: {plan['additional_sql']}")
            result = db.run(plan["additional_sql"])
            results["sql_result"] = result
            results["execution_notes"].append("✓ SQL adicional ejecutado")
            log_info(f"Resultado SQL: {result}")
        except Exception as e:
            results["execution_notes"].append(f"✗ Error en SQL: {str(e)}")
            log_info(f"Error SQL: {e}")
    
    # Si NO hay tarea ni SQL, hacer consulta genérica para obtener contexto
    if not results["task_result"] and not results["sql_result"]:
        try:
            log_info("No hay tarea específica, consultando resumen de BD...")
            generic_query = """
            SELECT 
                COUNT(*) as total_transacciones,
                SUM(amount) as monto_total,
                MIN(transaction_date) as fecha_inicio,
                MAX(transaction_date) as fecha_fin
            FROM transactions
            """
            generic_result = db.run(generic_query)
            results["sql_result"] = generic_result
            results["execution_notes"].append("✓ Consulta genérica ejecutada")
            log_info(f"Resultado genérico: {generic_result}")
        except Exception as e:
            results["execution_notes"].append(f"✗ Error en consulta genérica: {str(e)}")
            log_info(f"Error consulta genérica: {e}")
    
    # Buscar documentos relevantes
    search_query = " ".join(plan.get("search_keywords", []))
    if search_query:
        try:
            log_info(f"Buscando documentos: {search_query}")
            docs = retriever.invoke(search_query)
            if docs:
                results["document_context"] = "\n".join([d.page_content for d in docs[:3]])
                results["execution_notes"].append(f"✓ {len(docs)} documentos encontrados")
            else:
                results["execution_notes"].append("⚠️ No se encontraron documentos relevantes")
        except Exception as e:
            results["execution_notes"].append(f"✗ Error en búsqueda: {str(e)}")
            log_info(f"Error búsqueda docs: {e}")
    
    log_info(f"Ejecución completada. Notas: {results['execution_notes']}")
    return results


def _analyze_results(question: str, results: dict) -> str:
    """
    Paso 4: LLM analiza los resultados obtenidos.
    Extrae insights, identifica patrones, valida datos.
    """
    llm = get_chat_model()
    
    # Si la BD está vacía, generar análisis especial
    if results.get("database_status", {}).get("is_empty"):
        return """
ANÁLISIS: Base de datos vacía

La base de datos no contiene transacciones ni asientos contables procesados.
Esto significa que no se han cargado documentos (Excel o PDF) aún.

Estado actual:
- Documentos: 0
- Transacciones: 0  
- Asientos contables: 0

Para poder responder preguntas contables, primero debes:
1. Cargar un archivo Excel con transacciones
2. O subir facturas en PDF

Una vez cargados, podré analizar:
- Balance general
- Estado de resultados
- Flujo de caja
- Resúmenes de ventas/compras
- Y mucho más
"""
    
    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", """Eres un analista financiero experto.
        
Analiza los datos contables obtenidos y extrae insights:
- Valida si los datos tienen sentido
- Identifica patrones y tendencias
- Destaca valores anormales
- Proporciona contexto

Sé preciso, profesional y conciso.
Usa la moneda COP para valores."""),
        ("human", """Pregunta: {question}

DATOS OBTENIDOS:
{results}

Análisis:""")
    ])
    
    chain = analysis_prompt | llm | StrOutputParser()
    analysis = chain.invoke({
        "question": question,
        "results": json.dumps(results, ensure_ascii=False, indent=2, default=str)
    })
    
    return analysis


def _synthesize_response(question: str, analysis: str, results: dict) -> str:
    """
    Paso 5: LLM sintetiza la respuesta final.
    Combina análisis, datos y recomendaciones.
    """
    llm = get_chat_model()
    
    # Si la BD está vacía, respuesta directa sin LLM
    if results.get("database_status", {}).get("is_empty"):
        return """## 📊 Sistema Contable - Primera Configuración

Hola! Veo que aún no has cargado datos contables en el sistema.

### ⚠️ Estado Actual
- **Base de datos:** Vacía (0 transacciones)
- **Documentos:** Ninguno cargado
- **Asientos contables:** No generados aún

### 🚀 Pasos para Comenzar

**1. Prepara tus datos:**
   - **Excel:** Columnas recomendadas: Fecha, Factura, Cliente/Proveedor, Producto, Cantidad, Precio, Subtotal, IVA, Total
   - **PDF:** Facturas, extractos bancarios, o cualquier documento contable

**2. Sube el archivo:**
   - Ve al panel izquierdo (**Cargar Documentos**)
   - Click en "Selecciona un archivo"
   - Elige tu Excel o PDF
   - Espera la confirmación ✅

**3. Haz preguntas:**
   - "¿Cuál es mi balance general?"
   - "¿Cuánto vendí este mes?"
   - "Muéstrame un resumen de gastos"

### 📋 Ejemplo de Excel

Si quieres probar, crea un Excel con estas columnas:

| Fecha | Factura | Cliente | Producto | Cantidad | Precio | Subtotal | IVA | Total |
|-------|---------|---------|----------|----------|--------|----------|-----|-------|
| 2025-01-15 | FAC-001 | Empresa A | Producto X | 10 | 50000 | 500000 | 95000 | 595000 |
| 2025-01-16 | FAC-002 | Empresa B | Servicio Y | 5 | 120000 | 600000 | 114000 | 714000 |

Guarda como `.xlsx` y súbelo.

### 💡 Una vez que subas datos, podré:
✅ Calcular tu balance general automáticamente  
✅ Generar asientos contables (doble partida)  
✅ Analizar tendencias de ventas y compras  
✅ Validar que débitos = créditos  
✅ Responder preguntas financieras complejas  

**¿Listo para comenzar? Sube tu primer archivo!** 📁
"""
    
    synthesis_prompt = ChatPromptTemplate.from_messages([
        ("system", """Eres un asesor contable con 20+ años de experiencia.

Tu respuesta debe:
✓ Responder directamente la pregunta
✓ Incluir datos precisos
✓ Explicar el contexto
✓ Dar recomendaciones accionables
✓ Ser clara y profesional
✓ Usar COP para moneda

Estructura:
1. Respuesta directa
2. Datos/Métricas principales
3. Análisis e interpretación
4. Recomendaciones
5. Próximos pasos"""),
        ("human", """Pregunta: {question}

ANÁLISIS PREVIO:
{analysis}

DATOS DETALLADOS:
{results}

RESPUESTA FINAL Y RECOMENDACIONES:""")
    ])
    
    chain = synthesis_prompt | llm | StrOutputParser()
    response = chain.invoke({
        "question": question,
        "analysis": analysis,
        "results": json.dumps(results, ensure_ascii=False, indent=2, default=str)
    })
    
    return response


def answer_question(question: str) -> str:
    """
    Responde preguntas contables con LLM como protagonista.
    
    Flujo:
    1. ENTENDER: LLM entiende la pregunta profundamente
    2. PLANIFICAR: LLM planifica qué hacer
    3. EJECUTAR: Ejecuta plan (tareas, SQL, búsquedas)
    4. ANALIZAR: LLM analiza resultados
    5. SINTETIZAR: LLM genera respuesta final
    """
    log_info(f"=== NUEVA PREGUNTA ===")
    log_info(f"Pregunta: {question}")
    
    # Obtener esquema de BD
    db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")
    schema = db.get_table_info()
    
    # PASO 1: Entender
    log_info("PASO 1: Entendiendo la pregunta...")
    understanding = _understand_question(question, schema)
    
    # PASO 2: Planificar
    log_info("PASO 2: Planificando análisis...")
    plan = _plan_analysis(question, understanding, schema)
    
    # PASO 3: Ejecutar plan
    log_info("PASO 3: Ejecutando plan...")
    results = _execute_planned_analysis(plan, understanding)
    
    # PASO 4: Analizar resultados
    log_info("PASO 4: Analizando resultados...")
    analysis = _analyze_results(question, results)
    
    # PASO 5: Sintetizar respuesta
    log_info("PASO 5: Sintetizando respuesta...")
    response = _synthesize_response(question, analysis, results)
    
    log_info(f"=== RESPUESTA GENERADA ===")
    
    return response
