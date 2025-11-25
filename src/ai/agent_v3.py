"""
Agente Contable Autónomo v3.0 (2025)
=====================================
Arquitectura avanzada multi-agente basada en LangGraph StateGraph.

Características principales:
- StateGraph con nodos especializados (planner, executor, reflector, synthesis)
- Orquestación multi-agente para tareas complejas
- Auto-corrección iterativa con reflexión
- Checkpoint persistente con SQLite
- Tool calling nativo con Gemini 2.0
- Soporte para SQL, búsqueda semántica y análisis de archivos

Autor: Sistema IA Contable
Fecha: Noviembre 2025
Versión: 3.0.0
"""

import json
from typing import Dict, Any, List, Literal, Optional
from datetime import datetime
import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.ai.client import get_chat_model
from src.ai.tools_v3 import get_all_tools, query_sql_database, search_documents, analyze_file
from src.ai.prompts_v3 import (
    get_planner_system_prompt,
    get_sql_executor_prompt,
    get_reflector_prompt,
    get_agent_config
)
from src.ai.state_v3 import (
    AgentState,
    create_initial_state,
    update_state_with_result,
    finalize_state,
    get_state_summary,
    ExecutionPlan,
    Reflection
)
from src.utils.logger import log_info


# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

AGENT_CONFIG = get_agent_config()
MAX_ITERATIONS = AGENT_CONFIG["max_iterations"]
CHECKPOINT_DB_PATH = AGENT_CONFIG["checkpoint_db"]


# ============================================================================
# NODO 1: PLANNER (Planificación estratégica)
# ============================================================================

def planner_node(state: AgentState) -> AgentState:
    """
    Nodo PLANNER: Analiza la pregunta y crea un plan de acción.
    
    Este nodo decide:
    - Complejidad de la pregunta (simple, media, compleja)
    - Enfoque (single-agent o multi-agent)
    - Pasos específicos a ejecutar
    - Herramientas a usar en cada paso
    """
    log_info("=" * 80)
    log_info("🎯 [PLANNER NODE] Creando plan de acción...")
    log_info(f"Pregunta: {state['original_question']}")
    
    try:
        # Obtener LLM para planificación
        llm = get_chat_model()
        
        # Prompt del planner
        planner_prompt = get_planner_system_prompt()
        
        # Construir mensaje para el LLM
        messages = [
            SystemMessage(content=planner_prompt),
            HumanMessage(content=f"""Analiza esta pregunta y crea un plan de acción detallado:

PREGUNTA DEL USUARIO:
{state['original_question']}

INSTRUCCIONES:
1. Clasifica la complejidad (simple, medium, complex)
2. Decide el enfoque (single_agent o multi_agent)
3. Crea una lista de pasos específicos
4. Asigna herramientas y agentes a cada paso
5. Devuelve el plan en formato JSON válido

FORMATO REQUERIDO:
{{
  "complexity": "simple|medium|complex",
  "approach": "single_agent|multi_agent",
  "steps": [
    {{
      "step": 1,
      "action": "query_sql_database|search_documents|analyze_file",
      "description": "Descripción específica del paso",
      "expected_output": "Qué esperas obtener",
      "agent": "sql_agent|document_agent|file_agent|synthesis_agent"
    }}
  ],
  "final_synthesis": "Cómo sintetizar los resultados"
}}
""")
        ]
        
        # Invocar el LLM
        response = llm.invoke(messages)
        
        # Extraer contenido de la respuesta
        if hasattr(response, 'content'):
            if isinstance(response.content, list):
                # Gemini puede devolver lista de partes
                content_parts = []
                for part in response.content:
                    if isinstance(part, dict) and 'text' in part:
                        content_parts.append(part['text'])
                    elif isinstance(part, str):
                        content_parts.append(part)
                content = '\n'.join(content_parts)
            else:
                content = response.content
        else:
            content = str(response)
        
        # Extraer JSON del contenido (puede venir con markdown)
        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parsear el plan
        plan_dict = json.loads(content)
        
        # Validar plan
        if "complexity" not in plan_dict or "steps" not in plan_dict:
            raise ValueError("Plan inválido: falta complexity o steps")
        
        # Guardar plan en el estado
        state["plan"] = plan_dict
        
        log_info(f"✅ Plan creado:")
        log_info(f"  Complejidad: {plan_dict.get('complexity', 'N/A')}")
        log_info(f"  Enfoque: {plan_dict.get('approach', 'N/A')}")
        log_info(f"  Total pasos: {len(plan_dict.get('steps', []))}")
        
        for step in plan_dict.get('steps', [])[:3]:  # Mostrar solo los primeros 3
            log_info(f"  Step {step['step']}: {step['action']} - {step['description'][:60]}...")
        
        return state
    
    except Exception as e:
        log_info(f"❌ Error en planner: {e}")
        
        # Plan de fallback simple
        fallback_plan = {
            "complexity": "simple",
            "approach": "single_agent",
            "steps": [
                {
                    "step": 1,
                    "action": "query_sql_database",
                    "description": "Intentar resolver con una consulta SQL exploratoria",
                    "expected_output": "Datos relevantes de la base de datos",
                    "agent": "sql_agent"
                }
            ],
            "final_synthesis": "Presentar los datos obtenidos al usuario"
        }
        
        state["plan"] = fallback_plan
        log_info("⚠️ Usando plan de fallback simple")
        
        return state


# ============================================================================
# NODO 2: EXECUTOR (Ejecución de herramientas)
# ============================================================================

def executor_node(state: AgentState) -> AgentState:
    """
    Nodo EXECUTOR: Ejecuta el siguiente paso del plan.
    
    Este nodo:
    - Toma el siguiente paso del plan
    - Ejecuta la herramienta correspondiente
    - Guarda los resultados en el estado
    - Maneja errores y reintentos
    """
    log_info("=" * 80)
    log_info("⚙️ [EXECUTOR NODE] Ejecutando paso del plan...")
    
    try:
        plan = state.get("plan")
        if not plan or "steps" not in plan:
            log_info("❌ No hay plan disponible")
            return state
        
        current_step_idx = state["current_step"]
        steps = plan["steps"]
        
        # Verificar si hay más pasos
        if current_step_idx >= len(steps):
            log_info("✅ Todos los pasos completados")
            return state
        
        # Obtener el paso actual
        step = steps[current_step_idx]
        action = step["action"]
        description = step["description"]
        
        log_info(f"📌 Ejecutando Step {step['step']}: {action}")
        log_info(f"   Descripción: {description}")
        
        start_time = time.time()
        
        # ===== EJECUTAR SEGÚN EL TIPO DE ACCIÓN =====
        
        if action == "query_sql_database":
            result = _execute_sql_action(state, step)
        
        elif action == "search_documents":
            result = _execute_document_search(state, step)
        
        elif action == "analyze_file":
            result = _execute_file_analysis(state, step)
        
        elif action == "synthesis":
            result = _execute_synthesis(state, step)
        
        else:
            log_info(f"⚠️ Acción desconocida: {action}")
            result = {
                "success": False,
                "error": f"Acción no soportada: {action}"
            }
        
        duration = time.time() - start_time
        
        # Actualizar estado con el resultado
        state = update_state_with_result(
            state=state,
            step=step["step"],
            action=action,
            success=result.get("success", False),
            result=result,
            error=result.get("error"),
            duration=duration
        )
        
        log_info(f"✅ Step {step['step']} completado en {duration:.2f}s")
        
        # Incrementar iteración
        state["iteration_count"] += 1
        
        return state
    
    except Exception as e:
        log_info(f"❌ Error en executor: {e}")
        
        # Registrar error en el estado
        if state.get("plan") and state["plan"].get("steps"):
            current_step = state["plan"]["steps"][state["current_step"]]
            state = update_state_with_result(
                state=state,
                step=current_step["step"],
                action=current_step["action"],
                success=False,
                error=str(e),
                duration=0.0
            )
        
        return state


def _execute_sql_action(state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta una acción SQL usando el agente SQL."""
    log_info("  🗄️ Ejecutando consulta SQL...")
    
    try:
        # Obtener LLM para generar la query
        llm = get_chat_model()
        sql_prompt = get_sql_executor_prompt()
        
        # Contexto de resultados previos
        previous_results = "\n\n".join([
            f"Step {r['step']} ({r['action']}): {json.dumps(r['result'], ensure_ascii=False)[:500]}..."
            for r in state["execution_results"][-3:]  # Últimos 3 resultados
        ]) if state["execution_results"] else "Sin resultados previos"
        
        messages = [
            SystemMessage(content=sql_prompt),
            HumanMessage(content=f"""Genera y ejecuta una consulta SQL para este paso:

OBJETIVO: {step['description']}
SALIDA ESPERADA: {step['expected_output']}

RESULTADOS PREVIOS:
{previous_results}

INSTRUCCIONES:
1. Genera la query SQL óptima
2. Usa query_sql_database() para ejecutarla
3. Si falla, analiza el error y corrige
4. Puedes hacer hasta 3 intentos

Genera la query SQL ahora.
""")
        ]
        
        # Configurar LLM con la tool
        llm_with_tools = llm.bind_tools([query_sql_database])
        
        # Ejecutar con retry
        max_retries = 3
        for attempt in range(max_retries):
            log_info(f"  Intento {attempt + 1}/{max_retries}")
            
            response = llm_with_tools.invoke(messages)
            
            # Verificar si hay tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_call = response.tool_calls[0]
                sql_query = tool_call['args'].get('sql_query', '')
                
                log_info(f"  Query generada: {sql_query[:100]}...")
                
                # Ejecutar la tool
                result_str = query_sql_database.invoke({"sql_query": sql_query})
                result = json.loads(result_str)
                
                if result.get("success"):
                    log_info(f"  ✅ Query exitosa: {result.get('count', 0)} filas")
                    return result
                else:
                    log_info(f"  ⚠️ Query falló: {result.get('error', 'Unknown error')}")
                    
                    # Agregar el error al contexto para el siguiente intento
                    messages.append(AIMessage(content=f"Query falló: {result.get('error')}"))
                    messages.append(HumanMessage(content=f"Corrige la query basándote en el error. Sugerencia: {result.get('suggestion', '')}"))
                    
                    if attempt == max_retries - 1:
                        return result  # Último intento, devolver aunque falle
            else:
                # No generó tool call, extraer query del contenido
                content = response.content if hasattr(response, 'content') else str(response)
                log_info(f"  ⚠️ No se generó tool call, buscando query en contenido...")
                
                # Intentar extraer query SQL del contenido
                if "SELECT" in content.upper() or "WITH" in content.upper():
                    # Extraer la query
                    lines = content.split('\n')
                    query_lines = [l for l in lines if l.strip().upper().startswith(('SELECT', 'WITH', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT'))]
                    sql_query = '\n'.join(query_lines)
                    
                    result_str = query_sql_database.invoke({"sql_query": sql_query})
                    result = json.loads(result_str)
                    
                    if result.get("success"):
                        return result
        
        # Si llegamos aquí, todos los intentos fallaron
        return {
            "success": False,
            "error": "No se pudo generar una query SQL válida después de 3 intentos"
        }
    
    except Exception as e:
        log_info(f"  ❌ Error ejecutando SQL: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _execute_document_search(state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta una búsqueda en documentos."""
    log_info("  📚 Buscando en documentos...")
    
    try:
        # Generar query de búsqueda basada en la descripción
        search_query = step['description']
        
        # Ejecutar búsqueda
        result_str = search_documents.invoke({
            "query": search_query,
            "max_results": 5
        })
        
        result = json.loads(result_str)
        log_info(f"  ✅ Encontrados {result.get('count', 0)} documentos")
        
        return result
    
    except Exception as e:
        log_info(f"  ❌ Error buscando documentos: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _execute_file_analysis(state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta análisis de un archivo."""
    log_info("  📄 Analizando archivo...")
    
    try:
        # Extraer file_path de la descripción o usar un default
        # En un caso real, el file_path debería venir del step
        file_path = step.get("file_path", "")
        
        if not file_path:
            return {
                "success": False,
                "error": "No se especificó file_path en el step"
            }
        
        result_str = analyze_file.invoke({
            "file_path": file_path,
            "analysis_type": "auto"
        })
        
        result = json.loads(result_str)
        log_info(f"  ✅ Archivo analizado: {result.get('file_type', 'unknown')}")
        
        return result
    
    except Exception as e:
        log_info(f"  ❌ Error analizando archivo: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _execute_synthesis(state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta una tarea de síntesis (combinar resultados)."""
    log_info("  🔀 Sintetizando resultados...")
    
    try:
        # Recopilar todos los resultados previos
        synthesis_context = {
            "sql_results": state.get("sql_results", []),
            "document_results": state.get("document_results", []),
            "file_results": state.get("file_results", []),
            "execution_results": state.get("execution_results", [])
        }
        
        return {
            "success": True,
            "synthesis_ready": True,
            "context": synthesis_context
        }
    
    except Exception as e:
        log_info(f"  ❌ Error en síntesis: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# NODO 3: REFLECTOR (Evaluación de progreso)
# ============================================================================

def reflector_node(state: AgentState) -> AgentState:
    """
    Nodo REFLECTOR: Evalúa si los resultados son suficientes.
    
    Este nodo:
    - Analiza los resultados obtenidos
    - Evalúa completitud y calidad
    - Decide si continuar o finalizar
    - Sugiere próximos pasos si es necesario
    """
    log_info("=" * 80)
    log_info("🔍 [REFLECTOR NODE] Evaluando progreso...")
    
    try:
        # Obtener LLM
        llm = get_chat_model()
        reflector_prompt = get_reflector_prompt()
        
        # Preparar contexto de evaluación
        plan = state.get("plan", {})
        execution_results = state.get("execution_results", [])
        current_step = state["current_step"]
        total_steps = len(plan.get("steps", []))
        
        # Resumen de resultados
        results_summary = json.dumps({
            "completed_steps": current_step,
            "total_steps": total_steps,
            "execution_results": execution_results,
            "sql_results_count": len(state.get("sql_results", [])),
            "document_results_count": len(state.get("document_results", [])),
            "file_results_count": len(state.get("file_results", []))
        }, ensure_ascii=False, indent=2)
        
        messages = [
            SystemMessage(content=reflector_prompt),
            HumanMessage(content=f"""Evalúa el progreso actual:

PREGUNTA ORIGINAL:
{state['original_question']}

PLAN:
- Complejidad: {plan.get('complexity', 'N/A')}
- Total pasos: {total_steps}
- Pasos completados: {current_step}

RESULTADOS OBTENIDOS:
{results_summary}

ÚLTIMA EJECUCIÓN:
{json.dumps(execution_results[-1], ensure_ascii=False, indent=2) if execution_results else 'Sin resultados'}

INSTRUCCIONES:
1. Evalúa si los resultados son suficientes para responder la pregunta
2. Verifica calidad y consistencia
3. Decide: CONTINUE (necesitas más) o READY (listo para responder)
4. Devuelve tu evaluación en formato JSON

FORMATO REQUERIDO:
{{
  "decision": "CONTINUE|READY",
  "reasoning": "Por qué tomaste esta decisión",
  "completeness_score": 0-100,
  "quality_score": 0-100,
  "next_action": "Qué hacer si CONTINUE (null si READY)",
  "issues_found": ["lista de problemas si hay"]
}}
""")
        ]
        
        response = llm.invoke(messages)
        
        # Extraer contenido
        if hasattr(response, 'content'):
            if isinstance(response.content, list):
                content_parts = []
                for part in response.content:
                    if isinstance(part, dict) and 'text' in part:
                        content_parts.append(part['text'])
                    elif isinstance(part, str):
                        content_parts.append(part)
                content = '\n'.join(content_parts)
            else:
                content = response.content
        else:
            content = str(response)
        
        # Limpiar y parsear JSON
        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        reflection_dict = json.loads(content)
        
        # Guardar reflexión en el estado
        state["reflection"] = reflection_dict
        
        decision = reflection_dict.get("decision", "CONTINUE")
        log_info(f"✅ Reflexión completada: {decision}")
        log_info(f"  Completitud: {reflection_dict.get('completeness_score', 0)}/100")
        log_info(f"  Calidad: {reflection_dict.get('quality_score', 0)}/100")
        log_info(f"  Razón: {reflection_dict.get('reasoning', 'N/A')[:100]}...")
        
        return state
    
    except Exception as e:
        log_info(f"❌ Error en reflector: {e}")
        
        # Reflexión de fallback: si completamos todos los pasos, estamos listos
        plan = state.get("plan", {})
        current_step = state["current_step"]
        total_steps = len(plan.get("steps", []))
        
        if current_step >= total_steps:
            decision = "READY"
            reasoning = "Todos los pasos completados (fallback)"
        else:
            decision = "CONTINUE"
            reasoning = "Aún hay pasos pendientes (fallback)"
        
        state["reflection"] = {
            "decision": decision,
            "reasoning": reasoning,
            "completeness_score": 50,
            "quality_score": 50,
            "next_action": "Continuar con el siguiente paso" if decision == "CONTINUE" else None,
            "issues_found": [f"Error en reflexión: {str(e)}"]
        }
        
        return state


# ============================================================================
# NODO 4: SYNTHESIS (Síntesis final y respuesta)
# ============================================================================

def synthesis_node(state: AgentState) -> AgentState:
    """
    Nodo SYNTHESIS: Genera la respuesta final para el usuario.
    
    Este nodo:
    - Combina todos los resultados obtenidos
    - Genera una respuesta profesional y completa
    - Incluye análisis, interpretación y recomendaciones
    - Formatea la respuesta con estilo contable profesional
    """
    log_info("=" * 80)
    log_info("📊 [SYNTHESIS NODE] Generando respuesta final...")
    
    try:
        # Obtener LLM
        llm = get_chat_model()
        
        # Recopilar todos los datos
        question = state["original_question"]
        plan = state.get("plan", {})
        sql_results = state.get("sql_results", [])
        document_results = state.get("document_results", [])
        file_results = state.get("file_results", [])
        execution_results = state.get("execution_results", [])
        
        # Crear contexto completo para la síntesis
        synthesis_context = f"""
PREGUNTA ORIGINAL DEL USUARIO:
{question}

DATOS RECOPILADOS:

=== RESULTADOS SQL ({len(sql_results)} consultas) ===
{json.dumps(sql_results, ensure_ascii=False, indent=2)[:5000]}

=== RESULTADOS DE DOCUMENTOS ({len(document_results)} búsquedas) ===
{json.dumps(document_results, ensure_ascii=False, indent=2)[:3000]}

=== RESULTADOS DE ARCHIVOS ({len(file_results)} análisis) ===
{json.dumps(file_results, ensure_ascii=False, indent=2)[:2000]}

=== RESUMEN DE EJECUCIÓN ===
Total de pasos ejecutados: {len(execution_results)}
Pasos exitosos: {sum(1 for r in execution_results if r.get('success'))}
Pasos fallidos: {sum(1 for r in execution_results if not r.get('success'))}
"""
        
        system_prompt = """Eres el Director Financiero y Contador Jefe Senior con 40 años de experiencia en contabilidad colombiana (NIIF, normativa DIAN, impuestos).

TU MISIÓN: Generar una respuesta PROFESIONAL, COMPLETA y ACCIONABLE basándote en todos los datos recopilados.

ESTRUCTURA DE RESPUESTA OBLIGATORIA:

1. **📊 RESUMEN EJECUTIVO** (2-3 líneas clave)

2. **📈 DATOS Y ANÁLISIS**
   - Presenta los datos principales con formato
   - Usa tablas markdown si hay muchos datos
   - Todos los montos en COP con formato: $1.234.567
   - Fechas en formato DD/MM/YYYY

3. **💡 INTERPRETACIÓN FINANCIERA**
   - Qué significan estos datos
   - Tendencias o patrones importantes
   - Alertas o banderas rojas
   - Oportunidades identificadas

4. **🎯 RECOMENDACIONES** (si aplica)
   - Acciones concretas y priorizadas
   - Plazos sugeridos
   - Impacto esperado

5. **📋 NORMATIVA Y POLÍTICAS** (si se consultaron docs)
   - Referencias a normativa aplicable
   - Procedimientos recomendados
   - Cumplimiento regulatorio

REGLAS DE ORO:
✅ Sé conciso pero completo
✅ Usa lenguaje profesional pero accesible
✅ Prioriza la acción sobre la teoría
✅ Valida consistencia (ej: ecuación contable debe cuadrar)
✅ Si hay errores o inconsistencias, explícalos claramente
✅ Usa emojis moderadamente para estructura visual
✅ Formatea números con separadores de miles
✅ Si los datos son insuficientes, dilo claramente y sugiere qué falta

¡Genera una respuesta que el CEO pueda usar inmediatamente para tomar decisiones!
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=synthesis_context)
        ]
        
        log_info("  Generando respuesta con LLM...")
        response = llm.invoke(messages)
        
        # Extraer contenido
        if hasattr(response, 'content'):
            if isinstance(response.content, list):
                content_parts = []
                for part in response.content:
                    if isinstance(part, dict) and 'text' in part:
                        content_parts.append(part['text'])
                    elif isinstance(part, str):
                        content_parts.append(part)
                final_answer = '\n'.join(content_parts)
            else:
                final_answer = response.content
        else:
            final_answer = str(response)
        
        # Finalizar estado
        state = finalize_state(state, final_answer)
        
        log_info(f"✅ Respuesta generada: {len(final_answer)} caracteres")
        log_info(f"  Duración total: {state['metadata']['total_duration_seconds']:.2f}s")
        
        return state
    
    except Exception as e:
        log_info(f"❌ Error en synthesis: {e}")
        
        # Respuesta de fallback
        fallback_answer = f"""❌ Error generando la respuesta final:

{str(e)}

**Datos recopilados:**
- Consultas SQL: {len(state.get('sql_results', []))}
- Búsquedas en documentos: {len(state.get('document_results', []))}
- Análisis de archivos: {len(state.get('file_results', []))}

Por favor, reformula tu pregunta o contacta soporte.
"""
        
        state = finalize_state(state, fallback_answer)
        return state


# ============================================================================
# FUNCIÓN DE ENRUTAMIENTO (Routing)
# ============================================================================

def should_continue(state: AgentState) -> Literal["executor", "reflector", "synthesis", "end"]:
    """
    Función de routing que decide el próximo nodo.
    
    Lógica:
    - Si no hay plan → ir a planner (no debería pasar)
    - Si hay plan y pasos pendientes → ir a executor
    - Después de executor → ir a reflector
    - Si reflector dice READY → ir a synthesis
    - Si reflector dice CONTINUE y hay más pasos → ir a executor
    - Si llegamos al límite de iteraciones → ir a synthesis (forzar cierre)
    - Después de synthesis → END
    """
    
    # Verificar límite de iteraciones
    if state["iteration_count"] >= MAX_ITERATIONS:
        log_info(f"⚠️ Límite de iteraciones alcanzado ({MAX_ITERATIONS})")
        return "synthesis"
    
    # Si no hay plan, error crítico
    if not state.get("plan"):
        log_info("❌ No hay plan, forzando synthesis")
        return "synthesis"
    
    plan = state["plan"]
    current_step = state["current_step"]
    total_steps = len(plan.get("steps", []))
    
    # Si no hay reflexión aún, necesitamos ejecutar y luego reflexionar
    if not state.get("reflection"):
        if current_step < total_steps:
            return "executor"
        else:
            return "reflector"
    
    # Hay reflexión, analizar decisión
    reflection = state["reflection"]
    decision = reflection.get("decision", "CONTINUE")
    
    if decision == "READY":
        log_info("✅ Reflector indica READY, yendo a synthesis")
        return "synthesis"
    
    elif decision == "CONTINUE":
        if current_step < total_steps:
            log_info(f"🔄 Reflector indica CONTINUE, yendo a executor (paso {current_step + 1}/{total_steps})")
            # Resetear reflexión para el próximo ciclo
            state["reflection"] = None
            return "executor"
        else:
            log_info("✅ No hay más pasos, forzando synthesis")
            return "synthesis"
    
    else:
        # Decisión desconocida, ir a synthesis
        log_info(f"⚠️ Decisión desconocida: {decision}, yendo a synthesis")
        return "synthesis"


# ============================================================================
# CREACIÓN DEL GRAFO DE LANGGRAPH
# ============================================================================

def create_accounting_agent_v3():
    """
    Crea el agente contable v3.0 con LangGraph StateGraph.
    
    Returns:
        CompiledStateGraph listo para invocar
    """
    log_info("=" * 80)
    log_info("🚀 Creando Agente Contable v3.0 (LangGraph StateGraph)")
    log_info("=" * 80)
    
    # Crear el grafo
    workflow = StateGraph(AgentState)
    
    # Agregar nodos
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("reflector", reflector_node)
    workflow.add_node("synthesis", synthesis_node)
    
    # Definir entrada: siempre empieza en planner
    workflow.set_entry_point("planner")
    
    # Definir transiciones
    workflow.add_edge("planner", "executor")  # Después de planear → ejecutar
    workflow.add_edge("executor", "reflector")  # Después de ejecutar → reflexionar
    
    # Routing condicional desde reflector
    workflow.add_conditional_edges(
        "reflector",
        should_continue,
        {
            "executor": "executor",      # Continuar ejecutando
            "synthesis": "synthesis",    # Ir a síntesis final
            "end": END                   # Terminar (no usado normalmente)
        }
    )
    
    # Después de synthesis → END
    workflow.add_edge("synthesis", END)
    
    # Compilar con checkpointing (MemorySaver en RAM)
    if AGENT_CONFIG.get("enable_checkpointing", False):
        log_info(f"✅ Checkpointing habilitado (MemorySaver en memoria)")
        try:
            memory = MemorySaver()
            agent = workflow.compile(checkpointer=memory)
        except Exception as e:
            log_info(f"⚠️ Error creando checkpointer, compilando sin memoria: {e}")
            agent = workflow.compile()
    else:
        log_info("⚠️ Checkpointing deshabilitado")
        agent = workflow.compile()
    
    log_info("✅ Agente v3.0 creado exitosamente")
    log_info(f"  Nodos: planner → executor → reflector → synthesis")
    log_info(f"  Max iteraciones: {MAX_ITERATIONS}")
    log_info(f"  Herramientas: query_sql_database, search_documents, analyze_file")
    log_info("=" * 80)
    
    return agent


# ============================================================================
# FUNCIÓN PRINCIPAL DE RESPUESTA
# ============================================================================

def answer_question_v3(question: str, thread_id: str = "default") -> str:
    """
    Responde preguntas contables usando el agente v3.0 (multi-agente con LangGraph).
    
    El agente:
    - Analiza la pregunta y crea un plan estratégico
    - Ejecuta múltiples herramientas de forma iterativa
    - Auto-corrige errores y refina resultados
    - Sintetiza todo en una respuesta profesional
    - Mantiene contexto entre conversaciones
    
    Args:
        question: Pregunta del usuario
        thread_id: ID del hilo de conversación (para checkpointing)
        
    Returns:
        Respuesta profesional del contador
    """
    log_info("=" * 80)
    log_info("🎯 NUEVA PREGUNTA (AGENTE V3.0)")
    log_info(f"Thread ID: {thread_id}")
    log_info(f"Pregunta: {question}")
    log_info("=" * 80)
    
    try:
        # Crear el agente
        agent = create_accounting_agent_v3()
        
        # Crear estado inicial
        initial_state = create_initial_state(question, thread_id)
        
        # Configuración de ejecución
        config = RunnableConfig(
            configurable={"thread_id": thread_id},
            recursion_limit=MAX_ITERATIONS + 5  # Límite de recursión
        )
        
        # Invocar el agente
        log_info("🚀 Iniciando ejecución del grafo...")
        final_state = agent.invoke(initial_state, config)
        
        # Extraer respuesta final
        final_answer = final_state.get("final_answer")
        
        if not final_answer:
            log_info("⚠️ No se generó respuesta final, extrayendo de mensajes...")
            
            # Intentar extraer del último mensaje
            messages = final_state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content'):
                    final_answer = last_msg.content
                else:
                    final_answer = str(last_msg)
            else:
                final_answer = "No se pudo generar una respuesta. Por favor, intenta reformular tu pregunta."
        
        # Log de resultados
        log_info("=" * 80)
        log_info("✅ EJECUCIÓN COMPLETADA")
        log_info(f"  Iteraciones: {final_state.get('iteration_count', 0)}")
        log_info(f"  Pasos ejecutados: {len(final_state.get('execution_results', []))}")
        log_info(f"  Herramientas usadas: {', '.join(final_state.get('metadata', {}).get('tools_used', []))}")
        log_info(f"  Duración: {final_state.get('metadata', {}).get('total_duration_seconds', 0):.2f}s")
        log_info(f"  Longitud respuesta: {len(final_answer)} caracteres")
        log_info("=" * 80)
        
        return final_answer
    
    except Exception as e:
        log_info(f"❌ Error en agente v3.0: {e}")
        import traceback
        log_info(traceback.format_exc())
        
        return f"""❌ Error procesando la pregunta:

{str(e)}

**Posibles soluciones:**
- Verifica que la base de datos esté inicializada
- Asegúrate de tener datos cargados
- Reformula la pregunta de forma más específica
- Contacta soporte si el error persiste

**Detalles técnicos:**
```
{traceback.format_exc()[:500]}
```
"""


# ============================================================================
# FUNCIÓN DE COMPATIBILIDAD
# ============================================================================

def answer_question(question: str) -> str:
    """
    Wrapper de compatibilidad con versiones anteriores.
    Redirige a answer_question_v3 con thread_id por defecto.
    """
    return answer_question_v3(question, thread_id="default")


# ============================================================================
# UTILIDADES DE DIAGNÓSTICO
# ============================================================================

def visualize_graph():
    """
    Genera una visualización del grafo (requiere graphviz).
    Útil para debugging y documentación.
    """
    try:
        agent = create_accounting_agent_v3()
        
        # Intentar obtener visualización
        graph_ascii = agent.get_graph().draw_ascii()
        
        log_info("=" * 80)
        log_info("VISUALIZACIÓN DEL GRAFO")
        log_info("=" * 80)
        print(graph_ascii)
        log_info("=" * 80)
        
        return graph_ascii
    
    except Exception as e:
        log_info(f"⚠️ No se pudo visualizar el grafo: {e}")
        return None


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("🧪 Testing Agente Contable v3.0 (LangGraph StateGraph)")
    print("=" * 80)
    
    # Visualizar grafo
    visualize_graph()
    
    # Pregunta de prueba
    test_question = "¿Cuántas transacciones tengo en la base de datos?"
    print(f"\n❓ Pregunta: {test_question}")
    print("-" * 80)
    
    answer = answer_question_v3(test_question)
    print(f"\n💬 Respuesta:\n{answer}")
    print("=" * 80)
