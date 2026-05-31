from __future__ import annotations

from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.ingestao.parser import (
    NFeData,
    NFeItem,
    XmlNFeInvalido,
    parse_xml_nfe,
)
from app.modules.ingestao.repo import DocumentoFiscalRepo
from app.shared.db.models import DocumentoFiscal, DocumentoFiscalItem
from app.shared.exceptions import (
    DocumentoJaIngerido,
    EmpresaNaoEncontrada,
    XmlInvalido,
)

log = structlog.get_logger(__name__)


class IngestaoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._empresa_repo = EmpresaRepo(session)
        self._doc_repo = DocumentoFiscalRepo(session)

    async def ingerir_upload(
        self,
        tenant_id: UUID,
        empresa_id: UUID,
        xml_bytes: bytes,
    ) -> DocumentoFiscal:
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        try:
            nfe: NFeData = parse_xml_nfe(xml_bytes)
        except XmlNFeInvalido as exc:
            raise XmlInvalido(str(exc)) from exc

        if nfe.chave:
            existente = await self._doc_repo.buscar_por_chave(nfe.chave)
            if existente is not None:
                raise DocumentoJaIngerido(
                    f"Documento com chave {nfe.chave} já ingerido (id={existente.id})"
                )

        direcao = "saida" if nfe.cnpj_emitente == empresa.cnpj else "entrada"

        regime_emitente: str | None = None
        if nfe.crt == "1":
            regime_emitente = "simples_nacional"
        elif nfe.crt == "2":
            regime_emitente = "simples_nacional_excesso"
        elif nfe.crt == "3":
            regime_emitente = "regime_normal"

        valor_impostos = (nfe.valor_icms + nfe.valor_ipi + nfe.valor_pis + nfe.valor_cofins)

        doc_id = uuid4()
        doc = DocumentoFiscal(
            id=doc_id,
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=nfe.tipo,
            direcao=direcao,
            chave=nfe.chave,
            numero=nfe.numero,
            serie=nfe.serie,
            status="autorizada",
            emitida_em=nfe.emitida_em,
            cnpj_emitente=nfe.cnpj_emitente,
            cnpj_destinatario=nfe.cnpj_destinatario,
            valor_total=nfe.valor_total,
            valor_impostos=valor_impostos,
            valor_icms=nfe.valor_icms,
            valor_ipi=nfe.valor_ipi,
            valor_pis=nfe.valor_pis,
            valor_cofins=nfe.valor_cofins,
            valor_iss=None,
            cfop=nfe.cfop,
            ncm=nfe.ncm,
            valor_cbs=nfe.valor_cbs,
            valor_ibs=nfe.valor_ibs,
            cclasstrib=nfe.cclasstrib,
            natureza_operacao=nfe.natureza_operacao,
            regime_emitente=regime_emitente,
            ingested_via="upload",
        )
        # Itens granular (Sprint 18 PR1 — pendência #26).
        doc.itens = [_item_to_model(tenant_id, doc_id, it) for it in nfe.itens]

        salvo = await self._doc_repo.salvar(doc)

        log.info(
            "ingestao.upload.ok",
            empresa_id=str(empresa_id),
            chave=nfe.chave,
            tipo=nfe.tipo,
            direcao=direcao,
            valor_total=str(nfe.valor_total),
            itens=len(nfe.itens),
        )

        return salvo


def _item_to_model(
    tenant_id: UUID, documento_fiscal_id: UUID, item: NFeItem
) -> DocumentoFiscalItem:
    """Converte ``NFeItem`` (dataclass do parser) em modelo ORM.

    Função pura — testável isoladamente. Mantém ``tenant_id`` propagado
    porque o RLS da tabela ``documento_fiscal_item`` é independente
    (não puxa do pai via FK).
    """
    return DocumentoFiscalItem(
        tenant_id=tenant_id,
        documento_fiscal_id=documento_fiscal_id,
        n_item=item.n_item,
        codigo_produto=item.codigo_produto,
        descricao=item.descricao,
        ncm=item.ncm,
        cfop=item.cfop,
        cst_icms=item.cst_icms,
        cst_pis=item.cst_pis,
        cst_cofins=item.cst_cofins,
        unidade=item.unidade,
        quantidade=item.quantidade,
        valor_unitario=item.valor_unitario,
        valor_total=item.valor_total,
        valor_icms=item.valor_icms,
        valor_ipi=item.valor_ipi,
        valor_pis=item.valor_pis,
        valor_cofins=item.valor_cofins,
        valor_cbs=item.valor_cbs,
        valor_ibs=item.valor_ibs,
    )
