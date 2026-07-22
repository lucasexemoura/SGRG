# SGRG — versão PostgreSQL

## Arquivos já ajustados

- conexão híbrida PostgreSQL/SQLite;
- criação das tabelas no PostgreSQL;
- dashboard e filtros de datas;
- booleanos de usuários e setores;
- rotas de rondas, pendências, histórico, usuários e setores;
- dependências do PostgreSQL;
- inicialização automática do banco no Render.

## Uso local

1. Copie `.env.example` para `.env`.
2. Coloque a **External Database URL** do Render em `DATABASE_URL`.
3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Crie/atualize as tabelas:

```bash
python criar_banco.py
```

5. Inicie o sistema:

```bash
python app.py
```

## Render

Configure estas variáveis no serviço web:

- `DATABASE_URL`: use a **Internal Database URL** do PostgreSQL do Render;
- `SGRG_SECRET_KEY`: uma chave longa e secreta;
- `SESSION_COOKIE_SECURE`: `true`;
- `FLASK_DEBUG`: `false`.

O `Procfile` já contém:

```text
web: python criar_banco.py && gunicorn app:app
```

## Administrador inicial

- E-mail: `admin@sgrg.com`
- Senha: `123456`

Troque a senha após o primeiro acesso.
