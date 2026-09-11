from datetime import date, datetime
import secrets

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from database.conexao import DATABASE_URL, conectar
from pdf.relatorio_auditoria import gerar_relatorio_auditoria_pdf


CRITERIOS = [
    ("prontuarios_revisados", "Prontuários revisados"),
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
            prontuarios_revisados INTEGER,
            prontuarios_revisados_obs TEXT,
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

    # Colunas adicionais preservam os registros das versões anteriores.
    # Não conformidades antigas continuam sendo calculadas a partir da amostra
    # original, somente quando não há uma contagem independente salva.
    if DATABASE_URL:
        colunas = conexao.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'auditorias'
        """).fetchall()
        existentes = {coluna["column_name"] for coluna in colunas}
    else:
        colunas = conexao.execute("PRAGMA table_info(auditorias)").fetchall()
        existentes = {coluna["name"] for coluna in colunas}

    novas_colunas = [
        ("nome", "VARCHAR(200)"),
        ("prontuarios_revisados", "INTEGER"),
        ("prontuarios_revisados_obs", "TEXT"),
        *[(f"{campo}_nao_conformes", "INTEGER") for campo, _ in CRITERIOS],
    ]
    for coluna, tipo in novas_colunas:
        if coluna not in existentes:
            condicao = "IF NOT EXISTS " if DATABASE_URL else ""
            conexao.execute(
                f"ALTER TABLE auditorias ADD COLUMN {condicao}{coluna} {tipo}"
            )

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
    auditoria.update(resumir_resultados(montar_resultados(auditoria)))
    return auditoria


def montar_resultados(auditoria):
    resultados = []

    for campo, titulo in CRITERIOS:
        conformes = auditoria.get(campo)
        nao_conformes = auditoria.get(f"{campo}_nao_conformes")
        if campo == "prontuarios_revisados" and conformes is None:
            # A versão anterior guardava apenas a quantidade de prontuários,
            # sem classificar o próprio tópico como conforme ou não conforme.
            total = auditoria["quantidade_prontuarios"]
            percentual = None
        else:
            if nao_conformes is None:
                nao_conformes = max(auditoria["quantidade_prontuarios"] - conformes, 0)
            total = conformes + nao_conformes
            percentual = round(conformes / total * 100, 1) if total else None
        resultados.append({
            "campo": campo,
            "titulo": titulo,
            "total": total,
            "conformes": conformes,
            "nao_conformes": nao_conformes,
            "percentual": percentual,
            "observacao": auditoria.get(f"{campo}_obs") or "",
        })

    return resultados


def resumir_resultados(resultados):
    conformes = sum(item["conformes"] or 0 for item in resultados)
    nao_conformes = sum(item["nao_conformes"] or 0 for item in resultados)
    total = conformes + nao_conformes
    return {
        "total_conformes": conformes,
        "total_nao_conformes": nao_conformes,
        "total_avaliado": total,
        "conformidade_geral": round(conformes / total * 100, 1) if total else None,
    }


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

            resultados_registros = [montar_resultados(item) for item in registros]
            resumo = resumir_resultados([
                resultado
                for resultados in resultados_registros
                for resultado in resultados
            ])

            indicadores = []
            for indice, (_, titulo) in enumerate(CRITERIOS):
                resumo_criterio = resumir_resultados([
                    resultados[indice] for resultados in resultados_registros
                ])
                indicadores.append({
                    "titulo": titulo,
                    "percentual": resumo_criterio["conformidade_geral"],
                })

            return render_template(
                "auditorias.html",
                auditorias=registros,
                setores=setores,
                setor_id=setor_id,
                data_inicio=data_inicio,
                data_fim=data_fim,
                indicadores=indicadores,
                **resumo,
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
                    if not setor_id or not data_auditoria or not responsavel:
                        raise ValueError(
                            "Preencha a data, o setor e o responsável pela auditoria."
                        )

                    valores = {}
                    observacoes = {}
                    for campo, titulo in CRITERIOS:
                        valores[campo] = numero_inteiro(
                            request.form.get(campo),
                            f"O total conforme de {titulo}",
                        )
                        valores[f"{campo}_nao_conformes"] = numero_inteiro(
                            request.form.get(f"{campo}_nao_conformes"),
                            f"O total não conforme de {titulo}",
                        )
                        observacoes[campo] = request.form.get(
                            f"{campo}_obs", ""
                        ).strip()

                    if not sum(valores.values()):
                        raise ValueError("Informe pelo menos uma quantidade conforme ou não conforme no checklist.")

                    # Mantém a coluna original para compatibilidade; ela agora
                    # representa somente o total do tópico de prontuários.
                    quantidade = valores["prontuarios_revisados"] + valores["prontuarios_revisados_nao_conformes"]
                    colunas = ["nome", "setor_id", "data", "responsavel", "quantidade_prontuarios"]
                    parametros = [nome, setor_id, data_auditoria, responsavel, quantidade]
                    for campo, _ in CRITERIOS:
                        colunas.extend([campo, f"{campo}_nao_conformes", f"{campo}_obs"])
                        parametros.extend([valores[campo], valores[f"{campo}_nao_conformes"], observacoes[campo]])
                    colunas.extend(["conclusao", "criado_por"])
                    parametros.extend([request.form.get("conclusao", "").strip(), session.get("usuario_id")])
                    consulta_insercao = (
                        f"INSERT INTO auditorias ({', '.join(colunas)}) "
                        f"VALUES ({', '.join(['?'] * len(colunas))})"
                    )
                    if DATABASE_URL:
                        consulta_insercao += " RETURNING id"

                    cursor = conexao.execute(consulta_insercao, parametros)

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

            return render_template(
                "detalhes_auditoria.html",
                auditoria=auditoria,
                resultados=resultados,
                planos=planos,
                conformidade_geral=auditoria["conformidade_geral"],
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
        arquivo = gerar_relatorio_auditoria_pdf(
            auditoria, resultados, planos, auditoria["conformidade_geral"],
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
