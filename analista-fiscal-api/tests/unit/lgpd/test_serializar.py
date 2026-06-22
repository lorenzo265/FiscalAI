"""Golden -- serializador do export LGPD (Marco 3).

Testa a logica pura de serializacao (sem DB): coercao de tipos JSON-safe e a
exclusao do denylist de PII (``senha_hash``).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.modules.lgpd.service import _coerce, _serializar
from app.shared.db.models import Usuario


def test_coerce_tipos_basicos_passam_direto() -> None:
    assert _coerce(None) is None
    assert _coerce(True) is True
    assert _coerce(42) == 42
    assert _coerce("texto") == "texto"


def test_coerce_decimal_vira_string() -> None:
    # Dinheiro nunca vira float -- preserva a precisao como string.
    assert _coerce(Decimal("10.50")) == "10.50"


def test_coerce_datas_viram_iso() -> None:
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert _coerce(dt) == dt.isoformat()
    assert _coerce(date(2026, 1, 2)) == "2026-01-02"


def test_coerce_uuid_vira_string() -> None:
    u = UUID("12345678-1234-5678-1234-567812345678")
    assert _coerce(u) == str(u)


def test_coerce_blob_binario_vira_none() -> None:
    # Blobs (XML/PDF) ficam fora do JSON.
    assert _coerce(b"\x00\x01\x02") is None


def test_coerce_jsonb_passa_direto() -> None:
    assert _coerce({"chave": 1}) == {"chave": 1}
    assert _coerce([1, 2, 3]) == [1, 2, 3]


def test_serializar_exclui_senha_hash_e_serializa_pii() -> None:
    usuario = Usuario(
        tenant_id=UUID(int=1),
        email="dono@pme.com.br",
        nome="Dono da PME",
        senha_hash="HASH_SECRETO_NUNCA_EXPORTA",
    )
    dados = _serializar(usuario)

    assert "senha_hash" not in dados
    assert dados["email"] == "dono@pme.com.br"
    assert dados["nome"] == "Dono da PME"
    assert dados["tenant_id"] == str(UUID(int=1))
