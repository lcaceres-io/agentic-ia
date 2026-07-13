# Agentic IA — Asistente Académico (Function Calling + Structured Output)

Proyecto experimental para el curso de LLM: una app Python que demuestra,
de punta a punta, cómo un LLM (Gemini) **elige** qué herramienta (tool)
usar para responder una pregunta, y cómo se le puede forzar a devolver
una respuesta con un formato JSON estricto (Structured Output).

El dominio elegido es un asistente académico universitario: el alumno
pregunta por sus notas, promedio, asistencia o materias, y el modelo
decide sola qué función de Python ejecutar contra una base SQLite para
responder con datos reales (no inventados).

## Idea central

El LLM **nunca ejecuta código ni toca la base de datos**. Solo decide
"quiero llamar a la función `obtener_notas` con `id_alumno=1`" y
devuelve eso como JSON. La aplicación (este backend en Python) es quien
realmente ejecuta la función, y le devuelve el resultado al modelo para
que arme la respuesta final.

## Arquitectura

```
                    Usuario (navegador)
                            │
                            ▼
                 Frontend (HTML/CSS/JS)
                 static/index.html
                            │  POST /api/chat
                            ▼
                  FastAPI (app/main.py)
                            │
                            ▼
              gemini_client.py — orquestador
                            │
        ┌───────────────────┴────────────────────┐
        │  FASE 1 · Function Calling              │
        │  Gemini recibe: system prompt + tools    │
        │  disponibles + historial + mensaje.      │
        │  Decide: ¿responde directo o pide         │
        │  ejecutar una tool (con qué argumentos)?  │
        └───────────────────┬────────────────────┘
                            │ function_call(nombre, args)
                            ▼
                  tools.py — DISPATCH
                            │
                            ▼
                 SQLite (data/academia.db)
              alumnos · materias · notas · asistencias
                            │
                            ▼
                   resultado real (JSON)
                            │
        ┌───────────────────┴────────────────────┐
        │  FASE 2 · Structured Output              │
        │  Gemini recibe el resultado de la tool    │
        │  y responde OBLIGADO a cumplir el         │
        │  esquema RespuestaFinal (Pydantic).       │
        └───────────────────┬────────────────────┘
                            │
                            ▼
        { respuesta, datos_clave, trace }
                            │
                            ▼
              Frontend renderiza la respuesta
           + panel lateral con las tools ejecutadas
```

### ¿Por qué dos llamadas al modelo?

1. **Function Calling** resuelve *qué dato traer* (y con qué
   herramienta). El modelo puede decidir no usar ninguna tool si la
   pregunta no lo requiere.
2. **Structured Output** resuelve *cómo entregar la respuesta*: fuerza
   que el JSON final tenga siempre la forma `{ respuesta, datos_clave }`,
   sin importar qué tool (o ninguna) se haya usado. Esto es lo que
   permite que el frontend renderice la respuesta de forma consistente.

Importante: Structured Output garantiza la **forma** del JSON, no que
los datos sean correctos — por eso `herramienta_utilizada` y `trace` los
calcula el backend (no el modelo), a partir de lo que realmente se
ejecutó contra la base.

## Tools disponibles

| Tool | Qué hace | Argumentos |
|---|---|---|
| `buscar_alumno` | Resuelve `id_alumno` a partir de un nombre | `nombre` |
| `obtener_notas` | Notas de un alumno, materia por materia | `id_alumno` |
| `obtener_promedio` | Promedio general de notas | `id_alumno` |
| `obtener_asistencia` | % de asistencia, opcionalmente por materia | `id_alumno`, `materia?` |
| `listar_materias` | Materias disponibles, opcionalmente por carrera | `carrera?` |

Definidas en [app/tools.py](app/tools.py): cada tool es una función
Python normal + su `FunctionDeclaration` (el "contrato" que ve el
modelo).

## Estructura del proyecto

```
agenticIA/
├── app/
│   ├── main.py          # FastAPI: sirve el frontend y expone /api/chat
│   ├── gemini_client.py # Orquestación Function Calling + Structured Output
│   ├── tools.py          # Las 5 tools + sus FunctionDeclaration
│   ├── schemas.py        # Esquema Pydantic del Structured Output
│   ├── database.py       # SQLite: creación de tablas + datos de ejemplo
│   ├── config.py          # Carga de variables de entorno (.env)
│   └── static/            # Frontend (HTML/CSS/JS), sin frameworks
├── data/                  # academia.db (se genera sola, no se versiona)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Instalación y uso local

Requisitos: Python 3.11+ y una API key gratuita de Gemini
([aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

```bash
# 1. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar la API key
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
# Editar .env y pegar tu GEMINI_API_KEY

# 4. Levantar el servidor
uvicorn app.main:app --reload
```

Abrir [http://localhost:8000](http://localhost:8000).

La base SQLite se crea sola en `data/academia.db` la primera vez que se
levanta el servidor, con 3 alumnos de ejemplo, 4 materias, notas y
asistencias ya cargadas.

### Probar el flujo completo

- *"¿Cuáles son las notas de Lucas Cáceres?"* → dispara `buscar_alumno` +
  `obtener_notas`.
- *"¿Cuál es el promedio de Martina Gómez?"* → `buscar_alumno` +
  `obtener_promedio`.
- *"¿Qué asistencia tiene el alumno 1 en Matemática?"* → `obtener_asistencia`.
- *"¿Qué materias hay en Analista de Sistemas?"* → `listar_materias`.
- *"¿Cómo está el clima hoy?"* → el modelo no llama ninguna tool y
  responde que solo puede ayudar con temas académicos (definido en el
  system prompt).

El panel lateral derecho muestra, para cada mensaje, qué tool se ejecutó
y con qué argumentos y resultado — pensado para que se vea claramente
"la magia" del function calling.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `GEMINI_API_KEY` | API key de Google AI Studio (tier free) |
| `GEMINI_MODEL` | Modelo a usar (default: `gemini-2.5-flash`) |

## Despliegue en Coolify

El proyecto incluye `Dockerfile` y `docker-compose.yml`, listos para un
deploy tipo "Dockerfile"/"Docker Compose" en Coolify.

1. En Coolify, crear una nueva aplicación apuntando a este repositorio
   de GitHub.
2. Build pack: **Dockerfile** (o Docker Compose, usando
   `docker-compose.yml`).
3. Variables de entorno: cargar `GEMINI_API_KEY` (y opcionalmente
   `GEMINI_MODEL`) en la sección *Environment Variables* de Coolify —
   **no** se sube el `.env` al repo.
4. Puerto interno: `8000`.
5. Dominio: configurar `agente.mi.barcelo.edu.ar` como dominio de la
   aplicación en Coolify (Coolify se encarga del proxy/TLS).
6. Montar un volumen persistente en `/app/data` si se quiere conservar
   la base SQLite entre deploys (ya definido en `docker-compose.yml`).

## Stack

- **Python 3.12**
- **FastAPI** + Uvicorn — backend y API del chat
- **google-genai** — SDK oficial de Gemini (function calling + structured output)
- **SQLite** — base de datos de ejemplo, sin dependencias externas
- **Pydantic** — esquema del Structured Output
- HTML/CSS/JS plano — frontend, sin frameworks, tipografía **Raleway**
  y color institucional **#004C97**

---

Proyecto hecho como experimento del curso de LLM (Módulo 1: Function
Calling + Structured Output).
