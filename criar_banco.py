from database.conexao import DATABASE_URL, conectar
from werkzeug.security import generate_password_hash



SETORES_PADRAO = [
    "Classificação de Risco",
    "Centro Obstétrico",
    "Observação Clínica",
    "Centro de Material e Esterilização (CME)",
    "Centro Cirúrgico (CC)",
    "Alojamento Conjunto (ALCON)",
    "UTI Neonatal",
    "UCINCa",
    "Clínica Cirúrgica",
    "Clínica Ginecológica"
]

def cadastrar_setores_padrao(conexao):

    for nome_setor in SETORES_PADRAO:

        setor = conexao.execute("""
            SELECT id
            FROM setores
            WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
        """, (
            nome_setor,
        )).fetchone()

        if setor is None:

            conexao.execute("""
                INSERT INTO setores (
                    nome,
                    ativo
                )
                VALUES (?, ?)
            """, (
                nome_setor,
                True
            ))

        else:

            conexao.execute("""
                UPDATE setores
                SET ativo = TRUE
                WHERE id = ?
            """, (
                setor["id"],
            ))


def criar_banco():

    conexao = conectar()

    chave_primaria = (
        "SERIAL PRIMARY KEY"
        if DATABASE_URL
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    try:

        # =========================
        # SETORES
        # =========================

        conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS setores(
            id {chave_primaria},
            nome VARCHAR(200) UNIQUE NOT NULL,
            ativo BOOLEAN DEFAULT TRUE
        )
        """)

        # =========================
        # USUÁRIOS
        # =========================

        conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS usuarios(
            id {chave_primaria},
            nome VARCHAR(200) NOT NULL,
            email VARCHAR(200) UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            perfil VARCHAR(50) DEFAULT 'Enfermeiro',
            ativo BOOLEAN DEFAULT TRUE
        )
        """)

        # =========================
        # RONDAS
        # =========================

        conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS rondas(
            id {chave_primaria},
            setor_id INTEGER NOT NULL REFERENCES setores(id),
            data VARCHAR(20) NOT NULL,
            hora VARCHAR(10) NOT NULL,
            responsavel VARCHAR(200) NOT NULL,
            observacoes TEXT
        )
        """)

        # =========================
        # PENDÊNCIAS
        # =========================

        conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS pendencias(
            id {chave_primaria},
            ronda_id INTEGER NOT NULL REFERENCES rondas(id) ON DELETE CASCADE,
            descricao TEXT NOT NULL,
            categoria VARCHAR(100),
            prioridade VARCHAR(30) DEFAULT 'Baixa',
            status VARCHAR(30) DEFAULT 'Aberta',
            responsavel VARCHAR(200),
            prazo VARCHAR(30),
            observacao_resolucao TEXT,
            foto_antes TEXT,
            foto_depois TEXT
        )
        """)

        # =========================
        # AUDITORIAS ASSISTENCIAIS
        # =========================

        conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS auditorias(
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

        conexao.execute(f"""
        CREATE TABLE IF NOT EXISTS planos_acao_auditoria(
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
        CREATE INDEX IF NOT EXISTS indice_rondas_setor
        ON rondas(setor_id)
        """)

        conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_rondas_data
        ON rondas(data)
        """)

        conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_pendencias_ronda
        ON pendencias(ronda_id)
        """)

        conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_pendencias_status
        ON pendencias(status)
        """)

        conexao.execute("""
        CREATE INDEX IF NOT EXISTS indice_pendencias_prazo
        ON pendencias(prazo)
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

        print("Tabelas criadas.")

        # =========================
        # SETORES PADRÃO
        # =========================

        cadastrar_setores_padrao(conexao)

        conexao.commit()

        # =========================
        # ADMIN
        # =========================

        admin = conexao.execute("""
            SELECT id
            FROM usuarios
            WHERE LOWER(email)=LOWER(?)
        """, ("admin@sgrg.com",)).fetchone()

        if admin is None:

            conexao.execute("""
            INSERT INTO usuarios(
                nome,
                email,
                senha,
                perfil,
                ativo
            )
            VALUES(?,?,?,?,?)
            """, (
                "Administrador",
                "admin@sgrg.com",
                generate_password_hash("123456"),
                "Administrador",
                True
            ))

            conexao.commit()

            print("Administrador criado.")

        print("Banco criado com sucesso.")

    except Exception as erro:

        conexao.rollback()

        raise erro

    finally:

        conexao.close()

if __name__ == "__main__":

    criar_banco()
