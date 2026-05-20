from __future__ import annotations

from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.ingestao.parser import NFeData, XmlNFeInvalido, parse_xml_nfe
from app.modules.ingestao.repo import DocumentoFiscalRepo
from app.shared.db.models import DocumentoFiscal
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

        doc = DocumentoFiscal(
            id=uuid4(),
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
            natureza_operacao=nfe.natureza_operacao,
            regime_emitente=regime_emitente,
            ingested_via="upload",
        )

        salvo = await self._doc_repo.salvar(doc)

        log.info(
            "ingestao.upload.ok",
            empresa_id=str(empresa_id),
            chave=nfe.chave,
            tipo=nfe.tipo,
            direcao=direcao,
            valor_total=str(nfe.valor_total),
        )

        return salvo
