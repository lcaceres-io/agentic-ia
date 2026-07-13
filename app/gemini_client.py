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

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL
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
        respuesta_tools = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[TOOLS],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        function_calls = respuesta_tools.function_calls
        if not function_calls:
            break

        contents.append(respuesta_tools.candidates[0].content)
        response_parts, paso_trace = _ejecutar_tool_calls(function_calls)
        trace.extend(paso_trace)
        contents.append(types.Content(role="user", parts=response_parts))

    # --- Fase 2: Structured Output --------------------------------------
    respuesta_2 = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=RespuestaFinal,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    final: RespuestaFinal = respuesta_2.parsed
    return {
        "respuesta": final.respuesta,
        "datos_clave": final.datos_clave,
        "trace": trace,
    }
