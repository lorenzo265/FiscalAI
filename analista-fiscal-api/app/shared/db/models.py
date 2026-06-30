from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    DATE,
    NUMERIC,
    BigInteger,
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

from app.shared.crypto.pii_type import PiiCifrada
from app.shared.db.base import Base
from app.shared.types import JsonObject

try:
    from pgvector.sqlalchemy import Vector as PG_VECTOR
    _VECTOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _VECTOR_AVAILABLE = False
    PG_VECTOR = None


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
    # Sprint 19.6 PR3 (#17): NOT NULL (era nullable=True desde Fase 2 PR6 — fase 1).
    # Migration 0049 aplica ALTER COLUMN SET NOT NULL após pre-check garantir
    # 0 linhas com NULL. Service não precisa mais checar `is None` em runtime.
    codigo_municipio_ibge: Mapped[str] = mapped_column(String(7), nullable=False)
    uf: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    ie: Mapped[str | None] = mapped_column(String(20), nullable=True)
    im: Mapped[str | None] = mapped_column(String(20), nullable=True)
    faturamento_12m: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    # PII cifrada em repouso (Marco 3): AES-256-GCM via PiiCifrada (impl Text).
    whatsapp_phone: Mapped[str | None] = mapped_column(PiiCifrada(), nullable=True)
    proximo_numero_rps: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    ativa: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    aliquota_iss_validada: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False, default=False
    )
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
    """NF-e / NFS-e / NFC-e ingerida. ImutÃ¡vel apÃ³s criaÃ§Ã£o (Â§8.2)."""

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
    cclasstrib: Mapped[str | None] = mapped_column(String(20), nullable=True)
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
    itens: Mapped[list[DocumentoFiscalItem]] = relationship(
        "DocumentoFiscalItem",
        back_populates="documento",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="DocumentoFiscalItem.n_item",
    )

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
        CheckConstraint(
            r"cclasstrib IS NULL OR cclasstrib ~ '^[0-9]{6}$'",
            name="ck_doc_cclasstrib_formato",
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
    """Tabela tributÃ¡ria SN â€” SCD Type 2 (Â§8.3). Nunca atualiza linhas; adiciona nova versÃ£o."""

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
    """Resultado imutÃ¡vel de uma apuraÃ§Ã£o fiscal mensal (Â§8.2)."""

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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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


class GuiaPagamento(Base):
    """Guia de pagamento gerada a partir de uma apuração (§8.2 — fato imutável).

    LP paga IRPJ/CSLL via DARF (código 2089/2372) e PIS/Cofins via DARF
    (código 8109/2172). Sprint 20 PR1.
    """

    __tablename__ = "guia_pagamento"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    apuracao_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("apuracao_fiscal.id"),
        nullable=True,
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    codigo_receita: Mapped[str] = mapped_column(String(4), nullable=False)
    denominacao: Mapped[str] = mapped_column(String(100), nullable=False)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    periodo_apuracao: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_principal: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    juros: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    multa: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    data_vencimento: Mapped[date] = mapped_column(DATE, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="a_pagar"
    )
    pago_em: Mapped[date | None] = mapped_column(DATE, nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    fundamento_legal: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('darf','das','gps','grf','dare')",
            name="ck_guia_tipo",
        ),
        CheckConstraint(
            "status IN ('a_pagar','pago','cancelado')",
            name="ck_guia_status",
        ),
        CheckConstraint(
            "valor_principal >= 0",
            name="ck_guia_principal_nao_negativo",
        ),
        CheckConstraint(
            "total = valor_principal + juros + multa",
            name="ck_guia_total_consistente",
        ),
        UniqueConstraint(
            "empresa_id",
            "competencia",
            "codigo_receita",
            name="uq_guia_empresa_comp_receita",
        ),
        Index("ix_guia_tenant", "tenant_id"),
        Index("ix_guia_empresa_status", "empresa_id", "status"),
        Index("ix_guia_empresa_venc", "empresa_id", "data_vencimento"),
    )


class SelicMensal(Base):
    """Taxa SELIC acumulada por competÃªncia â€” usada para cÃ¡lculo de mora e denÃºncia espontÃ¢nea."""

    __tablename__ = "selic_mensal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False, unique=True)
    taxa_mensal: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False, server_default="BACEN")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class AgendaItem(Base):
    """Item do calendÃ¡rio fiscal por empresa â€” obrigaÃ§Ãµes com data de vencimento."""

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
    """NÃ³ do grafo de memÃ³ria da empresa â€” fatos persistentes citÃ¡veis pelo LLM (Â§5.9)."""

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
    """Aresta do grafo de memÃ³ria â€” relaÃ§Ãµes SCD Type 2 entre nÃ³s (Â§5.9)."""

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
    """Estado de conversa WhatsApp por nÃºmero de telefone e empresa (Sprint 5).

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


class WhatsappMensagemProcessada(Base):
    """Dedup de mensagens recebidas via webhook Meta WhatsApp (Fase 2 PR7).

    Atende Â§8.9 (idempotÃªncia em integraÃ§Ãµes externas). O Meta Cloud API faz
    retry sob falha de rede / timeout â€” sem esta tabela, o mesmo ``mensagem_id``
    Ã© processado N vezes, inflando ``SessaoWhatsApp.mensagens_na_sessao`` e
    enviando resposta duplicada.

    Sem RLS â€” rota de sistema, mesmo padrÃ£o de ``pluggy_webhook_event``. O
    isolamento por tenant vem dos campos ``tenant_id``/``empresa_id`` gravados
    junto, mas a checagem ``ON CONFLICT DO NOTHING`` Ã© global por ``mensagem_id``.

    Task Celery ``whatsapp.expurgar_processadas`` (cron diÃ¡rio 04:00) apaga
    linhas > 7 dias. Tabela Ã© append-only por design (REVOKE UPDATE/DELETE).
    """

    __tablename__ = "whatsapp_mensagem_processada"

    mensagem_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_whatsapp_msg_processed_at", "processed_at"),
    )


class SerproCredencial(Base):
    """Cert e-CNPJ (.p12) + senha do cliente, cifrados para uso pelo SERPRO (Sprint 6).

    Sprint 6 Â§ Plano Â§8.7 / Â§8.12: o cliente assina termo de delegaÃ§Ã£o no
    onboarding; cert Ã© armazenado cifrado e usado pelo SERPRO Integra Contador
    para transmissÃ£o de PGDAS-D/DCTFWeb/etc.
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


class CertificadoA1(Base):
    """Cofre do certificado A1 (.p12 ICP-Brasil) por empresa — épico cert A1.

    Guarda o .p12 e a senha CIFRADOS em repouso (envelope AES-256-GCM, §8.7):
    ``pfx_cifrado`` = ``cifrar(base64(pfx_bytes))`` e ``senha_cifrada`` =
    ``cifrar(senha)`` — ambos TEXT (token do envelope). O material só é
    decifrado no ato do envio, via o único ponto de entrada
    ``app.shared.crypto.cert_loader.carregar_cert_a1``.

    Uma linha ATIVA por empresa (unique parcial ``WHERE ativo`` na migration
    0069); substituir desativa a anterior e insere a nova (histórico preservado).
    A senha é guardada cifrada (decisão PO 2026-06-30) p/ permitir transmissão
    automática; nunca aparece em log estruturado (§8.7).
    """

    __tablename__ = "certificado_a1"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    pfx_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    senha_cifrada: Mapped[str] = mapped_column(Text, nullable=False)
    cn_titular: Mapped[str] = mapped_column(Text, nullable=False)
    cnpj_titular: Mapped[str | None] = mapped_column(String(14), nullable=True)
    validade_inicio: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    validade_fim: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_certificado_a1_tenant", "tenant_id"),)


class Certidao(Base):
    """CertidÃ£o CND / CRF / CNDT emitida (Sprint 6).

    Append-only. RenovaÃ§Ã£o anual gera nova linha. `valid_until` indica atÃ©
    quando a certidÃ£o atual continua vÃ¡lida (CND: 180 dias; CRF: 30 dias;
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
    """Audit log de cada chamada SERPRO (Sprint 6). Â§8.10."""

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
    """TransmissÃ£o de PGDAS-D ao SERPRO (Sprint 6 PR2). Append-only.

    Cada tentativa de transmitir um PGDAS-D para uma competÃªncia gera uma linha.
    RetificaÃ§Ãµes criam nova linha com `tentativa = N+1` e `eh_retificadora=True`.
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
    """ConexÃ£o Open Finance Pluggy autorizada pelo cliente (Sprint 7 PR1).

    Uma empresa pode ter mÃºltiplos itens (um por banco/conector). O
    ``pluggy_item_id`` Ã© o identificador externo da Pluggy â€” UNIQUE para
    idempotÃªncia do callback do widget.
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
    """Conta bancÃ¡ria extraÃ­da via Pluggy (Sprint 7 PR1).

    ``saldo_atual`` Ã© snapshot do Ãºltimo sync â€” fonte de verdade fica no
    prÃ³prio banco. Atualizado a cada chamada de sync de transaÃ§Ãµes.
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
    """TransaÃ§Ã£o bancÃ¡ria extraÃ­da via Pluggy (Sprint 7 PR2).

    UPSERT por ``pluggy_transaction_id``. ``valor`` Ã© signed (positivo
    entrada, negativo saÃ­da). ``raw_json`` mantÃ©m snapshot bruto Pluggy
    para auditoria e re-processamento se o algoritmo de conciliaÃ§Ã£o mudar
    (Â§8.2).
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
    """Saldo mensal materializado por (empresa, conta, competencia) â€” Sprint 9 PR3.

    Populado pelo serviÃ§o de encerramento mensal. ``status='fechado'`` Ã© o
    valor canÃ´nico apÃ³s encerramento; ``aberto`` indica computaÃ§Ã£o em curso.
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
    """Conta contÃ¡bil hierÃ¡rquica â€” SCD Type 2 (Sprint 9 PR1).

    Apenas contas com ``aceita_lancamento=True`` (analÃ­ticas) podem aparecer
    em ``partida_lancamento``. SintÃ©ticas (contas-pai) servem para
    consolidaÃ§Ã£o no balancete.
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
    """CabeÃ§alho de lanÃ§amento em partidas dobradas (Sprint 9 PR1).

    Invariante DB-level: ``total_debito = total_credito`` (CHECK). UNIQUE
    parcial em (origem_tipo, origem_id) garante idempotÃªncia do motor
    automÃ¡tico (PR2).
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
            "'provisao','encerramento','ajuste','importacao','folha','apuracao')",
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
    """Linha de dÃ©bito ou crÃ©dito de um lanÃ§amento (Sprint 9 PR1)."""

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
    """ProvisÃ£o trabalhista mensal â€” fÃ©rias, 13Âº, INSS, FGTS (Sprint 8 PR2).

    ``funcionario_id`` Ã© nullable; null indica provisÃ£o agregada por empresa
    (modo atual â€” folha individual chega na Sprint 10). UNIQUE parcial
    distinguindo agregada vs individual garante idempotÃªncia (Â§8.9).
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
    aliquota: Mapped[Decimal] = mapped_column(NUMERIC(8, 6), nullable=False)
    valor_provisao: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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

    Sem ``tenant_id`` â€” referÃªncia pÃºblica. Seed inicial cobre 6 categorias.
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
    """Ativo imobilizado da empresa â€” IN SRF 162/1998 (Sprint 8 PR1)."""

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
    # Sprint 19.6 PR1 (#31) — ICMS destacado na NF-e de aquisição.
    # NULL = bem não entra no CIAP (legado sem dado ou aquisição sem
    # ICMS destacado). Quando preenchido, 1/48 do valor é apropriado
    # por 48 meses (LC 87/1996 art. 20 §5º).
    icms_aquisicao_destacado: Mapped[Decimal | None] = mapped_column(
        NUMERIC(14, 2), nullable=True
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
        CheckConstraint(
            "icms_aquisicao_destacado IS NULL OR "
            "(icms_aquisicao_destacado > 0 "
            " AND icms_aquisicao_destacado <= valor_aquisicao)",
            name="ck_bem_icms_aquisicao_positivo",
        ),
        Index("ix_bem_imob_tenant", "tenant_id"),
    )


class DepreciacaoMensal(Base):
    """Parcela mensal de depreciaÃ§Ã£o calculada (Sprint 8 PR1).

    UNIQUE (bem_id, competencia) garante idempotÃªncia do worker mensal (Â§8.9).
    Append-only â€” recÃ¡lculo histÃ³rico se a taxa mudar requer migration explÃ­cita.
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
    """Match banco Ã— NF (Sprint 7 PR3). Trilha auditÃ¡vel em ``score_breakdown_json``.

    UNIQUE (transacao_id, documento_fiscal_id) â€” nÃ£o permite duplicar matches
    para o mesmo par. Re-rodar o algoritmo Ã© seguro (no-op em pares existentes).
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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

    Cross-tenant â€” webhook chega antes do routing por item_id. Acesso direto
    a esta tabela sÃ³ pelo handler do webhook. IdempotÃªncia Â§8.9 garantida
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
    """DeclaraÃ§Ã£o anual SN/MEI â€” DEFIS ou DASN-SIMEI (Sprint 6 PR3).

    Append-only. Uma Ãºnica linha por (empresa, tipo, ano_base) â€” retificaÃ§Ãµes
    seriam novas linhas em ano futuro (regra de negÃ³cio: para o MVP nÃ£o
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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

    Sincronizada periodicamente via SERPRO Integra Contador. ClassificaÃ§Ã£o por
    LLM (tipo, prioridade, prazo) ocorre apÃ³s ingestÃ£o â€” campos nullable atÃ©
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


# â”€â”€ Pessoal / Folha (Sprint 10 PR1) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class Funcionario(Base):
    """FuncionÃ¡rio CLT da empresa (Sprint 10 PR1).

    SÃ³cio/prÃ³-labore ficam fora deste cadastro â€” virÃ£o em modelo dedicado na
    Sprint 10 PR3 conforme Â§5.7 do Plano.
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
    """CabeÃ§alho da folha mensal (Sprint 10 PR1).

    ``status='fechada'`` torna a folha um fato imutÃ¡vel (Â§8.2): UPDATE em
    holerite vinculado Ã© bloqueado em service, e o algoritmo_versao usado
    Ã© congelado em ``algoritmo_versao``.
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
    algoritmo_versao: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
    """Holerite de um funcionÃ¡rio em uma folha (Sprint 10 PR1).

    Snapshot do cÃ¡lculo aplicado â€” preserva alÃ­quotas e parcelas usadas mesmo
    que a tabela tributÃ¡ria SCD mude depois (Â§8.3).
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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
    """Tabela INSS SCD Type 2 (Â§8.3). Sprint 10 PR1.

    ``tipo='empregado'`` â†’ 4 faixas progressivas (cÃ¡lculo escalonado).
    ``tipo='contribuinte_individual'`` â†’ 1 faixa, alÃ­quota plana atÃ© o teto
    (usado em prÃ³-labore â€” Sprint 10 PR3).
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
    """Tabela IRRF mensal SCD Type 2 (Â§8.3). Sprint 10 PR1.

    5 faixas + deduÃ§Ã£o por dependente. ``base_ate`` da faixa 5 Ã© simbÃ³lico
    (teto altÃ­ssimo) â€” representa "acima da faixa 4".
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
    """Tabela FGTS SCD Type 2 (Â§8.3). Sprint 10 PR1."""

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
    """Snapshot imutÃ¡vel de DRE/BalanÃ§o/DFC/Indicadores (Â§8.2). Sprint 12 PR1.

    Re-cÃ¡lculos geram nova linha; a anterior recebe ``superseded_by``
    apontando para a nova â€” preservando histÃ³rico. UNIQUE parcial garante
    apenas 1 versÃ£o ativa por (empresa, tipo, perÃ­odo).
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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
    """Caixa postal DomicÃ­lio EletrÃ´nico Trabalhista â€” Sprint 11 PR3.

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
    """Snapshot da situaÃ§Ã£o cadastral CNPJ na RFB â€” Sprint 11 PR3.

    Append-only â€” cada sync gera nova linha (Â§8.2). O frontend lÃª apenas o
    mais recente. MudanÃ§as de situaÃ§Ã£o ('ativa' â†’ 'suspensa') ficam
    rastreÃ¡veis no histÃ³rico.
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
    """Snapshot da inscriÃ§Ã£o estadual (IE) por UF â€” Sprint 11 PR3. Append-only."""

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
    """Parcelamento fiscal â€” Lei 10.522/2002, PERT, PERT2 etc. Sprint 11 PR3."""

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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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
    """AlÃ­quota interna ICMS por UF â€” SCD Type 2 (Â§8.3). Sprint 11 PR2.

    Sprint 19.6 PR1 adicionou ``dia_vencimento_padrao`` (#33) — dia do mês
    seguinte quando vence o ICMS apurado (regime normal, não-Simples
    Nacional). Default 10 cobre Convênio ICMS 92/2006; UFs com prazos
    próprios têm valores específicos (ver migration 0046).
    """

    __tablename__ = "aliquota_icms_uf"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    uf: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    aliquota_interna: Mapped[Decimal] = mapped_column(NUMERIC(6, 4), nullable=False)
    aliquota_fecp: Mapped[Decimal] = mapped_column(
        NUMERIC(6, 4), nullable=False, server_default="0"
    )
    dia_vencimento_padrao: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "dia_vencimento_padrao BETWEEN 1 AND 28",
            name="ck_icms_dia_vencimento_padrao",
        ),
        Index("ix_icms_uf_vigente", "uf", "valid_from", "valid_to"),
    )


class EfdReinfEvento(Base):
    """Evento EFD-Reinf preparado para transmissÃ£o (Sprint 11 PR2 â€” skeleton).

    Tipos R-2010 (serviÃ§os tomados com retenÃ§Ã£o previdenciÃ¡ria), R-4020
    (pagamentos diversos a PJ â€” IR + CSRF), R-9000 (exclusÃ£o), entre outros
    do leiaute v2.1.2.

    XML real e assinatura ICP-Brasil ficam para sprint futura â€” por ora
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    transmitido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Marco 4 PR2 (#11) -- transmissao real (XMLDSig + envio API + recibo).
    xml_assinado: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    lote_protocolo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    recibo_numero: Mapped[str | None] = mapped_column(String(40), nullable=True)
    hash_xml: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "tipo_evento", "referencia_id",
            name="uq_reinf_empresa_tipo_ref",
        ),
        Index("ix_reinf_tenant", "tenant_id"),
        Index("ix_reinf_empresa_periodo", "empresa_id", "periodo_apuracao"),
        Index(
            "ix_reinf_lote_protocolo",
            "lote_protocolo",
            postgresql_where="lote_protocolo IS NOT NULL",
        ),
    )


class PresuncaoLucroPresumido(Base):
    """Percentuais de presunÃ§Ã£o LP por atividade â€” SCD Type 2 (Â§8.3).

    Sprint 11 PR1. Match por ``cnae_pattern`` (prefixo do CNAE 2.3, varia
    de 2 a 5 chars) com ``prioridade`` como desempate. ``limite_receita_anual``
    quando nÃ£o-NULL aplica a regra do art. 15 Â§4Âº (serviÃ§os gerais atÃ© R$120k
    tÃªm presunÃ§Ã£o reduzida de 32% â†’ 16%).
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


class AliquotaCbsIbs(Base):
    """Alíquotas CBS/IBS por fase da Reforma Tributária — SCD Type 2 (§8.3).

    Sprint 14. Pool global (sem ``tenant_id``); leitura aberta + REVOKE UPDATE/DELETE
    do role público (apenas ``tax_table_admin`` insere novas vigências).

    Fonte normativa: LC 214/2025 (lei base CBS/IBS) + PLP 68/2024 (em tramitação).
    O cronograma de transição vive em ``app/modules/reforma/periodo_transicao.py``.

    A fase ``teste_2026`` (CBS 0,9% + IBS 0,1%) é **informacional** — coexiste com
    PIS/Cofins/ICMS/ISS sem recolhimento separado. As fases ``transicao_2027_2032``
    e ``regime_pleno_2033`` têm alíquotas **preliminares** até regulamentação final
    do Comitê Gestor IBS (princípio §8.12 — toda saída é labelada "estimativa").

    A coluna ``classificacao_lc214`` reflete o art. 9º LC 214: ``geral``,
    ``reducao_60`` (educação/saúde/transporte), ``reducao_30`` (serv. liberais
    regulamentados), ``regime_diferenciado`` (combustíveis/financeiras/imóveis etc.).
    NULL = aplica à classificação ``geral``.
    """

    __tablename__ = "aliquota_cbs_ibs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    fase: Mapped[str] = mapped_column(String(30), nullable=False)
    regime: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnae_pattern: Mapped[str | None] = mapped_column(String(20), nullable=True)
    classificacao_lc214: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aliquota_cbs: Mapped[Decimal] = mapped_column(NUMERIC(7, 4), nullable=False)
    aliquota_ibs: Mapped[Decimal] = mapped_column(NUMERIC(7, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    fonte_norma: Mapped[str] = mapped_column(String(200), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "aliquota_cbs >= 0 AND aliquota_cbs <= 1",
            name="ck_aliq_cbs_ibs_cbs",
        ),
        CheckConstraint(
            "aliquota_ibs >= 0 AND aliquota_ibs <= 1",
            name="ck_aliq_cbs_ibs_ibs",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_aliq_cbs_ibs_vigencia",
        ),
        Index("ix_aliq_cbs_ibs_lookup", "fase", "valid_from"),
    )


class Socio(Base):
    """SÃ³cio da empresa (Sprint 10 PR3) â€” separado de Funcionario CLT.

    Recebe prÃ³-labore mensal (INSS 11% contribuinte individual + IRRF) e
    distribuiÃ§Ãµes de lucros (isentas atÃ© o limite contÃ¡bil â€” Lei 9.249/1995).
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
    """Pagamento mensal de prÃ³-labore (Sprint 10 PR3).

    INSS 11% como contribuinte individual (Lei 8.212/1991 art. 21) atÃ© o
    teto vigente. IRRF segue tabela mensal regular. Fato imutÃ¡vel apÃ³s
    persistir (Â§8.2).
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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
    """DistribuiÃ§Ã£o de lucros para um sÃ³cio (Sprint 10 PR3).

    Lei 9.249/1995 art. 10: lucros distribuÃ­dos sÃ£o isentos de IRRF atÃ© o
    limite contÃ¡bil (presunÃ§Ã£o menos impostos, para LP sem escrituraÃ§Ã£o;
    lucro lÃ­quido contÃ¡bil real, com escrituraÃ§Ã£o). Acima do limite, o
    excesso Ã© tributado como rendimento (faixa progressiva IRRF mensal).
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
    # Lei 15.270/2025 — retenção antecipada de 10% na fonte sobre dividendos
    # que excedam R$ 50.000/mês da mesma PJ → mesma PF (inclusive Simples).
    # 0 para distribuições históricas ou abaixo do limite.
    retencao_dividendos_10pct: Mapped[Decimal] = mapped_column(
        NUMERIC(14, 2), nullable=False, server_default="0"
    )
    base_calculo_referencia: Mapped[str] = mapped_column(String(40), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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
    trabalho), S-2200 (admissão), S-2299 (desligamento), S-2300 (TSVE —
    início de prestação de serviços, usado pra sócio com pró-labore).
    XML real é gerado em sprint futura — por ora o ``payload`` JSONB
    carrega os campos já normalizados.

    Sprint 19.6 PR1 (#14): S-2400 (Cadastro Beneficiário Ente Público
    RPPS, uso adaptado) substituído por S-2300 (TSVE — evento canônico
    do leiaute). Migration 0048 fez backfill + atualizou CHECK.
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    transmitido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Sprint 19.7 PR2 (#13) — transmissão real (XMLDSig + envio API + recibo).
    xml_assinado: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    lote_protocolo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    recibo_numero: Mapped[str | None] = mapped_column(String(40), nullable=True)
    hash_xml: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "tipo_evento IN ('S-1200','S-1210','S-2200','S-2205','S-2206',"
            "'S-2230','S-2298','S-2299','S-2300','S-3000')",
            name="ck_esocial_tipo",
        ),
        CheckConstraint(
            "status IN ('preparado','assinado','em_lote','transmitido','aceito',"
            "'rejeitado','rejeitado_xsd','cancelado')",
            name="ck_esocial_status",
        ),
        UniqueConstraint(
            "empresa_id", "tipo_evento", "referencia_id",
            name="uq_esocial_empresa_tipo_ref",
        ),
        Index("ix_esocial_tenant", "tenant_id"),
        Index("ix_esocial_empresa_periodo", "empresa_id", "periodo_apuracao"),
        Index(
            "ix_esocial_lote_protocolo",
            "lote_protocolo",
            postgresql_where="lote_protocolo IS NOT NULL",
        ),
    )


class EventoFolha(Base):
    """Pagamento pontual fora do holerite mensal (Sprint 10 PR2).

    Cobre 13Âº (1Âª/2Âª parcela), fÃ©rias e rescisÃ£o. Snapshot do cÃ¡lculo em
    ``detalhes`` JSONB (fato imutÃ¡vel â€” Â§8.2). IdempotÃªncia por UNIQUE
    parcial em Ã­ndice (ver migration 0017).
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
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
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


# ── Marketplace de contadores parceiros (Sprint 13 PR1) ─────────────────────


class ContadorParceiro(Base):
    """Contador parceiro do marketplace (§5.8 + §10).

    Pool global (SEM ``tenant_id``) — curado manualmente. Campos LGPD e de
    curadoria (``ativo``, ``crc_status``, ``rating_medio``) governam quem
    aparece nos resultados do matching. REVOKE UPDATE/DELETE FROM PUBLIC
    (rating só recalculado por role admin via task Celery do PR3).
    """

    __tablename__ = "contador_parceiro"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    cpf: Mapped[str | None] = mapped_column(String(11), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    crc_numero: Mapped[str] = mapped_column(String(20), nullable=False)
    crc_uf: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    crc_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="ativo"
    )
    crc_status_atualizado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    especialidades: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    uf_atuacao: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    rating_medio: Mapped[Decimal | None] = mapped_column(NUMERIC(3, 2), nullable=True)
    total_consultas: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    taxa_resposta_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sla_resposta_horas: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="24"
    )
    oab_numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    oab_uf: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    senha_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aceitou_nda_lgpd_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "crc_status IN ('ativo','suspenso','baixado')",
            name="ck_contador_crc_status",
        ),
        CheckConstraint(
            "rating_medio IS NULL OR (rating_medio >= 0 AND rating_medio <= 5)",
            name="ck_contador_rating",
        ),
        UniqueConstraint("email", name="uq_contador_email"),
        UniqueConstraint("crc_numero", "crc_uf", name="uq_contador_crc"),
        Index("ix_contador_ativo_rating", "ativo", "rating_medio"),
    )


class ConsultaMarketplace(Base):
    """Consulta criada por cliente PME e atribuída a contador parceiro (§5.8).

    RLS dual aplicada via migration 0032 — cliente vê por ``app.tenant_id``,
    parceiro vê por ``app.contador_id`` (role ``marketplace_partner``). Status
    segue máquina determinística (aberta → atribuida → aceita → concluida).
    ``idempotency_key`` UNIQUE garante que mesma pergunta no mesmo dia retorna
    a consulta existente (§8.9).
    """

    __tablename__ = "consulta_marketplace"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
    )
    contador_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contador_parceiro.id", ondelete="RESTRICT"),
        nullable=True,
    )
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    pergunta: Mapped[str | None] = mapped_column(Text, nullable=True)
    pergunta_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    contexto_empresa_jsonb: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    snapshot_versao: Mapped[str] = mapped_column(String(20), nullable=False)
    consentimento_compartilhamento: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    consentimento_revogado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    pii_apagado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_consulta: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    comissao_plataforma: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    resposta_resumo: Mapped[str | None] = mapped_column(Text, nullable=True)
    arquivos_anexos: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    rating_cliente: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comentario_cliente: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sla_aceitar_ate: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    sla_responder_ate: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    aberta_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    aceita_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    respondida_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    paga_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "categoria IN ("
            "'consulta_rapida','analise_intimacao_simples','analise_intimacao_complexa',"
            "'parecer_tecnico','peticao_administrativa','defesa_auto',"
            "'planejamento_tributario','holding','sucessao'"
            ")",
            name="ck_consulta_mkt_categoria",
        ),
        CheckConstraint(
            "status IN ("
            "'aberta','atribuida','aceita','em_andamento',"
            "'concluida','cancelada','expirada'"
            ")",
            name="ck_consulta_mkt_status",
        ),
        CheckConstraint(
            "comissao_plataforma >= 0 AND comissao_plataforma <= valor_consulta",
            name="ck_consulta_mkt_comissao",
        ),
        UniqueConstraint("idempotency_key", name="uq_consulta_mkt_idempotency"),
        Index("ix_consulta_mkt_tenant", "tenant_id"),
        Index("ix_consulta_mkt_empresa_status", "empresa_id", "status"),
        Index("ix_consulta_mkt_contador_status", "contador_id", "status"),
    )


class CobrancaConsulta(Base):
    """Cobrança gerada para uma consulta concluída (Sprint 13 PR3).

    1:1 com ``ConsultaMarketplace`` (UNIQUE em ``consulta_id``). Provider real
    (Stripe/Pagar.me) entra em sprint futura — ADR 0015. ``idempotency_key``
    UNIQUE evita double-spend em retry de webhook (§8.9).
    """

    __tablename__ = "cobranca_consulta"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    consulta_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("consulta_marketplace.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="fake"
    )
    provider_externo_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    valor: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendente")
    checkout_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    paga_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    cancelada_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pendente','paga','falhou','cancelada')",
            name="ck_cobranca_status",
        ),
        CheckConstraint("valor >= 0", name="ck_cobranca_valor"),
        UniqueConstraint("consulta_id", name="uq_cobranca_consulta"),
        UniqueConstraint("idempotency_key", name="uq_cobranca_idempotency"),
        Index("ix_cobranca_tenant", "tenant_id"),
        Index("ix_cobranca_status", "status"),
    )


class AnomaliaFiscal(Base):
    """Alerta proativo de salto atípico em apuração fiscal (Sprint 15 PR1).

    Append-only (§8.2). Re-detecção da mesma chave ``(empresa, tipo,
    competencia)`` produz nova linha; a anterior recebe ``superseded_by``
    apontando para a nova. UNIQUE parcial garante uma única versão ativa.

    Dispensa é UPDATE in-place: ``dispensada_em`` + ``dispensada_por`` +
    ``motivo_dispensa``. A linha continua "ativa" do ponto de vista de
    versionamento (``superseded_by IS NULL``); endpoints "abertas" filtram
    onde ``dispensada_em IS NULL``.
    """

    __tablename__ = "anomalia_fiscal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    severidade: Mapped[str] = mapped_column(String(10), nullable=False)
    valor_observado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_esperado: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    z_score: Mapped[Decimal] = mapped_column(NUMERIC(6, 3), nullable=False)
    delta_percentual: Mapped[Decimal] = mapped_column(NUMERIC(7, 4), nullable=False)
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    amostra_n: Mapped[int] = mapped_column(Integer, nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    detectado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    dispensada_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    dispensada_por: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    motivo_dispensa: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("anomalia_fiscal.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('das','irpj','csll','pis','cofins','iss','icms')",
            name="ck_anomalia_tipo",
        ),
        CheckConstraint(
            "severidade IN ('baixa','media','alta')",
            name="ck_anomalia_severidade",
        ),
        CheckConstraint(
            "metodo IN ('zscore','iqr')",
            name="ck_anomalia_metodo",
        ),
        CheckConstraint(
            "valor_observado >= 0 AND valor_esperado >= 0",
            name="ck_anomalia_valores_positivos",
        ),
        CheckConstraint("amostra_n >= 3", name="ck_anomalia_amostra_minima"),
        CheckConstraint(
            "(dispensada_em IS NULL AND dispensada_por IS NULL)"
            " OR (dispensada_em IS NOT NULL AND dispensada_por IS NOT NULL)",
            name="ck_anomalia_dispensa_coerente",
        ),
        Index("ix_anomalia_tenant", "tenant_id"),
    )


class DigestSemanal(Base):
    """Weekly digest WhatsApp do AI Advisor (Sprint 15 PR3).

    Snapshot semanal proativo gerado segunda 06:00 BR pelo worker. Texto
    pronto para envio via WhatsApp utility template; envio real fica como
    pendência consciente (depende de template aprovado Meta).

    Append-only (§8.2): re-gerações geram nova linha com ``superseded_by``;
    UNIQUE parcial garante 1 versão ativa por (empresa, semana_iso) (§8.9).
    """

    __tablename__ = "digest_semanal"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    semana_iso: Mapped[str] = mapped_column(String(10), nullable=False)
    periodo_inicio: Mapped[date] = mapped_column(DATE, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(DATE, nullable=False)
    conteudo_estruturado: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    texto_redigido: Mapped[str] = mapped_column(Text, nullable=False)
    fonte_redacao: Mapped[str] = mapped_column(String(30), nullable=False)
    citacoes: Mapped[JsonObject] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="preparado")
    llm_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    custo_usd: Mapped[Decimal | None] = mapped_column(NUMERIC(10, 6), nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_cached: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enviado_via_whatsapp_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Sprint 15.5 — auditoria do envio Meta WhatsApp
    tentativas_envio: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    ultimo_erro_envio: Mapped[str | None] = mapped_column(Text, nullable=True)
    enviado_template_name: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("digest_semanal.id", ondelete="SET NULL"),
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('preparado','enviado','cancelado','falhou')",
            name="ck_digest_status",
        ),
        CheckConstraint(
            "fonte_redacao IN ('template','llm_gemini_flash','llm_fallback')",
            name="ck_digest_fonte_redacao",
        ),
        CheckConstraint(
            "periodo_fim >= periodo_inicio",
            name="ck_digest_periodo_coerente",
        ),
        CheckConstraint(
            "tentativas_envio >= 0",
            name="ck_digest_tentativas_positivas",
        ),
        UniqueConstraint("idempotency_key", name="uq_digest_idempotency"),
        Index("ix_digest_tenant", "tenant_id"),
        Index("ix_digest_empresa_semana", "empresa_id", "semana_iso"),
    )


# ── SPED files (Sprint 16 PR1) ──────────────────────────────────────────────


class ArquivoSped(Base):
    """Arquivo SPED gerado — ECD/ECF/EFD-Contribuições/EFD ICMS-IPI (Sprint 16).

    Snapshot imutável (§8.2): re-geração para mesma chave de domínio cria
    nova linha com ``supersedes``; anterior recebe ``superseded_by``.
    UNIQUE parcial (DB-level) garante 1 arquivo ativo por
    ``(empresa, tipo, periodo_inicio, periodo_fim)`` — idempotência §8.9.

    Conteúdo do ``.txt`` em object storage (``storage_key`` + Marco 4 #10)
    OU, para linhas legadas ainda não migradas, em ``conteudo_bytea``
    (BYTEA). A geração nova escreve no storage e zera ``conteudo_bytea``;
    a leitura é storage-first com fallback BYTEA
    (``app.modules.sped.storage.ler_conteudo_sped``). Em prod
    ``STORAGE_BACKEND=s3`` tira blobs de 5-50MB do Postgres.

    ``status`` começa em ``gerado`` (PR1). PR3 introduz ``validado``.
    Transições para ``transmitido``/``aceito``/``rejeitado`` exigem
    recibo ReceitaNet entregue pelo cliente — §8.12 (transmissão é ato
    consciente).
    """

    __tablename__ = "arquivo_sped"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    periodo_inicio: Mapped[date] = mapped_column(DATE, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(DATE, nullable=False)
    # Marco 4 #10: nullable porque o conteúdo agora vive no object storage
    # (storage_key). Permanece preenchido em linhas legadas até o backfill.
    conteudo_bytea: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_arquivo: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recibo_transmissao: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="gerado"
    )
    validacao_jsonb: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    gerado_por_usuario_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    supersedes: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("arquivo_sped.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("arquivo_sped.id", ondelete="SET NULL"),
        nullable=True,
    )
    gerado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    transmitido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('ecd','ecf','efd_contribuicoes','efd_icms_ipi')",
            name="ck_sped_tipo",
        ),
        CheckConstraint(
            "status IN ('gerado','validado','transmitido','aceito','rejeitado')",
            name="ck_sped_status",
        ),
        CheckConstraint(
            "periodo_fim >= periodo_inicio",
            name="ck_sped_periodo_coerente",
        ),
        CheckConstraint(
            "tamanho_bytes > 0",
            name="ck_sped_tamanho_positivo",
        ),
        CheckConstraint(
            "hash_arquivo ~ '^[0-9a-f]{64}$'",
            name="ck_sped_hash_formato",
        ),
        Index("ix_sped_tenant", "tenant_id"),
        Index(
            "ix_sped_empresa_tipo_periodo", "empresa_id", "tipo", "periodo_inicio"
        ),
    )


# ── Sprint 18 PR1 — Fundação da migração de escritório antigo ──────────────


class DocumentoFiscalItem(Base):
    """Item granular da NF-e — resolve pendência #26 (Sprint 18 PR1).

    Hoje ``documento_fiscal`` carrega só cabeçalho. Esta tabela traz a
    granularidade por linha (``<det>`` do XML, C170 do SPED EFD-Contribuições)
    que é necessária para:

    1. Escriturar PIS/Cofins por item no SPED EFD-Contribuições sem
       colapsar 50 linhas em "MERC-GENERICO" (era o workaround da Sprint 17).
    2. Cálculo CBS/IBS por NCM (Reforma Tributária — Sprint 14 deixou no
       cabeçalho; aqui ganha resolução real).
    3. Importador SPED histórico (PR2/PR3) preservar fidelidade dos C170
       do escritório anterior.

    Imutabilidade (§8.2) é herdada do pai: ``ON DELETE CASCADE`` quando o
    ``documento_fiscal`` cabeçalho é destruído (caso raro — só via admin).
    Re-emissão da NF gera novo cabeçalho com ``supersedes`` apontando para
    o anterior; novos itens nascem ligados ao novo cabeçalho.
    """

    __tablename__ = "documento_fiscal_item"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    documento_fiscal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documento_fiscal.id", ondelete="CASCADE"),
        nullable=False,
    )
    n_item: Mapped[int] = mapped_column(Integer, nullable=False)
    codigo_produto: Mapped[str | None] = mapped_column(String(60), nullable=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    ncm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cfop: Mapped[str | None] = mapped_column(String(4), nullable=True)
    cst_icms: Mapped[str | None] = mapped_column(String(3), nullable=True)
    cst_pis: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cst_cofins: Mapped[str | None] = mapped_column(String(2), nullable=True)
    unidade: Mapped[str | None] = mapped_column(String(6), nullable=True)
    quantidade: Mapped[Decimal] = mapped_column(NUMERIC(15, 4), nullable=False)
    valor_unitario: Mapped[Decimal] = mapped_column(NUMERIC(15, 4), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    valor_icms: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_ipi: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_pis: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_cofins: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_cbs: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    valor_ibs: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    documento: Mapped[DocumentoFiscal] = relationship(
        "DocumentoFiscal", back_populates="itens"
    )

    __table_args__ = (
        UniqueConstraint(
            "documento_fiscal_id", "n_item", name="uq_doc_item_documento_n"
        ),
        CheckConstraint("n_item >= 1", name="ck_doc_item_n_positivo"),
        CheckConstraint("quantidade > 0", name="ck_doc_item_qtd_positiva"),
        CheckConstraint(
            "valor_unitario >= 0", name="ck_doc_item_unit_nao_negativo"
        ),
        CheckConstraint(
            "valor_total >= 0", name="ck_doc_item_total_nao_negativo"
        ),
        CheckConstraint(
            r"cfop IS NULL OR cfop ~ '^\d{4}$'",
            name="ck_doc_item_cfop_formato",
        ),
        CheckConstraint(
            r"ncm IS NULL OR ncm ~ '^\d{8}$'",
            name="ck_doc_item_ncm_formato",
        ),
        CheckConstraint(
            r"cst_icms IS NULL OR cst_icms ~ '^\d{2,3}$'",
            name="ck_doc_item_cst_icms_formato",
        ),
        CheckConstraint(
            r"cst_pis IS NULL OR cst_pis ~ '^\d{2}$'",
            name="ck_doc_item_cst_pis_formato",
        ),
        CheckConstraint(
            r"cst_cofins IS NULL OR cst_cofins ~ '^\d{2}$'",
            name="ck_doc_item_cst_cofins_formato",
        ),
        Index("ix_doc_item_tenant", "tenant_id"),
        Index("ix_doc_item_documento", "documento_fiscal_id", "n_item"),
        Index(
            "ix_doc_item_ncm",
            "ncm",
            postgresql_where="ncm IS NOT NULL",
        ),
    )


class LoteImportacao(Base):
    """Lote de importação de SPED/CSV — auditoria da migração (Sprint 18 PR1).

    Cada upload de arquivo de migração de escritório antigo cria um lote;
    parsers/services do módulo ``migracao`` (PR2+) registram aqui o
    progresso, o resumo (contagens) e os erros estruturados (warnings,
    rejeições por SCD ausente, conflitos cross-fonte etc.).

    Idempotência forte por hash: 1 lote ``concluido`` por
    ``(empresa_id, hash_arquivo)`` — re-upload do mesmo arquivo retorna o
    lote anterior em vez de reprocessar.
    """

    __tablename__ = "lote_importacao"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    fonte: Mapped[str] = mapped_column(String(40), nullable=False)
    arquivo_sped_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("arquivo_sped.id", ondelete="SET NULL"),
        nullable=True,
    )
    nome_arquivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hash_arquivo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iniciado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    concluido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="processando"
    )
    resumo_jsonb: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    erros_jsonb: Mapped[JsonObject | None] = mapped_column(JSONB, nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "fonte IN ('sped_ecd','sped_ecf','sped_efd_contribuicoes',"
            "'sped_efd_icms_ipi','csv_balancete','csv_razao')",
            name="ck_lote_fonte",
        ),
        CheckConstraint(
            "status IN ('processando','concluido','falhou')",
            name="ck_lote_status",
        ),
        CheckConstraint(
            "hash_arquivo IS NULL OR hash_arquivo ~ '^[0-9a-f]{64}$'",
            name="ck_lote_hash_formato",
        ),
        CheckConstraint(
            "(status = 'processando' AND concluido_em IS NULL) "
            "OR (status IN ('concluido','falhou') AND concluido_em IS NOT NULL)",
            name="ck_lote_status_concluido_coerente",
        ),
        Index("ix_lote_tenant", "tenant_id"),
        Index(
            "ix_lote_empresa_fonte",
            "empresa_id",
            "fonte",
            "iniciado_em",
        ),
    )


class VigenciaTabelaLog(Base):
    """Audit append-only do painel admin de tabelas tributárias (Sprint 19.5 PR1).

    Cada linha = 1 POST aceito em ``/v1/admin/tabelas/<tipo>/vigencia``. O serviço
    aplica o INSERT na tabela SCD correspondente (``tabela_inss_faixa``,
    ``tabela_irrf_faixa``, ``tabela_fgts_aliquota``, ``tabela_simples_faixa``,
    ``presuncao_lucro_presumido``, ``aliquota_icms_uf``, ``aliquota_cbs_ibs``)
    — o trigger ``scd_close_previous_valid_to`` da migration 0025 fecha o
    ``valid_to`` da vigência anterior automaticamente.

    Cross-tenant (sem RLS): operação de sistema controlada pelo role
    ``tax_table_admin`` + token estático. Append-only via REVOKE UPDATE/DELETE
    de PUBLIC na migration 0042 (princípio §8.2 estendido ao audit).

    Idempotência §8.9: ``idempotency_key = uuid5(NS_TABELA_ADMIN, ...)`` UNIQUE
    — re-POST com mesma chave + mesmo payload devolve o log anterior (200);
    payload divergente devolve 409 ``VigenciaTributariaJaPostada``.

    Citação §8.5: ``fonte_norma TEXT`` com CHECK ``char_length >= 10`` no DB +
    validação Pydantic ``min_length=10`` na borda.
    """

    __tablename__ = "vigencia_tabela_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid4,
    )
    tipo_tabela: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    fonte_norma: Mapped[str] = mapped_column(Text, nullable=False)
    payload_jsonb: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    usuario_admin_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    registros_criados: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo_tabela IN "
            "('inss','irrf','fgts','simples_nacional','presuncao_lp',"
            "'icms_uf','cbs_ibs')",
            name="ck_vig_tab_log_tipo",
        ),
        CheckConstraint(
            "char_length(fonte_norma) >= 10",
            name="ck_vig_tab_log_fonte_minima",
        ),
        CheckConstraint(
            "registros_criados >= 0",
            name="ck_vig_tab_log_registros_nao_negativo",
        ),
        UniqueConstraint(
            "idempotency_key", name="uq_vig_tab_log_idempotency"
        ),
        Index(
            "ix_vig_tab_log_tipo_data",
            "tipo_tabela",
            "valid_from",
        ),
        Index("ix_vig_tab_log_criado_em", "criado_em"),
    )


class AlertaAdmin(Base):
    """Alerta proativo do painel admin (Sprint 19.5 PR2).

    Worker diário ``tabelas.verificar_vigencias`` insere uma linha por
    chave ``(tipo, tipo_tabela, ano_corrente)`` quando detecta vigência
    SCD desatualizada. Endpoints ``GET /v1/admin/alertas`` filtram por
    ``severidade`` e ``resolvido`` (= ``resolvido_em IS NULL`` ou ≤ now).

    Diferente de ``vigencia_tabela_log`` (audit puramente append-only),
    aqui o UPDATE é parte do contrato — resolver e snooze atualizam
    ``resolvido_em`` in-place. Não é fato fiscal, é estado operacional.

    Idempotência §8.9: ``idempotency_key = uuid5(NS_TABELA_ADMIN,
    "alerta|{tipo}|{tipo_tabela}|{ano_corrente}")``. 2 runs do worker no
    mesmo mês caem em ``UNIQUE`` violation e ficam no-op.

    ``contexto_jsonb`` carrega metadados úteis para o UI / digest WhatsApp:
    ``tipo_tabela``, ``ano_corrente``, ``ano_vigencia_ativa``,
    ``dias_desde_ultima_atualizacao``, link sugerido etc.
    """

    __tablename__ = "alerta_admin"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid4,
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    severidade: Mapped[str] = mapped_column(String(10), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    contexto_jsonb: Mapped[JsonObject] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    idempotency_key: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    resolvido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    resolvido_por_usuario_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "severidade IN ('info','aviso','critico')",
            name="ck_alerta_admin_severidade",
        ),
        UniqueConstraint(
            "idempotency_key", name="uq_alerta_admin_idempotency"
        ),
        Index("ix_alerta_admin_tipo", "tipo"),
        # Index parcial ix_alerta_admin_abertos é criado via SQL puro na
        # migration 0043 (Alembic não tem alias de Index parcial direto
        # para WHERE; criar aqui só vazaria definição). Não precisamos
        # do índice em testes unitários.
    )


class SugestaoVigenciaTabela(Base):
    """Sugestão de vigência tributária gerada por LLM (Sprint 19.5 PR3).

    Camada 3 do painel admin. Worker mensal varre o DOU, extrai PDFs via
    ``pdfplumber``, passa para LLM Gemini Flash com prompt versionado que
    devolve JSON estruturado matching ``VigenciaInssIn`` (e similares),
    aplica re-check determinístico §8.6 e cria **uma sugestão pendente**.

    **NUNCA cria vigência tributária diretamente** — princípio inviolável
    §8.8. Admin humano revisa via ``GET /v1/admin/sugestoes-vigencia`` e
    aprova/rejeita com 1 clique.

    Aprovação chama ``TabelaAdminService.criar_vigencia_<tipo>`` da Camada 1
    com ``payload_jsonb`` como body — link bidirecional via
    ``vigencia_tabela_log_id`` FK.

    Re-check §8.6 NÃO bloqueia a criação da sugestão — registra
    ``recheck_passou=false`` + detalhes em ``recheck_observacoes`` para a
    UI destacar em vermelho. Admin decide se quer aprovar mesmo assim
    (cenário: LLM acertou a estrutura mas errou um valor que humano
    consegue corrigir mentalmente).
    """

    __tablename__ = "sugestao_vigencia_tabela"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid4,
    )
    tipo_tabela: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[date] = mapped_column(DATE, nullable=False)
    payload_jsonb: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    fonte_norma: Mapped[str] = mapped_column(Text, nullable=False)
    fonte_dou_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fonte_dou_pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_modelo: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_versao_prompt: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_confianca: Mapped[Decimal] = mapped_column(
        NUMERIC(3, 2), nullable=False
    )
    recheck_passou: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recheck_observacoes: Mapped[JsonObject] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pendente"
    )
    aprovada_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    aprovada_por_usuario_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    rejeitada_motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    vigencia_tabela_log_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("vigencia_tabela_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo_tabela IN "
            "('inss','irrf','fgts','simples_nacional','presuncao_lp',"
            "'icms_uf','cbs_ibs')",
            name="ck_sugestao_tipo",
        ),
        CheckConstraint(
            "status IN ('pendente','aprovada','rejeitada','expirada')",
            name="ck_sugestao_status",
        ),
        CheckConstraint(
            "char_length(fonte_norma) >= 10",
            name="ck_sugestao_fonte_minima",
        ),
        CheckConstraint(
            "llm_confianca >= 0 AND llm_confianca <= 1",
            name="ck_sugestao_confianca_intervalo",
        ),
        CheckConstraint(
            "(status = 'aprovada') = (aprovada_em IS NOT NULL)",
            name="ck_sugestao_aprovada_coerente",
        ),
        UniqueConstraint(
            "idempotency_key", name="uq_sugestao_idempotency"
        ),
        Index(
            "ix_sugestao_status", "status", "criado_em"
        ),
    )


# ── Billing — assinatura SaaS (Marco 2 produção) ─────────────────────────────


class Assinatura(Base):
    """Assinatura do cliente (tenant) ao Arkan — cobrança recorrente via Stripe.

    Uma assinatura viva por tenant. Status: trial → ativa →
    (inadimplente → ativa | cancelada). RLS por ``tenant_id``; o webhook do
    Stripe escreve via sessão superuser (que bypassa RLS, sem FORCE).
    """

    __tablename__ = "assinatura"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    plano_codigo: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="trial"
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    planos_versao: Mapped[str] = mapped_column(String(40), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('trial','ativa','inadimplente','cancelada')",
            name="ck_assinatura_status",
        ),
        Index("ix_assinatura_tenant", "tenant_id"),
        Index("ix_assinatura_stripe_sub", "stripe_subscription_id"),
    )


class Fatura(Base):
    """Fatura de uma assinatura — espelho da invoice do Stripe."""

    __tablename__ = "fatura"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assinatura_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assinatura.id", ondelete="CASCADE"),
        nullable=False,
    )
    valor: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="aberta"
    )
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    competencia: Mapped[date] = mapped_column(DATE, nullable=False)
    pago_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('aberta','paga','falhou','cancelada')",
            name="ck_fatura_status",
        ),
        UniqueConstraint("stripe_invoice_id", name="uq_fatura_stripe_invoice"),
        Index("ix_fatura_tenant", "tenant_id"),
        Index("ix_fatura_assinatura", "assinatura_id"),
    )


class EventoBilling(Base):
    """Evento de webhook do Stripe — idempotencia via ``stripe_event_id`` UNIQUE.

    ``tenant_id`` nullable: eventos globais do Stripe podem nao mapear a um
    tenant. Escrito pelo webhook (sessao superuser, bypassa RLS).
    """

    __tablename__ = "evento_billing"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    stripe_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[JsonObject] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    processado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "stripe_event_id", name="uq_evento_billing_stripe_event"
        ),
        Index("ix_evento_billing_stripe", "stripe_event_id"),
    )


class LgpdSolicitacao(Base):
    """Trilha de auditoria de solicitacao de direito do titular (LGPD art. 18).

    Marco 3. Uma linha por exportacao (portabilidade) ou exclusao
    (esquecimento por anonimizacao). ``detalhes`` guarda o RESUMO do ato
    (contagens, campos anonimizados) -- nunca a PII em si. Migration 0062.
    """

    __tablename__ = "lgpd_solicitacao"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="concluida"
    )
    detalhes: Mapped[JsonObject] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('exportacao','exclusao')", name="ck_lgpd_solicitacao_tipo"
        ),
        CheckConstraint(
            "status IN ('concluida','agendada','erro')",
            name="ck_lgpd_solicitacao_status",
        ),
        Index("ix_lgpd_solicitacao_tenant", "tenant_id"),
    )


class ManifestacaoNFe(Base):
    """Manifestação do Destinatário de NF-e (MD-e) — PR1 fundação.

    4 eventos NT 2014.002 / NT 2020.001:
      210200 — Confirmação da Operação
      210210 — Ciência da Operação
      210220 — Desconhecimento da Operação
      210240 — Operação não Realizada (exige justificativa 15–255 chars)

    Status machine: preparado → assinado → transmitido → aceito/rejeitado
    (§8.2: append-only; cancelamento = novo evento no SEFAZ, não UPDATE aqui).

    Migration 0067.
    """

    __tablename__ = "manifestacao_nfe"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False
    )
    chave_nfe: Mapped[str] = mapped_column(String(44), nullable=False)
    cnpj_destinatario: Mapped[str] = mapped_column(String(14), nullable=False)
    tipo_evento: Mapped[str] = mapped_column(String(6), nullable=False)
    sequencial: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="preparado")
    protocolo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    codigo_status_sefaz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motivo_sefaz: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_evento_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_recibo_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    algoritmo_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    assinado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    transmitido_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    respondido_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "tipo_evento IN ('210200','210210','210220','210240')",
            name="ck_manifestacao_tipo_evento",
        ),
        CheckConstraint(
            "status IN ('preparado','assinado','transmitido','aceito','rejeitado')",
            name="ck_manifestacao_status",
        ),
        CheckConstraint(
            "(tipo_evento = '210240') = (justificativa IS NOT NULL)",
            name="ck_manifestacao_just_obrigatoria",
        ),
        CheckConstraint(
            "justificativa IS NULL OR "
            "(char_length(justificativa) >= 15 AND char_length(justificativa) <= 255)",
            name="ck_manifestacao_just_tamanho",
        ),
        CheckConstraint(
            r"chave_nfe ~ '^\d{44}$'",
            name="ck_manifestacao_chave_formato",
        ),
        CheckConstraint(
            r"cnpj_destinatario ~ '^\d{14}$'",
            name="ck_manifestacao_cnpj_formato",
        ),
        CheckConstraint(
            "sequencial >= 1",
            name="ck_manifestacao_sequencial_positivo",
        ),
        Index("ix_manifestacao_tenant", "tenant_id"),
        Index("ix_manifestacao_empresa_chave", "empresa_id", "chave_nfe"),
        Index("ix_manifestacao_status", "status"),
        UniqueConstraint(
            "empresa_id", "chave_nfe", "tipo_evento", "sequencial",
            name="uq_manifestacao_empresa_chave_tipo_seq",
        ),
    )


class RefreshToken(Base):
    """Refresh token DB-backed com rotacao + revogacao (Marco 3).

    Guarda so o SHA-256 hex do token (nunca o valor cru). ``family_id`` encadeia
    a linhagem de rotacao: cada renovacao revoga o token atual e emite um novo na
    MESMA familia. Apresentar um token ja revogado (``revoked_at`` setado) =
    reuso -> sinal de roubo -> toda a familia e revogada. Migration 0064.
    """

    __tablename__ = "refresh_token"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    usuario_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    family_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
        Index("ix_refresh_token_family", "family_id"),
        Index("ix_refresh_token_tenant", "tenant_id"),
    )


class NfeDestinada(Base):
    """NF-e emitida contra o CNPJ da empresa, descoberta pelo DistribuiçãoDFe.

    Uma linha por (empresa, chave_nfe). O upsert transiciona o documento de
    'resumo' (resNFe, antes da Ciência) para 'completo' (nfeProc, após Ciência)
    sem duplicar (§8.9). Migration 0068.

    Fonte: NT 2014.002 / retDistDFeInt (SEFAZ Ambiente Nacional).
    """

    __tablename__ = "nfe_destinada"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
    )
    chave_nfe: Mapped[str] = mapped_column(String(44), nullable=False)
    nsu: Mapped[int] = mapped_column(BigInteger, nullable=False)
    emitente_cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    emitente_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valor_total: Mapped[Decimal | None] = mapped_column(NUMERIC(14, 2), nullable=True)
    dh_emissao: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    tipo_documento: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="resumo"
    )
    tem_xml_completo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    xml_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            r"chave_nfe ~ '^\d{44}$'",
            name="ck_nfe_destinada_chave_formato",
        ),
        CheckConstraint(
            "tipo_documento IN ('resumo','completo')",
            name="ck_nfe_destinada_tipo_doc",
        ),
        Index("ix_nfe_destinada_tenant", "tenant_id"),
        Index("ix_nfe_destinada_empresa_nsu", "empresa_id", "nsu"),
        UniqueConstraint(
            "empresa_id", "chave_nfe", name="uq_nfe_destinada_empresa_chave"
        ),
    )


class NfeDistribuicaoCursor(Base):
    """Cursor de NSU por empresa para o serviço DistribuiçãoDFe.

    Uma linha por empresa (PK = empresa_id). O service de sincronização lê
    ``ult_nsu`` antes de cada chamada e atualiza ambos os campos após cada
    batch. Quando ``ult_nsu == max_nsu``, não há mais documentos a consumir.
    Migration 0068.
    """

    __tablename__ = "nfe_distribuicao_cursor"

    empresa_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    ult_nsu: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    max_nsu: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    ultima_sync_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_nfe_distribuicao_cursor_tenant", "tenant_id"),
    )
