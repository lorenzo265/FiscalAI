"""Endpoints REST — operações cross-tipo SPED (Sprint 16 PR3).

Os endpoints específicos de geração ficam em ``ecd/router.py`` e
``ecf/router.py``. Aqui ficam:

* Listagem de arquivos SPED da empresa (com filtros).
* Validação local de um arquivo já gerado.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict

from app.modules.sped.ecd.repo import ArquivoSpedRepo
from app.modules.sped.ecd.schemas import ArquivoSpedOut
from app.modules.sped.validacao_service import SpedValidacaoService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["sped"])


class TipoSpedFiltro(StrEnum):
    ECD = "ecd"
    ECF = "ecf"
    EFD_CONTRIBUICOES = "efd_contribuicoes"
    EFD_ICMS_IPI = "efd_icms_ipi"


class IssueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severidade: str
    codigo: str
    mensagem: str
    contexto: dict[str, str]


class ValidacaoOut(BaseModel):
    """Resposta do POST /sped/{tipo}/{id}/validar."""

    model_config = ConfigDict(extra="forbid")

    arquivo: ArquivoSpedOut
    ok: bool
    total_erros: int
    total_warnings: int
    validador_versao: str
    erros: list[IssueOut]
    warnings: list[IssueOut]


@router.get(
    "/{empresa_id}/sped",
    response_model=list[ArquivoSpedOut],
    summary="Lista arquivos SPED da empresa",
    description=(
        "Lista arquivos SPED gerados/validados/transmitidos. Filtros: "
        "``tipo`` (ecd|ecf|efd_contribuicoes|efd_icms_ipi) e "
        "``somente_ativos`` (default true — esconde versões supersededas)."
    ),
)
async def listar_sped(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoSpedFiltro | None = Query(default=None),
    somente_ativos: bool = Query(default=True),
    limite: int = Query(default=50, ge=1, le=500),
) -> list[ArquivoSpedOut]:
    rows = await ArquivoSpedRepo(session).listar(
        empresa_id,
        tipo=tipo.value if tipo else None,
        somente_ativos=somente_ativos,
        limite=limite,
    )
    return [ArquivoSpedOut.model_validate(r) for r in rows]


# Sprint 19.7 PR3 (#35) — endpoint de download genérico cobre os 4 tipos
# (ECD, ECF, EFD-Contribuições, EFD-ICMS-IPI). Os endpoints específicos
# de download em ecd/router.py e ecf/router.py continuam funcionando
# (compat backward); este endpoint unifica acesso pra novos clientes.


@router.get(
    "/{empresa_id}/sped/{tipo}/{sped_id}/download",
    summary="Baixa o .txt SPED gerado (qualquer tipo)",
    description=(
        "Devolve o ``.txt`` SPED persistido em ``arquivo_sped.conteudo_bytea`` "
        "em ``application/octet-stream`` + Content-Disposition attachment. "
        "Headers de auditoria: ``X-Sped-Hash`` (SHA-256 do arquivo, cliente "
        "compara antes de transmitir ao PVA) e ``X-Sped-Algoritmo-Versao`` "
        "(versão do gerador). 404 se ``sped_id`` não pertence à empresa ou "
        "se o tipo do arquivo não casa com a URL (defesa em profundidade)."
    ),
)
async def download_sped_generico(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoSpedFiltro = Path(...),
    sped_id: UUID = Path(...),
) -> Response:
    arquivo = await ArquivoSpedRepo(session).por_id(sped_id)
    if (
        arquivo is None
        or arquivo.empresa_id != empresa_id
        or arquivo.tipo != tipo.value
    ):
        raise HTTPException(status_code=404, detail="Arquivo SPED não encontrado")

    nome = (
        f"sped_{arquivo.tipo}_"
        f"{arquivo.periodo_inicio.strftime('%Y%m%d')}-"
        f"{arquivo.periodo_fim.strftime('%Y%m%d')}.txt"
    )
    return Response(
        content=bytes(arquivo.conteudo_bytea),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "X-Sped-Hash": arquivo.hash_arquivo,
            "X-Sped-Algoritmo-Versao": arquivo.algoritmo_versao,
        },
    )


@router.post(
    "/{empresa_id}/sped/{tipo}/{sped_id}/validar",
    response_model=ValidacaoOut,
    summary="Valida localmente o arquivo SPED gerado",
    description=(
        "Executa o validador local (estrutural + amarrações de negócio) "
        "no conteúdo persistido em ``arquivo_sped.conteudo_bytea``. Persiste "
        "o resultado em ``validacao_jsonb`` e, se zero erros, transita "
        "``status='gerado' → 'validado'``. Idempotente — pode ser chamado "
        "repetidamente; o ``validacao_jsonb`` é sobrescrito a cada chamada.\n\n"
        "**Resposta sempre 200** — erros não são exceção HTTP; o cliente "
        "inspeciona ``ok`` + ``erros`` para decidir se transmite ao PVA."
    ),
)
async def validar_sped(
    empresa_id: UUID,
    tipo: TipoSpedFiltro = Path(...),
    sped_id: UUID = Path(...),
    *,
    ctx: TenantDep,
    session: SessionDep,
) -> ValidacaoOut:
    executada = await SpedValidacaoService().validar(
        session, empresa_id, sped_id, tipo=tipo.value,
    )
    return ValidacaoOut(
        arquivo=ArquivoSpedOut.model_validate(executada.arquivo),
        ok=executada.resultado.ok,
        total_erros=executada.resultado.total_erros,
        total_warnings=executada.resultado.total_warnings,
        validador_versao=executada.resultado.validador_versao,
        erros=[
            IssueOut(
                severidade=i.severidade,
                codigo=i.codigo,
                mensagem=i.mensagem,
                contexto=dict(i.contexto),
            )
            for i in executada.resultado.erros
        ],
        warnings=[
            IssueOut(
                severidade=i.severidade,
                codigo=i.codigo,
                mensagem=i.mensagem,
                contexto=dict(i.contexto),
            )
            for i in executada.resultado.warnings
        ],
    )
