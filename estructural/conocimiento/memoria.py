"""Memoria persistente del agente: normas, criterios y lecciones aprendidas (SQLite).

En producción (Railway) se reemplaza por PostgreSQL con la misma interfaz.
"""
import sqlite3


class Memoria:
    def __init__(self, ruta: str = "memoria.db"):
        self.db = sqlite3.connect(ruta)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS conocimiento ("
            "id INTEGER PRIMARY KEY, norma TEXT, tema TEXT, contenido TEXT, fuente TEXT,"
            "verificado INTEGER DEFAULT 0)"
        )

    def guardar(self, norma: str, tema: str, contenido: str, fuente: str = "") -> int:
        cur = self.db.execute(
            "INSERT INTO conocimiento (norma, tema, contenido, fuente) VALUES (?,?,?,?)",
            (norma, tema, contenido, fuente),
        )
        self.db.commit()
        return cur.lastrowid

    def verificar(self, id_: int) -> None:
        """Un ingeniero marca una entrada como revisada."""
        self.db.execute("UPDATE conocimiento SET verificado=1 WHERE id=?", (id_,))
        self.db.commit()

    def buscar(self, texto: str, solo_verificado: bool = False) -> list[dict]:
        q = "SELECT id, norma, tema, contenido, fuente, verificado FROM conocimiento WHERE (tema LIKE ? OR contenido LIKE ? OR norma LIKE ?)"
        if solo_verificado:
            q += " AND verificado=1"
        like = f"%{texto}%"
        cols = ("id", "norma", "tema", "contenido", "fuente", "verificado")
        return [dict(zip(cols, r)) for r in self.db.execute(q, (like, like, like))]
