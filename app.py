from flask import Flask
import os

from routes.auth import registrar_rotas as auth_rotas
from routes.dashboard import registrar_rotas as dashboard_rotas
from routes.rondas import registrar_rotas as rondas_rotas
from routes.historico import registrar_rotas as historico_rotas
from routes.pendencias import registrar_rotas as pendencias_rotas
from routes.usuarios import registrar_rotas as usuarios_rotas
from routes.setores import registrar_rotas as setores_rotas


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def criar_app():

    app = Flask(__name__)

    # =====================================================
    # CONFIGURAÇÕES GERAIS
    # =====================================================

    app.config["SECRET_KEY"] = os.environ.get(
        "SGRG_SECRET_KEY",
        "sgrg-chave-secreta-altere-em-producao"
    )

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Altere para True somente quando o sistema usar HTTPS
    app.config["SESSION_COOKIE_SECURE"] = False

    # =====================================================
    # CONFIGURAÇÃO DE UPLOAD
    # =====================================================

    app.config["UPLOAD_FOLDER"] = os.path.join(
        BASE_DIR,
        "static",
        "uploads"
    )

    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True
    )

    os.makedirs(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            "antes"
        ),
        exist_ok=True
    )

    os.makedirs(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            "depois"
        ),
        exist_ok=True
    )

    # =====================================================
    # REGISTRO DAS ROTAS
    # =====================================================

    auth_rotas(app)
    dashboard_rotas(app)
    rondas_rotas(app)
    historico_rotas(app)
    pendencias_rotas(app)
    usuarios_rotas(app)
    setores_rotas(app)

    # =====================================================
    # TRATAMENTO DE ERROS
    # =====================================================

    @app.errorhandler(413)
    def arquivo_muito_grande(erro):

        return (
            "O arquivo enviado ultrapassa o limite máximo de 10 MB.",
            413
        )

    @app.errorhandler(404)
    def pagina_nao_encontrada(erro):

        return (
            "Página não encontrada.",
            404
        )

    @app.errorhandler(500)
    def erro_interno(erro):

        app.logger.error(
            "Erro interno no sistema: %s",
            erro
        )

        return (
            "Ocorreu um erro interno no sistema.",
            500
        )

    return app


app = criar_app()


if __name__ == "__main__":

    modo_debug = os.environ.get(
        "FLASK_DEBUG",
        "true"
    ).lower() == "true"

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=modo_debug
    )