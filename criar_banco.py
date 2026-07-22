import sqlite3

from werkzeug.security import generate_password_hash


BANCO = "sgrg.db"


SETORES_PADRAO = [
    "Classificação de Risco",
    "Centro Obstétrico",
    "Observação Clínica",
    "Centro de Material e Esterilização (CME)",
    "Centro Cirúrgico (CC)",
    "Alojamento Conjunto (ALCON)",
    "UTI Neonatal",
    "UCINCa",
    "Clínica Cirúrgica",
    "Clínica Ginecológica"
]


def coluna_existe(conexao, tabela, coluna):

    colunas = conexao.execute(
        f"PRAGMA table_info({tabela})"
    ).fetchall()

    return any(
        item[1] == coluna
        for item in colunas
    )


def adicionar_coluna(
    conexao,
    tabela,
    coluna,
    definicao
):

    if not coluna_existe(
        conexao,
        tabela,
        coluna
    ):

        conexao.execute(
            f"""
            ALTER TABLE {tabela}
            ADD COLUMN {coluna} {definicao}
            """
        )


def cadastrar_setores_padrao(conexao):

    # Remove todos os setores cadastrados
    conexao.execute("""
        DELETE FROM setores
    """)

    # Reinicia a numeração dos IDs (opcional)
    conexao.execute("""
        DELETE FROM sqlite_sequence
        WHERE name = 'setores'
    """)

    # Cadastra somente os setores oficiais
    for nome_setor in SETORES_PADRAO:

        conexao.execute("""
            INSERT INTO setores (
                nome,
                ativo
            )
            VALUES (?, ?)
        """, (
            nome_setor,
            1
        ))

    for nome_setor in SETORES_PADRAO:

        setor_existente = conexao.execute("""
            SELECT id
            FROM setores
            WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
        """, (
            nome_setor,
        )).fetchone()

        if setor_existente is None:

            conexao.execute("""
                INSERT INTO setores (
                    nome,
                    ativo
                )
                VALUES (?, ?)
            """, (
                nome_setor,
                1
            ))

        else:

            conexao.execute("""
                UPDATE setores
                SET ativo = 1
                WHERE id = ?
            """, (
                setor_existente[0],
            ))


def criar_banco():

    conexao = sqlite3.connect(BANCO)

    try:

        conexao.execute(
            "PRAGMA foreign_keys = ON"
        )

        # ==================================================
        # TABELA DE SETORES
        # ==================================================

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS setores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)

        adicionar_coluna(
            conexao,
            "setores",
            "ativo",
            "INTEGER NOT NULL DEFAULT 1"
        )

        cadastrar_setores_padrao(conexao)

        # ==================================================
        # TABELA DE RONDAS
        # ==================================================

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS rondas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setor_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                hora TEXT NOT NULL,
                responsavel TEXT NOT NULL,
                observacoes TEXT,
                FOREIGN KEY (setor_id)
                    REFERENCES setores(id)
            )
        """)

        # ==================================================
        # TABELA DE PENDÊNCIAS
        # ==================================================

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS pendencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ronda_id INTEGER NOT NULL,
                descricao TEXT NOT NULL,
                categoria TEXT,
                prioridade TEXT NOT NULL DEFAULT 'Baixa',
                status TEXT NOT NULL DEFAULT 'Aberta',
                responsavel TEXT,
                prazo TEXT,
                observacao_resolucao TEXT,
                foto_antes TEXT,
                foto_depois TEXT,
                FOREIGN KEY (ronda_id)
                    REFERENCES rondas(id)
                    ON DELETE CASCADE
            )
        """)

        adicionar_coluna(
            conexao,
            "pendencias",
            "observacao_resolucao",
            "TEXT"
        )

        adicionar_coluna(
            conexao,
            "pendencias",
            "foto_antes",
            "TEXT"
        )

        adicionar_coluna(
            conexao,
            "pendencias",
            "foto_depois",
            "TEXT"
        )

        # ==================================================
        # TABELA DE USUÁRIOS
        # ==================================================

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                perfil TEXT NOT NULL DEFAULT 'Enfermeiro',
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)

        adicionar_coluna(
            conexao,
            "usuarios",
            "perfil",
            "TEXT NOT NULL DEFAULT 'Enfermeiro'"
        )

        adicionar_coluna(
            conexao,
            "usuarios",
            "ativo",
            "INTEGER NOT NULL DEFAULT 1"
        )

        # ==================================================
        # ADMINISTRADOR PADRÃO
        # ==================================================

        administrador = conexao.execute("""
            SELECT id
            FROM usuarios
            WHERE LOWER(email) = LOWER(?)
        """, (
            "admin@sgrg.com",
        )).fetchone()

        if administrador is None:

            senha_hash = generate_password_hash(
                "123456"
            )

            conexao.execute("""
                INSERT INTO usuarios (
                    nome,
                    email,
                    senha,
                    perfil,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                "Administrador",
                "admin@sgrg.com",
                senha_hash,
                "Administrador",
                1
            ))

        # ==================================================
        # ÍNDICES
        # ==================================================

        conexao.execute("""
            CREATE INDEX IF NOT EXISTS
            indice_rondas_setor
            ON rondas(setor_id)
        """)

        conexao.execute("""
            CREATE INDEX IF NOT EXISTS
            indice_rondas_data
            ON rondas(data)
        """)

        conexao.execute("""
            CREATE INDEX IF NOT EXISTS
            indice_pendencias_ronda
            ON pendencias(ronda_id)
        """)

        conexao.execute("""
            CREATE INDEX IF NOT EXISTS
            indice_pendencias_status
            ON pendencias(status)
        """)

        conexao.execute("""
            CREATE INDEX IF NOT EXISTS
            indice_pendencias_prazo
            ON pendencias(prazo)
        """)

        conexao.commit()

        print(
            "Banco de dados criado e atualizado com sucesso."
        )

        print(
            "Setores da maternidade cadastrados com sucesso."
        )

    except sqlite3.Error as erro:

        conexao.rollback()

        print(
            f"Erro ao criar ou atualizar o banco: {erro}"
        )

    finally:

        conexao.close()


if __name__ == "__main__":

    criar_banco()