import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "academia.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL,
            carrera TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            carrera TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY,
            alumno_id INTEGER NOT NULL REFERENCES alumnos(id),
            materia_id INTEGER NOT NULL REFERENCES materias(id),
            nota REAL NOT NULL,
            fecha TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS asistencias (
            id INTEGER PRIMARY KEY,
            alumno_id INTEGER NOT NULL REFERENCES alumnos(id),
            materia_id INTEGER NOT NULL REFERENCES materias(id),
            fecha TEXT NOT NULL,
            presente INTEGER NOT NULL
        );
        """
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM alumnos")
    if cur.fetchone()[0] == 0:
        _seed(cur)
        conn.commit()

    conn.close()


def _seed(cur: sqlite3.Cursor) -> None:
    cur.executemany(
        "INSERT INTO alumnos (id, nombre, email, carrera) VALUES (?, ?, ?, ?)",
        [
            (1, "Lucas Caceres", "lcaceres@uade.edu.ar", "Ingenieria en Informatica"),
            (2, "Martina Gomez", "mgomez@uade.edu.ar", "Ingenieria en Informatica"),
            (3, "Juan Perez", "jperez@uade.edu.ar", "Analista de Sistemas"),
        ],
    )

    cur.executemany(
        "INSERT INTO materias (id, nombre, carrera) VALUES (?, ?, ?)",
        [
            (1, "Matematica", "Ingenieria en Informatica"),
            (2, "Fisica", "Ingenieria en Informatica"),
            (3, "Programacion II", "Ingenieria en Informatica"),
            (4, "Bases de Datos", "Analista de Sistemas"),
        ],
    )

    cur.executemany(
        "INSERT INTO notas (id, alumno_id, materia_id, nota, fecha) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, 1, 8, "2026-05-10"),
            (2, 1, 2, 9, "2026-05-20"),
            (3, 1, 3, 7, "2026-06-01"),
            (4, 2, 1, 6, "2026-05-10"),
            (5, 2, 3, 8, "2026-06-01"),
            (6, 3, 4, 9, "2026-05-15"),
        ],
    )

    cur.executemany(
        "INSERT INTO asistencias (id, alumno_id, materia_id, fecha, presente) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, 1, "2026-05-01", 1),
            (2, 1, 1, "2026-05-08", 1),
            (3, 1, 1, "2026-05-15", 0),
            (4, 1, 3, "2026-06-01", 1),
            (5, 2, 1, "2026-05-01", 1),
            (6, 2, 1, "2026-05-08", 0),
        ],
    )
