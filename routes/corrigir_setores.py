import sqlite3


BANCO = "sgrg.db"


SETORES_OFICIAIS = [
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


def corrigir_setores():

    conexao = sqlite3.connect(BANCO)

    try:

        conexao.execute("PRAGMA foreign_keys = ON")

        setores_utilizados = conexao.execute("""
            SELECT DISTINCT setor_id
            FROM rondas
        """).fetchall()

        ids_utilizados = {
            setor[0]
            for setor in setores_utilizados
        }

        setores_atuais = conexao.execute("""
            SELECT id, nome
            FROM setores
        """).fetchall()

        nomes_oficiais_normalizados = {
            nome.strip().lower()
            for nome in SETORES_OFICIAIS
        }

        for setor_id, nome in setores_atuais:

            nome_normalizado = nome.strip().lower()

            if nome_normalizado not in nomes_oficiais_normalizados:

                if setor_id in ids_utilizados:

                    conexao.execute("""
                        UPDATE setores
                        SET ativo = 0
                        WHERE id = ?
                    """, (
                        setor_id,
                    ))

                else:

                    conexao.execute("""
                        DELETE FROM setores
                        WHERE id = ?
                    """, (
                        setor_id,
                    ))

        for nome_setor in SETORES_OFICIAIS:

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
                    VALUES (?, 1)
                """, (
                    nome_setor,
                ))

            else:

                conexao.execute("""
                    UPDATE setores
                    SET
                        nome = ?,
                        ativo = 1
                    WHERE id = ?
                """, (
                    nome_setor,
                    setor_existente[0]
                ))

        conexao.commit()

        print("Setores corrigidos com sucesso.")
        print("Somente os 10 setores oficiais permanecerão ativos.")

    except sqlite3.Error as erro:

        conexao.rollback()

        print(
            f"Erro ao corrigir os setores: {erro}"
        )

    finally:

        conexao.close()


if __name__ == "__main__":

    corrigir_setores()