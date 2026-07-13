from pydantic import BaseModel, Field


class RespuestaFinal(BaseModel):
    """Esquema de Structured Output: el modelo esta obligado a devolver JSON con esta forma."""

    respuesta: str = Field(
        description="Respuesta final para el alumno, en tono claro, breve y cordial."
    )
    datos_clave: list[str] = Field(
        default_factory=list,
        description=(
            "Lista breve de datos concretos mencionados en la respuesta "
            "(ej: '8 en Matematica', '90% de asistencia')."
        ),
    )
