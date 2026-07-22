import io
import os
from datetime import datetime

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    current_app,
    send_file
)

from database.conexao import conectar


def registrar_rotas(app):

    # ======================================================
    # FUNÇÕES AUXILIARES
    # ======================================================

    def formatar_data(data):

        if not data:
            return "-"

        try:
            return datetime.strptime(
                data,
                "%Y-%m-%d"
            ).strftime("%d/%m/%Y")

        except ValueError:
            return data


    def formatar_hora(hora):

        if not hora:
            return "-"

        return hora[:5]


    def localizar_foto(caminho_foto, tipo):

        if not caminho_foto:
            return None

        caminho_foto = caminho_foto.replace("\\", "/")
        nome_arquivo = os.path.basename(caminho_foto)

        caminhos_possiveis = [
            os.path.join(
                current_app.static_folder,
                caminho_foto
            ),
            os.path.join(
                current_app.static_folder,
                "uploads",
                tipo,
                nome_arquivo
            ),
            os.path.join(
                current_app.static_folder,
                "uploads",
                nome_arquivo
            )
        ]

        for caminho in caminhos_possiveis:

            if os.path.isfile(caminho):
                return caminho

        return None


    def excluir_arquivo_foto(caminho_foto, tipo):

        caminho = localizar_foto(
            caminho_foto,
            tipo
        )

        if caminho and os.path.isfile(caminho):

            try:
                os.remove(caminho)

            except OSError:
                pass


    # ======================================================
    # NOVA RONDA
    # ======================================================

    @app.route("/nova-ronda", methods=["GET", "POST"])
    def nova_ronda():

        conexao = conectar()

        try:

            if request.method == "POST":

                setor_id = request.form.get("setor_id")
                data = request.form.get("data", "").strip()
                hora = request.form.get("hora", "").strip()
                responsavel = request.form.get(
                    "responsavel",
                    ""
                ).strip()

                observacoes = request.form.get(
                    "observacoes",
                    ""
                ).strip()

                conexao.execute("""
                    INSERT INTO rondas (
                        setor_id,
                        data,
                        hora,
                        responsavel,
                        observacoes
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    setor_id,
                    data,
                    hora,
                    responsavel,
                    observacoes
                ))

                conexao.commit()

                return redirect(url_for("inicio"))

            setores = conexao.execute("""
                SELECT
                    id,
                    nome
                FROM setores
                WHERE ativo = TRUE
                ORDER BY nome
            """).fetchall()

            return render_template(
                "nova_ronda.html",
                setores=setores
            )

        finally:

            conexao.close()


    # ======================================================
    # DETALHES DA RONDA
    # ======================================================

    @app.route("/ronda/<int:id>")
    def detalhes_ronda(id):

        conexao = conectar()

        try:

            ronda = conexao.execute("""
                SELECT
                    rondas.id,
                    rondas.setor_id,
                    rondas.data,
                    rondas.hora,
                    rondas.responsavel,
                    rondas.observacoes,
                    setores.nome AS setor
                FROM rondas
                INNER JOIN setores
                    ON setores.id = rondas.setor_id
                WHERE rondas.id = ?
            """, (id,)).fetchone()

            if ronda is None:

                return "Ronda não encontrada.", 404

            pendencias = conexao.execute("""
                SELECT
                    id,
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
                FROM pendencias
                WHERE ronda_id = ?
                ORDER BY id DESC
            """, (id,)).fetchall()

            return render_template(
                "detalhes_ronda.html",
                ronda=ronda,
                pendencias=pendencias
            )

        finally:

            conexao.close()


    # ======================================================
    # RELATÓRIO DA RONDA EM PDF
    # ======================================================

    @app.route("/relatorio-ronda/<int:id>")
    def relatorio_ronda(id):

        try:

            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import (
                getSampleStyleSheet,
                ParagraphStyle
            )
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Spacer,
                Table,
                TableStyle,
                Image,
                PageBreak,
                KeepTogether
            )

        except ImportError:

            return (
                "A biblioteca ReportLab não está instalada. "
                "Execute: pip install reportlab",
                500
            )

        conexao = conectar()

        try:

            ronda = conexao.execute("""
                SELECT
                    rondas.id,
                    rondas.setor_id,
                    rondas.data,
                    rondas.hora,
                    rondas.responsavel,
                    rondas.observacoes,
                    setores.nome AS setor
                FROM rondas
                INNER JOIN setores
                    ON setores.id = rondas.setor_id
                WHERE rondas.id = ?
            """, (id,)).fetchone()

            if ronda is None:

                return "Ronda não encontrada.", 404

            pendencias = conexao.execute("""
                SELECT
                    id,
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
                FROM pendencias
                WHERE ronda_id = ?
                ORDER BY id ASC
            """, (id,)).fetchall()

        finally:

            conexao.close()

        memoria_pdf = io.BytesIO()

        documento = SimpleDocTemplate(
            memoria_pdf,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2.2 * cm,
            bottomMargin=1.8 * cm,
            title=f"Relatório da Ronda #{id}",
            author="SGRG"
        )

        estilos = getSampleStyleSheet()

        estilo_titulo = ParagraphStyle(
            "TituloRelatorio",
            parent=estilos["Title"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=4
        )

        estilo_subtitulo = ParagraphStyle(
            "SubtituloRelatorio",
            parent=estilos["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=12
        )

        estilo_secao = ParagraphStyle(
            "SecaoRelatorio",
            parent=estilos["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=8,
            spaceAfter=7
        )

        estilo_normal = ParagraphStyle(
            "TextoNormalRelatorio",
            parent=estilos["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155")
        )

        estilo_pequeno = ParagraphStyle(
            "TextoPequenoRelatorio",
            parent=estilos["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569")
        )

        estilo_rotulo = ParagraphStyle(
            "RotuloRelatorio",
            parent=estilos["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569")
        )

        elementos = []

        elementos.append(
            Paragraph(
                "HOSPITAL DA MULHER E DA CRIANÇA DO VALE DO JURUÁ",
                estilo_titulo
            )
        )

        elementos.append(
            Paragraph(
                "Sistema de Gestão de Rondas Gerenciais - SGRG",
                estilo_subtitulo
            )
        )

        elementos.append(
            Paragraph(
                f"RELATÓRIO DA RONDA GERENCIAL Nº {ronda['id']}",
                estilo_secao
            )
        )

        dados_ronda = [
            [
                Paragraph("<b>Setor</b>", estilo_rotulo),
                Paragraph(
                    str(ronda["setor"] or "-"),
                    estilo_normal
                ),
                Paragraph("<b>Data</b>", estilo_rotulo),
                Paragraph(
                    formatar_data(ronda["data"]),
                    estilo_normal
                )
            ],
            [
                Paragraph("<b>Responsável</b>", estilo_rotulo),
                Paragraph(
                    str(ronda["responsavel"] or "-"),
                    estilo_normal
                ),
                Paragraph("<b>Horário</b>", estilo_rotulo),
                Paragraph(
                    formatar_hora(ronda["hora"]),
                    estilo_normal
                )
            ]
        ]

        tabela_ronda = Table(
            dados_ronda,
            colWidths=[
                2.6 * cm,
                7.3 * cm,
                2.2 * cm,
                4.9 * cm
            ]
        )

        tabela_ronda.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F1F5F9")
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor("#F1F5F9")
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    colors.HexColor("#CBD5E1")
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#CBD5E1")
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )
            ])
        )

        elementos.append(tabela_ronda)
        elementos.append(Spacer(1, 0.35 * cm))

        elementos.append(
            Paragraph(
                "Observações da ronda",
                estilo_secao
            )
        )

        observacoes = ronda["observacoes"] or (
            "Nenhuma observação registrada."
        )

        tabela_observacoes = Table(
            [[
                Paragraph(
                    str(observacoes),
                    estilo_normal
                )
            ]],
            colWidths=[17 * cm]
        )

        tabela_observacoes.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F8FAFC")
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    colors.HexColor("#CBD5E1")
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    9
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    9
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    9
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    9
                )
            ])
        )

        elementos.append(tabela_observacoes)
        elementos.append(Spacer(1, 0.35 * cm))

        elementos.append(
            Paragraph(
                f"Pendências registradas ({len(pendencias)})",
                estilo_secao
            )
        )

        if not pendencias:

            elementos.append(
                Paragraph(
                    "Nenhuma pendência foi registrada nesta ronda.",
                    estilo_normal
                )
            )

        for indice, pendencia in enumerate(
            pendencias,
            start=1
        ):

            prazo_formatado = formatar_data(
                pendencia["prazo"]
            )

            dados_pendencia = [
                [
                    Paragraph(
                        f"<b>Pendência {indice}</b>",
                        estilo_normal
                    ),
                    Paragraph(
                        f"<b>Status:</b> "
                        f"{pendencia['status'] or '-'}",
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "<b>Descrição</b>",
                        estilo_rotulo
                    ),
                    Paragraph(
                        str(
                            pendencia["descricao"] or "-"
                        ),
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "<b>Categoria</b>",
                        estilo_rotulo
                    ),
                    Paragraph(
                        str(
                            pendencia["categoria"] or "-"
                        ),
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "<b>Prioridade</b>",
                        estilo_rotulo
                    ),
                    Paragraph(
                        str(
                            pendencia["prioridade"] or "-"
                        ),
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "<b>Responsável</b>",
                        estilo_rotulo
                    ),
                    Paragraph(
                        str(
                            pendencia["responsavel"] or "-"
                        ),
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "<b>Prazo</b>",
                        estilo_rotulo
                    ),
                    Paragraph(
                        prazo_formatado,
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "<b>Observação da resolução</b>",
                        estilo_rotulo
                    ),
                    Paragraph(
                        str(
                            pendencia[
                                "observacao_resolucao"
                            ] or "-"
                        ),
                        estilo_normal
                    )
                ]
            ]

            tabela_pendencia = Table(
                dados_pendencia,
                colWidths=[
                    4.1 * cm,
                    12.9 * cm
                ]
            )

            tabela_pendencia.setStyle(
                TableStyle([
                    (
                        "SPAN",
                        (0, 0),
                        (0, 0)
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#E2E8F0")
                    ),
                    (
                        "BACKGROUND",
                        (0, 1),
                        (0, -1),
                        colors.HexColor("#F8FAFC")
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.7,
                        colors.HexColor("#94A3B8")
                    ),
                    (
                        "INNERGRID",
                        (0, 1),
                        (-1, -1),
                        0.4,
                        colors.HexColor("#CBD5E1")
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP"
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        7
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        7
                    )
                ])
            )

            elementos.append(tabela_pendencia)
            elementos.append(Spacer(1, 0.25 * cm))

            foto_antes = localizar_foto(
                pendencia["foto_antes"],
                "antes"
            )

            foto_depois = localizar_foto(
                pendencia["foto_depois"],
                "depois"
            )

            if foto_antes or foto_depois:

                fotos = []
                titulos_fotos = []

                if foto_antes:

                    try:

                        imagem_antes = Image(
                            foto_antes
                        )

                        imagem_antes._restrictSize(
                            7.7 * cm,
                            7 * cm
                        )

                        fotos.append(imagem_antes)

                        titulos_fotos.append(
                            Paragraph(
                                "<b>Foto antes</b>",
                                estilo_pequeno
                            )
                        )

                    except Exception:
                        pass

                if foto_depois:

                    try:

                        imagem_depois = Image(
                            foto_depois
                        )

                        imagem_depois._restrictSize(
                            7.7 * cm,
                            7 * cm
                        )

                        fotos.append(imagem_depois)

                        titulos_fotos.append(
                            Paragraph(
                                "<b>Foto depois</b>",
                                estilo_pequeno
                            )
                        )

                    except Exception:
                        pass

                if fotos:

                    if len(fotos) == 1:

                        tabela_fotos = Table(
                            [
                                [titulos_fotos[0]],
                                [fotos[0]]
                            ],
                            colWidths=[8.2 * cm]
                        )

                    else:

                        tabela_fotos = Table(
                            [
                                titulos_fotos,
                                fotos
                            ],
                            colWidths=[
                                8.2 * cm,
                                8.2 * cm
                            ]
                        )

                    tabela_fotos.setStyle(
                        TableStyle([
                            (
                                "ALIGN",
                                (0, 0),
                                (-1, -1),
                                "CENTER"
                            ),
                            (
                                "VALIGN",
                                (0, 0),
                                (-1, -1),
                                "MIDDLE"
                            ),
                            (
                                "BOX",
                                (0, 0),
                                (-1, -1),
                                0.5,
                                colors.HexColor("#CBD5E1")
                            ),
                            (
                                "INNERGRID",
                                (0, 0),
                                (-1, -1),
                                0.4,
                                colors.HexColor("#E2E8F0")
                            ),
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, 0),
                                colors.HexColor("#F8FAFC")
                            ),
                            (
                                "TOPPADDING",
                                (0, 0),
                                (-1, -1),
                                7
                            ),
                            (
                                "BOTTOMPADDING",
                                (0, 0),
                                (-1, -1),
                                7
                            ),
                            (
                                "LEFTPADDING",
                                (0, 0),
                                (-1, -1),
                                7
                            ),
                            (
                                "RIGHTPADDING",
                                (0, 0),
                                (-1, -1),
                                7
                            )
                        ])
                    )

                    elementos.append(
                        KeepTogether([
                            tabela_fotos,
                            Spacer(1, 0.3 * cm)
                        ])
                    )

            elementos.append(Spacer(1, 0.35 * cm))

            if indice < len(pendencias):

                elementos.append(
                    Table(
                        [[""]],
                        colWidths=[17 * cm],
                        rowHeights=[0.02 * cm],
                        style=TableStyle([
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, -1),
                                colors.HexColor("#CBD5E1")
                            )
                        ])
                    )
                )

                elementos.append(
                    Spacer(1, 0.35 * cm)
                )

        elementos.append(Spacer(1, 1 * cm))

        assinatura = Table(
            [
                [""],
                [
                    Paragraph(
                        str(ronda["responsavel"] or ""),
                        estilo_normal
                    )
                ],
                [
                    Paragraph(
                        "Responsável pela ronda",
                        estilo_pequeno
                    )
                ]
            ],
            colWidths=[8 * cm],
            rowHeights=[
                0.1 * cm,
                0.55 * cm,
                0.45 * cm
            ]
        )

        assinatura.setStyle(
            TableStyle([
                (
                    "LINEABOVE",
                    (0, 1),
                    (0, 1),
                    0.7,
                    colors.HexColor("#475569")
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                )
            ])
        )

        elementos.append(assinatura)

        def cabecalho_rodape(canvas, doc):

            canvas.saveState()

            largura, altura = A4

            canvas.setStrokeColor(
                colors.HexColor("#CBD5E1")
            )

            canvas.setLineWidth(0.5)

            canvas.line(
                1.5 * cm,
                altura - 1.6 * cm,
                largura - 1.5 * cm,
                altura - 1.6 * cm
            )

            canvas.setFont(
                "Helvetica",
                7.5
            )

            canvas.setFillColor(
                colors.HexColor("#64748B")
            )

            canvas.drawString(
                1.5 * cm,
                1 * cm,
                f"SGRG - Relatório da Ronda nº {id}"
            )

            canvas.drawRightString(
                largura - 1.5 * cm,
                1 * cm,
                f"Página {doc.page}"
            )

            canvas.restoreState()

        documento.build(
            elementos,
            onFirstPage=cabecalho_rodape,
            onLaterPages=cabecalho_rodape
        )

        memoria_pdf.seek(0)

        nome_arquivo = (
            f"relatorio_ronda_{ronda['id']}_"
            f"{ronda['data'] or 'sem_data'}.pdf"
        )

        return send_file(
            memoria_pdf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=nome_arquivo
        )


    # ======================================================
    # EDITAR RONDA
    # ======================================================

    @app.route(
        "/editar-ronda/<int:id>",
        methods=["GET", "POST"]
    )
    def editar_ronda(id):

        conexao = conectar()

        try:

            ronda = conexao.execute("""
                SELECT
                    id,
                    setor_id,
                    data,
                    hora,
                    responsavel,
                    observacoes
                FROM rondas
                WHERE id = ?
            """, (id,)).fetchone()

            if ronda is None:

                return "Ronda não encontrada.", 404

            if request.method == "POST":

                setor_id = request.form.get("setor_id")
                data = request.form.get("data", "").strip()
                hora = request.form.get("hora", "").strip()

                responsavel = request.form.get(
                    "responsavel",
                    ""
                ).strip()

                observacoes = request.form.get(
                    "observacoes",
                    ""
                ).strip()

                conexao.execute("""
                    UPDATE rondas
                    SET
                        setor_id = ?,
                        data = ?,
                        hora = ?,
                        responsavel = ?,
                        observacoes = ?
                    WHERE id = ?
                """, (
                    setor_id,
                    data,
                    hora,
                    responsavel,
                    observacoes,
                    id
                ))

                conexao.commit()

                return redirect(
                    url_for(
                        "detalhes_ronda",
                        id=id
                    )
                )

            setores = conexao.execute("""
                SELECT
                    id,
                    nome
                FROM setores
                ORDER BY nome
            """).fetchall()

            return render_template(
                "editar_ronda.html",
                ronda=ronda,
                setores=setores
            )

        finally:

            conexao.close()


    # ======================================================
    # EXCLUIR RONDA
    # ======================================================

    @app.route("/excluir-ronda/<int:id>")
    def excluir_ronda(id):

        conexao = conectar()

        try:

            ronda = conexao.execute("""
                SELECT id
                FROM rondas
                WHERE id = ?
            """, (id,)).fetchone()

            if ronda is None:

                return "Ronda não encontrada.", 404

            fotos_pendencias = conexao.execute("""
                SELECT
                    foto_antes,
                    foto_depois
                FROM pendencias
                WHERE ronda_id = ?
            """, (id,)).fetchall()

            for pendencia in fotos_pendencias:

                excluir_arquivo_foto(
                    pendencia["foto_antes"],
                    "antes"
                )

                excluir_arquivo_foto(
                    pendencia["foto_depois"],
                    "depois"
                )

            conexao.execute("""
                DELETE FROM pendencias
                WHERE ronda_id = ?
            """, (id,))

            conexao.execute("""
                DELETE FROM rondas
                WHERE id = ?
            """, (id,))

            conexao.commit()

            return redirect(url_for("historico"))

        finally:

            conexao.close()