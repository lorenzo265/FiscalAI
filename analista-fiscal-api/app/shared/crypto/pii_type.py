"""``TypeDecorator`` que cifra/decifra PII transparente em repouso (Marco 3).

O ORM le e escreve texto puro; o banco guarda APENAS o ciphertext do envelope
AES-256-GCM. A chave vem de ``settings.PII_ENCRYPTION_KEY`` (KMS em prod).

Aplicado a colunas SEM constraint de unicidade nem lookup por valor (o GCM e
nao-deterministico: o mesmo texto vira ciphertext diferente a cada escrita).
Coluna de prova do Marco 3: ``empresa.whatsapp_phone``.
"""
from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.config import get_settings
from app.shared.crypto.envelope import carregar_chave, cifrar, decifrar


class PiiCifrada(TypeDecorator[str]):
    """Cifra strings de PII em repouso (AES-256-GCM), transparente ao ORM."""

    impl = Text
    cache_ok = True

    def process_bind_param(
        self, value: str | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        chave = carregar_chave(get_settings().PII_ENCRYPTION_KEY)
        return cifrar(value, chave)

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        chave = carregar_chave(get_settings().PII_ENCRYPTION_KEY)
        return decifrar(value, chave)
