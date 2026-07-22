from flask import render_template, request
from database.conexao import conectar


def registrar_rotas(app):

    @app.route("/historico")
    def historico():

        pesquisa = request.args.get("pesquisa", "").strip()

        conexao = conectar()

        try:

            parametros = []
            filtro = ""

            if pesquisa:

                filtro = """
                    WHERE
                        setores.nome LIKE ?
                        OR rondas.responsavel LIKE ?
                        OR rondas.data LIKE ?
                        OR rondas.hora LIKE ?
                """

                termo = f"%{pesquisa}%"

                parametros = [
                    termo,
                    termo,
                    termo,
                    termo
                ]

            rondas = conexao.execute(f"""
                SELECT
                    rondas.id,
                    rondas.data,
                    rondas.hora,
                    rondas.responsavel,
                    setores.nome AS setor
                FROM rondas
                INNER JOIN setores
                    ON setores.id = rondas.setor_id
                {filtro}
                ORDER BY
                    rondas.data DESC,
                    rondas.hora DESC,
                    rondas.id DESC
            """, parametros).fetchall()

            return render_template(
                "historico.html",
                rondas=rondas,
                pesquisa=pesquisa
            )

        finally:

            conexao.close()