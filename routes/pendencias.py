import os
from uuid import uuid4

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from werkzeug.utils import secure_filename

from database.conexao import conectar


EXTENSOES_PERMITIDAS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def extensao_permitida(nome_arquivo):

    return (
        "." in nome_arquivo
        and nome_arquivo.rsplit(".", 1)[1].lower()
        in EXTENSOES_PERMITIDAS
    )


def salvar_foto(app, arquivo, pasta):

    if arquivo is None or arquivo.filename == "":

        return None

    if not extensao_permitida(arquivo.filename):

        raise ValueError(
            "Formato de imagem inválido. Utilize PNG, JPG, JPEG ou WEBP."
        )

    nome_original = secure_filename(arquivo.filename)

    extensao = nome_original.rsplit(".", 1)[1].lower()

    nome_arquivo = f"{uuid4().hex}.{extensao}"

    pasta_destino = os.path.join(
        app.config["UPLOAD_FOLDER"],
        pasta
    )

    os.makedirs(
        pasta_destino,
        exist_ok=True
    )

    caminho_completo = os.path.join(
        pasta_destino,
        nome_arquivo
    )

    arquivo.save(caminho_completo)

    return f"{pasta}/{nome_arquivo}"


def excluir_foto(app, caminho_relativo):

    if not caminho_relativo:

        return

    caminho_completo = os.path.join(
        app.config["UPLOAD_FOLDER"],
        caminho_relativo
    )

    if os.path.isfile(caminho_completo):

        os.remove(caminho_completo)


def registrar_rotas(app):

    # ======================================================
    # PAINEL DE PENDÊNCIAS
    # ======================================================

    @app.route("/pendencias")
    def painel_pendencias():

        conexao = conectar()

        try:

            busca = request.args.get(
                "busca",
                ""
            ).strip()

            status = request.args.get(
                "status",
                ""
            ).strip()

            prioridade = request.args.get(
                "prioridade",
                ""
            ).strip()

            setor_id = request.args.get(
                "setor_id",
                ""
            ).strip()

            responsavel = request.args.get(
                "responsavel",
                ""
            ).strip()

            prazo_inicio = request.args.get(
                "prazo_inicio",
                ""
            ).strip()

            prazo_fim = request.args.get(
                "prazo_fim",
                ""
            ).strip()

            atrasada = request.args.get(
                "atrasada",
                ""
            ).strip()

            filtros = []
            parametros = []

            if busca:

                filtros.append("""
                    (
                        pendencias.descricao LIKE ?
                        OR pendencias.categoria LIKE ?
                        OR pendencias.responsavel LIKE ?
                        OR setores.nome LIKE ?
                    )
                """)

                termo_busca = f"%{busca}%"

                parametros.extend([
                    termo_busca,
                    termo_busca,
                    termo_busca,
                    termo_busca
                ])

            if status:

                filtros.append(
                    "pendencias.status = ?"
                )

                parametros.append(status)

            if prioridade:

                filtros.append(
                    "pendencias.prioridade = ?"
                )

                parametros.append(prioridade)

            if setor_id:

                filtros.append(
                    "setores.id = ?"
                )

                parametros.append(setor_id)

            if responsavel:

                filtros.append(
                    "pendencias.responsavel = ?"
                )

                parametros.append(responsavel)

            if prazo_inicio:

                filtros.append("""
                    pendencias.prazo IS NOT NULL
                    AND pendencias.prazo != ''
                    AND DATE(pendencias.prazo) >= DATE(?)
                """)

                parametros.append(prazo_inicio)

            if prazo_fim:

                filtros.append("""
                    pendencias.prazo IS NOT NULL
                    AND pendencias.prazo != ''
                    AND DATE(pendencias.prazo) <= DATE(?)
                """)

                parametros.append(prazo_fim)

            if atrasada == "1":

                filtros.append("""
                    pendencias.prazo IS NOT NULL
                    AND pendencias.prazo != ''
                    AND DATE(pendencias.prazo)
                        < CURRENT_DATE
                    AND pendencias.status != 'Resolvida'
                """)

            clausula_where = ""

            if filtros:

                clausula_where = (
                    "WHERE "
                    + " AND ".join(filtros)
                )

            consulta = f"""
                SELECT
                    pendencias.*,
                    setores.nome AS setor,
                    setores.id AS setor_id,
                    CASE
                        WHEN pendencias.prazo IS NOT NULL
                         AND pendencias.prazo != ''
                         AND DATE(pendencias.prazo)
                             < CURRENT_DATE
                         AND pendencias.status != 'Resolvida'
                        THEN 1
                        ELSE 0
                    END AS atrasada
                FROM pendencias
                INNER JOIN rondas
                    ON rondas.id = pendencias.ronda_id
                INNER JOIN setores
                    ON setores.id = rondas.setor_id
                {clausula_where}
                ORDER BY
                    atrasada DESC,
                    CASE pendencias.status
                        WHEN 'Aberta' THEN 1
                        WHEN 'Em andamento' THEN 2
                        WHEN 'Resolvida' THEN 3
                        ELSE 4
                    END,
                    CASE pendencias.prioridade
                        WHEN 'Urgente' THEN 1
                        WHEN 'Alta' THEN 2
                        WHEN 'Média' THEN 3
                        WHEN 'Baixa' THEN 4
                        ELSE 5
                    END,
                    pendencias.id DESC
            """

            pendencias = conexao.execute(
                consulta,
                parametros
            ).fetchall()

            setores = conexao.execute("""
                SELECT
                    id,
                    nome
                FROM setores
                WHERE ativo = TRUE
                ORDER BY nome
            """).fetchall()

            responsaveis = conexao.execute("""
                SELECT DISTINCT
                    TRIM(responsavel) AS responsavel
                FROM pendencias
                WHERE responsavel IS NOT NULL
                  AND TRIM(responsavel) != ''
                ORDER BY responsavel
            """).fetchall()

            total_filtrado = len(pendencias)

            return render_template(
                "pendencias.html",
                pendencias=pendencias,
                setores=setores,
                responsaveis=responsaveis,
                total_filtrado=total_filtrado,
                busca=busca,
                status_selecionado=status,
                prioridade_selecionada=prioridade,
                setor_selecionado=setor_id,
                responsavel_selecionado=responsavel,
                prazo_inicio=prazo_inicio,
                prazo_fim=prazo_fim,
                atrasada_selecionada=atrasada
            )

        finally:

            conexao.close()


    # ======================================================
    # NOVA PENDÊNCIA
    # ======================================================

    @app.route(
        "/nova-pendencia/<int:ronda_id>",
        methods=["GET", "POST"]
    )
    def nova_pendencia(ronda_id):

        conexao = conectar()

        try:

            ronda = conexao.execute("""
                SELECT id
                FROM rondas
                WHERE id = ?
            """, (ronda_id,)).fetchone()

            if ronda is None:

                return "Ronda não encontrada.", 404

            if request.method == "POST":

                descricao = request.form.get(
                    "descricao",
                    ""
                ).strip()

                categoria = request.form.get(
                    "categoria",
                    ""
                ).strip()

                prioridade = request.form.get(
                    "prioridade",
                    "Baixa"
                ).strip()

                status = request.form.get(
                    "status",
                    "Aberta"
                ).strip()

                responsavel = request.form.get(
                    "responsavel",
                    ""
                ).strip()

                prazo = request.form.get(
                    "prazo",
                    ""
                ).strip()

                observacao_resolucao = request.form.get(
                    "observacao_resolucao",
                    ""
                ).strip()

                if not descricao:

                    flash(
                        "Informe a descrição da pendência.",
                        "erro"
                    )

                    return render_template(
                        "nova_pendencia.html",
                        ronda_id=ronda_id
                    )

                foto_antes = None
                foto_depois = None

                try:

                    foto_antes = salvar_foto(
                        app,
                        request.files.get("foto_antes"),
                        "antes"
                    )

                    foto_depois = salvar_foto(
                        app,
                        request.files.get("foto_depois"),
                        "depois"
                    )

                except ValueError as erro:

                    excluir_foto(
                        app,
                        foto_antes
                    )

                    excluir_foto(
                        app,
                        foto_depois
                    )

                    flash(
                        str(erro),
                        "erro"
                    )

                    return render_template(
                        "nova_pendencia.html",
                        ronda_id=ronda_id
                    )

                try:

                    conexao.execute("""
                        INSERT INTO pendencias (
                            ronda_id,
                            descricao,
                            categoria,
                            prioridade,
                            status,
                            responsavel,
                            prazo,
                            observacao_resolucao,
                            foto_antes,
                            foto_depois
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ronda_id,
                        descricao,
                        categoria,
                        prioridade,
                        status,
                        responsavel,
                        prazo,
                        observacao_resolucao,
                        foto_antes,
                        foto_depois
                    ))

                    conexao.commit()

                except Exception:

                    excluir_foto(
                        app,
                        foto_antes
                    )

                    excluir_foto(
                        app,
                        foto_depois
                    )

                    raise

                flash(
                    "Pendência cadastrada com sucesso.",
                    "sucesso"
                )

                return redirect(
                    url_for(
                        "detalhes_ronda",
                        id=ronda_id
                    )
                )

            return render_template(
                "nova_pendencia.html",
                ronda_id=ronda_id
            )

        finally:

            conexao.close()


    # ======================================================
    # EDITAR PENDÊNCIA
    # ======================================================

    @app.route(
        "/editar-pendencia/<int:id>",
        methods=["GET", "POST"]
    )
    def editar_pendencia(id):

        conexao = conectar()

        try:

            pendencia = conexao.execute("""
                SELECT *
                FROM pendencias
                WHERE id = ?
            """, (id,)).fetchone()

            if pendencia is None:

                return "Pendência não encontrada.", 404

            if request.method == "POST":

                descricao = request.form.get(
                    "descricao",
                    ""
                ).strip()

                categoria = request.form.get(
                    "categoria",
                    ""
                ).strip()

                prioridade = request.form.get(
                    "prioridade",
                    "Baixa"
                ).strip()

                status = request.form.get(
                    "status",
                    "Aberta"
                ).strip()

                responsavel = request.form.get(
                    "responsavel",
                    ""
                ).strip()

                prazo = request.form.get(
                    "prazo",
                    ""
                ).strip()

                observacao_resolucao = request.form.get(
                    "observacao_resolucao",
                    ""
                ).strip()

                if not descricao:

                    flash(
                        "Informe a descrição da pendência.",
                        "erro"
                    )

                    return render_template(
                        "editar_pendencia.html",
                        pendencia=pendencia
                    )

                foto_antes = pendencia["foto_antes"]
                foto_depois = pendencia["foto_depois"]

                nova_foto_antes = None
                nova_foto_depois = None

                try:

                    nova_foto_antes = salvar_foto(
                        app,
                        request.files.get("foto_antes"),
                        "antes"
                    )

                    nova_foto_depois = salvar_foto(
                        app,
                        request.files.get("foto_depois"),
                        "depois"
                    )

                except ValueError as erro:

                    excluir_foto(
                        app,
                        nova_foto_antes
                    )

                    excluir_foto(
                        app,
                        nova_foto_depois
                    )

                    flash(
                        str(erro),
                        "erro"
                    )

                    return render_template(
                        "editar_pendencia.html",
                        pendencia=pendencia
                    )

                remover_foto_antes = (
                    request.form.get("remover_foto_antes")
                    == "1"
                )

                remover_foto_depois = (
                    request.form.get("remover_foto_depois")
                    == "1"
                )

                foto_antes_antiga = pendencia["foto_antes"]
                foto_depois_antiga = pendencia["foto_depois"]

                if nova_foto_antes:

                    foto_antes = nova_foto_antes

                elif remover_foto_antes:

                    foto_antes = None

                if nova_foto_depois:

                    foto_depois = nova_foto_depois

                elif remover_foto_depois:

                    foto_depois = None

                try:

                    conexao.execute("""
                        UPDATE pendencias
                        SET
                            descricao = ?,
                            categoria = ?,
                            prioridade = ?,
                            status = ?,
                            responsavel = ?,
                            prazo = ?,
                            observacao_resolucao = ?,
                            foto_antes = ?,
                            foto_depois = ?
                        WHERE id = ?
                    """, (
                        descricao,
                        categoria,
                        prioridade,
                        status,
                        responsavel,
                        prazo,
                        observacao_resolucao,
                        foto_antes,
                        foto_depois,
                        id
                    ))

                    conexao.commit()

                except Exception:

                    excluir_foto(
                        app,
                        nova_foto_antes
                    )

                    excluir_foto(
                        app,
                        nova_foto_depois
                    )

                    raise

                if (
                    nova_foto_antes
                    or remover_foto_antes
                ):

                    excluir_foto(
                        app,
                        foto_antes_antiga
                    )

                if (
                    nova_foto_depois
                    or remover_foto_depois
                ):

                    excluir_foto(
                        app,
                        foto_depois_antiga
                    )

                flash(
                    "Pendência atualizada com sucesso.",
                    "sucesso"
                )

                return redirect(
                    url_for(
                        "detalhes_ronda",
                        id=pendencia["ronda_id"]
                    )
                )

            return render_template(
                "editar_pendencia.html",
                pendencia=pendencia
            )

        finally:

            conexao.close()


    # ======================================================
    # EXCLUIR PENDÊNCIA
    # ======================================================

    @app.route("/excluir-pendencia/<int:id>")
    def excluir_pendencia(id):

        conexao = conectar()

        try:

            pendencia = conexao.execute("""
                SELECT
                    id,
                    ronda_id,
                    foto_antes,
                    foto_depois
                FROM pendencias
                WHERE id = ?
            """, (id,)).fetchone()

            if pendencia is None:

                return "Pendência não encontrada.", 404

            conexao.execute("""
                DELETE FROM pendencias
                WHERE id = ?
            """, (id,))

            conexao.commit()

            excluir_foto(
                app,
                pendencia["foto_antes"]
            )

            excluir_foto(
                app,
                pendencia["foto_depois"]
            )

            flash(
                "Pendência excluída com sucesso.",
                "sucesso"
            )

            return redirect(
                url_for(
                    "detalhes_ronda",
                    id=pendencia["ronda_id"]
                )
            )

        finally:

            conexao.close()