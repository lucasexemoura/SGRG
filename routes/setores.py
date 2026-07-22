from functools import wraps

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from database.conexao import conectar


def registrar_rotas(app):

    # ======================================================
    # PROTEÇÃO DAS ROTAS ADMINISTRATIVAS
    # ======================================================

    def somente_administrador(funcao):

        @wraps(funcao)
        def verificar_permissao(*args, **kwargs):

            if session.get("usuario_perfil") != "Administrador":

                flash(
                    "Você não possui permissão para acessar esta página.",
                    "erro"
                )

                return redirect(url_for("inicio"))

            return funcao(*args, **kwargs)

        return verificar_permissao


    # ======================================================
    # LISTAR SETORES
    # ======================================================

    @app.route("/setores")
    @somente_administrador
    def listar_setores():

        conexao = conectar()

        try:

            setores = conexao.execute("""
                SELECT
                    id,
                    nome,
                    ativo
                FROM setores
                ORDER BY nome
            """).fetchall()

            return render_template(
                "setores.html",
                setores=setores
            )

        finally:

            conexao.close()


    # ======================================================
    # NOVO SETOR
    # ======================================================

    @app.route("/novo-setor", methods=["GET", "POST"])
    @somente_administrador
    def novo_setor():

        if request.method == "POST":

            nome = request.form.get("nome", "").strip()
            ativo = bool(request.form.get("ativo"))

            if not nome:

                flash(
                    "Informe o nome do setor.",
                    "erro"
                )

                return render_template(
                    "novo_setor.html",
                    nome=nome,
                    ativo=ativo
                )

            conexao = conectar()

            try:

                setor_existente = conexao.execute("""
                    SELECT id
                    FROM setores
                    WHERE LOWER(nome) = LOWER(?)
                """, (nome,)).fetchone()

                if setor_existente:

                    flash(
                        "Já existe um setor cadastrado com este nome.",
                        "erro"
                    )

                    return render_template(
                        "novo_setor.html",
                        nome=nome,
                        ativo=ativo
                    )

                conexao.execute("""
                    INSERT INTO setores (
                        nome,
                        ativo
                    )
                    VALUES (?, ?)
                """, (
                    nome,
                    ativo
                ))

                conexao.commit()

                flash(
                    "Setor cadastrado com sucesso.",
                    "sucesso"
                )

                return redirect(url_for("listar_setores"))

            finally:

                conexao.close()

        return render_template(
            "novo_setor.html"
        )


    # ======================================================
    # EDITAR SETOR
    # ======================================================

    @app.route("/editar-setor/<int:id>", methods=["GET", "POST"])
    @somente_administrador
    def editar_setor(id):

        conexao = conectar()

        try:

            setor = conexao.execute("""
                SELECT
                    id,
                    nome,
                    ativo
                FROM setores
                WHERE id = ?
            """, (id,)).fetchone()

            if setor is None:

                return "Setor não encontrado.", 404

            if request.method == "POST":

                nome = request.form.get("nome", "").strip()
                ativo = bool(request.form.get("ativo"))

                if not nome:

                    flash(
                        "Informe o nome do setor.",
                        "erro"
                    )

                    return render_template(
                        "editar_setor.html",
                        setor=setor
                    )

                setor_existente = conexao.execute("""
                    SELECT id
                    FROM setores
                    WHERE LOWER(nome) = LOWER(?)
                      AND id != ?
                """, (
                    nome,
                    id
                )).fetchone()

                if setor_existente:

                    flash(
                        "Já existe outro setor cadastrado com este nome.",
                        "erro"
                    )

                    return render_template(
                        "editar_setor.html",
                        setor=setor
                    )

                conexao.execute("""
                    UPDATE setores
                    SET
                        nome = ?,
                        ativo = ?
                    WHERE id = ?
                """, (
                    nome,
                    ativo,
                    id
                ))

                conexao.commit()

                flash(
                    "Setor atualizado com sucesso.",
                    "sucesso"
                )

                return redirect(url_for("listar_setores"))

            return render_template(
                "editar_setor.html",
                setor=setor
            )

        finally:

            conexao.close()


    # ======================================================
    # ATIVAR OU DESATIVAR SETOR
    # ======================================================

    @app.route("/alterar-status-setor/<int:id>")
    @somente_administrador
    def alterar_status_setor(id):

        conexao = conectar()

        try:

            setor = conexao.execute("""
                SELECT
                    id,
                    ativo
                FROM setores
                WHERE id = ?
            """, (id,)).fetchone()

            if setor is None:

                return "Setor não encontrado.", 404

            novo_status = not bool(setor["ativo"])

            conexao.execute("""
                UPDATE setores
                SET ativo = ?
                WHERE id = ?
            """, (
                novo_status,
                id
            ))

            conexao.commit()

            if novo_status:

                mensagem = "Setor ativado com sucesso."

            else:

                mensagem = "Setor desativado com sucesso."

            flash(
                mensagem,
                "sucesso"
            )

            return redirect(url_for("listar_setores"))

        finally:

            conexao.close()


    # ======================================================
    # EXCLUIR SETOR
    # ======================================================

    @app.route("/excluir-setor/<int:id>")
    @somente_administrador
    def excluir_setor(id):

        conexao = conectar()

        try:

            setor = conexao.execute("""
                SELECT
                    id,
                    nome
                FROM setores
                WHERE id = ?
            """, (id,)).fetchone()

            if setor is None:

                return "Setor não encontrado.", 404

            possui_rondas = conexao.execute("""
                SELECT id
                FROM rondas
                WHERE setor_id = ?
                LIMIT 1
            """, (id,)).fetchone()

            if possui_rondas:

                flash(
                    "Este setor possui rondas vinculadas e não pode ser excluído. Desative-o.",
                    "erro"
                )

                return redirect(url_for("listar_setores"))

            conexao.execute("""
                DELETE FROM setores
                WHERE id = ?
            """, (id,))

            conexao.commit()

            flash(
                "Setor excluído com sucesso.",
                "sucesso"
            )

            return redirect(url_for("listar_setores"))

        finally:

            conexao.close()