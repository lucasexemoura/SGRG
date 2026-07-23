import os
from dotenv import load_dotenv

load_dotenv()

import sqlite3

import psycopg2
from psycopg2.extras import DictCursor


DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_DATABASE = "sgrg.db"


class ConexaoPostgres:

    def __init__(self, conexao):
        self._conexao = conexao

    def execute(self, consulta, parametros=None):

        # Converte os placeholders do SQLite para PostgreSQL
        consulta = consulta.replace("?", "%s")

        cursor = self._conexao.cursor(
            cursor_factory=DictCursor
        )

        cursor.execute(
            consulta,
            parametros or ()
        )

        return cursor

    def cursor(self):
        return self._conexao.cursor(
            cursor_factory=DictCursor
        )

    def commit(self):
        self._conexao.commit()

    def rollback(self):
        self._conexao.rollback()

    def close(self):
        self._conexao.close()


def conectar():

    if DATABASE_URL:

        print("=" * 60)
        print("USANDO POSTGRESQL")
        print("=" * 60)

        conexao = psycopg2.connect(
            DATABASE_URL
        )

        return ConexaoPostgres(conexao)

    print("=" * 60)
    print("USANDO SQLITE")
    print("=" * 60)

    conexao = sqlite3.connect(
        SQLITE_DATABASE
    )

    conexao.row_factory = sqlite3.Row

    return conexao