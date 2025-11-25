"""
Estados y Schemas del Agente Contable v3.0
===========================================
Definición de estados para el StateGraph de LangGraph.
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from typing_extensions import NotRequired
from dataclasses import dataclass, field
from datetime import datetime

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


# ============================================================================
# ESTADO PRINCIPAL DEL AGENTE
# ============================================================================

class AgentState(TypedDict):
    """
    Estado principal del agente contable v3.
    
    Este estado se pasa entre todos los nodos del grafo y contiene
    toda la información necesaria para resolver la pregunta del usuario.
    """
    
    # ===== MENSAJES DE CONVERSACIÓN =====
    messages: Annotated[List[BaseMessage], add_messages]
    """Historial de mensajes (pregunta del usuario, respuestas del agente, tool calls)"""
    
    # ===== PREGUNTA ORIGINAL =====
    original_question: str
    """Pregunta original del usuario (se mantiene inmutable)"""
    
    # ===== PLAN DE EJECUCIÓN =====
    plan: Optional[Dict[str, Any]]
    """
    Plan generado por el nodo planner:
    {
        "complexity": "simple|medium|complex",
        "approach": "single_agent|multi_agent",
        "steps": [
            {
                "step": 1,
                "action": "query_sql_database|search_documents|analyze_file",
                "description": "...",
                "expected_output": "...",
                "agent": "sql_agent|document_agent|file_agent|synthesis_agent"
            },
            ...
        ],
        "final_synthesis": "..."
    }
    """
    
    # ===== EJECUCIÓN Y RESULTADOS =====
    current_step: int
    """Número del paso actual en ejecución (1-based)"""
    
    execution_results: List[Dict[str, Any]]
    """
    Resultados de cada paso ejecutado:
    [
        {
            "step": 1,
            "action": "query_sql_database",
            "success": true,
            "result": {...},
            "error": null,
            "timestamp": "2025-11-24T10:30:00"
        },
        ...
    ]
    """
    
    # ===== REFLEXIÓN Y CONTROL =====
    reflection: Optional[Dict[str, Any]]
    """
    Resultado de la reflexión del nodo reflector:
    {
        "decision": "CONTINUE|READY",
        "reasoning": "...",
        "completeness_score": 0-100,
        "quality_score": 0-100,
        "next_action": "...",
        "issues_found": [...]
    }
    """
    
    iteration_count: int
    """Número de iteraciones del agente (para evitar loops infinitos)"""
    
    # ===== DATOS INTERMEDIOS =====
    sql_results: List[Dict[str, Any]]
    """Resultados acumulados de consultas SQL"""
    
    document_results: List[Dict[str, Any]]
    """Resultados acumulados de búsquedas en documentos"""
    
    file_results: List[Dict[str, Any]]
    """Resultados acumulados de análisis de archivos"""
    
    # ===== METADATOS =====
    metadata: Dict[str, Any]
    """
    Metadatos adicionales:
    {
        "start_time": "...",
        "end_time": "...",
        "total_duration_seconds": 0.0,
        "tools_used": ["query_sql_database", ...],
        "agent_version": "3.0",
        "thread_id": "..."
    }
    """
    
    # ===== RESPUESTA FINAL =====
    final_answer: Optional[str]
    """Respuesta final formateada para el usuario (solo se llena al final)"""


# ============================================================================
# ESTADOS ESPECÍFICOS PARA SUB-AGENTES
# ============================================================================

class SQLAgentState(TypedDict):
    """Estado específico para el sub-agente de SQL."""
    query: str
    """Query SQL a ejecutar"""
    
    results: Optional[Dict[str, Any]]
    """Resultados de la query"""
    
    error: Optional[str]
    """Error si la query falló"""
    
    retry_count: int
    """Número de reintentos realizados"""


class DocumentAgentState(TypedDict):
    """Estado específico para el sub-agente de documentos."""
    search_query: str
    """Query de búsqueda semántica"""
    
    max_results: int
    """Número máximo de documentos a recuperar"""
    
    results: Optional[Dict[str, Any]]
    """Documentos encontrados"""


class FileAgentState(TypedDict):
    """Estado específico para el sub-agente de análisis de archivos."""
    file_path: str
    """Ruta al archivo a analizar"""
    
    analysis_type: str
    """Tipo de análisis ('auto', 'summary', 'extract_tables', 'full')"""
    
    results: Optional[Dict[str, Any]]
    """Resultados del análisis"""


# ============================================================================
# SCHEMAS DE DATOS
# ============================================================================

@dataclass
class PlanStep:
    """Representa un paso individual en el plan de ejecución."""
    step: int
    action: Literal["query_sql_database", "search_documents", "analyze_file", "synthesis"]
    description: str
    expected_output: str
    agent: Literal["sql_agent", "document_agent", "file_agent", "synthesis_agent"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el paso a diccionario."""
        return {
            "step": self.step,
            "action": self.action,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent": self.agent
        }


@dataclass
class ExecutionPlan:
    """Plan completo de ejecución generado por el planner."""
    complexity: Literal["simple", "medium", "complex"]
    approach: Literal["single_agent", "multi_agent"]
    steps: List[PlanStep]
    final_synthesis: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el plan a diccionario."""
        return {
            "complexity": self.complexity,
            "approach": self.approach,
            "steps": [step.to_dict() for step in self.steps],
            "final_synthesis": self.final_synthesis
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        """Crea un ExecutionPlan desde un diccionario."""
        steps = [
            PlanStep(
                step=s["step"],
                action=s["action"],
                description=s["description"],
                expected_output=s["expected_output"],
                agent=s["agent"]
            )
            for s in data.get("steps", [])
        ]
        
        return cls(
            complexity=data.get("complexity", "simple"),
            approach=data.get("approach", "single_agent"),
            steps=steps,
            final_synthesis=data.get("final_synthesis", "")
        )


@dataclass
class ExecutionResult:
    """Resultado de la ejecución de un paso."""
    step: int
    action: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el resultado a diccionario."""
        return {
            "step": self.step,
            "action": self.action,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds
        }


@dataclass
class Reflection:
    """Resultado de la reflexión sobre el progreso."""
    decision: Literal["CONTINUE", "READY"]
    reasoning: str
    completeness_score: int  # 0-100
    quality_score: int  # 0-100
    next_action: Optional[str] = None
    issues_found: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la reflexión a diccionario."""
        return {
            "decision": self.decision,
            "reasoning": self.reasoning,
            "completeness_score": self.completeness_score,
            "quality_score": self.quality_score,
            "next_action": self.next_action,
            "issues_found": self.issues_found
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reflection":
        """Crea una Reflection desde un diccionario."""
        return cls(
            decision=data.get("decision", "CONTINUE"),
            reasoning=data.get("reasoning", ""),
            completeness_score=data.get("completeness_score", 0),
            quality_score=data.get("quality_score", 0),
            next_action=data.get("next_action"),
            issues_found=data.get("issues_found", [])
        )


# ============================================================================
# FUNCIONES AUXILIARES PARA MANEJAR ESTADOS
# ============================================================================

def create_initial_state(question: str, thread_id: str = "default") -> AgentState:
    """
    Crea el estado inicial del agente para una nueva pregunta.
    
    Args:
        question: Pregunta del usuario
        thread_id: ID del hilo de conversación
        
    Returns:
        Estado inicial poblado
    """
    from langchain_core.messages import HumanMessage
    
    return {
        "messages": [HumanMessage(content=question)],
        "original_question": question,
        "plan": None,
        "current_step": 0,
        "execution_results": [],
        "reflection": None,
        "iteration_count": 0,
        "sql_results": [],
        "document_results": [],
        "file_results": [],
        "metadata": {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_duration_seconds": 0.0,
            "tools_used": [],
            "agent_version": "3.0",
            "thread_id": thread_id
        },
        "final_answer": None
    }


def update_state_with_result(
    state: AgentState,
    step: int,
    action: str,
    success: bool,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration: float = 0.0
) -> AgentState:
    """
    Actualiza el estado con el resultado de un paso ejecutado.
    
    Args:
        state: Estado actual
        step: Número del paso
        action: Acción ejecutada
        success: Si fue exitosa
        result: Resultado de la acción
        error: Error si falló
        duration: Duración en segundos
        
    Returns:
        Estado actualizado
    """
    execution_result = ExecutionResult(
        step=step,
        action=action,
        success=success,
        result=result,
        error=error,
        duration_seconds=duration
    )
    
    # Agregar resultado a la lista
    state["execution_results"].append(execution_result.to_dict())
    
    # Actualizar resultados específicos según el tipo de acción
    if action == "query_sql_database" and result:
        state["sql_results"].append(result)
        if "query_sql_database" not in state["metadata"]["tools_used"]:
            state["metadata"]["tools_used"].append("query_sql_database")
    
    elif action == "search_documents" and result:
        state["document_results"].append(result)
        if "search_documents" not in state["metadata"]["tools_used"]:
            state["metadata"]["tools_used"].append("search_documents")
    
    elif action == "analyze_file" and result:
        state["file_results"].append(result)
        if "analyze_file" not in state["metadata"]["tools_used"]:
            state["metadata"]["tools_used"].append("analyze_file")
    
    # Incrementar contador de paso
    state["current_step"] = step
    
    return state


def finalize_state(state: AgentState, final_answer: str) -> AgentState:
    """
    Finaliza el estado con la respuesta final.
    
    Args:
        state: Estado actual
        final_answer: Respuesta final para el usuario
        
    Returns:
        Estado finalizado
    """
    end_time = datetime.now()
    start_time = datetime.fromisoformat(state["metadata"]["start_time"])
    duration = (end_time - start_time).total_seconds()
    
    state["final_answer"] = final_answer
    state["metadata"]["end_time"] = end_time.isoformat()
    state["metadata"]["total_duration_seconds"] = duration
    
    return state


def get_state_summary(state: AgentState) -> str:
    """
    Genera un resumen legible del estado actual.
    
    Args:
        state: Estado actual
        
    Returns:
        Resumen en texto
    """
    summary_parts = [
        f"Pregunta: {state['original_question']}",
        f"Iteración: {state['iteration_count']}",
        f"Paso actual: {state['current_step']}"
    ]
    
    if state.get("plan"):
        summary_parts.append(f"Complejidad: {state['plan'].get('complexity', 'N/A')}")
        summary_parts.append(f"Enfoque: {state['plan'].get('approach', 'N/A')}")
        summary_parts.append(f"Total pasos: {len(state['plan'].get('steps', []))}")
    
    summary_parts.append(f"Resultados SQL: {len(state['sql_results'])}")
    summary_parts.append(f"Resultados Docs: {len(state['document_results'])}")
    summary_parts.append(f"Resultados Archivos: {len(state['file_results'])}")
    
    if state.get("reflection"):
        summary_parts.append(f"Decisión: {state['reflection'].get('decision', 'N/A')}")
        summary_parts.append(f"Calidad: {state['reflection'].get('quality_score', 0)}/100")
    
    return " | ".join(summary_parts)


# ============================================================================
# VALIDACIONES
# ============================================================================

def validate_state(state: AgentState) -> tuple[bool, Optional[str]]:
    """
    Valida que el estado tenga la estructura correcta.
    
    Args:
        state: Estado a validar
        
    Returns:
        (es_válido, mensaje_error)
    """
    # Verificar campos obligatorios
    required_fields = [
        "messages", "original_question", "current_step", 
        "execution_results", "iteration_count", "metadata"
    ]
    
    for field in required_fields:
        if field not in state:
            return False, f"Campo obligatorio faltante: {field}"
    
    # Verificar tipos
    if not isinstance(state["messages"], list):
        return False, "messages debe ser una lista"
    
    if not isinstance(state["original_question"], str):
        return False, "original_question debe ser string"
    
    if not isinstance(state["current_step"], int):
        return False, "current_step debe ser int"
    
    # Verificar límites
    if state["iteration_count"] > 20:
        return False, "Límite de iteraciones excedido (máximo 20)"
    
    return True, None
