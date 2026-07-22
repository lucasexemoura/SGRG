from functools import wraps

from flask import (
    render_template,
    request,
    redirect,
    session,
    url_for
)

from werkzeug.security import check_password_hash

from database.conexao import conectar


def login_obrigatorio(funcao):

    @wraps(funcao)
    def funcao_protegida(*args, **kwargs):

        if "usuario_id" not in session:

            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return funcao_protegida


def registrar_rotas(app):

    # ==========================================
    # PROTEÇÃO GLOBAL DAS ROTAS
    # ==========================================

    @app.before_request
    def proteger_rotas():

        rotas_livres = [
            "login",
            "static"
        ]

        if request.endpoint is None:

            return None

        if request.endpoint in rotas_livres:

            return None

        if "usuario_id" not in session:

            return redirect(url_for("login"))

        return None

    # ==========================================
    # DADOS DO USUÁRIO NOS TEMPLATES
    # ==========================================

    @app.context_processor
    def dados_usuario():

        return {
            "usuario_nome": session.get("usuario_nome"),
            "usuario_perfil": session.get("usuario_perfil")
        }

    # ==========================================
    # LOGIN
    # ==========================================

    @app.route("/login", methods=["GET", "POST"])
    def login():

        if "usuario_id" in session:

            return redirect(url_for("inicio"))

        erro = None

        if request.method == "POST":

            email = request.form.get("email", "").strip().lower()
            senha = request.form.get("senha", "")

            conexao = conectar()

            usuario = conexao.execute("""
                SELECT
                    id,
                    nome,
                    email,
                    senha,
                    perfil
                FROM usuarios
                WHERE LOWER(email) = ?
            """, (email,)).fetchone()

            conexao.close()

            if usuario and check_password_hash(
                usuario["senha"],
                senha
            ):

                session.clear()

                session["usuario_id"] = usuario["id"]
                session["usuario_nome"] = usuario["nome"]
                session["usuario_email"] = usuario["email"]
                session["usuario_perfil"] = usuario["perfil"]

                return redirect(url_for("inicio"))

            erro = "E-mail ou senha inválidos."

        return render_template(
            "login.html",
            erro=erro
        )

    # ==========================================
    # LOGOUT
    # ==========================================

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(url_for("login"))