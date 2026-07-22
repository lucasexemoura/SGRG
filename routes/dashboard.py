from flask import render_template
from database.conexao import conectar


def registrar_rotas(app):

    @app.route("/")
    def inicio():

        conexao = conectar()

        try:

            total_rondas = conexao.execute("""
                SELECT COUNT(*)
                FROM rondas
            """).fetchone()[0]

            total_setores = conexao.execute("""
                SELECT COUNT(*)
                FROM setores
                WHERE ativo = 1
            """).fetchone()[0]

            rondas_hoje = conexao.execute("""
                SELECT COUNT(*)
                FROM rondas
                WHERE data = DATE('now', 'localtime')
            """).fetchone()[0]

            total_pendencias = conexao.execute("""
                SELECT COUNT(*)
                FROM pendencias
            """).fetchone()[0]

            pendencias_abertas = conexao.execute("""
                SELECT COUNT(*)
                FROM pendencias
                WHERE status = 'Aberta'
            """).fetchone()[0]

            pendencias_andamento = conexao.execute("""
                SELECT COUNT(*)
                FROM pendencias
                WHERE status = 'Em andamento'
            """).fetchone()[0]

            pendencias_resolvidas = conexao.execute("""
                SELECT COUNT(*)
                FROM pendencias
                WHERE status = 'Resolvida'
            """).fetchone()[0]

            pendencias_urgentes = conexao.execute("""
                SELECT COUNT(*)
                FROM pendencias
                WHERE prioridade = 'Urgente'
                  AND status != 'Resolvida'
            """).fetchone()[0]

            pendencias_atrasadas = conexao.execute("""
                SELECT COUNT(*)
                FROM pendencias
                WHERE prazo IS NOT NULL
                  AND prazo != ''
                  AND DATE(prazo) < DATE('now', 'localtime')
                  AND status != 'Resolvida'
            """).fetchone()[0]

            if total_pendencias > 0:

                taxa_resolucao = round(
                    (
                        pendencias_resolvidas
                        / total_pendencias
                    ) * 100,
                    1
                )

            else:

                taxa_resolucao = 0

            pendencias_por_status = conexao.execute("""
                SELECT
                    status,
                    COUNT(*) AS total
                FROM pendencias
                GROUP BY status
                ORDER BY
                    CASE status
                        WHEN 'Aberta' THEN 1
                        WHEN 'Em andamento' THEN 2
                        WHEN 'Resolvida' THEN 3
                        ELSE 4
                    END
            """).fetchall()

            pendencias_por_prioridade = conexao.execute("""
                SELECT
                    prioridade,
                    COUNT(*) AS total
                FROM pendencias
                GROUP BY prioridade
                ORDER BY
                    CASE prioridade
                        WHEN 'Urgente' THEN 1
                        WHEN 'Alta' THEN 2
                        WHEN 'Média' THEN 3
                        WHEN 'Baixa' THEN 4
                        ELSE 5
                    END
            """).fetchall()

            pendencias_por_setor = conexao.execute("""
                SELECT
                    setores.nome AS setor,
                    COUNT(pendencias.id) AS total
                FROM setores
                LEFT JOIN rondas
                    ON rondas.setor_id = setores.id
                LEFT JOIN pendencias
                    ON pendencias.ronda_id = rondas.id
                WHERE setores.ativo = 1
                GROUP BY
                    setores.id,
                    setores.nome
                ORDER BY
                    total DESC,
                    setores.nome ASC
                LIMIT 10
            """).fetchall()

            ultimas_rondas = conexao.execute("""
                SELECT
                    rondas.id,
                    rondas.data,
                    rondas.hora,
                    rondas.responsavel,
                    setores.nome AS setor
                FROM rondas
                INNER JOIN setores
                    ON setores.id = rondas.setor_id
                ORDER BY
                    rondas.data DESC,
                    rondas.hora DESC,
                    rondas.id DESC
                LIMIT 5
            """).fetchall()

            ultimas_pendencias = conexao.execute("""
                SELECT
                    pendencias.id,
                    pendencias.descricao,
                    pendencias.prioridade,
                    pendencias.status,
                    pendencias.prazo,
                    rondas.id AS ronda_id,
                    setores.nome AS setor,
                    CASE
                        WHEN pendencias.prazo IS NOT NULL
                         AND pendencias.prazo != ''
                         AND DATE(pendencias.prazo)
                             < DATE('now', 'localtime')
                         AND pendencias.status != 'Resolvida'
                        THEN 1
                        ELSE 0
                    END AS atrasada
                FROM pendencias
                INNER JOIN rondas
                    ON rondas.id = pendencias.ronda_id
                INNER JOIN setores
                    ON setores.id = rondas.setor_id
                ORDER BY
                    atrasada DESC,
                    CASE pendencias.prioridade
                        WHEN 'Urgente' THEN 1
                        WHEN 'Alta' THEN 2
                        WHEN 'Média' THEN 3
                        WHEN 'Baixa' THEN 4
                        ELSE 5
                    END,
                    pendencias.id DESC
                LIMIT 5
            """).fetchall()

            return render_template(
                "index.html",
                total_rondas=total_rondas,
                total_setores=total_setores,
                rondas_hoje=rondas_hoje,
                total_pendencias=total_pendencias,
                pendencias_abertas=pendencias_abertas,
                pendencias_andamento=pendencias_andamento,
                pendencias_resolvidas=pendencias_resolvidas,
                pendencias_urgentes=pendencias_urgentes,
                pendencias_atrasadas=pendencias_atrasadas,
                taxa_resolucao=taxa_resolucao,
                pendencias_por_status=pendencias_por_status,
                pendencias_por_prioridade=pendencias_por_prioridade,
                pendencias_por_setor=pendencias_por_setor,
                ultimas_rondas=ultimas_rondas,
                ultimas_pendencias=ultimas_pendencias
            )

        finally:

            conexao.close()