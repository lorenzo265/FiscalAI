"""Service do módulo pessoal (Sprint 10 PR1).

Cobre:
  * Cadastro de funcionário CLT (validação de unicidade de CPF na empresa).
  * Fechamento de folha mensal:
      1. lista funcionários ativos da empresa na competência;
      2. busca tabelas tributárias vigentes (INSS/IRRF/FGTS);
      3. calcula um holerite por funcionário (algoritmos puros);
      4. persiste cabeçalho ``folha_mensal`` (status='fechada') + linhas
         ``holerite`` em transação única;
      5. é idempotente — se já existe folha para (empresa, competência),
         retorna 409 ``FolhaJaFechada``.

§8.1 RLS multi-tenant via ``get_session`` (SET LOCAL no Postgres).
§8.2 Folha fechada é fato imutável — não permite reaberta nem alteração.
§8.3 Snapshot das alíquotas vigentes vai pro holerite (SCD-friendly).
§8.4 Algoritmos puros golden-tested (cobertura em tests/unit/pessoal/).
§8.10 Log estruturado por fechamento.
"""

from __future__ import annotations

from datetime import date
from datetime import datetime as _dt
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.pessoal.calcula_holerite import calcular_holerite
from app.modules.pessoal.repo import (
    FolhaRepo,
    FuncionarioRepo,
    HoleriteRepo,
    TabelasTributariasRepo,
)
from app.modules.pessoal.schemas import (
    FecharFolhaOut,
    FuncionarioIn,
    StatusFolha,
)
from app.shared.db.models import FolhaMensal, Funcionario, Holerite
from app.shared.exceptions import (
    CpfJaCadastrado,
    EmpresaNaoEncontrada,
    FolhaJaFechada,
    TabelaTributariaAusente,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_ZERO = Decimal("0.00")


class PessoalService:
    # ── Funcionário ─────────────────────────────────────────────────────────

    async def cadastrar_funcionario(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: FuncionarioIn,
    ) -> Funcionario:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = FuncionarioRepo(session)
        if await repo.cpf_existe(empresa_id, payload.cpf):
            raise CpfJaCadastrado(
                f"CPF {payload.cpf} já cadastrado para a empresa"
            )

        funcionario = Funcionario(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            nome=payload.nome,
            cpf=payload.cpf,
            cargo=payload.cargo,
            vinculo=payload.vinculo.value,
            data_admissao=payload.data_admissao,
            salario_base=payload.salario_base,
            dependentes_irrf=payload.dependentes_irrf,
        )
        try:
            await repo.criar(funcionario)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise CpfJaCadastrado(
                f"CPF {payload.cpf} já cadastrado para a empresa"
            ) from exc

        log.info(
            "pessoal.funcionario.criado",
            funcionario_id=str(funcionario.id),
            empresa_id=str(empresa_id),
            salario=str(funcionario.salario_base),
            dependentes=funcionario.dependentes_irrf,
        )
        return funcionario

    # ── Folha mensal ────────────────────────────────────────────────────────

    async def fechar_folha_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        competencia: date,
    ) -> FecharFolhaOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        comp_dia1 = date(competencia.year, competencia.month, 1)

        folha_repo = FolhaRepo(session)
        existente = await folha_repo.por_competencia(empresa_id, comp_dia1)
        if existente is not None:
            raise FolhaJaFechada(
                f"Folha de {comp_dia1.isoformat()} já existe (status={existente.status})"
            )

        # Carrega tabelas tributárias vigentes (§8.3).
        tabelas = TabelasTributariasRepo(session)
        faixas_inss = await tabelas.inss_faixas_vigentes(comp_dia1, tipo="empregado")
        if len(faixas_inss) != 4:
            raise TabelaTributariaAusente(
                f"Tabela INSS empregado incompleta em {comp_dia1.isoformat()} "
                f"({len(faixas_inss)} faixas; esperadas 4)"
            )
        faixas_irrf = await tabelas.irrf_faixas_vigentes(comp_dia1)
        if len(faixas_irrf) != 5:
            raise TabelaTributariaAusente(
                f"Tabela IRRF incompleta em {comp_dia1.isoformat()} "
                f"({len(faixas_irrf)} faixas; esperadas 5)"
            )
        aliq_fgts_clt = await tabelas.fgts_aliquota_vigente(comp_dia1, vinculo="clt")
        if aliq_fgts_clt is None:
            raise TabelaTributariaAusente(
                f"Alíquota FGTS CLT ausente em {comp_dia1.isoformat()}"
            )

        # Cabeçalho (status='aberta' até calcular; depois fechada no commit).
        folha = FolhaMensal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=comp_dia1,
            status=StatusFolha.ABERTA.value,
        )
        await folha_repo.criar(folha)

        funcionarios = await FuncionarioRepo(session).listar_ativos_para_folha(
            empresa_id, comp_dia1
        )

        holerites: list[Holerite] = []
        total_proventos = _ZERO
        total_inss = _ZERO
        total_irrf = _ZERO
        total_fgts = _ZERO

        for func in funcionarios:
            resultado = calcular_holerite(
                salario_base=func.salario_base,
                dependentes_irrf=func.dependentes_irrf,
                faixas_inss=faixas_inss,
                faixas_irrf=faixas_irrf,
                aliquota_fgts=aliq_fgts_clt,
                vinculo=func.vinculo,
            )
            holerites.append(
                Holerite(
                    tenant_id=tenant_id,
                    folha_mensal_id=folha.id,
                    funcionario_id=func.id,
                    competencia=comp_dia1,
                    salario_base=resultado.salario_base,
                    salario_bruto=resultado.salario_bruto,
                    inss_empregado=resultado.inss.inss,
                    inss_aliquota_efetiva=resultado.inss.aliquota_efetiva,
                    dependentes_irrf=resultado.irrf.dependentes,
                    deducao_dependentes_irrf=resultado.irrf.deducao_dependentes,
                    base_irrf=resultado.irrf.base_irrf,
                    irrf=resultado.irrf.irrf,
                    irrf_faixa=resultado.irrf.faixa,
                    fgts_empregador=resultado.fgts.fgts,
                    fgts_aliquota=resultado.fgts.aliquota,
                    valor_liquido=resultado.valor_liquido,
                    algoritmo_versao=resultado.algoritmo_versao,
                )
            )
            total_proventos += resultado.salario_bruto
            total_inss += resultado.inss.inss
            total_irrf += resultado.irrf.irrf
            total_fgts += resultado.fgts.fgts

        if holerites:
            await HoleriteRepo(session).criar_em_massa(holerites)

        total_descontos = total_inss + total_irrf
        total_liquido = total_proventos - total_descontos
        fechada_em = _dt.now(tz=_TZ_BR)

        folha.status = StatusFolha.FECHADA.value
        folha.qtd_funcionarios = len(funcionarios)
        folha.total_proventos = total_proventos
        folha.total_inss_empregado = total_inss
        folha.total_irrf = total_irrf
        folha.total_fgts_empregador = total_fgts
        folha.total_descontos = total_descontos
        folha.total_liquido = total_liquido
        folha.algoritmo_versao = "holerite.clt.v1"
        folha.fechada_em = fechada_em

        await session.commit()
        await session.refresh(folha)

        log.info(
            "pessoal.folha.fechada",
            empresa_id=str(empresa_id),
            competencia=comp_dia1.isoformat(),
            qtd=len(funcionarios),
            total_proventos=str(total_proventos),
            total_inss=str(total_inss),
            total_irrf=str(total_irrf),
            total_fgts=str(total_fgts),
            total_liquido=str(total_liquido),
        )

        return FecharFolhaOut(
            folha_id=folha.id,
            competencia=comp_dia1,
            status=StatusFolha.FECHADA,
            qtd_funcionarios=len(funcionarios),
            total_proventos=total_proventos,
            total_inss_empregado=total_inss,
            total_irrf=total_irrf,
            total_fgts_empregador=total_fgts,
            total_descontos=total_descontos,
            total_liquido=total_liquido,
            algoritmo_versao=folha.algoritmo_versao,
            fechada_em=fechada_em,
        )
