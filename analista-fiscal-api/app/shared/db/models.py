from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    DATE,
    NUMERIC,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.shared.db.base import Base
from app.shared.types import JsonObject

try:
    from pgvector.sqlalchemy import Vector as PG_VECTOR
    _VECTOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _VECTOR_AVAILABLE = False
    PG_VECTOR = None  # noqa: N816


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    usuarios: Mapped[list[Usuario]] = relationship("Usuario", back_populates="tenant")
    empresas: Mapped[list[Empresa]] = relationship("Empresa", back_populates="tenant")


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="usuarios")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_usuario_tenant_email"),
        Index("ix_usuario_tenant_email", "tenant_id", "email"),
    )


class Empresa(Base):
    __tablename__ = "empresa"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    razao_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regime_tributario: Mapped[str] = mapped_column(String(50), nullable=False)
    perfil_ui: Mapped[str] = mapped_column(String(50), nullable=False)
    anexo_simples: Mapped[str | None] = mapped_column(CHAR(1), nullable=True)
    cnae_principal: Mapped[str | None] = mapped_column(String(10), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uf: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    ie: Mapped[str | None] = mapped_column(String(20), nullable=True)
    im: Mapped[str | None] = mapped_column(String(20), nullable=True)
    faturamento_12m: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    whatsapp_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    proximo_numero_rps: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    ativa: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="empresas")
    documentos: Mapped[list[DocumentoFiscal]] = relationship(
        "DocumentoFiscal", back_populates="empresa"
    )
    apuracoes: Mapped[list[ApuracaoFiscal]] = relationship(
        "ApuracaoFiscal", back_populates="empresa"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "cnpj", name="uq_empresa_tenant_cnpj"),
        CheckConstraint(
            "regime_tributario IN ('mei','simples_nacional','lucro_presumido','lucro_real')",
            name="ck_empresa_regime",
        ),
        CheckConstraint(
            "perfil_ui IN ('mei','sn_sem_funcionarios','sn_com_funcionarios','lucro_presumido','lucro_real')",
            name="ck_empresa_perfil",
        ),
        CheckConstraint(
            "anexo_simples IS NULL OR anexo_simples IN ('I','II','III','IV','V')",
            name="ck_empresa_anexo",
        ),
        Index("ix_empresa_tenant", "tenant_id"),
        Index("ix_empresa_cnpj", "cnpj"),
        Index("ix_empresa_tenant_perfil", "tenant_id", "perfil_ui"),
    )


class DocumentoFiscal(Base):
    """NF-e / NFS-e / NFC-e ingerida. Imutável após criação (§8.2)."""

    __tablename__ = "documento_fiscal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    direcao: Mapped[str] = mapped_column(String(10), nullable=False)
    chave: Mapped[str | None] = mapped_column(String(44), nullable=True)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    serie: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="autorizada")
    emitida_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    cnpj_emitente: Mapped[str] = mapped_column(String(14), nullable=False)
    cnpj_destinatario: Mapped[str | None] = mapped_column(String(14), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_impostos: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_icms: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_ipi: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_pis: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_cofins: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_iss: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    cfop: Mapped[str | None] = mapped_column(String(4), nullable=True)
    cst: Mapped[str | None] = mapped_column(String(3), nullable=True)
    ncm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    valor_cbs: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_ibs: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    xml_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    focus_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    natureza_operacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regime_emitente: Mapped[str | None] = mapped_column(String(50), nullable=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    supersedes: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documento_fiscal.id"), nullable=True
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documento_fiscal.id"), nullable=True
    )
    evento: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    ingested_via: Mapped[str | None] = mapped_column(String(50), nullable=True)

    empresa: Mapped[Empresa] = relationship("Empresa", back_populates="documentos")

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('nfe','nfse','nfce','cte','mdfe','nfcom','dce')",
            name="ck_doc_tipo",
        ),
        CheckConstraint("direcao IN ('saida','entrada')", name="ck_doc_direcao"),
        CheckConstraint(
            "evento IS NULL OR evento IN ('cancelou','denegou','retificou')",
            name="ck_doc_evento",
        ),
        CheckConstraint(
            r"cfop IS NULL OR cfop ~ '^\d{4}$'",
            name="ck_doc_cfop_formato",
        ),
        CheckConstraint(
            r"cst IS NULL OR cst ~ '^\d{2,3}$'",
            name="ck_doc_cst_formato",
        ),
        Index("ix_doc_chave", "chave"),
        Index("ix_doc_empresa_tipo", "empresa_id", "tipo", "direcao"),
        Index("ix_doc_emitida", "empresa_id", "emitida_em"),
        Index("ix_doc_tenant", "tenant_id"),
        Index(
            "ix_doc_vigente",
            "empresa_id",
            "tipo",
            "emitida_em",
            postgresql_where="superseded_by IS NULL",
        ),
        Index(
            "uq_doc_empresa_chave_vigente",
            "empresa_id",
            "chave",
            unique=True,
            postgresql_where="superseded_by IS NULL AND chave IS NOT NULL",
        ),
    )


class TabelaSimplesFaixa(Base):
    """Tabela tributária SN — SCD Type 2 (§8.3). Nunca atualiza linhas; adiciona nova versão."""

    __tablename__ = "tabela_simples_faixa"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    anexo: Mapped[str] = mapped_column(CHAR(3), nullable=False)  # I,II,III,IV,V
    faixa: Mapped[int] = mapped_column(Integer, nullable=False)
    rbt12_ate: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    aliquota_nominal: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    parcela_deduzir: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("anexo IN ('I','II','III','IV','V')", name="ck_faixa_anexo"),
        CheckConstraint("faixa BETWEEN 1 AND 6", name="ck_faixa_numero"),
        Index("ix_faixa_anexo_vigente", "anexo", "valid_from", "valid_to"),
    )


class ApuracaoFiscal(Base):
    """Resultado imutável de uma apuração fiscal mensal (§8.2)."""

    __tablename__ = "apuracao_fiscal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id"), nullable=False
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    regime: Mapped[str] = mapped_column(String(50), nullable=False)
    input_jsonb: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    output_jsonb: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    faixas_usadas: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="calculado")
    transmitido_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    pago_em: Mapped[date | None] = mapped_column(DATE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped[Empresa] = relationship("Empresa", back_populates="apuracoes")

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('das','irpj','csll','pis','cofins','iss','icms','dctf','efd_contrib')",
            name="ck_apuracao_tipo",
        ),
        UniqueConstraint("empresa_id", "competencia", "tipo", name="uq_apuracao_empresa_comp_tipo"),
        Index("ix_apuracao_tenant", "tenant_id"),
        Index("ix_apuracao_empresa_comp", "empresa_id", "competencia"),
    )


class SelicMensal(Base):
    """Taxa SELIC acumulada por competência — usada para cálculo de mora e denúncia espontânea."""

    __tablename__ = "selic_mensal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False, unique=True)
    taxa_mensal: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False, server_default="BACEN")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class AgendaItem(Base):
    """Item do calendário fiscal por empresa — obrigações com data de vencimento."""

    __tablename__ = "agenda_item"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id"), nullable=False
    )
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_vencimento: Mapped[date] = mapped_column(DATE, nullable=False)
    regime: Mapped[str] = mapped_column(String(50), nullable=False)
    tipo_obrigacao: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendente")
    alertado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped[Empresa] = relationship("Empresa")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pendente','concluido','vencido')",
            name="ck_agenda_status",
        ),
        Index("ix_agenda_empresa_venc", "empresa_id", "data_vencimento"),
        Index("ix_agenda_tenant", "tenant_id"),
    )


class MemoriaNode(Base):
    """Nó do grafo de memória da empresa — fatos persistentes citáveis pelo LLM (§5.9)."""

    __tablename__ = "memoria_node"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    rotulo: Mapped[str] = mapped_column(String(255), nullable=False)
    atributos: Mapped[JsonObject] = mapped_column(JSONB, nullable=False, server_default="{}")
    fonte_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    fonte_tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    imutavel: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    edges_origem: Mapped[list[MemoriaEdge]] = relationship(
        "MemoriaEdge",
        foreign_keys="MemoriaEdge.origem_id",
        back_populates="origem",
    )

    __table_args__ = (
        Index("ix_memoria_node_empresa", "empresa_id", "tipo"),
        Index("ix_memoria_node_tenant", "tenant_id"),
    )


class MemoriaEdge(Base):
    """Aresta do grafo de memória — relações SCD Type 2 entre nós (§5.9)."""

    __tablename__ = "memoria_edge"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    origem_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("memoria_node.id"), nullable=False
    )
    destino_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("memoria_node.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    atributos: Mapped[JsonObject] = mapped_column(JSONB, nullable=False, server_default="{}")
    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    origem: Mapped[MemoriaNode] = relationship(
        "MemoriaNode", foreign_keys=[origem_id], back_populates="edges_origem"
    )

    __table_args__ = (
        Index("ix_memoria_edge_origem", "origem_id"),
        Index("ix_memoria_edge_destino", "destino_id"),
        Index("ix_memoria_edge_empresa", "empresa_id"),
    )


class SessaoWhatsApp(Base):
    """Estado de conversa WhatsApp por número de telefone e empresa (Sprint 5).

    Persiste o estado entre mensagens para suportar contexto multi-turno.
    """

    __tablename__ = "sessao_whatsapp"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[JsonObject] = mapped_column(JSONB, nullable=False, server_default="{}")
    mensagens_na_sessao: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped[Empresa] = relationship("Empresa")

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_sessao_whatsapp_tenant_phone"),
        Index("ix_sessao_whatsapp_phone", "phone"),
        Index("ix_sessao_whatsapp_tenant", "tenant_id"),
    )


class SerproCredencial(Base):
    """Cert e-CNPJ (.p12) + senha do cliente, cifrados para uso pelo SERPRO (Sprint 6).

    Sprint 6 § Plano §8.7 / §8.12: o cliente assina termo de delegação no
    onboarding; cert é armazenado cifrado e usado pelo SERPRO Integra Contador
    para transmissão de PGDAS-D/DCTFWeb/etc.
    """

    __tablename__ = "serpro_credencial"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    cert_p12_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    cert_senha_cifrada: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    cert_valid_until: Mapped[date] = mapped_column(DATE, nullable=False)
    termo_delegacao_assinado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", name="uq_serpro_credencial_empresa"),
        Index("ix_serpro_credencial_tenant", "tenant_id"),
    )


class Certidao(Base):
    """Certidão CND / CRF / CNDT emitida (Sprint 6).

    Append-only. Renovação anual gera nova linha. `valid_until` indica até
    quando a certidão atual continua válida (CND: 180 dias; CRF: 30 dias;
    CNDT: 180 dias).
    """

    __tablename__ = "certidao"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    emitida_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    valid_until: Mapped[date | None] = mapped_column(DATE, nullable=True)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    serpro_chamada_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("tipo IN ('CND','CRF','CNDT')", name="ck_certidao_tipo"),
        CheckConstraint(
            "status IN ('emitida','negativa','positiva',"
            "'positiva_com_efeitos_de_negativa','erro','processando')",
            name="ck_certidao_status",
        ),
        Index("ix_certidao_tenant", "tenant_id"),
        Index("ix_certidao_empresa_tipo", "empresa_id", "tipo"),
        Index("ix_certidao_valid_until", "valid_until"),
    )


class SerproChamada(Base):
    """Audit log de cada chamada SERPRO (Sprint 6). §8.10."""

    __tablename__ = "serpro_chamada"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    servico: Mapped[str] = mapped_column(String(60), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status_http: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "servico",
            "idempotency_key",
            name="uq_serpro_chamada_idempotente",
        ),
        Index("ix_serpro_chamada_tenant", "tenant_id"),
        Index("ix_serpro_chamada_servico_data", "servico", "criado_em"),
    )


class TransmissaoPgdas(Base):
    """Transmissão de PGDAS-D ao SERPRO (Sprint 6 PR2). Append-only.

    Cada tentativa de transmitir um PGDAS-D para uma competência gera uma linha.
    Retificações criam nova linha com `tentativa = N+1` e `eh_retificadora=True`.
    """

    __tablename__ = "transmissao_pgdas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    apuracao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("apuracao_fiscal.id", ondelete="RESTRICT"),
        nullable=False,
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    tentativa: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    eh_retificadora: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    protocolo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    recibo_pdf_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    serpro_chamada_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    payload_envio_json: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    resposta_json: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pendente','transmitida','erro','retificada')",
            name="ck_transmissao_pgdas_status",
        ),
        UniqueConstraint(
            "empresa_id",
            "competencia",
            "tentativa",
            name="uq_transmissao_pgdas_comp_tentativa",
        ),
        Index("ix_transmissao_pgdas_tenant", "tenant_id"),
        Index("ix_transmissao_pgdas_empresa_comp", "empresa_id", "competencia"),
    )


class PluggyItem(Base):
    """Conexão Open Finance Pluggy autorizada pelo cliente (Sprint 7 PR1).

    Uma empresa pode ter múltiplos itens (um por banco/conector). O
    ``pluggy_item_id`` é o identificador externo da Pluggy — UNIQUE para
    idempotência do callback do widget.
    """

    __tablename__ = "pluggy_item"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    pluggy_item_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    connector_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connector_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    status_detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    consent_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="READ_ONLY"
    )
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "consent_type IN ('READ_ONLY','PAYMENT_INITIATION')",
            name="ck_pluggy_item_consent",
        ),
        Index("ix_pluggy_item_tenant", "tenant_id"),
        Index("ix_pluggy_item_empresa", "empresa_id"),
    )


class ContaBancaria(Base):
    """Conta bancária extraída via Pluggy (Sprint 7 PR1).

    ``saldo_atual`` é snapshot do último sync — fonte de verdade fica no
    próprio banco. Atualizado a cada chamada de sync de transações.
    """

    __tablename__ = "conta_bancaria"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    pluggy_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pluggy_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    pluggy_account_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    banco_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agencia: Mapped[str | None] = mapped_column(String(20), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    subtipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    moeda: Mapped[str] = mapped_column(String(3), nullable=False, server_default="BRL")
    saldo_atual: Mapped[Decimal] = mapped_column(
        NUMERIC(18, 2), nullable=False, server_default="0"
    )
    saldo_disponivel: Mapped[Decimal | None] = mapped_column(NUMERIC(18, 2), nullable=True)
    saldo_atualizado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    ativa: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('CHECKING','SAVINGS','CREDIT_CARD')",
            name="ck_conta_bancaria_tipo",
        ),
        Index("ix_conta_bancaria_tenant", "tenant_id"),
        Index("ix_conta_bancaria_empresa", "empresa_id"),
    )


class TransacaoBancaria(Base):
    """Transação bancária extraída via Pluggy (Sprint 7 PR2).

    UPSERT por ``pluggy_transaction_id``. ``valor`` é signed (positivo
    entrada, negativo saída). ``raw_json`` mantém snapshot bruto Pluggy
    para auditoria e re-processamento se o algoritmo de conciliação mudar
    (§8.2).
    """

    __tablename__ = "transacao_bancaria"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    conta_bancaria_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conta_bancaria.id", ondelete="CASCADE"),
        nullable=False,
    )
    pluggy_transaction_id: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True
    )
    data_transacao: Mapped[date] = mapped_column(DATE, nullable=False)
    valor: Mapped[Decimal] = mapped_column(NUMERIC(18, 2), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="CONFIRMED"
    )
    categoria_pluggy: Mapped[str | None] = mapped_column(String(80), nullable=True)
    merchant_cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    merchant_nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_json: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("tipo IN ('CREDIT','DEBIT')", name="ck_transacao_tipo"),
        CheckConstraint(
            "status IN ('PENDING','CONFIRMED')", name="ck_transacao_status"
        ),
        Index("ix_transacao_tenant", "tenant_id"),
        Index("ix_transacao_conta_data", "conta_bancaria_id", "data_transacao"),
        Index("ix_transacao_empresa_data", "empresa_id", "data_transacao"),
    )


class SaldoContaMes(Base):
    """Saldo mensal materializado por (empresa, conta, competencia) — Sprint 9 PR3.

    Populado pelo serviço de encerramento mensal. ``status='fechado'`` é o
    valor canônico após encerramento; ``aberto`` indica computação em curso.
    """

    __tablename__ = "saldo_conta_mes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    conta_contabil_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conta_contabil.id", ondelete="RESTRICT"),
        nullable=False,
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    saldo_inicial: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    total_debitos: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    total_creditos: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    saldo_final: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="fechado"
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('aberto','fechado')", name="ck_saldo_status"),
        UniqueConstraint(
            "empresa_id",
            "conta_contabil_id",
            "competencia",
            name="uq_saldo_empresa_conta_comp",
        ),
        Index("ix_saldo_tenant", "tenant_id"),
        Index("ix_saldo_empresa_comp", "empresa_id", "competencia"),
    )


class ContaContabil(Base):
    """Conta contábil hierárquica — SCD Type 2 (Sprint 9 PR1).

    Apenas contas com ``aceita_lancamento=True`` (analíticas) podem aparecer
    em ``partida_lancamento``. Sintéticas (contas-pai) servem para
    consolidação no balancete.
    """

    __tablename__ = "conta_contabil"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conta_contabil.id", ondelete="RESTRICT"),
        nullable=True,
    )
    natureza: Mapped[str] = mapped_column(String(1), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)
    aceita_lancamento: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    codigo_ecd_referencial: Mapped[str | None] = mapped_column(String(20), nullable=True)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("natureza IN ('D','C')", name="ck_conta_natureza"),
        CheckConstraint(
            "tipo IN ('ativo','passivo','patrimonio_liquido','receita',"
            "'despesa','conta_resultado')",
            name="ck_conta_tipo",
        ),
        CheckConstraint("nivel BETWEEN 1 AND 8", name="ck_conta_nivel"),
        UniqueConstraint(
            "empresa_id", "codigo", "valid_from", name="uq_conta_codigo_vigencia"
        ),
        Index("ix_conta_tenant", "tenant_id"),
        Index("ix_conta_empresa_codigo", "empresa_id", "codigo"),
        Index("ix_conta_parent", "parent_id"),
    )


class LancamentoContabil(Base):
    """Cabeçalho de lançamento em partidas dobradas (Sprint 9 PR1).

    Invariante DB-level: ``total_debito = total_credito`` (CHECK). UNIQUE
    parcial em (origem_tipo, origem_id) garante idempotência do motor
    automático (PR2).
    """

    __tablename__ = "lancamento_contabil"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    data_lancamento: Mapped[date] = mapped_column(DATE, nullable=False)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    historico: Mapped[str] = mapped_column(String(500), nullable=False)
    origem_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    origem_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    total_debito: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    total_credito: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="rascunho"
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
            "'provisao','encerramento','ajuste')",
            name="ck_lanc_origem_tipo",
        ),
        CheckConstraint(
            "status IN ('rascunho','confirmado','encerrado')",
            name="ck_lanc_status",
        ),
        CheckConstraint(
            "total_debito = total_credito", name="ck_lanc_partidas_dobradas"
        ),
        CheckConstraint(
            "total_debito >= 0", name="ck_lanc_totais_nao_negativos"
        ),
        Index("ix_lanc_tenant", "tenant_id"),
        Index("ix_lanc_empresa_comp", "empresa_id", "competencia"),
        Index("ix_lanc_empresa_data", "empresa_id", "data_lancamento"),
    )


class PartidaLancamento(Base):
    """Linha de débito ou crédito de um lançamento (Sprint 9 PR1)."""

    __tablename__ = "partida_lancamento"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    lancamento_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lancamento_contabil.id", ondelete="CASCADE"),
        nullable=False,
    )
    conta_contabil_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conta_contabil.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(1), nullable=False)
    valor: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("tipo IN ('D','C')", name="ck_partida_tipo"),
        CheckConstraint("valor > 0", name="ck_partida_valor_positivo"),
        Index("ix_partida_lanc", "lancamento_id", "ordem"),
        Index("ix_partida_conta", "conta_contabil_id"),
    )


class ProvisaoMensal(Base):
    """Provisão trabalhista mensal — férias, 13º, INSS, FGTS (Sprint 8 PR2).

    ``funcionario_id`` é nullable; null indica provisão agregada por empresa
    (modo atual — folha individual chega na Sprint 10). UNIQUE parcial
    distinguindo agregada vs individual garante idempotência (§8.9).
    """

    __tablename__ = "provisao_mensal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    funcionario_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    base_calculo: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    aliquota: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    valor_provisao: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(20), nullable=False)
    lancamento_contabil_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('ferias','13_salario','inss_ferias','inss_13',"
            "'fgts_ferias','fgts_13')",
            name="ck_provisao_tipo",
        ),
        CheckConstraint(
            "base_calculo >= 0 AND valor_provisao >= 0 AND aliquota >= 0",
            name="ck_provisao_valores_nao_negativos",
        ),
        Index("ix_provisao_empresa_comp", "empresa_id", "competencia", "tipo"),
        Index("ix_provisao_tenant", "tenant_id"),
    )


class TabelaDepreciacaoRfb(Base):
    """SCD Type 2 da IN SRF 162/1998 anexo I (Sprint 8 PR1).

    Sem ``tenant_id`` — referência pública. Seed inicial cobre 6 categorias.
    """

    __tablename__ = "tabela_depreciacao_rfb"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False)
    taxa_anual: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    vida_util_anos: Mapped[int] = mapped_column(Integer, nullable=False)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_tabela_depreciacao_categoria_vigencia",
            "categoria",
            "valid_from",
            "valid_to",
        ),
    )


class BemImobilizado(Base):
    """Ativo imobilizado da empresa — IN SRF 162/1998 (Sprint 8 PR1)."""

    __tablename__ = "bem_imobilizado"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False)
    data_aquisicao: Mapped[date] = mapped_column(DATE, nullable=False)
    valor_aquisicao: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    documento_fiscal_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documento_fiscal.id", ondelete="SET NULL"),
        nullable=True,
    )
    conta_contabil_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    taxa_depreciacao_anual: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    metodo_depreciacao: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="linear"
    )
    vida_util_meses: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_residual: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    data_baixa: Mapped[date | None] = mapped_column(DATE, nullable=True)
    motivo_baixa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "categoria IN ('imovel','edificacao','veiculo','maquina',"
            "'computador','movel','outro')",
            name="ck_bem_categoria",
        ),
        CheckConstraint(
            "metodo_depreciacao IN ('linear','soma_digitos','unidades_produzidas')",
            name="ck_bem_metodo",
        ),
        CheckConstraint("valor_aquisicao > 0", name="ck_bem_valor_positivo"),
        CheckConstraint("vida_util_meses > 0", name="ck_bem_vida_util_positiva"),
        CheckConstraint(
            "valor_residual >= 0 AND valor_residual <= valor_aquisicao",
            name="ck_bem_residual_valido",
        ),
        Index("ix_bem_imob_tenant", "tenant_id"),
    )


class DepreciacaoMensal(Base):
    """Parcela mensal de depreciação calculada (Sprint 8 PR1).

    UNIQUE (bem_id, competencia) garante idempotência do worker mensal (§8.9).
    Append-only — recálculo histórico se a taxa mudar requer migration explícita.
    """

    __tablename__ = "depreciacao_mensal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    bem_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bem_imobilizado.id", ondelete="CASCADE"),
        nullable=False,
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    valor_depreciado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_acumulado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    saldo_contabil: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    lancamento_contabil_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("valor_depreciado >= 0", name="ck_depr_mes_nao_negativo"),
        UniqueConstraint("bem_id", "competencia", name="uq_depr_bem_competencia"),
        Index("ix_depr_tenant", "tenant_id"),
        Index("ix_depr_competencia", "competencia"),
    )


class ConciliacaoMatch(Base):
    """Match banco × NF (Sprint 7 PR3). Trilha auditável em ``score_breakdown_json``.

    UNIQUE (transacao_id, documento_fiscal_id) — não permite duplicar matches
    para o mesmo par. Re-rodar o algoritmo é seguro (no-op em pares existentes).
    """

    __tablename__ = "conciliacao_match"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    transacao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transacao_bancaria.id", ondelete="CASCADE"),
        nullable=False,
    )
    documento_fiscal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documento_fiscal.id", ondelete="RESTRICT"),
        nullable=False,
    )
    confianca: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(20), nullable=False)
    score_breakdown_json: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    confirmado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    confirmado_por_usuario_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )
    rejeitado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    rejeitado_por_usuario_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("confianca BETWEEN 0 AND 100", name="ck_match_confianca"),
        CheckConstraint(
            "tipo IN ('AUTO','SUGERIDA','MANUAL','REJEITADA')",
            name="ck_match_tipo",
        ),
        UniqueConstraint(
            "transacao_id", "documento_fiscal_id", name="uq_match_par"
        ),
        Index("ix_match_tenant", "tenant_id"),
        Index("ix_match_empresa_tipo", "empresa_id", "tipo"),
        Index("ix_match_transacao", "transacao_id"),
        Index("ix_match_documento", "documento_fiscal_id"),
    )


class PluggyWebhookEvent(Base):
    """Dedup de eventos de webhook Pluggy (Sprint 7 PR2).

    Cross-tenant — webhook chega antes do routing por item_id. Acesso direto
    a esta tabela só pelo handler do webhook. Idempotência §8.9 garantida
    por UNIQUE em ``pluggy_event_id``.
    """

    __tablename__ = "pluggy_webhook_event"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    pluggy_event_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    pluggy_item_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_json: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    processado: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_pluggy_webhook_item", "pluggy_item_id"),
    )


class DeclaracaoAnual(Base):
    """Declaração anual SN/MEI — DEFIS ou DASN-SIMEI (Sprint 6 PR3).

    Append-only. Uma única linha por (empresa, tipo, ano_base) — retificações
    seriam novas linhas em ano futuro (regra de negócio: para o MVP não
    permitimos retificar a mesma anualidade; UNIQUE garante isso).
    """

    __tablename__ = "declaracao_anual"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ano_base: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(20), nullable=False)
    protocolo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    transmitida_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    recibo_pdf_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    serpro_chamada_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('DEFIS','DASN_SIMEI')",
            name="ck_declaracao_anual_tipo",
        ),
        CheckConstraint(
            "status IN ('gerada','transmitida','erro')",
            name="ck_declaracao_anual_status",
        ),
        CheckConstraint(
            "ano_base BETWEEN 2018 AND 2099",
            name="ck_declaracao_anual_ano",
        ),
        UniqueConstraint(
            "empresa_id",
            "tipo",
            "ano_base",
            name="uq_declaracao_anual_empresa_tipo_ano",
        ),
        Index("ix_declaracao_anual_tenant", "tenant_id"),
        Index("ix_declaracao_anual_empresa_ano", "empresa_id", "ano_base"),
    )


class MensagemECac(Base):
    """Mensagem da caixa postal e-CAC (RFB). Sprint 6 PR2.

    Sincronizada periodicamente via SERPRO Integra Contador. Classificação por
    LLM (tipo, prioridade, prazo) ocorre após ingestão — campos nullable até
    o classificador rodar.
    """

    __tablename__ = "mensagem_e_cac"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    id_externo_serpro: Mapped[str] = mapped_column(String(80), nullable=False)
    assunto: Mapped[str] = mapped_column(String(255), nullable=False)
    corpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem: Mapped[str] = mapped_column(String(50), nullable=False, server_default="RFB")
    recebida_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    lida_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prioridade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prazo_resposta: Mapped[date | None] = mapped_column(DATE, nullable=True)
    classificada_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    classificador_versao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    encaminhada_marketplace: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IS NULL OR tipo IN ('intimacao','aviso','informativa','outro')",
            name="ck_mensagem_e_cac_tipo",
        ),
        CheckConstraint(
            "prioridade IS NULL OR prioridade IN ('alta','media','baixa')",
            name="ck_mensagem_e_cac_prioridade",
        ),
        UniqueConstraint(
            "empresa_id",
            "id_externo_serpro",
            name="uq_mensagem_e_cac_idempotente",
        ),
        Index("ix_mensagem_e_cac_tenant", "tenant_id"),
        Index("ix_mensagem_e_cac_empresa_recebida", "empresa_id", "recebida_em"),
    )


# ── Pessoal / Folha (Sprint 10 PR1) ─────────────────────────────────────────


class Funcionario(Base):
    """Funcionário CLT da empresa (Sprint 10 PR1).

    Sócio/pró-labore ficam fora deste cadastro — virão em modelo dedicado na
    Sprint 10 PR3 conforme §5.7 do Plano.
    """

    __tablename__ = "funcionario"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vinculo: Mapped[str] = mapped_column(String(30), nullable=False, server_default="clt")
    data_admissao: Mapped[date] = mapped_column(DATE, nullable=False)
    data_demissao: Mapped[date | None] = mapped_column(DATE, nullable=True)
    salario_base: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    dependentes_irrf: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "vinculo IN ('clt','prazo_determinado','intermitente')",
            name="ck_funcionario_vinculo",
        ),
        CheckConstraint("salario_base >= 0", name="ck_funcionario_salario_nao_negativo"),
        CheckConstraint(
            "dependentes_irrf >= 0", name="ck_funcionario_dependentes_nao_negativo",
        ),
        UniqueConstraint("empresa_id", "cpf", name="uq_funcionario_empresa_cpf"),
        Index("ix_funcionario_tenant", "tenant_id"),
        Index("ix_funcionario_empresa_ativo", "empresa_id", "ativo"),
    )


class FolhaMensal(Base):
    """Cabeçalho da folha mensal (Sprint 10 PR1).

    ``status='fechada'`` torna a folha um fato imutável (§8.2): UPDATE em
    holerite vinculado é bloqueado em service, e o algoritmo_versao usado
    é congelado em ``algoritmo_versao``.
    """

    __tablename__ = "folha_mensal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="aberta")
    total_proventos: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    total_descontos: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    total_inss_empregado: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    total_irrf: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    total_fgts_empregador: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    total_liquido: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    qtd_funcionarios: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    algoritmo_versao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fechada_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('aberta','fechada')", name="ck_folha_status"),
        UniqueConstraint(
            "empresa_id", "competencia", name="uq_folha_empresa_competencia"
        ),
        Index("ix_folha_tenant", "tenant_id"),
        Index("ix_folha_empresa_comp", "empresa_id", "competencia"),
    )


class Holerite(Base):
    """Holerite de um funcionário em uma folha (Sprint 10 PR1).

    Snapshot do cálculo aplicado — preserva alíquotas e parcelas usadas mesmo
    que a tabela tributária SCD mude depois (§8.3).
    """

    __tablename__ = "holerite"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    folha_mensal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("folha_mensal.id", ondelete="CASCADE"),
        nullable=False,
    )
    funcionario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("funcionario.id", ondelete="RESTRICT"),
        nullable=False,
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    salario_base: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    salario_bruto: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    inss_empregado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    inss_aliquota_efetiva: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    dependentes_irrf: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    deducao_dependentes_irrf: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    base_irrf: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    irrf: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False, server_default="0")
    irrf_faixa: Mapped[int] = mapped_column(Integer, nullable=False)
    fgts_empregador: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    fgts_aliquota: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    valor_liquido: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "folha_mensal_id", "funcionario_id", name="uq_holerite_folha_func"
        ),
        Index("ix_holerite_tenant", "tenant_id"),
        Index("ix_holerite_funcionario_comp", "funcionario_id", "competencia"),
    )


class TabelaInssFaixa(Base):
    """Tabela INSS SCD Type 2 (§8.3). Sprint 10 PR1.

    ``tipo='empregado'`` → 4 faixas progressivas (cálculo escalonado).
    ``tipo='contribuinte_individual'`` → 1 faixa, alíquota plana até o teto
    (usado em pró-labore — Sprint 10 PR3).
    """

    __tablename__ = "tabela_inss_faixa"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    faixa: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_ate: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    aliquota: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('empregado','contribuinte_individual')",
            name="ck_inss_tipo",
        ),
        CheckConstraint("faixa BETWEEN 1 AND 4", name="ck_inss_faixa"),
        Index("ix_inss_tipo_vigente", "tipo", "valid_from", "valid_to"),
    )


class TabelaIrrfFaixa(Base):
    """Tabela IRRF mensal SCD Type 2 (§8.3). Sprint 10 PR1.

    5 faixas + dedução por dependente. ``base_ate`` da faixa 5 é simbólico
    (teto altíssimo) — representa "acima da faixa 4".
    """

    __tablename__ = "tabela_irrf_faixa"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    faixa: Mapped[int] = mapped_column(Integer, nullable=False)
    base_ate: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    aliquota: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    parcela_deduzir: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    deducao_dependente: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("faixa BETWEEN 1 AND 5", name="ck_irrf_faixa"),
        Index("ix_irrf_vigente", "valid_from", "valid_to"),
    )


class TabelaFgtsAliquota(Base):
    """Tabela FGTS SCD Type 2 (§8.3). Sprint 10 PR1."""

    __tablename__ = "tabela_fgts_aliquota"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    vinculo: Mapped[str] = mapped_column(String(30), nullable=False)
    aliquota: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "vinculo IN ('clt','jovem_aprendiz','domestico')",
            name="ck_fgts_vinculo",
        ),
        Index("ix_fgts_vinculo_vigente", "vinculo", "valid_from", "valid_to"),
    )


class RelatorioGerado(Base):
    """Snapshot imutável de DRE/Balanço/DFC/Indicadores (§8.2). Sprint 12 PR1.

    Re-cálculos geram nova linha; a anterior recebe ``superseded_by``
    apontando para a nova — preservando histórico. UNIQUE parcial garante
    apenas 1 versão ativa por (empresa, tipo, período).
    """

    __tablename__ = "relatorio_gerado"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    periodo_inicio: Mapped[date] = mapped_column(DATE, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(DATE, nullable=False)
    payload: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    saldos_base: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("relatorio_gerado.id", ondelete="SET NULL"),
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('dre','balanco','dfc','indicadores','dre_aux_lp')",
            name="ck_relatorio_tipo",
        ),
        Index("ix_relatorio_tenant", "tenant_id"),
        Index(
            "ix_relatorio_empresa_tipo", "empresa_id", "tipo", "periodo_inicio",
        ),
    )


class MensagemDet(Base):
    """Caixa postal Domicílio Eletrônico Trabalhista — Sprint 11 PR3.

    Espelha o pattern de ``MensagemECac`` (Sprint 6 PR2). Classificador LLM
    posterior preenche ``tipo``, ``prioridade`` e ``prazo_resposta``.
    """

    __tablename__ = "mensagem_det"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    id_externo_det: Mapped[str] = mapped_column(String(80), nullable=False)
    assunto: Mapped[str] = mapped_column(String(255), nullable=False)
    corpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem: Mapped[str] = mapped_column(String(50), nullable=False, server_default="MTE")
    recebida_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    lida_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prioridade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prazo_resposta: Mapped[date | None] = mapped_column(DATE, nullable=True)
    classificada_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    classificador_versao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    encaminhada_marketplace: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "id_externo_det", name="uq_det_idempotente",
        ),
        Index("ix_det_tenant", "tenant_id"),
        Index("ix_det_empresa_recebida", "empresa_id", "recebida_em"),
    )


class StatusCadastralRfb(Base):
    """Snapshot da situação cadastral CNPJ na RFB — Sprint 11 PR3.

    Append-only — cada sync gera nova linha (§8.2). O frontend lê apenas o
    mais recente. Mudanças de situação ('ativa' → 'suspensa') ficam
    rastreáveis no histórico.
    """

    __tablename__ = "status_cadastral_rfb"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    consultado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    situacao_cadastral: Mapped[str] = mapped_column(String(40), nullable=False)
    data_situacao: Mapped[date | None] = mapped_column(DATE, nullable=True)
    motivo_situacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    restricoes: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    regime_apuracao: Mapped[str | None] = mapped_column(String(50), nullable=True)
    snapshot: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_rfb_tenant", "tenant_id"),
        Index("ix_rfb_empresa_consultado", "empresa_id", "consultado_em"),
    )


class StatusSintegra(Base):
    """Snapshot da inscrição estadual (IE) por UF — Sprint 11 PR3. Append-only."""

    __tablename__ = "status_sintegra"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    uf: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    inscricao_estadual: Mapped[str] = mapped_column(String(20), nullable=False)
    consultado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    situacao: Mapped[str] = mapped_column(String(40), nullable=False)
    data_situacao: Mapped[date | None] = mapped_column(DATE, nullable=True)
    regime_apuracao_ie: Mapped[str | None] = mapped_column(String(60), nullable=True)
    snapshot: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_sintegra_tenant", "tenant_id"),
        Index(
            "ix_sintegra_empresa_uf_consultado",
            "empresa_id", "uf", "consultado_em",
        ),
    )


class ParcelamentoFiscal(Base):
    """Parcelamento fiscal — Lei 10.522/2002, PERT, PERT2 etc. Sprint 11 PR3."""

    __tablename__ = "parcelamento_fiscal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    identificador_externo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    data_adesao: Mapped[date] = mapped_column(DATE, nullable=False)
    divida_consolidada: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    num_parcelas: Mapped[int] = mapped_column(Integer, nullable=False)
    parcela_base: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ativo")
    cancelado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255), nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_parcelamento_tenant", "tenant_id"),
        Index(
            "ix_parcelamento_empresa_status", "empresa_id", "status",
        ),
    )


class ParcelaFiscal(Base):
    """Parcela mensal de um ``ParcelamentoFiscal``. Sprint 11 PR3."""

    __tablename__ = "parcela_fiscal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    parcelamento_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("parcelamento_fiscal.id", ondelete="CASCADE"),
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    vencimento: Mapped[date] = mapped_column(DATE, nullable=False)
    valor_projetado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_pago: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    pago_em: Mapped[date | None] = mapped_column(DATE, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="a_pagar")
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "parcelamento_id", "numero", name="uq_parcela_numero",
        ),
        Index("ix_parcela_tenant", "tenant_id"),
        Index("ix_parcela_vencimento", "vencimento", "status"),
    )


class AliquotaIcmsUf(Base):
    """Alíquota interna ICMS por UF — SCD Type 2 (§8.3). Sprint 11 PR2."""

    __tablename__ = "aliquota_icms_uf"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    uf: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    aliquota_interna: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    aliquota_fecp: Mapped[Decimal] = mapped_column(
        NUMERIC(6, 4), nullable=False, server_default="0"
    )
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_icms_uf_vigente", "uf", "valid_from", "valid_to"),
    )


class EfdReinfEvento(Base):
    """Evento EFD-Reinf preparado para transmissão (Sprint 11 PR2 — skeleton).

    Tipos R-2010 (serviços tomados com retenção previdenciária), R-4020
    (pagamentos diversos a PJ — IR + CSRF), R-9000 (exclusão), entre outros
    do leiaute v2.1.2.

    XML real e assinatura ICP-Brasil ficam para sprint futura — por ora
    o ``payload`` JSONB carrega os campos normalizados.
    """

    __tablename__ = "efd_reinf_evento"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    tipo_evento: Mapped[str] = mapped_column(String(10), nullable=False)
    referencia_tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    referencia_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    periodo_apuracao: Mapped[date] = mapped_column(DATE, nullable=False)
    valor_bruto_servico: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    ir_retido: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    pis_retido: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    cofins_retido: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    csll_retido: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    payload: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="preparado")
    protocolo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resposta: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    transmitido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "tipo_evento", "referencia_id",
            name="uq_reinf_empresa_tipo_ref",
        ),
        Index("ix_reinf_tenant", "tenant_id"),
        Index("ix_reinf_empresa_periodo", "empresa_id", "periodo_apuracao"),
    )


class PresuncaoLucroPresumido(Base):
    """Percentuais de presunção LP por atividade — SCD Type 2 (§8.3).

    Sprint 11 PR1. Match por ``cnae_pattern`` (prefixo do CNAE 2.3, varia
    de 2 a 5 chars) com ``prioridade`` como desempate. ``limite_receita_anual``
    quando não-NULL aplica a regra do art. 15 §4º (serviços gerais até R$120k
    têm presunção reduzida de 32% → 16%).
    """

    __tablename__ = "presuncao_lucro_presumido"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    grupo_atividade: Mapped[str] = mapped_column(String(60), nullable=False)
    cnae_pattern: Mapped[str | None] = mapped_column(String(20), nullable=True)
    percentual_irpj: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    percentual_csll: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    limite_receita_anual: Mapped[Decimal | None] = mapped_column(
        NUMERIC(14, 2), nullable=True
    )
    prioridade: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_presuncao_pattern_vigente", "cnae_pattern",
            "valid_from", "valid_to",
        ),
        Index("ix_presuncao_prioridade", "prioridade", "valid_from"),
    )


class Socio(Base):
    """Sócio da empresa (Sprint 10 PR3) — separado de Funcionario CLT.

    Recebe pró-labore mensal (INSS 11% contribuinte individual + IRRF) e
    distribuições de lucros (isentas até o limite contábil — Lei 9.249/1995).
    """

    __tablename__ = "socio"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    percentual_participacao: Mapped[Decimal] = mapped_column(
        NUMERIC(7, 4), nullable=False, server_default="0"
    )
    data_entrada: Mapped[date] = mapped_column(DATE, nullable=False)
    data_saida: Mapped[date | None] = mapped_column(DATE, nullable=True)
    dependentes_irrf: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "cpf", name="uq_socio_empresa_cpf"),
        Index("ix_socio_tenant", "tenant_id"),
        Index("ix_socio_empresa_ativo", "empresa_id", "ativo"),
    )


class ProlaboreMensal(Base):
    """Pagamento mensal de pró-labore (Sprint 10 PR3).

    INSS 11% como contribuinte individual (Lei 8.212/1991 art. 21) até o
    teto vigente. IRRF segue tabela mensal regular. Fato imutável após
    persistir (§8.2).
    """

    __tablename__ = "prolabore_mensal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    socio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("socio.id", ondelete="RESTRICT"), nullable=False
    )
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    valor_bruto: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    base_inss: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    aliquota_inss: Mapped[Decimal] = mapped_column(
        NUMERIC(6, 4), nullable=False, server_default="0.1100"
    )
    inss_socio: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    base_irrf: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    irrf: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False, server_default="0")
    irrf_faixa: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_liquido: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "socio_id", "competencia", name="uq_prolabore_socio_competencia"
        ),
        Index("ix_prolabore_tenant", "tenant_id"),
        Index("ix_prolabore_empresa_comp", "empresa_id", "competencia"),
    )


class DistribuicaoLucros(Base):
    """Distribuição de lucros para um sócio (Sprint 10 PR3).

    Lei 9.249/1995 art. 10: lucros distribuídos são isentos de IRRF até o
    limite contábil (presunção menos impostos, para LP sem escrituração;
    lucro líquido contábil real, com escrituração). Acima do limite, o
    excesso é tributado como rendimento (faixa progressiva IRRF mensal).
    """

    __tablename__ = "distribuicao_lucros"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    socio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("socio.id", ondelete="RESTRICT"), nullable=False
    )
    data_distribuicao: Mapped[date] = mapped_column(DATE, nullable=False)
    valor: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    limite_isento_apurado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_isento: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_tributavel: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    irrf_retido: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    base_calculo_referencia: Mapped[str] = mapped_column(String(40), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "base_calculo_referencia IN ('presuncao_lp','simples_dentro_das',"
            "'lucro_contabil','mei')",
            name="ck_distribuicao_base",
        ),
        Index("ix_distribuicao_tenant", "tenant_id"),
        Index("ix_distribuicao_socio_data", "socio_id", "data_distribuicao"),
    )


class EventoESocial(Base):
    """Evento eSocial preparado para transmissão (Sprint 10 PR3 — skeleton).

    Suporta S-1200 (remuneração trabalhador RGPS), S-1210 (pagamentos do
    trabalho), S-2200 (admissão), S-2299 (desligamento), S-2400 (cadastro
    beneficiário). XML real será gerado em sprint futura — por ora o
    ``payload`` JSONB carrega os campos já normalizados.
    """

    __tablename__ = "evento_esocial"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    tipo_evento: Mapped[str] = mapped_column(String(10), nullable=False)
    referencia_tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    referencia_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    periodo_apuracao: Mapped[date | None] = mapped_column(DATE, nullable=True)
    payload: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="preparado")
    protocolo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resposta: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    transmitido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "tipo_evento IN ('S-1200','S-1210','S-2200','S-2299','S-2400')",
            name="ck_esocial_tipo",
        ),
        CheckConstraint(
            "status IN ('preparado','transmitido','aceito','rejeitado','cancelado')",
            name="ck_esocial_status",
        ),
        UniqueConstraint(
            "empresa_id", "tipo_evento", "referencia_id",
            name="uq_esocial_empresa_tipo_ref",
        ),
        Index("ix_esocial_tenant", "tenant_id"),
        Index("ix_esocial_empresa_periodo", "empresa_id", "periodo_apuracao"),
    )


class EventoFolha(Base):
    """Pagamento pontual fora do holerite mensal (Sprint 10 PR2).

    Cobre 13º (1ª/2ª parcela), férias e rescisão. Snapshot do cálculo em
    ``detalhes`` JSONB (fato imutável — §8.2). Idempotência por UNIQUE
    parcial em índice (ver migration 0017).
    """

    __tablename__ = "evento_folha"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    funcionario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("funcionario.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    data_evento: Mapped[date] = mapped_column(DATE, nullable=False)
    ano_referencia: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodo_inicio: Mapped[date | None] = mapped_column(DATE, nullable=True)
    periodo_fim: Mapped[date | None] = mapped_column(DATE, nullable=True)
    valor_bruto: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    inss_empregado: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    irrf: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    fgts_empregador: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    multa_fgts: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    valor_liquido: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    detalhes: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('13_primeira','13_segunda','ferias','rescisao')",
            name="ck_evento_tipo",
        ),
        Index("ix_evento_tenant", "tenant_id"),
        Index("ix_evento_func_data", "funcionario_id", "data_evento"),
    )
