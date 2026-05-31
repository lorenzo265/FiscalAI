"""Golden tests do algoritmo puro ``gera_digest_estruturado`` (Sprint 15 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.advisor.gera_digest_semanal import (
    ALGORITMO_VERSAO,
    AnomaliaResumo,
    ApuracaoResumo,
    SugestaoResumo,
    VencimentoResumo,
    gerar_digest_estruturado,
)


def _ap(uid: str, tipo: str, comp: date, valor: str) -> ApuracaoResumo:
    return ApuracaoResumo(
        apuracao_id=uid, tipo=tipo, competencia=comp, valor=Decimal(valor)
    )


def _an(
    uid: str, sev: str, comp: date = date(2026, 4, 1), tipo: str = "pis"
) -> AnomaliaResumo:
    return AnomaliaResumo(
        anomalia_id=uid,
        tipo=tipo,
        competencia=comp,
        severidade=sev,
        mensagem=f"{tipo.upper()} subiu — sev {sev}",
        valor_observado=Decimal("3000.00"),
        valor_esperado=Decimal("1000.00"),
    )


def _venc(uid: str, dia: date, titulo: str = "DAS abril/2026") -> VencimentoResumo:
    return VencimentoResumo(
        agenda_item_id=uid,
        titulo=titulo,
        data_vencimento=dia,
        tipo_obrigacao="das_sn",
    )


def _sug(codigo: str, sev: str = "alta", economia: str | None = "1000.00") -> SugestaoResumo:
    return SugestaoResumo(
        codigo=codigo,
        titulo=f"Sug {codigo}",
        descricao="desc",
        severidade=sev,
        economia_anual_estimada=Decimal(economia) if economia else None,
    )


def test_semana_iso_e_periodo_da_competencia() -> None:
    """Quarta-feira 20/maio/2026 → semana ISO 2026-W21 (segunda 18 → domingo 24)."""
    digest = gerar_digest_estruturado(
        empresa_nome="ACME LTDA",
        apuracoes_semana=[],
        anomalias_abertas=[],
        agenda_proximos=[],
        sugestoes=[],
        referencia=date(2026, 5, 20),
    )
    assert digest.semana_iso == "2026-W21"
    assert digest.periodo_inicio == date(2026, 5, 18)  # segunda
    assert digest.periodo_fim == date(2026, 5, 24)  # domingo


def test_top3_apuracoes_ordenadas_por_competencia_desc() -> None:
    apuracoes = [
        _ap("a1", "das", date(2026, 1, 1), "1000"),
        _ap("a2", "das", date(2026, 4, 1), "1100"),
        _ap("a3", "das", date(2026, 3, 1), "1050"),
        _ap("a4", "das", date(2026, 2, 1), "1025"),
    ]
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=apuracoes,
        anomalias_abertas=[],
        agenda_proximos=[],
        sugestoes=[],
        referencia=date(2026, 5, 20),
    )
    assert [a.apuracao_id for a in digest.apuracoes] == ["a2", "a3", "a4"]


def test_top3_anomalias_priorizam_alta_sobre_media() -> None:
    anomalias = [
        _an("an1", "baixa"),
        _an("an2", "alta"),
        _an("an3", "media"),
        _an("an4", "alta"),
    ]
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[],
        anomalias_abertas=anomalias,
        agenda_proximos=[],
        sugestoes=[],
        referencia=date(2026, 5, 20),
    )
    # Top-3: as 2 altas + a media; baixa fica fora.
    sevs = [a.severidade for a in digest.anomalias]
    assert sevs == ["alta", "alta", "media"]


def test_vencimentos_filtrados_pela_janela_de_14_dias() -> None:
    ref = date(2026, 5, 20)
    proximos = [
        _venc("v1", date(2026, 5, 21)),  # 1 dia → dentro
        _venc("v2", date(2026, 6, 5)),  # 16 dias → fora
        _venc("v3", date(2026, 5, 30)),  # 10 dias → dentro
        _venc("v4", date(2026, 5, 15)),  # passado → fora
    ]
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[],
        anomalias_abertas=[],
        agenda_proximos=proximos,
        sugestoes=[],
        referencia=ref,
    )
    ids = [v.agenda_item_id for v in digest.proximos_vencimentos]
    assert ids == ["v1", "v3"]  # ordem crescente, dentro de 14d


def test_sugestoes_limitadas_a_top2() -> None:
    sugs = [_sug("s1"), _sug("s2"), _sug("s3")]
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[],
        anomalias_abertas=[],
        agenda_proximos=[],
        sugestoes=sugs,
        referencia=date(2026, 5, 20),
    )
    assert len(digest.sugestoes) == 2


def test_apelido_curto_remove_sufixos_ltda_sa() -> None:
    casos: list[tuple[str, str]] = [
        ("ACME COMERCIO LTDA", "ACME"),
        ("DDS Tecnologia ME", "DDS"),
        ("PADARIA DO ZE EPP", "PADARIA"),
        ("MyStartup", "MyStartup"),
        ("AB Consultoria S.A.", "AB"),
    ]
    for nome, esperado in casos:
        digest = gerar_digest_estruturado(
            empresa_nome=nome,
            apuracoes_semana=[],
            anomalias_abertas=[],
            agenda_proximos=[],
            sugestoes=[],
            referencia=date(2026, 5, 20),
        )
        assert digest.empresa_apelido_curto == esperado, nome


def test_fontes_geradas_por_categoria() -> None:
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[_ap("a1", "das", date(2026, 4, 1), "1000.00")],
        anomalias_abertas=[_an("an1", "alta")],
        agenda_proximos=[_venc("v1", date(2026, 5, 21))],
        sugestoes=[_sug("fator_r_migrar_anexo_iii")],
        referencia=date(2026, 5, 20),
    )
    ids = [f.id for f in digest.fontes]
    assert "apuracao:a1" in ids
    assert "anomalia:an1" in ids
    assert "agenda:v1" in ids
    assert "sugestao:fator_r_migrar_anexo_iii" in ids


def test_fonte_payload_contem_valor_monetario_literal() -> None:
    """``validar_resposta`` precisa achar R$ literal — payload tem que conter."""
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[_ap("a1", "das", date(2026, 4, 1), "1234.56")],
        anomalias_abertas=[],
        agenda_proximos=[],
        sugestoes=[],
        referencia=date(2026, 5, 20),
    )
    payload = digest.fontes[0].payload
    assert "R$ 1,234.56" in payload  # formato pt-BR padrão Python
    assert "DAS" in payload


def test_algoritmo_versao_estavel() -> None:
    assert ALGORITMO_VERSAO == "advisor.digest.v1"


def test_determinismo_mesma_entrada_mesma_saida() -> None:
    args: dict[str, object] = {
        "empresa_nome": "ACME",
        "apuracoes_semana": [_ap("a", "das", date(2026, 4, 1), "100")],
        "anomalias_abertas": [_an("b", "alta")],
        "agenda_proximos": [_venc("c", date(2026, 5, 22))],
        "sugestoes": [_sug("d")],
        "referencia": date(2026, 5, 20),
    }
    a = gerar_digest_estruturado(**args)  # type: ignore[arg-type]
    b = gerar_digest_estruturado(**args)  # type: ignore[arg-type]
    assert a == b


def test_digest_vazio_quando_nenhuma_entrada() -> None:
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[],
        anomalias_abertas=[],
        agenda_proximos=[],
        sugestoes=[],
        referencia=date(2026, 5, 20),
    )
    assert digest.apuracoes == []
    assert digest.anomalias == []
    assert digest.proximos_vencimentos == []
    assert digest.sugestoes == []
    assert digest.fontes == []
