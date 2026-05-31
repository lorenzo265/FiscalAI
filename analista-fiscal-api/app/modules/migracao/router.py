"""Endpoints REST — migração de escritório antigo (Sprint 18 PR2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.modules.migracao.repo import LoteImportacaoRepo
from app.modules.migracao.schemas import (
    FonteLote,
    LoteImportacaoOut,
    StatusLote,
)
from app.modules.migracao.service import MigracaoService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.db.models import LoteImportacao
from app.shared.exceptions import LoteImportacaoNaoEncontrado

router = APIRouter(prefix="/v1/empresas", tags=["migracao"])

# 50 MB — ECD anual de PME tipicamente fica em 5–15 MB; EFD-Contribuições
# anual pode chegar a 30 MB. Limite com folga.
_MAX_SPED_BYTES = 50 * 1024 * 1024


def _to_out(lote: LoteImportacao) -> LoteImportacaoOut:
    return LoteImportacaoOut(
        id=lote.id,
        empresa_id=lote.empresa_id,
        fonte=FonteLote(lote.fonte),
        arquivo_sped_id=lote.arquivo_sped_id,
        nome_arquivo=lote.nome_arquivo,
        hash_arquivo=lote.hash_arquivo,
        status=StatusLote(lote.status),
        iniciado_em=lote.iniciado_em,
        concluido_em=lote.concluido_em,
        resumo=lote.resumo_jsonb,
        erros=lote.erros_jsonb,
        algoritmo_versao=lote.algoritmo_versao,
    )


@router.post(
    "/{empresa_id}/migracao/sped/ecd/upload",
    response_model=LoteImportacaoOut,
    status_code=200,
    summary="Importa SPED ECD histórico do escritório antigo",
    description=(
        "Recebe o arquivo .txt SPED ECD entregue pelo escritório anterior "
        "e reconstrói os lançamentos contábeis do exercício como "
        "`origem_tipo='importacao'`. Idempotente por hash SHA-256 — "
        "re-upload do mesmo arquivo devolve o lote anterior. CNPJ do "
        "0000 deve bater com `Empresa.cnpj`. Período mínimo aceito: "
        "2024-01-01."
    ),
)
async def upload_ecd(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    conteudo = await arquivo.read(_MAX_SPED_BYTES)
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo SPED vazio")
    resultado = await MigracaoService().importar_sped_ecd(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        conteudo=conteudo,
        nome_arquivo=arquivo.filename,
    )
    return _to_out(resultado.lote)


@router.post(
    "/{empresa_id}/migracao/sped/ecf/upload",
    response_model=LoteImportacaoOut,
    status_code=200,
    summary="Importa SPED ECF histórico (snapshot read-only)",
    description=(
        "Recebe o arquivo .txt SPED ECF entregue pelo escritório anterior "
        "e registra **snapshot** das apurações IRPJ/CSLL trimestrais "
        "declaradas. NÃO recria apurações — usamos só para comparar "
        "com o que recalculamos por cima dos lançamentos importados "
        "via ECD."
    ),
)
async def upload_ecf(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    conteudo = await arquivo.read(_MAX_SPED_BYTES)
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo SPED vazio")
    resultado = await MigracaoService().importar_sped_ecf(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        conteudo=conteudo,
        nome_arquivo=arquivo.filename,
    )
    return _to_out(resultado.lote)


@router.post(
    "/{empresa_id}/migracao/sped/efd-contribuicoes/upload",
    response_model=LoteImportacaoOut,
    status_code=200,
    summary="Importa SPED EFD-Contribuições histórico (PIS/Cofins mensal)",
    description=(
        "Recebe `.txt` SPED EFD-Contribuições do escritório anterior e "
        "cria `documento_fiscal` + `documento_fiscal_item` por NF-e/NFS-e. "
        "Cross-check §8.9 por chave de acesso — se a NF já foi ingerida via "
        "XML (Sprint 2), não duplica e registra warning. Apuração PIS/Cofins "
        "(M200/M600) fica como snapshot em `resumo_jsonb` para audit."
    ),
)
async def upload_efd_contribuicoes(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    conteudo = await arquivo.read(_MAX_SPED_BYTES)
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo SPED vazio")
    resultado = await MigracaoService().importar_sped_efd_contribuicoes(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        conteudo=conteudo,
        nome_arquivo=arquivo.filename,
    )
    return _to_out(resultado.lote)


@router.post(
    "/{empresa_id}/migracao/sped/efd-icms-ipi/upload",
    response_model=LoteImportacaoOut,
    status_code=200,
    summary="Importa SPED EFD ICMS-IPI histórico (ICMS mensal)",
    description=(
        "Idem EFD-Contribuições mas para o leiaute ICMS-IPI: extrai "
        "C100/C170 + apuração E110 como snapshot. Bloco G (CIAP) e bloco H "
        "(inventário) ficam fora desta PR — pendências #31/#32."
    ),
)
async def upload_efd_icms_ipi(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    conteudo = await arquivo.read(_MAX_SPED_BYTES)
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo SPED vazio")
    resultado = await MigracaoService().importar_sped_efd_icms_ipi(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        conteudo=conteudo,
        nome_arquivo=arquivo.filename,
    )
    return _to_out(resultado.lote)


@router.post(
    "/{empresa_id}/migracao/csv/balancete/upload",
    response_model=LoteImportacaoOut,
    status_code=200,
    summary="Importa balancete CSV (snapshot read-only — fallback sem SPED)",
    description=(
        "Para escritórios que não entregam SPED. Cabeçalho: `codigo_conta;"
        "descricao;saldo_inicial;debito;credito;saldo_final`. Aceita "
        "separador ; ou , e decimal vírgula ou ponto. NÃO recria "
        "lançamentos — apenas grava snapshot em `resumo_jsonb`."
    ),
)
async def upload_csv_balancete(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    conteudo = await arquivo.read(_MAX_SPED_BYTES)
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo CSV vazio")
    resultado = await MigracaoService().importar_csv_balancete(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        conteudo=conteudo,
        nome_arquivo=arquivo.filename,
    )
    return _to_out(resultado.lote)


@router.post(
    "/{empresa_id}/migracao/csv/razao/upload",
    response_model=LoteImportacaoOut,
    status_code=200,
    summary="Importa razão CSV — gera lançamentos contábeis",
    description=(
        "Cabeçalho: `data;conta_debito;conta_credito;historico;valor`. "
        "Cada linha vira um `lancamento_contabil(origem_tipo='importacao')` "
        "idempotente. Contas ausentes do plano viram warning. Chaves NF-e "
        "(44 dígitos) detectadas no histórico ficam registradas em "
        "`resumo.chaves_nfe_referenciadas` para cross-check posterior."
    ),
)
async def upload_csv_razao(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    conteudo = await arquivo.read(_MAX_SPED_BYTES)
    if not conteudo:
        raise HTTPException(status_code=422, detail="Arquivo CSV vazio")
    resultado = await MigracaoService().importar_csv_razao(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        conteudo=conteudo,
        nome_arquivo=arquivo.filename,
    )
    return _to_out(resultado.lote)


@router.get(
    "/{empresa_id}/migracao/lote/{lote_id}",
    response_model=LoteImportacaoOut,
    summary="Detalhe de um lote de importação (polling)",
)
async def obter_lote(
    empresa_id: UUID,
    lote_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteImportacaoOut:
    lote = await LoteImportacaoRepo(session).por_id(lote_id)
    if lote is None or lote.empresa_id != empresa_id:
        raise LoteImportacaoNaoEncontrado(
            f"Lote {lote_id} não encontrado para empresa {empresa_id}"
        )
    return _to_out(lote)


@router.get(
    "/{empresa_id}/migracao/lotes",
    response_model=list[LoteImportacaoOut],
    summary="Lista lotes de importação da empresa",
)
async def listar_lotes(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    limite: int = Query(default=50, ge=1, le=200),
) -> list[LoteImportacaoOut]:
    lotes = await LoteImportacaoRepo(session).listar_empresa(
        empresa_id, limite=limite
    )
    return [_to_out(lote) for lote in lotes]
