-- Extensions exigidas pelo PlanoBackend.md (§3.2 + §5.4)
-- pgcrypto: pgp_sym_encrypt para campos sensíveis (LGPD)
-- vector:   pgvector para embeddings (memória/RAG na Sprint 4)
-- uuid-ossp: redundante com gen_random_uuid (que vem do pgcrypto), mantido por hábito

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Setting custom usado para multi-tenancy via RLS (Sprint 1).
-- Definir o GUC vazio aqui evita erro em sessões que ainda não setaram.
ALTER DATABASE fiscal SET app.tenant_id TO '';

-- Role não-superuser para o app — necessário porque fiscal é o bootstrap user
-- e PostgreSQL não permite rebaixá-lo. Usando SET LOCAL ROLE fiscal_app nas
-- sessões, o RLS passa a ser aplicado (superusers bypassam RLS).
CREATE ROLE fiscal_app WITH LOGIN PASSWORD 'fiscal_app' NOINHERIT;
GRANT CONNECT ON DATABASE fiscal TO fiscal_app;
GRANT USAGE ON SCHEMA public TO fiscal_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON empresa, usuario TO fiscal_app;
GRANT SELECT, INSERT ON tenant TO fiscal_app;
GRANT SELECT, INSERT, UPDATE ON alembic_version TO fiscal_app;
GRANT fiscal_app TO fiscal;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fiscal_app;
