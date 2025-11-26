# 🤖 IA Contable v3.0

<div align="center">

**Sistema Inteligente de Contabilidad con IA - Agente Autónomo con LangGraph**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/LangChain-1.0+-green.svg)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

---

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Características Principales](#-características-principales)
- [Arquitectura](#-arquitectura)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Funcionalidades Contables](#-funcionalidades-contables)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)
- [Ejemplos de Uso](#-ejemplos-de-uso)
- [Contribución](#-contribución)
- [Roadmap](#-roadmap)
- [Licencia](#-licencia)

---

## 📖 Descripción

**IA Contable** es un asistente contable inteligente impulsado por IA que automatiza y simplifica tareas de contabilidad empresarial. Utiliza **LangGraph** para crear un agente autónomo capaz de planificar, ejecutar y reflexionar sobre tareas contables complejas.

El sistema combina:
- 🧠 **IA conversacional** (Google Gemini 2.5-Flash)
- 📊 **Procesamiento de documentos** (PDF, Excel)
- 🗄️ **Base de datos contable** (SQLite)
- 🔍 **Búsqueda semántica** (FAISS + embeddings)
- 🔄 **Agente autónomo** (LangGraph con ReAct)
- 🎨 **Interfaz web intuitiva** (Streamlit)

### ¿Qué hace diferente a IA Contable v3.0?

✅ **Agente Autónomo**: Planifica y ejecuta múltiples pasos sin intervención  
✅ **Auto-reflexión**: Evalúa sus propios resultados y corrige errores  
✅ **Memoria Persistente**: Almacena transacciones y documentos en SQLite  
✅ **RAG Avanzado**: Combina búsqueda SQL con recuperación de documentos  
✅ **Tareas Automatizadas**: Balance general, flujo de caja, análisis de gastos, etc.

---

## ✨ Características Principales

### 🎯 Capacidades del Agente

- **Planificación Inteligente**: Descompone preguntas complejas en pasos ejecutables
- **Ejecución Multiherramienta**: Consultas SQL, búsqueda de documentos, análisis de archivos
- **Auto-corrección**: Detecta errores y reintenta con estrategias diferentes
- **Explicaciones Detalladas**: Muestra el razonamiento detrás de cada respuesta

### 📄 Procesamiento de Documentos

- ✅ **Facturas PDF**: Extracción automática de datos fiscales
- ✅ **Extractos bancarios Excel**: Lectura de movimientos y transacciones
- ✅ **Almacenamiento vectorial**: Búsqueda semántica en documentos históricos
- ✅ **Indexación automática**: FAISS para recuperación rápida

### 💼 Funcionalidades Contables

| Tarea | Descripción | Automatizado |
|-------|-------------|--------------|
| 📊 Balance General | Activos, pasivos y patrimonio | ✅ |
| 💰 Flujo de Caja | Ingresos y egresos por período | ✅ |
| 📈 Estado de Resultados | P&L detallado | ✅ |
| 🏷️ Análisis por Categoría | Gastos e ingresos clasificados | ✅ |
| 📉 Análisis de Tendencias | Evolución mensual de métricas | ✅ |
| 🔍 Conciliación Bancaria | Comparación con extractos | ✅ |
| 📑 Libro Mayor | Registro completo de transacciones | ✅ |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT UI (app.py)                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │
│  │  Upload    │  │  Chat      │  │  Analytics         │   │
│  │  Files     │  │  Interface │  │  Dashboard         │   │
│  └────────────┘  └────────────┘  └────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              LANGGRAPH AGENT v3 (agent_v3.py)               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PLANNER → EXECUTOR → REFLECTOR → FINALIZER        │   │
│  │     │          │          │           │             │   │
│  │     └──────────┴──────────┴───────────┘             │   │
│  │          (StateGraph Loop)                          │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────┬──────────────────┬───────────────────────────┘
               │                  │
       ┌───────▼────────┐  ┌─────▼──────┐
       │  TOOLS v3      │  │  RAG       │
       │  ┌──────────┐  │  │  ┌───────┐ │
       │  │ SQL DB   │  │  │  │ FAISS │ │
       │  │ Search   │  │  │  │ Index │ │
       │  │ Analyze  │  │  │  └───────┘ │
       │  └──────────┘  │  └────────────┘
       └────────────────┘
               │
       ┌───────▼────────────────────┐
       │  DATA LAYER                │
       │  ┌──────────┐  ┌─────────┐ │
       │  │ SQLite   │  │ Vectors │ │
       │  │ (trans,  │  │ (docs)  │ │
       │  │  docs)   │  │         │ │
       │  └──────────┘  └─────────┘ │
       └────────────────────────────┘
```

### Flujo del Agente v3

1. **PLANNER**: Analiza la pregunta y genera un plan de ejecución
2. **EXECUTOR**: Ejecuta herramientas (SQL, búsqueda, análisis)
3. **REFLECTOR**: Evalúa resultados y decide si son suficientes
4. **FINALIZER**: Genera respuesta en lenguaje natural

---

## 🔧 Requisitos

### Software

- **Python**: 3.12 o superior
- **pip**: Gestor de paquetes de Python
- **Git**: Para clonar el repositorio

### Dependencias Principales

- `langchain >= 1.0.0` - Framework de LLM
- `langgraph >= 0.2.0` - Orquestación de agentes
- `langchain-google-genai >= 0.0.13` - Integración con Gemini
- `streamlit >= 1.28.0` - Interfaz web
- `faiss-cpu >= 1.7.4` - Búsqueda vectorial
- `pandas >= 2.0.0` - Análisis de datos
- `pdfplumber >= 0.10.0` - Procesamiento de PDF
- `sqlite-utils >= 3.33.0` - Gestión de BD

---

## 🚀 Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/MattBuiles/IA_Contable.git
cd IA_Contable
```

### 2. Crear Entorno Virtual

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# .env
GOOGLE_API_KEY=tu_api_key_de_google_gemini

# Opcional: Configuración avanzada
LANGCHAIN_CHAT_MODEL=gemini-2.5-flash
LANGCHAIN_EMBEDDING_MODEL=models/text-embedding-004
LANGCHAIN_TEMPERATURE=0.3
RETRIEVER_K=4
MAX_SQL_RESULTS=50
DEFAULT_CURRENCY=COP
TAX_RATE=0.19
DEBUG_MODE=False
LOG_LEVEL=INFO
```

> 💡 **Obtén tu API Key**: https://makersuite.google.com/app/apikey

---

## ⚙️ Configuración

### Estructura de Archivos

El sistema creará automáticamente:

```
data/
├── contabilidad.db      # Base de datos SQLite
└── faiss_index/         # Índice vectorial
    └── index.faiss
```

### Base de Datos

El esquema se inicializa automáticamente con:

- **documents**: Almacena archivos subidos (PDF/Excel)
- **transactions**: Transacciones contables (ventas, compras, pagos)
- **journal_entries**: Asientos de diario contable
- **accounts**: Plan de cuentas contable

---

## 💻 Uso

### Iniciar la Aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá en: http://localhost:8501

### Interfaz Web

#### 1️⃣ Cargar Documentos

![Sidebar](https://via.placeholder.com/300x400.png?text=Upload+Panel)

- Sube facturas (PDF) o extractos bancarios (Excel)
- El sistema extrae automáticamente:
  - Números de factura
  - Fechas
  - Montos
  - Conceptos

#### 2️⃣ Hacer Preguntas

![Chat](https://via.placeholder.com/600x300.png?text=Chat+Interface)

**Ejemplos de preguntas:**

```
💬 "¿Cuál es el balance general de este mes?"
💬 "Muéstrame el flujo de caja de los últimos 3 meses"
💬 "¿Cuánto he gastado en servicios públicos este año?"
💬 "Genera un estado de resultados del Q3"
💬 "¿Hay pagos pendientes?"
```

#### 3️⃣ Ver Métricas

![Dashboard](https://via.placeholder.com/600x200.png?text=Analytics+Dashboard)

- Total de transacciones
- Documentos procesados
- Balance actual
- Gráficos de tendencias

---

## 📁 Estructura del Proyecto

```
IA_Contable/
│
├── app.py                      # 🎨 Aplicación Streamlit principal
├── requirements.txt            # 📦 Dependencias
├── .env                        # 🔐 Variables de entorno (no versionado)
├── LICENSE                     # 📄 Licencia MIT
├── README.md                   # 📖 Este archivo
│
├── data/                       # 💾 Datos persistentes
│   ├── contabilidad.db         # SQLite database
│   └── faiss_index/            # Índice vectorial
│       └── index.faiss
│
├── src/                        # 🧩 Código fuente
│   ├── __init__.py
│   ├── config.py               # ⚙️ Configuración global
│   │
│   ├── ai/                     # 🤖 Módulos de IA
│   │   ├── agent_v3_main.py    # Punto de entrada del agente v3
│   │   ├── agent_v3.py         # Lógica principal del agente LangGraph
│   │   ├── state_v3.py         # Estados del grafo
│   │   ├── tools_v3.py         # Herramientas del agente
│   │   ├── prompts_v3.py       # Prompts del sistema
│   │   ├── accounting_tasks.py # Tareas contables automatizadas
│   │   ├── vectorstore.py      # Gestión de FAISS
│   │   ├── client.py           # Cliente LLM
│   │   └── agent.py            # (Legacy) Agente v1
│   │
│   ├── db/                     # 🗄️ Gestión de base de datos
│   │   └── database.py         # Esquema e inicialización SQLite
│   │
│   ├── ingestion/              # 📥 Procesamiento de documentos
│   │   ├── loaders.py          # Cargadores de PDF/Excel
│   │   └── pipeline.py         # Pipeline de ingestión
│   │
│   └── utils/                  # 🛠️ Utilidades
│       └── logger.py           # Sistema de logging
│
├── generador.py                # 🔧 Generador de datos sintéticos
└── generar_datos_prueba.py     # 📊 Script de datos de prueba
```

---

## 💼 Funcionalidades Contables

### 1. Balance General

```python
from src.ai.accounting_tasks import AccountingTasks

balance = AccountingTasks.balance_sheet(
    start_date="2025-01-01",
    end_date="2025-11-30"
)

print(f"Activos: ${balance['activos']:,.2f}")
print(f"Pasivos: ${balance['pasivos']:,.2f}")
print(f"Patrimonio: ${balance['patrimonio']:,.2f}")
```

**Salida:**
```
Activos: $150,000,000.00
Pasivos: $50,000,000.00
Patrimonio: $100,000,000.00
```

### 2. Flujo de Caja

```python
cash_flow = AccountingTasks.cash_flow(
    start_date="2025-10-01",
    end_date="2025-10-31"
)

print(f"Ingresos: ${cash_flow['ingresos']:,.2f}")
print(f"Egresos: ${cash_flow['egresos']:,.2f}")
print(f"Flujo Neto: ${cash_flow['flujo_neto']:,.2f}")
```

### 3. Análisis por Categoría

```python
analysis = AccountingTasks.expense_breakdown(
    start_date="2025-01-01",
    end_date="2025-11-30"
)

for category, amount in analysis.items():
    print(f"{category}: ${amount:,.2f}")
```

**Salida:**
```
Servicios: $12,500,000.00
Nómina: $45,000,000.00
Arriendo: $8,000,000.00
Impuestos: $5,600,000.00
```

---

## 🛠️ Tecnologías Utilizadas

### IA y Machine Learning

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **LangChain** | 1.0+ | Framework de LLM |
| **LangGraph** | 0.2+ | Orquestación de agentes |
| **Google Gemini** | 2.5-Flash | Modelo de lenguaje |
| **FAISS** | 1.7.4+ | Búsqueda vectorial |

### Backend y Datos

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **SQLite** | 3.x | Base de datos |
| **Pandas** | 2.0+ | Análisis de datos |
| **PDFPlumber** | 0.10+ | Extracción de PDF |
| **OpenPyXL** | 3.1+ | Lectura de Excel |

### Frontend

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **Streamlit** | 1.28+ | Interfaz web |
| **Python-dotenv** | 1.0+ | Gestión de variables de entorno |

---

## 📚 Ejemplos de Uso

### Ejemplo 1: Análisis Financiero Rápido

```python
from src.ai.agent_v3_main import quick_ask

# Pregunta simple
respuesta = quick_ask("¿Cuál es mi balance actual?")
print(respuesta)
```

### Ejemplo 2: Consulta con Contexto

```python
from src.ai.agent_v3_main import answer_question_v3

resultado = answer_question_v3(
    question="Compara los ingresos de octubre vs septiembre",
    verbose=True  # Muestra el proceso de razonamiento
)

print(resultado["answer"])
print(resultado["plan"])  # Plan de ejecución
print(resultado["reflections"])  # Auto-evaluaciones
```

### Ejemplo 3: Procesamiento de Documentos

```python
from src.ingestion.pipeline import ingest_pdf

# Procesar factura
ingest_pdf(
    file_path="factura_123.pdf",
    filename="Factura #123"
)

# Ahora puedes preguntar sobre esta factura
respuesta = quick_ask("Muéstrame la información de la factura #123")
```

### Ejemplo 4: Uso Programático del Agente

```python
from src.ai.agent_v3 import create_accounting_agent_v3
from src.ai.state_v3 import create_initial_state

# Crear agente
agent = create_accounting_agent_v3()

# Preparar estado inicial
state = create_initial_state("Genera el balance general de 2025")

# Ejecutar agente
result = agent.invoke(state)

# Ver resultado
print(result["final_answer"])
```

---

## 🤝 Contribución

¡Las contribuciones son bienvenidas! Sigue estos pasos:

### 1. Fork del Proyecto

```bash
git clone https://github.com/tuusuario/IA_Contable.git
cd IA_Contable
```

### 2. Crear Rama

```bash
git checkout -b feature/nueva-funcionalidad
```

### 3. Hacer Cambios

```bash
git add .
git commit -m "feat: descripción de la funcionalidad"
```

### 4. Push y PR

```bash
git push origin feature/nueva-funcionalidad
```

Luego crea un **Pull Request** en GitHub.

### Guía de Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `docs:` Documentación
- `style:` Formato de código
- `refactor:` Refactorización
- `test:` Tests
- `chore:` Tareas de mantenimiento

---

## 🗺️ Roadmap

### v3.1 (En desarrollo)

- [ ] Integración con APIs de bancos (Open Banking)
- [ ] Exportación a PDF de reportes contables
- [ ] Soporte multi-moneda en tiempo real
- [ ] Gráficos interactivos (Plotly)
- [ ] Notificaciones por email

### v4.0 (Futuro)

- [ ] Modo multi-tenant (varias empresas)
- [ ] Integración con DIAN (Colombia)
- [ ] Facturación electrónica
- [ ] Predicción de flujo de caja con ML
- [ ] App móvil (React Native)
- [ ] API REST completa

### Ideas en Consideración

- 🔐 Autenticación y roles de usuario
- 📊 Dashboard de BI avanzado
- 🌐 Soporte multiidioma
- 📱 Integración con WhatsApp
- 🤖 Asistente de voz

---

## 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo [LICENSE](LICENSE) para más detalles.

```
MIT License

Copyright (c) 2025 Matt Builes

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

---

## 👥 Autor

**Matt Builes**  
GitHub: [@MattBuiles](https://github.com/MattBuiles)

---

## 🙏 Agradecimientos

- [LangChain](https://www.langchain.com/) - Framework de LLM
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Orquestación de agentes
- [Google Gemini](https://ai.google.dev/) - Modelo de IA
- [Streamlit](https://streamlit.io/) - Framework de UI
- Comunidad de Python y IA

---

## 📞 Soporte

¿Tienes preguntas o necesitas ayuda?

- 🐛 **Issues**: [GitHub Issues](https://github.com/MattBuiles/IA_Contable/issues)
- 💬 **Discusiones**: [GitHub Discussions](https://github.com/MattBuiles/IA_Contable/discussions)
- 📧 **Email**: (añade tu email aquí)

---

## 🌟 ¿Te gusta el proyecto?

Si este proyecto te resulta útil, considera:

- ⭐ Darle una estrella en GitHub
- 🔀 Hacer un fork
- 📣 Compartirlo con colegas
- 🤝 Contribuir con código o ideas

---

<div align="center">

**Hecho con ❤️ y 🤖 por Matt Builes**

[⬆️ Volver arriba](#-ia-contable-v30)

</div>