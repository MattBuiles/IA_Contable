"""
Agente Contable v3.0 - Módulo de Inicialización
================================================
Punto de entrada unificado para el agente v3.0 con LangGraph.

Este módulo facilita el uso del agente v3 exportando todas las funciones
y clases necesarias en un solo lugar.

Uso:
    from src.ai.agent_v3_main import answer_question_v3, create_accounting_agent_v3

Autor: Sistema IA Contable
Fecha: Noviembre 2025
Versión: 3.0.0
"""

# ============================================================================
# IMPORTS PRINCIPALES
# ============================================================================

# Función principal de respuesta
from src.ai.agent_v3 import (
    answer_question_v3,
    answer_question,
    create_accounting_agent_v3,
    visualize_graph
)

# Herramientas
from src.ai.tools_v3 import (
    query_sql_database,
    search_documents,
    analyze_file,
    get_all_tools,
    get_tools_description
)

# Estados y schemas
from src.ai.state_v3 import (
    AgentState,
    create_initial_state,
    update_state_with_result,
    finalize_state,
    get_state_summary,
    ExecutionPlan,
    Reflection,
    PlanStep,
    ExecutionResult
)

# Prompts y configuración
from src.ai.prompts_v3 import (
    get_planner_system_prompt,
    get_sql_executor_prompt,
    get_reflector_prompt,
    get_agent_config,
    get_database_schema,
    format_currency,
    get_current_date_info
)


# ============================================================================
# EXPORTS SIMPLIFICADOS
# ============================================================================

__all__ = [
    # Funciones principales
    "answer_question_v3",
    "answer_question",
    "create_accounting_agent_v3",
    "visualize_graph",
    
    # Herramientas
    "query_sql_database",
    "search_documents",
    "analyze_file",
    "get_all_tools",
    
    # Estados
    "AgentState",
    "create_initial_state",
    "ExecutionPlan",
    "Reflection",
    
    # Utilidades
    "get_agent_config",
    "get_database_schema",
    "format_currency",
]


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

def quick_ask(question: str) -> str:
    """
    Función de conveniencia para hacer una pregunta rápida.
    
    Args:
        question: Pregunta del usuario
        
    Returns:
        Respuesta del agente v3.0
        
    Example:
        >>> from src.ai.agent_v3_main import quick_ask
        >>> answer = quick_ask("¿Cuál es mi balance general?")
        >>> print(answer)
    """
    return answer_question_v3(question, thread_id="quick")


def ask_with_context(question: str, thread_id: str) -> str:
    """
    Hace una pregunta manteniendo el contexto de conversación.
    
    Args:
        question: Pregunta del usuario
        thread_id: ID único del hilo de conversación
        
    Returns:
        Respuesta del agente v3.0
        
    Example:
        >>> from src.ai.agent_v3_main import ask_with_context
        >>> # Primera pregunta
        >>> answer1 = ask_with_context("¿Cuántas facturas tengo?", "sesion_123")
        >>> # Segunda pregunta en el mismo contexto
        >>> answer2 = ask_with_context("¿Y cuánto suman en total?", "sesion_123")
    """
    return answer_question_v3(question, thread_id=thread_id)


def get_agent_info() -> dict:
    """
    Devuelve información sobre el agente v3.0.
    
    Returns:
        Diccionario con información del agente
    """
    config = get_agent_config()
    
    return {
        "version": "3.0.0",
        "name": "Agente Contable Autónomo v3.0",
        "architecture": "LangGraph StateGraph Multi-Agent",
        "model": config.get("model_name", "gemini-2.0-flash-exp"),
        "max_iterations": config.get("max_iterations", 15),
        "features": [
            "StateGraph con 4 nodos especializados",
            "Planificación estratégica automática",
            "Ejecución iterativa con auto-corrección",
            "Reflexión sobre calidad de resultados",
            "Síntesis profesional multi-fuente",
            "Checkpointing persistente (MemorySaver)",
            "Tool calling nativo",
            "Soporte para SQL, documentos y archivos"
        ],
        "nodes": ["planner", "executor", "reflector", "synthesis"],
        "tools": ["query_sql_database", "search_documents", "analyze_file"],
        "checkpointing": config.get("enable_checkpointing", False),
        "checkpoint_type": "MemorySaver (RAM)"
    }


def test_agent(simple_question: str = "¿Cuántas transacciones hay en la BD?") -> dict:
    """
    Ejecuta un test rápido del agente v3.0.
    
    Args:
        simple_question: Pregunta de prueba
        
    Returns:
        Diccionario con resultados del test
    """
    import time
    
    start = time.time()
    
    try:
        answer = answer_question_v3(simple_question, thread_id="test")
        duration = time.time() - start
        
        return {
            "success": True,
            "question": simple_question,
            "answer": answer,
            "duration_seconds": round(duration, 2),
            "answer_length": len(answer),
            "agent_info": get_agent_info()
        }
    
    except Exception as e:
        duration = time.time() - start
        
        return {
            "success": False,
            "question": simple_question,
            "error": str(e),
            "duration_seconds": round(duration, 2),
            "agent_info": get_agent_info()
        }


# ============================================================================
# DOCUMENTACIÓN Y EJEMPLOS
# ============================================================================

def print_usage_examples():
    """
    Imprime ejemplos de uso del agente v3.0.
    """
    examples = """
═══════════════════════════════════════════════════════════════════════════
AGENTE CONTABLE V3.0 - EJEMPLOS DE USO
═══════════════════════════════════════════════════════════════════════════

1. USO BÁSICO (pregunta simple):
   
   from src.ai.agent_v3_main import quick_ask
   
   answer = quick_ask("¿Cuántas facturas de venta tengo este mes?")
   print(answer)

───────────────────────────────────────────────────────────────────────────

2. USO CON CONTEXTO (conversación):
   
   from src.ai.agent_v3_main import ask_with_context
   
   # Primera pregunta
   answer1 = ask_with_context(
       "¿Cuál es mi balance general al 30 de noviembre?",
       thread_id="sesion_usuario_123"
   )
   
   # Segunda pregunta en el mismo contexto
   answer2 = ask_with_context(
       "¿Y cómo ha evolucionado comparado con el mes anterior?",
       thread_id="sesion_usuario_123"
   )

───────────────────────────────────────────────────────────────────────────

3. USO DIRECTO DEL AGENTE:
   
   from src.ai.agent_v3_main import answer_question_v3
   
   question = "Análisis completo de IVA 2025 y normativa aplicable"
   answer = answer_question_v3(question, thread_id="analisis_iva")
   print(answer)

───────────────────────────────────────────────────────────────────────────

4. CREAR Y USAR EL AGENTE MANUALMENTE:
   
   from src.ai.agent_v3_main import create_accounting_agent_v3, create_initial_state
   from langchain_core.runnables import RunnableConfig
   
   # Crear agente
   agent = create_accounting_agent_v3()
   
   # Crear estado inicial
   state = create_initial_state("¿Cuál es mi flujo de caja?", "thread_1")
   
   # Configurar
   config = RunnableConfig(configurable={"thread_id": "thread_1"})
   
   # Invocar
   final_state = agent.invoke(state, config)
   answer = final_state.get("final_answer")

───────────────────────────────────────────────────────────────────────────

5. USAR HERRAMIENTAS INDIVIDUALES:
   
   from src.ai.agent_v3_main import query_sql_database, search_documents
   import json
   
   # Ejecutar SQL directamente
   result = query_sql_database.invoke({
       "sql_query": "SELECT COUNT(*) as total FROM transactions"
   })
   data = json.loads(result)
   print(data)
   
   # Buscar en documentos
   docs = search_documents.invoke({
       "query": "retención en la fuente",
       "max_results": 3
   })
   print(docs)

───────────────────────────────────────────────────────────────────────────

6. OBTENER INFORMACIÓN DEL AGENTE:
   
   from src.ai.agent_v3_main import get_agent_info
   
   info = get_agent_info()
   print(f"Versión: {info['version']}")
   print(f"Arquitectura: {info['architecture']}")
   print(f"Nodos: {', '.join(info['nodes'])}")
   print(f"Herramientas: {', '.join(info['tools'])}")

───────────────────────────────────────────────────────────────────────────

7. VISUALIZAR EL GRAFO:
   
   from src.ai.agent_v3_main import visualize_graph
   
   graph_ascii = visualize_graph()
   # Muestra el flujo: planner → executor → reflector → synthesis

───────────────────────────────────────────────────────────────────────────

8. TEST RÁPIDO:
   
   from src.ai.agent_v3_main import test_agent
   
   result = test_agent("¿Cuántas cuentas contables tengo?")
   
   if result["success"]:
       print(f"✅ Test exitoso en {result['duration_seconds']}s")
       print(f"Respuesta: {result['answer'][:200]}...")
   else:
       print(f"❌ Test falló: {result['error']}")

═══════════════════════════════════════════════════════════════════════════

PREGUNTAS EJEMPLO PARA PROBAR:

• Simples:
  - "¿Cuántas facturas de venta tengo en noviembre 2025?"
  - "¿Cuál es el total de gastos del mes actual?"
  - "¿Qué dice la política de depreciación?"

• Medias:
  - "¿Cuál es mi posición de IVA este año y qué normativa aplica?"
  - "Balance general al 30/11/2025 con ecuación contable verificada"
  - "Clientes con mora mayor a 60 días y montos adeudados"

• Complejas:
  - "Análisis financiero completo Q3 2025 con comparación contra presupuesto"
  - "Flujo de caja del último año, tendencias y recomendaciones basadas en políticas"
  - "Estado de resultados + análisis de variaciones + búsqueda de oportunidades fiscales"

═══════════════════════════════════════════════════════════════════════════
"""
    
    print(examples)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("🚀 Agente Contable v3.0 - Módulo de Inicialización")
    print("=" * 80)
    
    # Mostrar info del agente
    info = get_agent_info()
    print(f"\n📋 Información del Agente:")
    print(f"   Versión: {info['version']}")
    print(f"   Nombre: {info['name']}")
    print(f"   Arquitectura: {info['architecture']}")
    print(f"   Modelo: {info['model']}")
    print(f"   Max iteraciones: {info['max_iterations']}")
    print(f"   Nodos: {', '.join(info['nodes'])}")
    print(f"   Herramientas: {', '.join(info['tools'])}")
    print(f"   Checkpointing: {'✅ Habilitado' if info['checkpointing'] else '❌ Deshabilitado'}")
    
    # Mostrar ejemplos
    print("\n" + "=" * 80)
    print_usage_examples()
    
    # Test opcional
    print("\n" + "=" * 80)
    print("🧪 ¿Deseas ejecutar un test rápido? (s/n): ", end="")
    
    try:
        response = input().strip().lower()
        if response == 's':
            print("\n🔬 Ejecutando test...")
            result = test_agent()
            
            if result["success"]:
                print(f"\n✅ Test completado en {result['duration_seconds']}s")
                print(f"\n💬 Respuesta ({result['answer_length']} caracteres):")
                print("-" * 80)
                print(result['answer'][:500])
                if result['answer_length'] > 500:
                    print(f"\n... (+ {result['answer_length'] - 500} caracteres más)")
            else:
                print(f"\n❌ Test falló: {result['error']}")
    except:
        pass
    
    print("\n" + "=" * 80)
    print("✅ Módulo cargado correctamente")
    print("=" * 80)
