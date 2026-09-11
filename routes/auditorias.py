from datetime import date, datetime
import secrets

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from database.conexao import DATABASE_URL, conectar
from pdf.relatorio_auditoria import gerar_relatorio_auditoria_pdf


CRITERIOS = [
    ("aprazamento_medicamentos", "Aprazamento de medicamentos"),
    ("checagem_medicamentos", "Checagem de medicamentos"),
    ("evolucao_enfermagem", "Evolução de enfermagem"),
    ("evolucao_tecnico", "Evolução do técnico de enfermagem"),
    ("solicitacoes_farmacia", "Solicitações para a farmácia"),
    ("solicitacoes_lavanderia", "Solicitações para a lavanderia"),
]


def garantir_tabelas_auditoria(conexao):
    chave_primaria = (
        "SERIAL PRIMARY KEY"
        if DATABASE_URL
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS auditorias (
            id {chave_primaria},
            nome VARCHAR(200),
            setor_id INTEGER NOT NULL REFERENCES setores(id),
            data VARCHAR(20) NOT NULL,
            responsavel VARCHAR(200) NOT NULL,
            quantidade_prontuarios INTEGER NOT NULL,
            aprazamento_medicamentos INTEGER NOT NULL DEFAULT 0,
            aprazamento_medicamentos_obs TEXT,
            checagem_medicamentos INTEGER NOT NULL DEFAULT 0,
            checagem_medicamentos_obs TEXT,
            evolucao_enfermagem INTEGER NOT NULL DEFAULT 0,
            evolucao_enfermagem_obs TEXT,
            evolucao_tecnico INTEGER NOT NULL DEFAULT 0,
            evolucao_tecnico_obs TEXT,
            solicitacoes_farmacia INTEGER NOT NULL DEFAULT 0,
            solicitacoes_farmacia_obs TEXT,
            solicitacoes_lavanderia INTEGER NOT NULL DEFAULT 0,
            solicitacoes_lavanderia_obs TEXT,
            conclusao TEXT,
            criado_por INTEGER REFERENCES usuarios(id),
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Acrescenta o nome aos bancos já existentes sem alterar seus registros.
    if DATABASE_URL:
        coluna_nome = conexao.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'auditorias' AND column_name = 'nome'
        """).fetchone()
        if coluna_nome is None:
            conexao.execute("""
                ALTER TABLE auditorias ADD COLUMN IF NOT EXISTS nome VARCHAR(200)
            """)
    else:
        colunas = conexao.execute("PRAGMA table_info(auditorias)").fetchall()
        if not any(coluna["name"] == "nome" for coluna in colunas):
            conexao.execute("ALTER TABLE auditorias ADD COLUMN nome VARCHAR(200)")

    conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS planos_acao_auditoria (
            id {chave_primaria},
            auditoria_id INTEGER NOT NULL
                REFERENCES auditorias(id) ON DELETE CASCADE,
            problema TEXT NOT NULL,
            acao TEXT NOT NULL,
            responsavel VARCHAR(200),
            prazo VARCHAR(20),
            prioridade VARCHAR(30) DEFAULT 'Média',
            status VARCHAR(30) DEFAULT 'Pendente',
            data_conclusao VARCHAR(20),
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_auditorias_setor
        ON auditorias(setor_id)
    """)
    conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_auditorias_data
        ON auditorias(data)
    """)
    conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_planos_auditoria
        ON planos_acao_auditoria(auditoria_id)
    """)
    conexao.commit()


def numero_inteiro(valor, nome_campo, minimo=0):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nome_campo} deve ser um número inteiro.")

    if numero < minimo:
        raise ValueError(f"{nome_campo} deve ser maior ou igual a {minimo}.")

    return numero


def validar_nome(valor):
    nome = " ".join((valor or "").split())
    if not nome or len(nome) > 200:
        raise ValueError("Informe um nome para a auditoria com até 200 caracteres.")
    return nome


def token_formulario_auditoria():
    if "token_auditoria" not in session:
        session["token_auditoria"] = secrets.token_urlsafe(32)
    return session["token_auditoria"]


def validar_token_auditoria():
    esperado = session.get("token_auditoria", "")
    recebido = request.form.get("token_auditoria", "")
    if not esperado or not secrets.compare_digest(esperado.encode(), recebido.encode()):
        abort(400, description="Atualize a página da auditoria e tente novamente.")


def preparar_auditoria(registro):
    auditoria = dict(registro)
    if not (auditoria.get("nome") or "").strip():
        data_texto = str(auditoria["data"])
        try:
            data_texto = date.fromisoformat(data_texto[:10]).strftime("%d/%m/%Y")
        except ValueError:
            pass
        auditoria["nome"] = f"Revisão - {auditoria['setor']} - {data_texto}"[:200]
    return auditoria


def montar_resultados(auditoria):
    total = auditoria["quantidade_prontuarios"]
    resultados = []

    for campo, titulo in CRITERIOS:
        conformes = auditoria[campo]
        nao_conformes = max(total - conformes, 0)
        percentual = round((conformes / total) * 100, 1) if total else 0
        resultados.append({
            "campo": campo,
            "titulo": titulo,
            "conformes": conformes,
            "nao_conformes": nao_conformes,
            "percentual": percentual,
            "observacao": auditoria[f"{campo}_obs"] or "",
        })

    return resultados


def carregar_detalhes_auditoria(conexao, id):
    auditoria = conexao.execute("""
        SELECT auditorias.*, setores.nome AS setor
        FROM auditorias
        INNER JOIN setores ON setores.id = auditorias.setor_id
        WHERE auditorias.id = ?
    """, (id,)).fetchone()
    if auditoria is None:
        return None, []
    planos = conexao.execute("""
        SELECT *,
            CASE
                WHEN DATE(NULLIF(prazo, '')) < CURRENT_DATE
                 AND status != 'Concluído'
                THEN 1 ELSE 0
            END AS atrasado
        FROM planos_acao_auditoria
        WHERE auditoria_id = ?
        ORDER BY id DESC
    """, (id,)).fetchall()
    return preparar_auditoria(auditoria), planos


def registrar_rotas(app):
    @app.route("/auditorias")
    def auditorias():
        conexao = conectar()

        try:
            garantir_tabelas_auditoria(conexao)

            setor_id = request.args.get("setor_id", "").strip()
            data_inicio = request.args.get("data_inicio", "").strip()
            data_fim = request.args.get("data_fim", "").strip()

            filtros = []
            parametros = []

            if setor_id:
                filtros.append("auditorias.setor_id = ?")
                parametros.append(setor_id)
            if data_inicio:
                filtros.append("DATE(auditorias.data) >= DATE(?)")
                parametros.append(data_inicio)
            if data_fim:
                filtros.append("DATE(auditorias.data) <= DATE(?)")
                parametros.append(data_fim)

            clausula_where = ""
            if filtros:
                clausula_where = "WHERE " + " AND ".join(filtros)

            registros = conexao.execute(f"""
                SELECT
                    auditorias.*,
                    setores.nome AS setor
                FROM auditorias
                INNER JOIN setores ON setores.id = auditorias.setor_id
                {clausula_where}
                ORDER BY auditorias.data DESC, auditorias.id DESC
            """, parametros).fetchall()
            registros = [preparar_auditoria(item) for item in registros]

            setores = conexao.execute("""
                SELECT id, nome
                FROM setores
                WHERE ativo = TRUE
                ORDER BY nome
            """).fetchall()

            total_prontuarios = sum(
                item["quantidade_prontuarios"] for item in registros
            )
            oportunidades = total_prontuarios * len(CRITERIOS)
            total_conformes = sum(
                sum(item[campo] for campo, _ in CRITERIOS)
                for item in registros
            )
            conformidade_geral = round(
                total_conformes / oportunidades * 100, 1
            ) if oportunidades else 0

            indicadores = []
            for campo, titulo in CRITERIOS:
                conformes = sum(item[campo] for item in registros)
                percentual = round(
                    conformes / total_prontuarios * 100, 1
                ) if total_prontuarios else 0
                indicadores.append({
                    "titulo": titulo,
                    "percentual": percentual,
                })

            return render_template(
                "auditorias.html",
                auditorias=registros,
                setores=setores,
                setor_id=setor_id,
                data_inicio=data_inicio,
                data_fim=data_fim,
                total_prontuarios=total_prontuarios,
                conformidade_geral=conformidade_geral,
                indicadores=indicadores,
                total_conformes=total_conformes,
                total_nao_conformes=max(oportunidades - total_conformes, 0),
            )
        finally:
            conexao.close()

    @app.route("/auditorias/nova", methods=["GET", "POST"])
    def nova_auditoria():
        conexao = conectar()

        try:
            garantir_tabelas_auditoria(conexao)

            setores = conexao.execute("""
                SELECT id, nome
                FROM setores
                WHERE ativo = TRUE
                ORDER BY nome
            """).fetchall()

            if request.method == "POST":
                try:
                    nome = validar_nome(request.form.get("nome"))
                    setor_id = request.form.get("setor_id", "").strip()
                    data_auditoria = request.form.get("data", "").strip()
                    responsavel = request.form.get("responsavel", "").strip()
                    quantidade = numero_inteiro(
                        request.form.get("quantidade_prontuarios"),
                        "A quantidade de prontuários",
                        1,
                    )

                    if not setor_id or not data_auditoria or not responsavel:
                        raise ValueError(
                            "Preencha a data, o setor e o responsável pela auditoria."
                        )

                    valores = {}
                    observacoes = {}
                    for campo, titulo in CRITERIOS:
                        valores[campo] = numero_inteiro(
                            request.form.get(campo, 0),
                            f"O total conforme de {titulo}",
                        )
                        if valores[campo] > quantidade:
                            raise ValueError(
                                f"O total conforme de {titulo} não pode "
                                "ultrapassar a quantidade de prontuários."
                            )
                        observacoes[campo] = request.form.get(
                            f"{campo}_obs", ""
                        ).strip()

                    conclusao = request.form.get("conclusao", "").strip()

                    consulta_insercao = """
                        INSERT INTO auditorias (
                            nome, setor_id, data, responsavel,
                            quantidade_prontuarios,
                            aprazamento_medicamentos,
                            aprazamento_medicamentos_obs,
                            checagem_medicamentos,
                            checagem_medicamentos_obs,
                            evolucao_enfermagem,
                            evolucao_enfermagem_obs,
                            evolucao_tecnico,
                            evolucao_tecnico_obs,
                            solicitacoes_farmacia,
                            solicitacoes_farmacia_obs,
                            solicitacoes_lavanderia,
                            solicitacoes_lavanderia_obs,
                            conclusao, criado_por
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """

                    if DATABASE_URL:
                        consulta_insercao += " RETURNING id"

                    cursor = conexao.execute(consulta_insercao, (
                        nome, setor_id, data_auditoria, responsavel, quantidade,
                        valores["aprazamento_medicamentos"],
                        observacoes["aprazamento_medicamentos"],
                        valores["checagem_medicamentos"],
                        observacoes["checagem_medicamentos"],
                        valores["evolucao_enfermagem"],
                        observacoes["evolucao_enfermagem"],
                        valores["evolucao_tecnico"],
                        observacoes["evolucao_tecnico"],
                        valores["solicitacoes_farmacia"],
                        observacoes["solicitacoes_farmacia"],
                        valores["solicitacoes_lavanderia"],
                        observacoes["solicitacoes_lavanderia"],
                        conclusao,
                        session.get("usuario_id"),
                    ))

                    auditoria_id = (
                        cursor.fetchone()[0]
                        if DATABASE_URL
                        else cursor.lastrowid
                    )

                    problema = request.form.get("problema", "").strip()
                    acao = request.form.get("acao", "").strip()

                    if problema or acao:
                        if not problema or not acao:
                            raise ValueError(
                                "Para criar o plano de ação, informe o problema e a ação corretiva."
                            )
                        conexao.execute("""
                            INSERT INTO planos_acao_auditoria (
                                auditoria_id, problema, acao, responsavel,
                                prazo, prioridade, status
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            auditoria_id,
                            problema,
                            acao,
                            request.form.get("plano_responsavel", "").strip(),
                            request.form.get("prazo", "").strip(),
                            request.form.get("prioridade", "Média").strip(),
                            "Pendente",
                        ))

                    conexao.commit()
                    flash("Auditoria registrada com sucesso.", "success")
                    return redirect(
                        url_for("detalhes_auditoria", id=auditoria_id)
                    )

                except ValueError as erro:
                    conexao.rollback()
                    flash(str(erro), "danger")

            return render_template(
                "nova_auditoria.html",
                setores=setores,
                criterios=CRITERIOS,
                data_hoje=date.today().isoformat(),
            )
        finally:
            conexao.close()

    @app.route("/auditorias/<int:id>")
    def detalhes_auditoria(id):
        conexao = conectar()

        try:
            garantir_tabelas_auditoria(conexao)
            auditoria, planos = carregar_detalhes_auditoria(conexao, id)

            if auditoria is None:
                return "Auditoria não encontrada.", 404

            resultados = montar_resultados(auditoria)
            conformidade_geral = round(
                sum(item["percentual"] for item in resultados)
                / len(resultados),
                1,
            ) if resultados else 0

            return render_template(
                "detalhes_auditoria.html",
                auditoria=auditoria,
                resultados=resultados,
                planos=planos,
                conformidade_geral=conformidade_geral,
                token_auditoria=token_formulario_auditoria(),
            )
        finally:
            conexao.close()

    @app.route("/auditorias/<int:id>/relatorio.pdf")
    def relatorio_auditoria(id):
        conexao = conectar()
        try:
            garantir_tabelas_auditoria(conexao)
            auditoria, planos = carregar_detalhes_auditoria(conexao, id)
        finally:
            conexao.close()
        if auditoria is None:
            return "Auditoria não encontrada.", 404

        resultados = montar_resultados(auditoria)
        conformidade_geral = round(
            sum(item["percentual"] for item in resultados) / len(resultados), 1,
        ) if resultados else 0
        arquivo = gerar_relatorio_auditoria_pdf(
            auditoria, resultados, planos, conformidade_geral,
        )
        resposta = send_file(
            arquivo, mimetype="application/pdf", as_attachment=False,
            download_name=f"{secure_filename(auditoria['nome']) or f'auditoria_{id}'}.pdf",
            max_age=0,
        )
        resposta.headers["Cache-Control"] = "private, no-store"
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        return resposta

    @app.route("/auditorias/<int:id>/nome", methods=["POST"])
    def renomear_auditoria(id):
        validar_token_auditoria()
        conexao = conectar()
        try:
            garantir_tabelas_auditoria(conexao)
            existe = conexao.execute(
                "SELECT id FROM auditorias WHERE id = ?", (id,),
            ).fetchone()
            if existe is None:
                return "Auditoria não encontrada.", 404
            try:
                nome = validar_nome(request.form.get("nome"))
            except ValueError as erro:
                flash(str(erro), "danger")
            else:
                conexao.execute("UPDATE auditorias SET nome = ? WHERE id = ?", (nome, id))
                conexao.commit()
                flash("Nome da auditoria atualizado.", "success")
            return redirect(url_for("detalhes_auditoria", id=id))
        finally:
            conexao.close()

    @app.route("/auditorias/<int:id>/excluir", methods=["POST"])
    def excluir_auditoria(id):
        validar_token_auditoria()
        conexao = conectar()
        try:
            garantir_tabelas_auditoria(conexao)
            existe = conexao.execute(
                "SELECT id FROM auditorias WHERE id = ?", (id,),
            ).fetchone()
            if existe is None:
                return "Auditoria não encontrada.", 404
            # Mantém a remoção completa também no SQLite sem foreign_keys ativo.
            conexao.execute("DELETE FROM planos_acao_auditoria WHERE auditoria_id = ?", (id,))
            conexao.execute("DELETE FROM auditorias WHERE id = ?", (id,))
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()
        flash("Auditoria e ações vinculadas excluídas.", "success")
        return redirect(url_for("auditorias"))

    @app.route("/auditorias/<int:id>/plano-acao", methods=["POST"])
    def adicionar_plano_acao(id):
        conexao = conectar()

        try:
            garantir_tabelas_auditoria(conexao)
            auditoria = conexao.execute(
                "SELECT id FROM auditorias WHERE id = ?", (id,)
            ).fetchone()
            if auditoria is None:
                return "Auditoria não encontrada.", 404

            problema = request.form.get("problema", "").strip()
            acao = request.form.get("acao", "").strip()
            if not problema or not acao:
                flash("Informe o problema e a ação corretiva.", "danger")
                return redirect(url_for("detalhes_auditoria", id=id))

            conexao.execute("""
                INSERT INTO planos_acao_auditoria (
                    auditoria_id, problema, acao, responsavel,
                    prazo, prioridade, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                id,
                problema,
                acao,
                request.form.get("responsavel", "").strip(),
                request.form.get("prazo", "").strip(),
                request.form.get("prioridade", "Média").strip(),
                "Pendente",
            ))
            conexao.commit()
            flash("Ação adicionada ao plano.", "success")
            return redirect(url_for("detalhes_auditoria", id=id))
        finally:
            conexao.close()

    @app.route("/planos-acao-auditoria/<int:id>/status", methods=["POST"])
    def atualizar_status_plano_auditoria(id):
        conexao = conectar()

        try:
            garantir_tabelas_auditoria(conexao)
            plano = conexao.execute("""
                SELECT id, auditoria_id
                FROM planos_acao_auditoria
                WHERE id = ?
            """, (id,)).fetchone()
            if plano is None:
                return "Plano de ação não encontrado.", 404

            status = request.form.get("status", "Pendente").strip()
            status_validos = {"Pendente", "Em andamento", "Concluído"}
            if status not in status_validos:
                flash("Status inválido.", "danger")
            else:
                data_conclusao = (
                    datetime.now().strftime("%Y-%m-%d")
                    if status == "Concluído"
                    else None
                )
                conexao.execute("""
                    UPDATE planos_acao_auditoria
                    SET status = ?, data_conclusao = ?
                    WHERE id = ?
                """, (status, data_conclusao, id))
                conexao.commit()
                flash("Status do plano de ação atualizado.", "success")

            return redirect(
                url_for("detalhes_auditoria", id=plano["auditoria_id"])
            )
        finally:
            conexao.close()

    @app.route("/auditorias/<int:id>/conclusao", methods=["POST"])
    def atualizar_conclusao_auditoria(id):
        conexao = conectar()

        try:
            garantir_tabelas_auditoria(conexao)
            conclusao = request.form.get("conclusao", "").strip()
            conexao.execute(
                "UPDATE auditorias SET conclusao = ? WHERE id = ?",
                (conclusao, id),
            )
            conexao.commit()
            flash("Conclusão atualizada com sucesso.", "success")
            return redirect(url_for("detalhes_auditoria", id=id))
        finally:
            conexao.close()
