"""Service — Validação local de arquivos SPED (Sprint 16 PR3).

Despacha por ``arquivo_sped.tipo`` para ``validador_ecd``/``validador_ecf``,
persiste o resultado em ``validacao_jsonb`` e transita
``status='gerado' → 'validado'`` quando não há erros.

Princípios:

* §8.2 — não substitui o arquivo (`conteudo_bytea` e `hash` permanecem).
  Apenas `validacao_jsonb` e `status` mudam — mas a tabela é REVOKE
  UPDATE FROM PUBLIC, então UPDATE precisa de role privilegiado. Em
  produção: usuário admin OU role ``sped_validator``. Neste sprint
  optamos por SQL UPDATE direto via service (caller é endpoint validar
  do contador autenticado — fail-fast quando RLS negar).
* §8.10 — log estruturado com totais por categoria.

UPDATE em ``arquivo_sped`` é permitido para o owner (RLS por tenant_id)
porque o REVOKE é apenas em PUBLIC — o role da aplicação (`fiscal`)
mantém INSERT/UPDATE. A imutabilidade do **fato** (conteúdo + hash +
algoritmo_versao + periodo) continua valendo: só metadados de auditoria
(status + validacao_jsonb + recibo_transmissao + transmitido_em) podem
mudar.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sped.ecd.repo import ArquivoSpedRepo
from app.modules.sped.validador import (
    ResultadoValidacao,
    resultado_para_jsonb,
    validar_por_tipo,
)
from app.shared.db.models import ArquivoSped
from app.shared.exceptions import ArquivoSpedNaoEncontrado

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ValidacaoExecutada:
    """Bundle devolvido — arquivo atualizado + resultado da validação."""

    arquivo: ArquivoSped
    resultado: ResultadoValidacao


class SpedValidacaoService:
    async def validar(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        sped_id: UUID,
        *,
        tipo: str,
    ) -> ValidacaoExecutada:
        """Executa validação local + persiste resultado em ``validacao_jsonb``.

        Raises:
            ArquivoSpedNaoEncontrado: ID inexistente, cross-tenant via RLS,
                cross-empresa, ou ``tipo`` divergente do esperado.
        """
        repo = ArquivoSpedRepo(session)
        arquivo = await repo.por_id(sped_id)
        if (
            arquivo is None
            or arquivo.empresa_id != empresa_id
            or arquivo.tipo != tipo
        ):
            raise ArquivoSpedNaoEncontrado(
                f"Arquivo SPED {sped_id} (tipo={tipo}) não encontrado."
            )

        conteudo_str = bytes(arquivo.conteudo_bytea).decode(
            "latin-1", errors="replace"
        )
        resultado = validar_por_tipo(arquivo.tipo, conteudo_str)

        arquivo.validacao_jsonb = resultado_para_jsonb(resultado)
        if resultado.ok and arquivo.status == "gerado":
            arquivo.status = "validado"

        await session.flush()
        await session.commit()
        await session.refresh(arquivo)

        log.info(
            "sped.validado",
            empresa_id=str(empresa_id),
            sped_id=str(sped_id),
            tipo=arquivo.tipo,
            ok=resultado.ok,
            total_erros=resultado.total_erros,
            total_warnings=resultado.total_warnings,
            status_novo=arquivo.status,
        )
        return ValidacaoExecutada(arquivo=arquivo, resultado=resultado)
