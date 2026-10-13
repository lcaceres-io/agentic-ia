"""
Orquestacion del flujo Function Calling -> Structured Output contra Gemini.

Fase 1 (Function Calling):
    Le mandamos el mensaje del usuario + las tools disponibles. El modelo
    responde CON TEXTO o pidiendo ejecutar una o mas tools (nunca las
    ejecuta el mismo).

Fase 2 (Structured Output):
    Con el resultado real de la tool (si hubo) le pedimos al modelo la
    respuesta final, forzando que el JSON cumpla el esquema RespuestaFinal.
"""

import logging
import threading

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODELS

logger = logging.getLogger(__name__)
from app.schemas import RespuestaFinal
from app.tools import DISPATCH, TOOLS

SYSTEM_PROMPT = """
Sos el Asistente Academico Virtual de la Universidad Barcelo.

Tu trabajo es ayudar a los alumnos a consultar sus notas, promedios,
asistencia y materias disponibles, usando UNICAMENTE los datos que te
devuelven las herramientas (tools) que tenes disponibles.

Reglas:
- Nunca inventes notas, porcentajes de asistencia ni nombres de materias.
  Si no tenes el dato, decilo explicitamente.
- Si el usuario menciona un nombre de alumno pero no un id, primero usa
  buscar_alumno para resolver el id_alumno antes de llamar a otra tool.
- Si la pregunta no tiene relacion con datos academicos de la universidad,
  respondé amablemente que solo podes ayudar con temas academicos.
- Mantene un tono cordial, claro y profesional, como el de una secretaria
  academica universitaria.
""".strip()

client = genai.Client(api_key=GEMINI_API_KEY)

# Errores transitorios ante los que se rota al siguiente modelo.
# 503 = sobrecargado, 429 = cuota del modelo, 500/504 = fallas del servidor.
CODIGOS_ROTABLES = {429, 500, 503, 504}

_lock = threading.Lock()
_favorito: str | None = None  # ultimo modelo que respondio OK


def _orden_modelos() -> list[str]:
    """Favorito primero (si hay), despues el resto en el orden configurado."""
    with _lock:
        fav = _favorito
    if fav in GEMINI_MODELS:
        return [fav] + [m for m in GEMINI_MODELS if m != fav]
    return list(GEMINI_MODELS)


def _generar(contents: list[types.Content], **config_kwargs) -> types.GenerateContentResponse:
    """
    generate_content con rotacion de modelos. Empieza por el favorito y, si
    falla con un error transitorio, prueba el siguiente. El modelo que
    responde pasa a ser el favorito de las proximas consultas.
    """
    global _favorito
    ultimo_error: Exception | None = None

    for modelo in _orden_modelos():
        # thinking_budget=0 solo lo soporta la familia 2.5
        extra = {"thinking_config": types.ThinkingConfig(thinking_budget=0)} if "2.5" in modelo else {}
        try:
            respuesta = client.models.generate_content(
                model=modelo,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT, **config_kwargs, **extra
                ),
            )
        except genai_errors.APIError as e:
            if e.code not in CODIGOS_ROTABLES:
                raise
            logger.warning("Modelo %s fallo con %s, rotando al siguiente", modelo, e.code)
            ultimo_error = e
            continue

        with _lock:
            if _favorito != modelo:
                logger.info("Modelo favorito: %s", modelo)
                _favorito = modelo
        return respuesta

    raise ultimo_error  # todos los modelos fallaron


def _ejecutar_tool_calls(function_calls: list[types.FunctionCall]) -> tuple[list[types.Part], list[dict]]:
    """Ejecuta localmente las tools que el modelo pidio invocar y arma la traza."""
    response_parts: list[types.Part] = []
    trace: list[dict] = []

    for call in function_calls:
        nombre = call.name
        args = dict(call.args or {})
        funcion = DISPATCH.get(nombre)

        if funcion is None:
            resultado = {"error": f"Tool desconocida: {nombre}"}
        else:
            resultado = funcion(**args)

        trace.append({"tool": nombre, "argumentos": args, "resultado": resultado})
        response_parts.append(
            types.Part.from_function_response(name=nombre, response={"result": resultado})
        )

    return response_parts, trace


def procesar_mensaje(historial: list[dict], mensaje: str) -> dict:
    """
    historial: lista de turnos previos [{"role": "user"|"model", "text": "..."}]
    mensaje: nuevo mensaje del usuario

    Devuelve {"respuesta": str, "datos_clave": list[str], "trace": list[dict]}
    """
    contents: list[types.Content] = [
        types.Content(role=turno["role"], parts=[types.Part(text=turno["text"])])
        for turno in historial
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=mensaje)]))

    # --- Fase 1: Function Calling ---------------------------------------
    # El modelo puede necesitar encadenar varias tools (ej: buscar_alumno
    # para resolver un id y despues obtener_notas con ese id), asi que
    # repetimos la llamada mientras siga pidiendo ejecutar tools.
    trace: list[dict] = []
    for _ in range(5):
        respuesta_tools = _generar(
            contents,
            tools=[TOOLS],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        function_calls = respuesta_tools.function_calls
        if not function_calls:
            break

        contents.append(respuesta_tools.candidates[0].content)
        response_parts, paso_trace = _ejecutar_tool_calls(function_calls)
        trace.extend(paso_trace)
        contents.append(types.Content(role="user", parts=response_parts))

    # --- Fase 2: Structured Output --------------------------------------
    respuesta_2 = _generar(
        contents,
        response_mime_type="application/json",
        response_schema=RespuestaFinal,
    )

    final: RespuestaFinal = respuesta_2.parsed
    return {
        "respuesta": final.respuesta,
        "datos_clave": final.datos_clave,
        "trace": trace,
    }
