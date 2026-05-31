"""Onboarding self-service bundle (Sprint 19 PR4).

Orquestra o bootstrap mínimo de uma empresa recém-criada para que o cliente
consiga emitir a primeira nota / lançar o primeiro fato em < 2h sem
contador (Plano §11 Sprint 19 — "bundle onboarding self-service").

O endpoint ``POST /v1/empresas/{empresa_id}/onboarding/bundle``:

  1. Verifica empresa existe (FK + tenant).
  2. **Guard contra conflito com importação SPED**: se houver
     ``lote_importacao`` concluído (Sprint 18 PR2-3), o plano de contas
     dela DEVE vir do SPED original. Bootstrap automático aqui sobrescrevia
     o plano migrado e causava divergência de códigos — levanta
     ``OnboardingConflitoComImportacao`` (HTTP 409). Operador resolve via
     rollback do lote OU pulando o bundle.
  3. Clona plano referencial RFB (chama ``ContabilService.clonar_plano_referencial``
     — Sprint 9 PR1, já idempotente: contas com mesmo código são puladas).
  4. Marca ``welcome_digest_optin=True`` em log estruturado (sem coluna
     própria — flag de intenção que o worker do digest semanal vai
     respeitar quando consultar ``empresa.whatsapp_phone``).
  5. Constrói checklist de próximos passos contextualizada por ``perfil_ui``
     (frontend usa ``chave`` para roteamento e ``concluido`` para pintar
     ícones — bundle é seguro de chamar várias vezes; checklist re-avalia
     o estado).

Princípios cravados:
  * §8.9 idempotência — re-execução é segura; clone pula contas existentes,
    checklist re-avalia o estado (não duplica nem regrede).
  * §8.10 observabilidade — log ``empresa.onboarding.bundle`` em cada
    operação com contadores estruturados.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.service import ContabilService
from app.modules.empresa.repo import EmpresaRepo
from app.modules.empresa.schemas import (
    OnboardingBundleOut,
    OnboardingPassoOut,
    PerfilUI,
)
from app.shared.db.models import Empresa, LoteImportacao
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    OnboardingConflitoComImportacao,
)

log = structlog.get_logger(__name__)


def _perfil_seguro(valor: str) -> PerfilUI:
    """Converte o ``perfil_ui`` do DB em ``PerfilUI`` com fallback defensivo.

    Se um perfil novo aparece no DB antes do enum (caso operacional ao
    introduzir novo regime), cai em ``SN_SEM_FUNCIONARIOS`` — menos opções,
    menos risco — em vez de quebrar o bundle.
    """
    try:
        return PerfilUI(valor)
    except ValueError:
        log.warning("empresa.perfil_ui_desconhecido", valor=valor)
        return PerfilUI.SN_SEM_FUNCIONARIOS


@dataclass(frozen=True, slots=True)
class _PassoSpec:
    """Especificação de um passo do checklist — definida estaticamente por
    perfil_ui; o service marca ``concluido`` consultando o estado da empresa.
    """

    chave: str
    titulo: str
    descricao: str
    endpoint: str | None


# Passos comuns a todos os regimes (ordem é exibida no UI).
_PASSO_PLANO = _PassoSpec(
    chave="plano_contas_clonado",
    titulo="Plano de contas inicial criado",
    descricao=(
        "36 contas do plano referencial RFB foram clonadas. "
        "Você pode personalizar via /v1/empresas/{id}/contabil/contas."
    ),
    endpoint="/v1/empresas/{empresa_id}/contabil/contas",
)

_PASSO_ISS_VALIDADO = _PassoSpec(
    chave="iss_validado",
    titulo="Validar alíquota ISS com seu contador",
    descricao=(
        "Antes da primeira emissão NFS-e, peça ao contador para confirmar "
        "a alíquota ISS do seu CNAE no município. Padrão (5%) pode estar errado."
    ),
    endpoint="/v1/empresas/{empresa_id}/iss-validada",
)

_PASSO_PLUGGY = _PassoSpec(
    chave="pluggy_conectado",
    titulo="Conectar conta bancária (Open Finance)",
    descricao=(
        "Conecte via Pluggy para conciliação automática de transações × NF. "
        "Sem isso, a conciliação fica manual."
    ),
    endpoint="/v1/empresas/{empresa_id}/open-finance/connect-token",
)

_PASSO_WHATSAPP = _PassoSpec(
    chave="whatsapp_cadastrado",
    titulo="Cadastrar telefone WhatsApp",
    descricao=(
        "Receba digest semanal + alertas fiscais via WhatsApp. "
        "Opcional — você pode atualizar mais tarde."
    ),
    endpoint="/v1/empresas/{empresa_id}",
)

_PASSO_SPED_ANUAL = _PassoSpec(
    chave="sped_anual_habilitado",
    titulo="Habilitar geração anual SPED ECF",
    descricao=(
        "Empresas no Lucro Presumido entregam ECF até último dia útil de julho. "
        "Worker proativo gera 30 dias antes — confirme aceitação."
    ),
    endpoint="/v1/empresas/{empresa_id}/sped/ecf",
)

# Lista de passos por perfil_ui — ordem importa (UI renderiza nessa sequência).
_CHECKLIST_POR_PERFIL: dict[PerfilUI, tuple[_PassoSpec, ...]] = {
    PerfilUI.MEI: (
        _PASSO_PLANO,
        _PASSO_ISS_VALIDADO,
        _PASSO_WHATSAPP,
    ),
    PerfilUI.SN_SEM_FUNCIONARIOS: (
        _PASSO_PLANO,
        _PASSO_ISS_VALIDADO,
        _PASSO_PLUGGY,
        _PASSO_WHATSAPP,
    ),
    PerfilUI.SN_COM_FUNCIONARIOS: (
        _PASSO_PLANO,
        _PASSO_ISS_VALIDADO,
        _PASSO_PLUGGY,
        _PASSO_WHATSAPP,
    ),
    PerfilUI.LUCRO_PRESUMIDO: (
        _PASSO_PLANO,
        _PASSO_ISS_VALIDADO,
        _PASSO_PLUGGY,
        _PASSO_WHATSAPP,
        _PASSO_SPED_ANUAL,
    ),
    PerfilUI.LUCRO_REAL: (
        _PASSO_PLANO,
        _PASSO_ISS_VALIDADO,
        _PASSO_PLUGGY,
        _PASSO_WHATSAPP,
        _PASSO_SPED_ANUAL,
    ),
}


class OnboardingBundleService:
    """Service do bundle. Stateless — recebe DB session por chamada."""

    def __init__(self, contabil_service: ContabilService | None = None) -> None:
        # DI explícita facilita testes — pode injetar fake ContabilService.
        self._contabil = contabil_service or ContabilService()

    async def executar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        *,
        valid_from: date,
        welcome_digest_optin: bool,
    ) -> OnboardingBundleOut:
        """Pipeline completo: guard → clone → checklist.

        Args:
            session: sessão com ``SET LOCAL app.tenant_id`` ativo (RLS §8.1).
            tenant_id: vindo do JWT — propagado para o ContabilService.
            empresa_id: alvo do bootstrap.
            valid_from: data ISO de início de vigência do plano clonado.
            welcome_digest_optin: flag que o worker do digest semanal vai
                respeitar quando construir a fila de envios da próxima 2ª.

        Raises:
            EmpresaNaoEncontrada: empresa não existe ou está em outro tenant.
            OnboardingConflitoComImportacao: existe ``lote_importacao``
                concluído para essa empresa — plano deve vir do SPED.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        await self._guard_sem_importacao_concluida(session, empresa_id)

        resultado_plano = await self._contabil.clonar_plano_referencial(
            session, tenant_id, empresa_id, valid_from,
        )

        perfil = _perfil_seguro(empresa.perfil_ui)
        proximos = self._construir_checklist(empresa, perfil, plano_clonado=True)

        log.info(
            "empresa.onboarding.bundle.executado",
            empresa_id=str(empresa_id),
            perfil_ui=empresa.perfil_ui,
            perfil_efetivo=perfil.value,
            contas_criadas=resultado_plano.contas_criadas,
            contas_existentes=resultado_plano.contas_existentes,
            welcome_digest_optin=welcome_digest_optin,
            passos_pendentes=sum(1 for p in proximos if not p.concluido),
        )

        return OnboardingBundleOut(
            empresa_id=empresa_id,
            perfil_ui=perfil,
            plano_contas_criadas=resultado_plano.contas_criadas,
            plano_contas_existentes=resultado_plano.contas_existentes,
            welcome_digest_optin=welcome_digest_optin,
            proximos_passos=proximos,
        )

    async def _guard_sem_importacao_concluida(
        self, session: AsyncSession, empresa_id: UUID,
    ) -> None:
        """Levanta se houver ``lote_importacao`` concluído para a empresa.

        Plano do SPED é fonte de verdade quando existe — bootstrap aqui
        clobbering os códigos contábeis seria corrupção de dados.
        """
        stmt = (
            select(func.count())
            .select_from(LoteImportacao)
            .where(
                LoteImportacao.empresa_id == empresa_id,
                LoteImportacao.status == "concluido",
            )
        )
        total = int((await session.execute(stmt)).scalar_one() or 0)
        if total > 0:
            raise OnboardingConflitoComImportacao(
                f"Empresa {empresa_id} já recebeu {total} importação(ões) SPED "
                "concluídas. O plano de contas dela deve vir do SPED original — "
                "bootstrap automático foi bloqueado para evitar conflito de "
                "códigos. Revise via GET /v1/empresas/{eid}/migracao/lotes."
            )

    def _construir_checklist(
        self,
        empresa: Empresa,
        perfil: PerfilUI,
        *,
        plano_clonado: bool,
    ) -> list[OnboardingPassoOut]:
        """Materializa checklist do perfil_ui com ``concluido`` por passo.

        Estado consultado:
          * ``plano_contas_clonado`` → param ``plano_clonado`` (acabou de rodar).
          * ``iss_validado``         → ``empresa.aliquota_iss_validada``.
          * ``pluggy_conectado``     → não há sinal direto; sempre False
            (UI mostra como pendente até PR futuro registrar status).
          * ``whatsapp_cadastrado``  → ``empresa.whatsapp_phone is not None``.
          * ``sped_anual_habilitado`` → sempre False por enquanto
            (worker proativo Sprint 16 já gera; toggle UI fica para sprint
            futura quando expusermos o flag).
        """
        especificacoes = _CHECKLIST_POR_PERFIL[perfil]
        estado: dict[str, bool] = {
            "plano_contas_clonado": plano_clonado,
            "iss_validado": bool(empresa.aliquota_iss_validada),
            "pluggy_conectado": False,
            "whatsapp_cadastrado": empresa.whatsapp_phone is not None,
            "sped_anual_habilitado": False,
        }
        return [
            OnboardingPassoOut(
                chave=spec.chave,
                titulo=spec.titulo,
                descricao=spec.descricao,
                endpoint=(
                    spec.endpoint.replace("{empresa_id}", str(empresa.id))
                    if spec.endpoint
                    else None
                ),
                concluido=estado.get(spec.chave, False),
            )
            for spec in especificacoes
        ]
