"""
Tools (funciones) que el LLM puede decidir invocar.

Cada tool es una funcion Python normal que consulta la base SQLite.
El modelo NUNCA ejecuta estas funciones: solo indica "quiero llamar a X con
estos argumentos" y es este modulo, controlado por nuestra aplicacion, el
que realmente las corre (ver gemini_client.py).
"""

from google.genai import types

from app.database import get_connection


def buscar_alumno(nombre: str) -> dict:
    """Busca un alumno por nombre (busqueda parcial, sin importar mayusculas)."""
    conn = get_connection()
    fila = conn.execute(
        "SELECT id, nombre, email, carrera FROM alumnos WHERE nombre LIKE ?",
        (f"%{nombre}%",),
    ).fetchone()
    conn.close()

    if fila is None:
        return {"error": f"No se encontro ningun alumno que coincida con '{nombre}'."}
    return dict(fila)


def obtener_notas(id_alumno: int) -> dict:
    """Devuelve todas las notas registradas de un alumno, con el nombre de cada materia."""
    conn = get_connection()
    filas = conn.execute(
        """
        SELECT m.nombre AS materia, n.nota, n.fecha
        FROM notas n
        JOIN materias m ON m.id = n.materia_id
        WHERE n.alumno_id = ?
        ORDER BY n.fecha
        """,
        (id_alumno,),
    ).fetchall()
    conn.close()

    if not filas:
        return {"error": f"El alumno {id_alumno} no tiene notas cargadas."}
    return {"id_alumno": id_alumno, "notas": [dict(f) for f in filas]}


def obtener_promedio(id_alumno: int) -> dict:
    """Calcula el promedio general de notas de un alumno."""
    conn = get_connection()
    fila = conn.execute(
        "SELECT AVG(nota) AS promedio, COUNT(*) AS cantidad_notas FROM notas WHERE alumno_id = ?",
        (id_alumno,),
    ).fetchone()
    conn.close()

    if fila["cantidad_notas"] == 0:
        return {"error": f"El alumno {id_alumno} no tiene notas cargadas."}
    return {
        "id_alumno": id_alumno,
        "promedio": round(fila["promedio"], 2),
        "cantidad_notas": fila["cantidad_notas"],
    }


def obtener_asistencia(id_alumno: int, materia: str | None = None) -> dict:
    """Calcula el porcentaje de asistencia de un alumno, opcionalmente filtrado por materia."""
    conn = get_connection()
    query = """
        SELECT m.nombre AS materia, a.presente
        FROM asistencias a
        JOIN materias m ON m.id = a.materia_id
        WHERE a.alumno_id = ?
    """
    params: list = [id_alumno]
    if materia:
        query += " AND m.nombre LIKE ?"
        params.append(f"%{materia}%")

    filas = conn.execute(query, params).fetchall()
    conn.close()

    if not filas:
        return {"error": f"No hay registros de asistencia para el alumno {id_alumno}."}

    total = len(filas)
    presentes = sum(f["presente"] for f in filas)
    return {
        "id_alumno": id_alumno,
        "materia": materia or "todas",
        "porcentaje_asistencia": round(presentes / total * 100, 1),
        "clases_totales": total,
        "clases_presente": presentes,
    }


def listar_materias(carrera: str | None = None) -> dict:
    """Lista las materias disponibles, opcionalmente filtradas por carrera."""
    conn = get_connection()
    if carrera:
        filas = conn.execute(
            "SELECT id, nombre, carrera FROM materias WHERE carrera LIKE ?",
            (f"%{carrera}%",),
        ).fetchall()
    else:
        filas = conn.execute("SELECT id, nombre, carrera FROM materias").fetchall()
    conn.close()

    return {"materias": [dict(f) for f in filas]}


# Despachador: nombre de la tool (tal cual lo ve el modelo) -> funcion Python real
DISPATCH = {
    "buscar_alumno": buscar_alumno,
    "obtener_notas": obtener_notas,
    "obtener_promedio": obtener_promedio,
    "obtener_asistencia": obtener_asistencia,
    "listar_materias": listar_materias,
}


# Declaraciones de las tools en el formato que espera la API de Gemini.
# Esto es lo que se le "muestra" al modelo para que sepa que herramientas
# tiene disponibles, sin darle acceso directo a la base de datos.
TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="buscar_alumno",
            description=(
                "Busca un alumno por nombre y devuelve su id, email y carrera. "
                "Usar esta tool primero cuando el usuario menciona un nombre pero "
                "no se conoce el id_alumno."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "nombre": types.Schema(
                        type="STRING", description="Nombre (total o parcial) del alumno."
                    )
                },
                required=["nombre"],
            ),
        ),
        types.FunctionDeclaration(
            name="obtener_notas",
            description="Devuelve todas las notas de un alumno, materia por materia.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "id_alumno": types.Schema(
                        type="INTEGER", description="Id numerico del alumno."
                    )
                },
                required=["id_alumno"],
            ),
        ),
        types.FunctionDeclaration(
            name="obtener_promedio",
            description="Calcula el promedio general de notas de un alumno.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "id_alumno": types.Schema(
                        type="INTEGER", description="Id numerico del alumno."
                    )
                },
                required=["id_alumno"],
            ),
        ),
        types.FunctionDeclaration(
            name="obtener_asistencia",
            description=(
                "Calcula el porcentaje de asistencia de un alumno. "
                "Se puede filtrar por materia."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "id_alumno": types.Schema(
                        type="INTEGER", description="Id numerico del alumno."
                    ),
                    "materia": types.Schema(
                        type="STRING",
                        description="Nombre de la materia para filtrar (opcional).",
                    ),
                },
                required=["id_alumno"],
            ),
        ),
        types.FunctionDeclaration(
            name="listar_materias",
            description="Lista las materias disponibles, opcionalmente filtradas por carrera.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "carrera": types.Schema(
                        type="STRING",
                        description="Nombre de la carrera para filtrar (opcional).",
                    )
                },
            ),
        ),
    ]
)
