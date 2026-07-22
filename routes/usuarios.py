from functools import wraps

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import generate_password_hash

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
    # LISTAR USUÁRIOS
    # ======================================================

    @app.route("/usuarios")
    @somente_administrador
    def listar_usuarios():

        conexao = conectar()

        try:

            usuarios = conexao.execute("""
                SELECT
                    id,
                    nome,
                    email,
                    perfil,
                    ativo
                FROM usuarios
                ORDER BY nome
            """).fetchall()

            return render_template(
                "usuarios.html",
                usuarios=usuarios
            )

        finally:

            conexao.close()


    # ======================================================
    # NOVO USUÁRIO
    # ======================================================

    @app.route("/novo-usuario", methods=["GET", "POST"])
    @somente_administrador
    def novo_usuario():

        if request.method == "POST":

            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip().lower()
            senha = request.form.get("senha", "")
            perfil = request.form.get("perfil", "").strip()
            ativo = 1 if request.form.get("ativo") else 0

            if not nome or not email or not senha or not perfil:

                flash(
                    "Preencha todos os campos obrigatórios.",
                    "erro"
                )

                return render_template(
                    "novo_usuario.html",
                    nome=nome,
                    email=email,
                    perfil=perfil,
                    ativo=ativo
                )

            if perfil not in [
                "Administrador",
                "Gerente",
                "Enfermeiro"
            ]:

                flash(
                    "O perfil selecionado é inválido.",
                    "erro"
                )

                return render_template(
                    "novo_usuario.html",
                    nome=nome,
                    email=email,
                    perfil=perfil,
                    ativo=ativo
                )

            conexao = conectar()

            try:

                usuario_existente = conexao.execute("""
                    SELECT id
                    FROM usuarios
                    WHERE LOWER(email) = LOWER(?)
                """, (email,)).fetchone()

                if usuario_existente:

                    flash(
                        "Já existe um usuário cadastrado com este e-mail.",
                        "erro"
                    )

                    return render_template(
                        "novo_usuario.html",
                        nome=nome,
                        email=email,
                        perfil=perfil,
                        ativo=ativo
                    )

                senha_hash = generate_password_hash(senha)

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
                    nome,
                    email,
                    senha_hash,
                    perfil,
                    ativo
                ))

                conexao.commit()

                flash(
                    "Usuário cadastrado com sucesso.",
                    "sucesso"
                )

                return redirect(url_for("listar_usuarios"))

            finally:

                conexao.close()

        return render_template(
            "novo_usuario.html"
        )


    # ======================================================
    # EDITAR USUÁRIO
    # ======================================================

    @app.route("/editar-usuario/<int:id>", methods=["GET", "POST"])
    @somente_administrador
    def editar_usuario(id):

        conexao = conectar()

        try:

            usuario = conexao.execute("""
                SELECT
                    id,
                    nome,
                    email,
                    perfil,
                    ativo
                FROM usuarios
                WHERE id = ?
            """, (id,)).fetchone()

            if usuario is None:

                return "Usuário não encontrado.", 404

            if request.method == "POST":

                nome = request.form.get("nome", "").strip()
                email = request.form.get("email", "").strip().lower()
                perfil = request.form.get("perfil", "").strip()
                ativo = 1 if request.form.get("ativo") else 0

                if not nome or not email or not perfil:

                    flash(
                        "Preencha todos os campos obrigatórios.",
                        "erro"
                    )

                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario
                    )

                if perfil not in [
                    "Administrador",
                    "Gerente",
                    "Enfermeiro"
                ]:

                    flash(
                        "O perfil selecionado é inválido.",
                        "erro"
                    )

                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario
                    )

                email_existente = conexao.execute("""
                    SELECT id
                    FROM usuarios
                    WHERE LOWER(email) = LOWER(?)
                      AND id != ?
                """, (
                    email,
                    id
                )).fetchone()

                if email_existente:

                    flash(
                        "Já existe outro usuário cadastrado com este e-mail.",
                        "erro"
                    )

                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario
                    )

                usuario_logado_id = session.get("usuario_id")

                if id == usuario_logado_id and ativo == 0:

                    flash(
                        "Você não pode desativar o próprio usuário.",
                        "erro"
                    )

                    return redirect(
                        url_for(
                            "editar_usuario",
                            id=id
                        )
                    )

                if id == usuario_logado_id and perfil != "Administrador":

                    flash(
                        "Você não pode retirar o próprio perfil de administrador.",
                        "erro"
                    )

                    return redirect(
                        url_for(
                            "editar_usuario",
                            id=id
                        )
                    )

                conexao.execute("""
                    UPDATE usuarios
                    SET
                        nome = ?,
                        email = ?,
                        perfil = ?,
                        ativo = ?
                    WHERE id = ?
                """, (
                    nome,
                    email,
                    perfil,
                    ativo,
                    id
                ))

                conexao.commit()

                if id == usuario_logado_id:

                    session["usuario_nome"] = nome
                    session["usuario_perfil"] = perfil

                flash(
                    "Usuário atualizado com sucesso.",
                    "sucesso"
                )

                return redirect(url_for("listar_usuarios"))

            return render_template(
                "editar_usuario.html",
                usuario=usuario
            )

        finally:

            conexao.close()


    # ======================================================
    # ALTERAR SENHA
    # ======================================================

    @app.route("/alterar-senha-usuario/<int:id>", methods=["GET", "POST"])
    @somente_administrador
    def alterar_senha_usuario(id):

        conexao = conectar()

        try:

            usuario = conexao.execute("""
                SELECT
                    id,
                    nome,
                    email
                FROM usuarios
                WHERE id = ?
            """, (id,)).fetchone()

            if usuario is None:

                return "Usuário não encontrado.", 404

            if request.method == "POST":

                nova_senha = request.form.get("nova_senha", "")
                confirmar_senha = request.form.get(
                    "confirmar_senha",
                    ""
                )

                if not nova_senha:

                    flash(
                        "Informe a nova senha.",
                        "erro"
                    )

                    return render_template(
                        "alterar_senha_usuario.html",
                        usuario=usuario
                    )

                if len(nova_senha) < 6:

                    flash(
                        "A senha deve possuir pelo menos 6 caracteres.",
                        "erro"
                    )

                    return render_template(
                        "alterar_senha_usuario.html",
                        usuario=usuario
                    )

                if nova_senha != confirmar_senha:

                    flash(
                        "As senhas informadas não são iguais.",
                        "erro"
                    )

                    return render_template(
                        "alterar_senha_usuario.html",
                        usuario=usuario
                    )

                senha_hash = generate_password_hash(nova_senha)

                conexao.execute("""
                    UPDATE usuarios
                    SET senha = ?
                    WHERE id = ?
                """, (
                    senha_hash,
                    id
                ))

                conexao.commit()

                flash(
                    "Senha alterada com sucesso.",
                    "sucesso"
                )

                return redirect(url_for("listar_usuarios"))

            return render_template(
                "alterar_senha_usuario.html",
                usuario=usuario
            )

        finally:

            conexao.close()


    # ======================================================
    # ATIVAR OU DESATIVAR USUÁRIO
    # ======================================================

    @app.route("/alterar-status-usuario/<int:id>")
    @somente_administrador
    def alterar_status_usuario(id):

        usuario_logado_id = session.get("usuario_id")

        if id == usuario_logado_id:

            flash(
                "Você não pode desativar o próprio usuário.",
                "erro"
            )

            return redirect(url_for("listar_usuarios"))

        conexao = conectar()

        try:

            usuario = conexao.execute("""
                SELECT
                    id,
                    ativo
                FROM usuarios
                WHERE id = ?
            """, (id,)).fetchone()

            if usuario is None:

                return "Usuário não encontrado.", 404

            novo_status = 0 if usuario["ativo"] == 1 else 1

            conexao.execute("""
                UPDATE usuarios
                SET ativo = ?
                WHERE id = ?
            """, (
                novo_status,
                id
            ))

            conexao.commit()

            if novo_status == 1:

                mensagem = "Usuário ativado com sucesso."

            else:

                mensagem = "Usuário desativado com sucesso."

            flash(
                mensagem,
                "sucesso"
            )

            return redirect(url_for("listar_usuarios"))

        finally:

            conexao.close()


    # ======================================================
    # EXCLUIR USUÁRIO
    # ======================================================

    @app.route("/excluir-usuario/<int:id>")
    @somente_administrador
    def excluir_usuario(id):

        usuario_logado_id = session.get("usuario_id")

        if id == usuario_logado_id:

            flash(
                "Você não pode excluir o próprio usuário.",
                "erro"
            )

            return redirect(url_for("listar_usuarios"))

        conexao = conectar()

        try:

            usuario = conexao.execute("""
                SELECT
                    id,
                    nome
                FROM usuarios
                WHERE id = ?
            """, (id,)).fetchone()

            if usuario is None:

                return "Usuário não encontrado.", 404

            conexao.execute("""
                DELETE FROM usuarios
                WHERE id = ?
            """, (id,))

            conexao.commit()

            flash(
                "Usuário excluído com sucesso.",
                "sucesso"
            )

            return redirect(url_for("listar_usuarios"))

        finally:

            conexao.close()