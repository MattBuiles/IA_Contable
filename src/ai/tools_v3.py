"""
Herramientas del Agente Contable v3.0
======================================
Herramientas optimizadas y potentes para el agente multi-agente con LangGraph.
Solo 3 herramientas esenciales y ultra-capaces.
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd

from langchain_core.tools import tool
from langchain_community.utilities import SQLDatabase

from src.db.database import DB_PATH, get_connection
from src.ai.client import get_embeddings
from src.ai.vectorstore import get_retriever
from src.utils.logger import log_info


# ============================================================================
# UTILIDADES PARA SQL
# ============================================================================

def get_sql_database() -> SQLDatabase:
    """Obtiene la instancia de SQLDatabase."""
    db_uri = f"sqlite:///{DB_PATH}"
    return SQLDatabase.from_uri(db_uri)


# ============================================================================
# TOOL 1: QUERY SQL (Ultra-potente con validación y auto-corrección)
# ============================================================================

@tool
def query_sql_database(sql_query: str) -> str:
    """
    Ejecuta consultas SQL SELECT en la base de datos contable.
    
    CAPACIDADES:
    - Ejecuta SELECT, WITH (CTEs), agregaciones complejas
    - Devuelve resultados en JSON estructurado con metadatos
    - Validación de seguridad (solo lectura)
    - Manejo robusto de errores con sugerencias de corrección
    - Límite automático de 1000 filas para evitar overflow
    
    ESQUEMA DE LA BD (principales tablas):
    - documents: documentos fuente (PDFs, XMLs, etc.)
    - transactions: transacciones contables (ventas, compras, pagos, etc.)
    - transaction_lines: líneas de detalle de transacciones
    - accounts: plan de cuentas contable (tipos: Activo, Pasivo, Patrimonio, Ingreso, Gasto, Costo)
    - journal_entries: asientos contables (débitos y créditos)
    
    EJEMPLOS DE QUERIES ÚTILES:
    
    1. Total de ventas en un período:
    ```sql
    SELECT 
        STRFTIME('%Y-%m', transaction_date) as mes,
        COUNT(*) as num_facturas,
        ROUND(SUM(amount), 2) as total_ventas
    FROM transactions
    WHERE transaction_type = 'sales_invoice'
      AND DATE(transaction_date) BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY mes
    ORDER BY mes;
    ```
    
    2. Balance de cuentas por tipo:
    ```sql
    SELECT 
        a.account_type,
        a.name,
        ROUND(SUM(CASE 
            WHEN a.account_type IN ('Activo', 'Gasto', 'Costo') 
            THEN je.debit - je.credit
            ELSE je.credit - je.debit
        END), 2) as balance
    FROM accounts a
    LEFT JOIN journal_entries je ON a.code = je.account_code
    GROUP BY a.account_type, a.name
    HAVING balance != 0
    ORDER BY a.account_type, balance DESC;
    ```
    
    3. Clientes con cuentas por cobrar:
    ```sql
    SELECT 
        counterparty as cliente,
        COUNT(*) as facturas_pendientes,
        ROUND(SUM(amount), 2) as total_adeudado,
        MIN(transaction_date) as factura_mas_antigua,
        CAST(JULIANDAY('now') - JULIANDAY(MIN(transaction_date)) AS INTEGER) as dias_mora_max
    FROM transactions
    WHERE transaction_type = 'sales_invoice' 
      AND status = 'pending'
    GROUP BY counterparty
    ORDER BY total_adeudado DESC;
    ```
    
    Args:
        sql_query: Consulta SQL a ejecutar (solo SELECT/WITH permitidos)
        
    Returns:
        JSON con estructura:
        {
            "success": true/false,
            "rows": [...],  # Lista de diccionarios con resultados
            "count": N,     # Número de filas
            "columns": [...],  # Nombres de columnas
            "truncated": true/false,  # Si se limitaron resultados
            "error": "...",  # Si hubo error
            "suggestion": "..."  # Sugerencia de corrección
        }
    """
    try:
        log_info(f"🔍 [TOOL] query_sql_database")
        log_info(f"Query: {sql_query[:200]}...")
        
        # ===== VALIDACIÓN DE SEGURIDAD =====
        query_lower = sql_query.lower().strip()
        
        # Solo permitir SELECT y WITH
        if not (query_lower.startswith("select") or query_lower.startswith("with")):
            error_msg = "❌ Solo se permiten consultas SELECT o WITH (CTEs)"
            log_info(error_msg)
            return json.dumps({
                "success": False,
                "error": error_msg,
                "suggestion": "Reformula tu query usando SELECT o WITH para consultas de lectura"
            }, ensure_ascii=False, indent=2)
        
        # Bloquear operaciones de escritura
        forbidden = ["insert", "update", "delete", "drop", "alter", "create", 
                    "truncate", "replace", "pragma", "attach", "detach"]
        
        for keyword in forbidden:
            if f" {keyword} " in f" {query_lower} ":
                error_msg = f"❌ Operación '{keyword.upper()}' no permitida (solo lectura)"
                log_info(error_msg)
                return json.dumps({
                    "success": False,
                    "error": error_msg,
                    "suggestion": "Solo puedes consultar datos con SELECT/WITH"
                }, ensure_ascii=False, indent=2)
        
        # ===== EJECUCIÓN DE LA QUERY =====
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            
            # Obtener metadatos
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            # Límite de seguridad
            truncated = False
            if len(rows) > 1000:
                log_info(f"⚠️ Resultados truncados: {len(rows)} → 1000 filas")
                rows = rows[:1000]
                truncated = True
            
            # Convertir a lista de diccionarios
            result_dicts = []
            for row in rows:
                row_dict = {col: row[idx] for idx, col in enumerate(columns)}
                result_dicts.append(row_dict)
            
            # Construir respuesta
            response = {
                "success": True,
                "rows": result_dicts,
                "count": len(result_dicts),
                "columns": columns,
                "truncated": truncated
            }
            
            if truncated:
                response["message"] = "⚠️ Resultados limitados a 1000 filas. Usa WHERE y LIMIT para refinar."
            
            if len(result_dicts) == 0:
                response["message"] = "ℹ️ La consulta no devolvió resultados. Verifica fechas y condiciones."
            
            log_info(f"✅ Query exitosa: {len(result_dicts)} filas")
            return json.dumps(response, ensure_ascii=False, indent=2)
    
    except sqlite3.OperationalError as e:
        # Errores de SQL (sintaxis, tabla inexistente, etc.)
        error_msg = str(e)
        log_info(f"❌ Error SQL: {error_msg}")
        
        # Sugerencias inteligentes
        suggestion = ""
        if "no such table" in error_msg:
            suggestion = "Verifica el nombre de la tabla. Tablas disponibles: documents, transactions, transaction_lines, accounts, journal_entries"
        elif "no such column" in error_msg:
            suggestion = "Verifica los nombres de columnas. Usa el esquema de la BD para consultar campos correctos."
        elif "syntax error" in error_msg:
            suggestion = "Error de sintaxis SQL. Revisa paréntesis, comas, palabras clave y formato SQLite."
        elif "ambiguous" in error_msg:
            suggestion = "Columna ambigua. Usa alias de tabla (ej: t.campo en vez de campo)."
        else:
            suggestion = "Revisa la sintaxis y estructura de tu query."
        
        return json.dumps({
            "success": False,
            "error": f"Error SQL: {error_msg}",
            "suggestion": suggestion,
            "query": sql_query[:500]
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        # Error general
        error_msg = str(e)
        log_info(f"❌ Error general: {error_msg}")
        return json.dumps({
            "success": False,
            "error": f"Error ejecutando query: {error_msg}",
            "suggestion": "Verifica la conexión a la BD y la sintaxis de la query."
        }, ensure_ascii=False, indent=2)


# ============================================================================
# TOOL 2: BÚSQUEDA SEMÁNTICA EN DOCUMENTOS (Ultra-potente con refinamiento)
# ============================================================================

@tool
def search_documents(query: str, max_results: int = 5) -> str:
    """
    Busca información en documentos contables, normativas y políticas usando búsqueda semántica.
    
    CASOS DE USO:
    - Normativas: "retención en la fuente sobre servicios", "IVA en importaciones"
    - Políticas contables: "política de depreciación", "reconocimiento de ingresos"
    - Procedimientos: "cierre mensual", "conciliación bancaria"
    - Conceptos: "diferencia entre NIIF y PCGA", "qué es un activo diferido"
    - Deducciones: "gastos deducibles impuesto de renta", "limitaciones fiscales"
    
    IMPORTANTE:
    - Esta herramienta busca en PDFs, Excel, Word, políticas internas
    - NO busca datos transaccionales (para eso usa query_sql_database)
    - Puedes llamarla múltiples veces con queries refinadas si no encuentras lo que buscas
    
    EJEMPLOS:
    - "política de reconocimiento de ingresos por ventas"
    - "retención en la fuente tabla 2025 Colombia"
    - "procedimiento de cierre contable mensual"
    - "NIIF 15 contratos con clientes"
    
    Args:
        query: Texto a buscar (usa lenguaje natural)
        max_results: Número máximo de documentos a devolver (default: 5)
        
    Returns:
        JSON con:
        {
            "success": true/false,
            "documents": [
                {"content": "...", "source": "...", "score": 0.95},
                ...
            ],
            "count": N,
            "query": "..."
        }
    """
    try:
        log_info(f"📚 [TOOL] search_documents")
        log_info(f"Query: {query}")
        log_info(f"Max results: {max_results}")
        
        embedder = get_embeddings()
        retriever = get_retriever(embedder, k=max_results)
        docs = retriever.invoke(query)
        
        if not docs:
            log_info("⚠️ No se encontraron documentos")
            return json.dumps({
                "success": True,
                "documents": [],
                "count": 0,
                "query": query,
                "message": "No se encontraron documentos relevantes. Intenta reformular la búsqueda con otros términos."
            }, ensure_ascii=False, indent=2)
        
        # Estructurar resultados
        documents = []
        for idx, doc in enumerate(docs, 1):
            doc_info = {
                "rank": idx,
                "content": doc.page_content,
                "metadata": doc.metadata if hasattr(doc, 'metadata') else {},
                "source": doc.metadata.get('source', 'Desconocido') if hasattr(doc, 'metadata') else 'Desconocido'
            }
            documents.append(doc_info)
        
        log_info(f"✅ Encontrados {len(documents)} documentos")
        
        return json.dumps({
            "success": True,
            "documents": documents,
            "count": len(documents),
            "query": query
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        log_info(f"❌ Error: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error buscando documentos: {str(e)}",
            "suggestion": "Verifica que el vectorstore esté inicializado y tenga documentos indexados."
        }, ensure_ascii=False, indent=2)


# ============================================================================
# TOOL 3: ANÁLISIS DE ARCHIVOS (Para Excel, CSV, PDFs específicos)
# ============================================================================

@tool
def analyze_file(file_path: str, analysis_type: str = "auto") -> str:
    """
    Analiza archivos específicos (Excel, CSV, PDF) para extraer datos estructurados.
    
    CAPACIDADES:
    - Excel (.xlsx, .xls): Lee hojas, detecta tablas, extrae datos
    - CSV (.csv): Carga y analiza datos tabulares
    - PDF (.pdf): Extrae texto y tablas (si es posible)
    - JSON (.json): Parsea y estructura datos
    
    CASOS DE USO:
    - "Analiza el archivo balance_2024.xlsx y dame un resumen"
    - "Extrae la tabla de la página 3 del PDF normativa_IVA.pdf"
    - "Lee el CSV transacciones.csv y cuenta cuántas filas tiene"
    
    TIPOS DE ANÁLISIS:
    - "auto": Detecta automáticamente el mejor método
    - "summary": Resumen ejecutivo del archivo
    - "extract_tables": Extrae todas las tablas encontradas
    - "full": Análisis completo (puede ser costoso en tokens)
    
    Args:
        file_path: Ruta absoluta o relativa al archivo
        analysis_type: Tipo de análisis ("auto", "summary", "extract_tables", "full")
        
    Returns:
        JSON con:
        {
            "success": true/false,
            "file_type": "xlsx/csv/pdf/json",
            "summary": "...",
            "data": {...},  # Datos extraídos
            "tables": [...],  # Tablas encontradas
            "error": "..."
        }
    """
    try:
        log_info(f"📄 [TOOL] analyze_file")
        log_info(f"File: {file_path}")
        log_info(f"Analysis type: {analysis_type}")
        
        file_path_obj = Path(file_path)
        
        # Verificar existencia
        if not file_path_obj.exists():
            error_msg = f"Archivo no encontrado: {file_path}"
            log_info(f"❌ {error_msg}")
            return json.dumps({
                "success": False,
                "error": error_msg,
                "suggestion": "Verifica la ruta del archivo. Debe ser absoluta o relativa al workspace."
            }, ensure_ascii=False, indent=2)
        
        file_ext = file_path_obj.suffix.lower()
        
        # ===== ANÁLISIS DE EXCEL =====
        if file_ext in ['.xlsx', '.xls']:
            try:
                # Leer todas las hojas
                excel_file = pd.ExcelFile(file_path)
                sheet_names = excel_file.sheet_names
                
                result = {
                    "success": True,
                    "file_type": "excel",
                    "file_name": file_path_obj.name,
                    "sheet_names": sheet_names,
                    "sheets": {}
                }
                
                for sheet in sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    
                    sheet_info = {
                        "rows": len(df),
                        "columns": list(df.columns),
                        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                        "preview": df.head(10).to_dict('records') if analysis_type in ["full", "auto"] else None,
                        "summary": {
                            "total_rows": len(df),
                            "total_columns": len(df.columns),
                            "numeric_columns": len(df.select_dtypes(include=['number']).columns),
                            "text_columns": len(df.select_dtypes(include=['object']).columns)
                        }
                    }
                    
                    result["sheets"][sheet] = sheet_info
                
                log_info(f"✅ Excel analizado: {len(sheet_names)} hojas")
                return json.dumps(result, ensure_ascii=False, indent=2, default=str)
            
            except Exception as e:
                log_info(f"❌ Error leyendo Excel: {e}")
                return json.dumps({
                    "success": False,
                    "error": f"Error leyendo Excel: {str(e)}",
                    "suggestion": "Verifica que el archivo no esté corrupto y tenga el formato correcto."
                }, ensure_ascii=False, indent=2)
        
        # ===== ANÁLISIS DE CSV =====
        elif file_ext == '.csv':
            try:
                df = pd.read_csv(file_path)
                
                result = {
                    "success": True,
                    "file_type": "csv",
                    "file_name": file_path_obj.name,
                    "rows": len(df),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "preview": df.head(10).to_dict('records') if analysis_type in ["full", "auto"] else None,
                    "summary": {
                        "total_rows": len(df),
                        "total_columns": len(df.columns),
                        "numeric_columns": len(df.select_dtypes(include=['number']).columns),
                        "text_columns": len(df.select_dtypes(include=['object']).columns),
                        "null_counts": df.isnull().sum().to_dict()
                    }
                }
                
                log_info(f"✅ CSV analizado: {len(df)} filas")
                return json.dumps(result, ensure_ascii=False, indent=2, default=str)
            
            except Exception as e:
                log_info(f"❌ Error leyendo CSV: {e}")
                return json.dumps({
                    "success": False,
                    "error": f"Error leyendo CSV: {str(e)}",
                    "suggestion": "Verifica el encoding (UTF-8, latin1) y el separador (coma, punto y coma)."
                }, ensure_ascii=False, indent=2)
        
        # ===== ANÁLISIS DE PDF =====
        elif file_ext == '.pdf':
            try:
                # Intentar con PyPDF2 (básico)
                try:
                    import PyPDF2
                    
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        num_pages = len(reader.pages)
                        
                        # Extraer texto de las primeras 5 páginas
                        text_preview = ""
                        for i in range(min(5, num_pages)):
                            text_preview += reader.pages[i].extract_text() + "\n\n"
                        
                        result = {
                            "success": True,
                            "file_type": "pdf",
                            "file_name": file_path_obj.name,
                            "total_pages": num_pages,
                            "text_preview": text_preview[:2000] if analysis_type in ["full", "auto"] else None,
                            "message": "Extracción básica de texto. Para tablas complejas, usa herramientas especializadas."
                        }
                        
                        log_info(f"✅ PDF analizado: {num_pages} páginas")
                        return json.dumps(result, ensure_ascii=False, indent=2)
                
                except ImportError:
                    error_msg = "PyPDF2 no instalado. Instala con: pip install PyPDF2"
                    log_info(f"⚠️ {error_msg}")
                    return json.dumps({
                        "success": False,
                        "error": error_msg,
                        "suggestion": "Instala PyPDF2 para análisis de PDFs."
                    }, ensure_ascii=False, indent=2)
            
            except Exception as e:
                log_info(f"❌ Error leyendo PDF: {e}")
                return json.dumps({
                    "success": False,
                    "error": f"Error leyendo PDF: {str(e)}"
                }, ensure_ascii=False, indent=2)
        
        # ===== ANÁLISIS DE JSON =====
        elif file_ext == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                result = {
                    "success": True,
                    "file_type": "json",
                    "file_name": file_path_obj.name,
                    "data": data if analysis_type == "full" else None,
                    "summary": {
                        "type": type(data).__name__,
                        "keys": list(data.keys()) if isinstance(data, dict) else None,
                        "length": len(data) if isinstance(data, (list, dict)) else None
                    }
                }
                
                log_info(f"✅ JSON analizado")
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            except Exception as e:
                log_info(f"❌ Error leyendo JSON: {e}")
                return json.dumps({
                    "success": False,
                    "error": f"Error leyendo JSON: {str(e)}"
                }, ensure_ascii=False, indent=2)
        
        # ===== FORMATO NO SOPORTADO =====
        else:
            error_msg = f"Formato de archivo no soportado: {file_ext}"
            log_info(f"⚠️ {error_msg}")
            return json.dumps({
                "success": False,
                "error": error_msg,
                "suggestion": "Formatos soportados: .xlsx, .xls, .csv, .pdf, .json"
            }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        log_info(f"❌ Error general: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error analizando archivo: {str(e)}"
        }, ensure_ascii=False, indent=2)


# ============================================================================
# UTILIDADES ADICIONALES
# ============================================================================

def get_all_tools() -> List:
    """Devuelve todas las herramientas disponibles para el agente."""
    return [
        query_sql_database,
        search_documents,
        analyze_file
    ]


def get_tools_description() -> str:
    """Devuelve descripción de todas las herramientas para el prompt."""
    return """
HERRAMIENTAS DISPONIBLES:

1. **query_sql_database(sql_query: str)**
   - Ejecuta consultas SQL SELECT en la base de datos contable
   - Devuelve JSON con resultados estructurados
   - Auto-corrección con sugerencias si hay errores
   - Límite de 1000 filas por seguridad

2. **search_documents(query: str, max_results: int = 5)**
   - Búsqueda semántica en documentos, normativas, políticas
   - Útil para conceptos, procedimientos, regulaciones
   - NO para datos transaccionales (usa SQL para eso)
   - Puedes llamarla múltiples veces con queries refinadas

3. **analyze_file(file_path: str, analysis_type: str = "auto")**
   - Analiza archivos Excel, CSV, PDF, JSON
   - Extrae datos estructurados y tablas
   - Útil cuando necesitas leer archivos específicos adjuntos
   - Types: "auto", "summary", "extract_tables", "full"
"""
