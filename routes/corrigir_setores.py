from database.conexao import conectar


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

    conexao = conectar()

    try:

        setores_utilizados = conexao.execute("""
            SELECT DISTINCT setor_id
            FROM rondas
        """).fetchall()

        ids_utilizados = {
            setor["setor_id"]
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

        for setor in setores_atuais:

            setor_id = setor["id"]
            nome = setor["nome"]
            nome_normalizado = nome.strip().lower()

            if nome_normalizado not in nomes_oficiais_normalizados:

                if setor_id in ids_utilizados:

                    conexao.execute("""
                        UPDATE setores
                        SET ativo = FALSE
                        WHERE id = ?
                    """, (setor_id,))

                else:

                    conexao.execute("""
                        DELETE FROM setores
                        WHERE id = ?
                    """, (setor_id,))

        for nome_setor in SETORES_OFICIAIS:

            setor_existente = conexao.execute("""
                SELECT id
                FROM setores
                WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """, (nome_setor,)).fetchone()

            if setor_existente is None:

                conexao.execute("""
                    INSERT INTO setores (nome, ativo)
                    VALUES (?, TRUE)
                """, (nome_setor,))

            else:

                conexao.execute("""
                    UPDATE setores
                    SET nome = ?, ativo = TRUE
                    WHERE id = ?
                """, (
                    nome_setor,
                    setor_existente["id"]
                ))

        conexao.commit()

        print("Setores corrigidos com sucesso.")
        print("Somente os 10 setores oficiais permanecerão ativos.")

    except Exception as erro:

        conexao.rollback()
        print(f"Erro ao corrigir os setores: {erro}")
        raise

    finally:

        conexao.close()


if __name__ == "__main__":

    corrigir_setores()
