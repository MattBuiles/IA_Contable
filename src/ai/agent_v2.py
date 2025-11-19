"""
Agente Contable Autónomo v2.0 (2025)
=====================================
Arquitectura moderna basada en LangGraph + ReAct con acceso directo a SQL.
El agente genera y ejecuta sus propias queries de forma iterativa con auto-corrección.

Características:
- Una sola herramienta SQL poderosa (query_sql_database)
- Auto-corrección iterativa de queries
- Acceso completo al esquema de la base de datos
- ReAct pattern (Thought → Action → Observation → Repeat)
- Manejo inteligente de resultados grandes
- Tool calling nativo con Gemini
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
import json
import sqlite3

from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.ai.client import get_chat_model, get_embeddings
from src.ai.vectorstore import get_retriever
from src.db.database import DB_PATH, get_connection
from src.utils.logger import log_info


# ============================================================================
# INICIALIZACIÓN DE BASE DE DATOS SQL
# ============================================================================

def get_sql_database() -> SQLDatabase:
    """Obtiene la instancia de SQLDatabase con el esquema completo."""
    db_uri = f"sqlite:///{DB_PATH}"
    db = SQLDatabase.from_uri(db_uri)
    return db


def get_database_schema() -> str:
    """
    Obtiene el esquema completo de la base de datos de forma dinámica.
    Incluye todas las tablas, columnas, tipos y relaciones.
    """
    try:
        db = get_sql_database()
        schema_info = db.get_table_info()
        
        # Agregar información adicional sobre las relaciones y tipos de datos
        additional_info = """
        
RELACIONES IMPORTANTES:
- documents.id → transactions.document_id (documento fuente de cada transacción)
- transactions.id → transaction_lines.transaction_id (líneas de detalle)
- transactions.id → journal_entries.transaction_id (asientos contables)
- accounts.code → journal_entries.account_code (plan de cuentas)

TIPOS DE TRANSACCIONES (transaction_type):
- 'sales_invoice' (factura de venta)
- 'purchase_invoice' (factura de compra)
- 'expense' (gasto)
- 'income' (ingreso)
- 'payment' (pago)
- 'receipt' (cobro)

TIPOS DE CUENTAS (account_type) - ¡IMPORTANTE! Los valores están en ESPAÑOL con mayúscula inicial:
- 'Activo' (activo corriente y no corriente)
- 'Pasivo' (pasivo corriente y no corriente)
- 'Patrimonio' (capital, reservas, utilidades)
- 'Ingreso' (ventas, ingresos operacionales)
- 'Gasto' (gastos operacionales y no operacionales)
- 'Costo' (costo de ventas)

CATEGORÍAS COMUNES:
- IVA: tax_rate 0.19 (19% en Colombia)
- Moneda: COP (pesos colombianos)
- Categorías de gastos: 'payroll', 'rent', 'utilities', 'marketing', 'supplies', etc.

CAMPOS CALCULADOS ÚTILES:
- Subtotal = quantity * unit_price
- Total = subtotal + tax_amount
- Balance cuenta = SUM(credit) - SUM(debit) para pasivos/patrimonio/ingresos
- Balance cuenta = SUM(debit) - SUM(credit) para activos/gastos/costos
"""
        
        return schema_info + additional_info
        
    except Exception as e:
        log_info(f"❌ Error obteniendo esquema: {e}")
        return "Error al obtener el esquema de la base de datos."


# ============================================================================
# HERRAMIENTAS DEL AGENTE
# ============================================================================

@tool
def query_sql_database(sql_query: str) -> str:
    """
    Ejecuta una consulta SQL en la base de datos contable y devuelve resultados en formato JSON.
    
    REGLAS DE SEGURIDAD:
    - SOLO se permiten consultas SELECT, WITH (CTEs)
    - NO se permiten: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE
    - Las queries deben estar bien formadas (sintaxis SQLite)
    
    MEJORES PRÁCTICAS:
    - Usa JOIN para relacionar tablas
    - Usa GROUP BY para agregaciones
    - Usa WHERE para filtrar fechas y condiciones
    - Usa ORDER BY para ordenar resultados
    - Usa LIMIT para limitar resultados grandes (máximo 1000 filas)
    - Formatea números con ROUND(valor, 2) para montos
    
    EJEMPLOS DE QUERIES ÚTILES:
    
    1. Balance General (Activos):
    ```sql
    SELECT 
        a.code,
        a.name,
        ROUND(SUM(je.debit) - SUM(je.credit), 2) as balance
    FROM accounts a
    LEFT JOIN journal_entries je ON a.code = je.account_code
    WHERE a.account_type = 'Activo'
    GROUP BY a.code, a.name
    HAVING balance != 0
    ORDER BY a.code;
    ```
    
    2. Estado de Resultados (Ingresos y Gastos):
    ```sql
    SELECT 
        a.account_type,
        ROUND(SUM(CASE WHEN a.account_type = 'Ingreso' THEN je.credit - je.debit
                       WHEN a.account_type IN ('Gasto', 'Costo') THEN je.debit - je.credit
                       ELSE 0 END), 2) as total
    FROM accounts a
    LEFT JOIN journal_entries je ON a.code = je.account_code
    WHERE a.account_type IN ('Ingreso', 'Gasto', 'Costo')
      AND DATE(je.entry_date) BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY a.account_type;
    ```
    
    3. Ventas por Cliente:
    ```sql
    SELECT 
        counterparty as cliente,
        COUNT(*) as num_transacciones,
        ROUND(SUM(amount), 2) as total_ventas
    FROM transactions
    WHERE transaction_type = 'sales_invoice'
      AND DATE(transaction_date) BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY counterparty
    ORDER BY total_ventas DESC
    LIMIT 10;
    ```
    
    Args:
        sql_query: La consulta SQL a ejecutar (solo SELECT/WITH permitidos)
        
    Returns:
        JSON string con los resultados o mensaje de error detallado
    """
    try:
        log_info(f"🔍 Tool: query_sql_database")
        log_info(f"Query: {sql_query}")
        
        # Validación de seguridad
        query_lower = sql_query.lower().strip()
        
        # Verificar que comience con SELECT o WITH
        if not (query_lower.startswith("select") or query_lower.startswith("with")):
            error_msg = "❌ Error: Solo se permiten consultas SELECT o WITH (CTEs)"
            log_info(error_msg)
            return json.dumps({
                "error": error_msg,
                "suggestion": "Reformula tu query para usar SELECT o WITH"
            }, ensure_ascii=False)
        
        # Verificar palabras prohibidas
        forbidden_keywords = [
            "insert", "update", "delete", "drop", "alter", "create", 
            "truncate", "replace", "pragma", "attach", "detach"
        ]
        
        for keyword in forbidden_keywords:
            if f" {keyword} " in f" {query_lower} " or query_lower.startswith(keyword):
                error_msg = f"❌ Error: Operación '{keyword.upper()}' no permitida (solo lectura)"
                log_info(error_msg)
                return json.dumps({
                    "error": error_msg,
                    "suggestion": "Solo puedes usar SELECT y WITH para consultar datos"
                }, ensure_ascii=False)
        
        # Ejecutar la query
        db = get_sql_database()
        result = db.run(sql_query)
        
        # Si el resultado está vacío
        if not result or result.strip() == "":
            log_info("⚠️ Query ejecutada pero sin resultados")
            return json.dumps({
                "rows": [],
                "count": 0,
                "message": "La consulta no devolvió resultados. Verifica las condiciones WHERE o las fechas."
            }, ensure_ascii=False)
        
        # Convertir resultado a estructura JSON
        try:
            # El resultado de db.run() es un string, intentamos parsearlo
            # Si es una lista de tuplas, lo convertimos a dict
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_query)
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                # Limitar a 1000 filas para evitar tokens excesivos
                if len(rows) > 1000:
                    log_info(f"⚠️ Resultado grande: {len(rows)} filas, limitando a 1000")
                    rows = rows[:1000]
                    truncated = True
                else:
                    truncated = False
                
                # Convertir Row objects a dicts
                result_dicts = []
                for row in rows:
                    row_dict = {}
                    for idx, col in enumerate(columns):
                        row_dict[col] = row[idx]
                    result_dicts.append(row_dict)
                
                response = {
                    "rows": result_dicts,
                    "count": len(result_dicts),
                    "columns": columns,
                    "truncated": truncated
                }
                
                if truncated:
                    response["message"] = "Resultados truncados a 1000 filas. Usa LIMIT y WHERE para refinar."
                
                log_info(f"✅ Query exitosa: {len(result_dicts)} filas devueltas")
                return json.dumps(response, ensure_ascii=False, indent=2)
                
        except Exception as parse_error:
            # Si falla el parsing, devolver el resultado crudo
            log_info(f"⚠️ No se pudo parsear a JSON, devolviendo texto: {parse_error}")
            return json.dumps({
                "raw_result": result,
                "message": "Resultado en formato texto (no JSON)"
            }, ensure_ascii=False)
        
    except sqlite3.OperationalError as e:
        # Error de SQL (sintaxis, tabla no existe, etc.)
        error_msg = str(e)
        log_info(f"❌ Error SQL: {error_msg}")
        
        suggestion = ""
        if "no such table" in error_msg:
            suggestion = "Verifica que el nombre de la tabla sea correcto. Usa el esquema de la base de datos."
        elif "no such column" in error_msg:
            suggestion = "Verifica que los nombres de las columnas sean correctos."
        elif "syntax error" in error_msg:
            suggestion = "Revisa la sintaxis SQL. Usa SQLite syntax."
        
        return json.dumps({
            "error": f"Error SQL: {error_msg}",
            "suggestion": suggestion,
            "query": sql_query
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        # Error general
        error_msg = str(e)
        log_info(f"❌ Error general: {error_msg}")
        return json.dumps({
            "error": f"Error ejecutando query: {error_msg}",
            "query": sql_query
        }, ensure_ascii=False, indent=2)


@tool
def search_accounting_documents(query: str) -> str:
    """
    Busca en documentos contables, normativas y políticas usando búsqueda semántica.
    Útil para encontrar información sobre:
    - Normas NIIF y contables colombianas
    - Políticas de la empresa
    - Procedimientos contables
    - Definiciones y conceptos
    - Retenciones, impuestos, deducciones
    
    NO uses esta herramienta para datos transaccionales (esos están en la base de datos SQL).
    
    Args:
        query: Texto a buscar (ej: "política de depreciación", "retención en la fuente IVA")
        
    Returns:
        Contenido de los documentos más relevantes
    """
    try:
        log_info(f"🔍 Tool: search_accounting_documents (query: {query})")
        embedder = get_embeddings()
        retriever = get_retriever(embedder)
        docs = retriever.invoke(query)
        
        if not docs:
            log_info("⚠️ No se encontraron documentos")
            return "No se encontraron documentos relevantes para esta consulta."
        
        # Combinar los 3 documentos más relevantes
        content_parts = []
        for idx, doc in enumerate(docs[:3], 1):
            content_parts.append(f"=== Documento {idx} ===\n{doc.page_content}")
        
        content = "\n\n".join(content_parts)
        log_info(f"✅ Encontrados {len(docs)} documentos, mostrando top 3")
        return content
        
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return f"Error buscando documentos: {str(e)}"


# ============================================================================
# SISTEMA DE PROMPTS
# ============================================================================

def get_system_prompt() -> str:
    """
    Genera el prompt del sistema con fecha actual y esquema de la base de datos.
    Este prompt define completamente el comportamiento del agente.
    """
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    db_schema = get_database_schema()
    
    prompt = f"""Eres el Contador Jefe y Asesor Financiero Senior con más de 30 años de experiencia en contabilidad colombiana bajo Normas Internacionales de Información Financiera (NIIF completas) y normativa local.

FECHA ACTUAL: {current_date}
MONEDA: COP (Pesos Colombianos) - usar siempre en respuestas
ZONA HORARIA: América/Bogotá

═══════════════════════════════════════════════════════════════════════════
TU MISIÓN
═══════════════════════════════════════════════════════════════════════════

Responder preguntas contables y financieras con MÁXIMA precisión usando las herramientas disponibles.

Debes ser completamente AUTÓNOMO e ITERATIVO:
- Ejecuta múltiples consultas SQL si es necesario
- Si una query falla → analiza el error → corrige → reintenta
- Si los datos no son suficientes → haz consultas adicionales
- NUNCA te rindas hasta obtener la respuesta correcta

═══════════════════════════════════════════════════════════════════════════
ESQUEMA DE LA BASE DE DATOS
═══════════════════════════════════════════════════════════════════════════

{db_schema}

═══════════════════════════════════════════════════════════════════════════
HERRAMIENTAS DISPONIBLES
═══════════════════════════════════════════════════════════════════════════

1. **query_sql_database(sql_query)** - TU HERRAMIENTA PRINCIPAL
   - Ejecuta queries SQL (SELECT, WITH permitidos)
   - Devuelve JSON con los resultados
   - Puedes llamarla MÚLTIPLES VECES en secuencia
   - Si falla, corrige y reintenta
   
2. **search_accounting_documents(query)** - Para normativa y políticas
   - Búsqueda semántica en documentos contables
   - Usa solo para conceptos, normas, políticas
   - NO para datos transaccionales

═══════════════════════════════════════════════════════════════════════════
PROTOCOLO DE TRABAJO (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════════

PASO 1: ENTENDER la pregunta del usuario
- Identifica qué información necesitas
- Determina qué tablas y campos usar
- Planifica la secuencia de queries si es complejo

PASO 2: EJECUTAR queries SQL de forma iterativa
- Primera query: exploratoria (ej: verificar si hay datos, listar cuentas)
- Segunda query: obtener datos específicos
- Tercera query: cálculos o cruces si es necesario
- Puedes hacer hasta 5-10 queries si la pregunta es compleja

PASO 3: ANALIZAR resultados
- Si hay error SQL → lee el mensaje, corrige la query, reintenta
- Si no hay datos → verifica fechas, condiciones WHERE
- Si los datos son insuficientes → haz query adicional

PASO 4: RESPONDER al usuario
- Respuesta clara, directa y profesional
- Datos numéricos con formato COP (ej: $1,234,567)
- Interpretación financiera
- Recomendaciones accionables si aplica

═══════════════════════════════════════════════════════════════════════════
EJEMPLOS DE RESOLUCIÓN PASO A PASO
═══════════════════════════════════════════════════════════════════════════

EJEMPLO 1: "¿Cuál es mi balance general al 30 de noviembre?"

Thought: Primero verifico si hay datos en journal_entries
Action: query_sql_database
Query:
```sql
SELECT COUNT(*) as total FROM journal_entries WHERE DATE(entry_date) <= '2025-11-30';
```

Observation: {{"rows": [{{"total": 0}}]}} (no hay datos en journal_entries)

Thought: No hay datos en journal_entries, intentaré con transactions directamente
Action: query_sql_database
Query:
```sql
SELECT 
    STRFTIME('%Y-%m', transaction_date) as periodo,
    transaction_type,
    COUNT(*) as cantidad,
    ROUND(SUM(amount), 2) as total
FROM transactions
WHERE DATE(transaction_date) <= '2025-11-30'
GROUP BY periodo, transaction_type
ORDER BY periodo DESC;
```

Observation: [transacciones por periodo y tipo]

Thought: Como no tenemos journal_entries completos, daré un resumen basado en transactions
Answer: "📊 **Resumen Financiero al 30/11/2025**

Basándome en las transacciones registradas:
- Total ventas (sales_invoice): $XXX
- Estado: [interpretación]

Nota: Para un balance general completo necesitaríamos que los asientos contables (journal_entries) estén actualizados."

---

EJEMPLO 2: "¿Cuánto IVA tengo a favor o en contra este año?"

Thought: Necesito calcular IVA cobrado (ventas) vs IVA pagado (compras).
Action: query_sql_database
Query:
```sql
SELECT 
    t.transaction_type,
    ROUND(SUM(tl.tax_amount), 2) as total_iva
FROM transactions t
JOIN transaction_lines tl ON t.id = tl.transaction_id
WHERE DATE(t.transaction_date) BETWEEN '2025-01-01' AND '2025-12-31'
  AND tl.tax_rate > 0
GROUP BY t.transaction_type;
```

Observation: [IVA por tipo de transacción]

Thought: Ahora calculo el neto
Answer: [IVA cobrado - IVA pagado = saldo a favor/contra, con interpretación]

---

EJEMPLO 3: "¿Clientes con mayor mora?"

Thought: Primero verifico si hay datos de cuentas por cobrar
Action: query_sql_database
Query:
```sql
SELECT COUNT(*) as total
FROM transactions
WHERE transaction_type = 'sales_invoice' AND status = 'pending';
```

Observation: [número de ventas pendientes]

Thought: Ahora obtengo el detalle con antigüedad
Action: query_sql_database
Query:
```sql
SELECT 
    counterparty as cliente,
    transaction_date as fecha_factura,
    ROUND(amount, 2) as monto,
    JULIANDAY('2025-11-18') - JULIANDAY(transaction_date) as dias_mora
FROM transactions
WHERE transaction_type = 'sales_invoice' 
  AND status = 'pending'
ORDER BY dias_mora DESC
LIMIT 10;
```

Answer: [Top 10 clientes con mora, ordenados por días]

═══════════════════════════════════════════════════════════════════════════
REGLAS CRÍTICAS
═══════════════════════════════════════════════════════════════════════════

✅ SIEMPRE:
- Usa query_sql_database para TODOS los datos transaccionales
- Genera tus propias queries SQL (no uses funciones pre-hechas obsoletas)
- Ejecuta múltiples queries si es necesario (iteración)
- Valida que la ecuación contable cuadre: Activos = Pasivos + Patrimonio
- Formatea montos con separadores de miles: $1,234,567
- Redondea a 2 decimales
- Usa fechas en formato YYYY-MM-DD
- Da recomendaciones financieras profesionales

❌ NUNCA:
- No uses herramientas obsoletas como generate_balance_sheet, run_custom_sql, etc.
- No te rindas si una query falla (corrige y reintenta)
- No devuelvas datos crudos sin interpretación
- No hagas suposiciones sobre datos que no has consultado
- No uses PRAGMA ni comandos de modificación

═══════════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTAS
═══════════════════════════════════════════════════════════════════════════

Estructura ideal:

1. **Resumen Ejecutivo** (1-2 líneas)
2. **Datos Clave** (tablas o listas con números)
3. **Análisis Financiero** (interpretación profesional)
4. **Recomendaciones** (acciones sugeridas)

Ejemplo:
"📊 **Balance General al 30/11/2025**

**Resumen:** Tu empresa tiene una posición financiera sólida con $45M en activos.

**Datos:**
- Activos Totales: $45,234,890
- Pasivos Totales: $12,500,000
- Patrimonio: $32,734,890
✅ Ecuación contable validada

**Análisis:** El ratio de endeudamiento es 27.6%, lo cual es saludable. La mayoría de tus activos son corrientes ($30M), mostrando buena liquidez.

**Recomendaciones:**
- Considera invertir el exceso de efectivo en instrumentos de corto plazo
- Revisa las cuentas por cobrar mayores a 60 días"

═══════════════════════════════════════════════════════════════════════════

¡Ahora estás listo para responder con máxima precisión y profesionalismo!
Recuerda: eres AUTÓNOMO, ITERATIVO y NUNCA te rindes hasta obtener la respuesta correcta.
"""
    
    return prompt


# ============================================================================
# CREACIÓN DEL AGENTE
# ============================================================================

def create_accounting_agent_v2():
    """
    Crea el agente contable autónomo v2.0 usando LangGraph + ReAct.
    
    El agente tiene:
    - Tool calling nativo con Gemini
    - Capacidad de auto-corrección iterativa
    - Acceso completo al esquema SQL
    - Memoria persistente de la conversación
    """
    log_info("=== Creando Agente Contable v2.0 (LangGraph + ReAct) ===")
    
    # Obtener el LLM con tool calling
    llm = get_chat_model()
    
    # Inyectar el system prompt en el LLM
    llm_with_system = llm.bind(system=get_system_prompt())
    
    # Herramientas disponibles
    tools = [
        query_sql_database,
        search_accounting_documents
    ]
    
    # Sistema de memoria para mantener contexto
    memory = MemorySaver()
    
    # Crear el agente ReAct
    agent_executor = create_react_agent(
        model=llm_with_system,
        tools=tools,
        checkpointer=memory  # Memoria para mantener contexto
    )
    
    log_info(f"✅ Agente creado con {len(tools)} herramientas")
    return agent_executor


# ============================================================================
# FUNCIÓN PRINCIPAL DE RESPUESTA
# ============================================================================

def answer_question_v2(question: str, thread_id: str = "default") -> str:
    """
    Responde preguntas contables usando el agente autónomo v2.0.
    
    El agente:
    - Genera sus propias queries SQL de forma iterativa
    - Se auto-corrige si hay errores
    - Ejecuta múltiples herramientas en secuencia si es necesario
    - Nunca se rinde hasta obtener la respuesta correcta
    
    Args:
        question: Pregunta del usuario
        thread_id: ID del hilo de conversación (para mantener contexto)
        
    Returns:
        Respuesta profesional del contador
    """
    log_info(f"=== NUEVA PREGUNTA (AGENTE V2.0) ===")
    log_info(f"Thread ID: {thread_id}")
    log_info(f"Pregunta: {question}")
    
    try:
        # Crear el agente
        agent = create_accounting_agent_v2()
        
        # Configuración de ejecución con memoria
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Ejecutar el agente
        # create_react_agent devuelve un CompiledStateGraph que se invoca con messages
        response = agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config=config
        )
        
        # Extraer la respuesta del último mensaje
        if "messages" in response and len(response["messages"]) > 0:
            last_message = response["messages"][-1]
            
            # Manejar diferentes formatos de mensaje
            if hasattr(last_message, 'content'):
                if isinstance(last_message.content, list):
                    # Gemini puede devolver content como lista de partes
                    text_parts = []
                    for part in last_message.content:
                        if isinstance(part, dict) and 'text' in part:
                            text_parts.append(part['text'])
                        elif isinstance(part, str):
                            text_parts.append(part)
                        else:
                            text_parts.append(str(part))
                    answer = '\n'.join(text_parts)
                else:
                    answer = last_message.content
            else:
                answer = str(last_message)
        else:
            answer = str(response)
        
        log_info(f"=== RESPUESTA GENERADA (V2.0) ===")
        log_info(f"Longitud: {len(answer)} caracteres")
        
        return answer
        
    except Exception as e:
        log_info(f"❌ Error en agente v2.0: {e}")
        import traceback
        log_info(traceback.format_exc())
        
        return f"""❌ Error procesando la pregunta:

{str(e)}

**Posibles soluciones:**
- Verifica que la base de datos contable esté inicializada
- Asegúrate de tener datos cargados en las tablas
- Reformula la pregunta de forma más específica
- Contacta soporte si el error persiste

**Detalles técnicos:** {traceback.format_exc()[:500]}"""


# ============================================================================
# FUNCIÓN DE COMPATIBILIDAD CON VERSIÓN ANTERIOR
# ============================================================================

def answer_question(question: str) -> str:
    """
    Wrapper de compatibilidad con la versión anterior.
    Redirige a answer_question_v2 con thread_id por defecto.
    """
    return answer_question_v2(question, thread_id="default")


# ============================================================================
# UTILIDADES
# ============================================================================

def check_database_health() -> Dict[str, Any]:
    """
    Verifica el estado de salud de la base de datos.
    Útil para diagnóstico y debugging.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            health = {
                "status": "healthy",
                "tables": {},
                "total_records": 0
            }
            
            tables = ["documents", "transactions", "transaction_lines", 
                     "accounts", "journal_entries"]
            
            for table in tables:
                try:
                    count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    health["tables"][table] = count
                    health["total_records"] += count
                except Exception as e:
                    health["tables"][table] = f"Error: {e}"
                    health["status"] = "degraded"
            
            return health
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    # Test rápido del agente
    print("🧪 Testing Agente Contable v2.0...")
    print("=" * 80)
    
    # Verificar salud de la BD
    health = check_database_health()
    print(f"\n📊 Estado de la BD: {health}")
    
    # Pregunta de prueba
    test_question = "¿Cuántas transacciones hay en la base de datos?"
    print(f"\n❓ Pregunta: {test_question}")
    print("-" * 80)
    
    answer = answer_question_v2(test_question)
    print(f"\n💬 Respuesta:\n{answer}")
    print("=" * 80)
