"""Assinatura XMLDSig com certificado A1 (.p12/.pfx ICP-Brasil).

Sprint 19.7 PR2 (#13) — pendência consciente que destravou a transmissão
real de eventos eSocial. Pattern: **Protocol + dois adapters**
(``NotImplementedXmldsigSigner`` em dev/CI por default, ``SignXmlSigner``
quando o grupo opt-in ``esocial`` (lxml + signxml + cryptography) está
instalado).

Camada 1 puramente determinística:

  * ``hash_xml_canonico(xml: str) -> str`` calcula SHA-256 hex do XML
    pré-assinatura (idempotency key auxiliar — Sprint 19.7 PR2 acrescenta
    ``evento_esocial.hash_xml``).

  * ``XmldsigSigner.assinar(xml_canonico: str, id_referencia: str) ->
    bytes`` aplica `<ds:Signature>` enveloped XMLDSig (W3C Recommendation
    16 Apr 2013) com C14N exclusiva (sem comentários) + SHA-256 +
    RSA-SHA-256, embutido no XML de saída. Retorna bytes UTF-8 prontos
    pra ``EsocialClient.enviar_lote``.

§8.12 — flag ``ESOCIAL_TRANSMISSAO_ATIVA=false`` mantém o assinador como
``NotImplementedXmldsigSigner`` mesmo se o grupo estiver instalado;
assinatura é ato consciente do operador.

§8.9 — ``hash_xml_canonico`` torna idempotência forte: regenerar o mesmo
payload + mesma versão de algoritmo emite o mesmo hash → service
detecta duplicata mesmo se ``referencia_id`` mudou.
"""

from __future__ import annotations

import hashlib
from typing import Final, Protocol

ALGORITMO_VERSAO: Final = "xmldsig.v1"


class XmldsigSigningError(RuntimeError):
    """Erro ao aplicar XMLDSig (cert inválido, senha errada, lib ausente)."""


def hash_xml_canonico(xml: str) -> str:
    """SHA-256 hex do XML canônico (pré-assinatura).

    Função pura. Usado pra:
      * Idempotência forte — mesmo hash = mesmo conteúdo conceitual.
      * Persistência em ``evento_esocial.hash_xml`` (Sprint 19.7 PR2
        migration 0051).
    """
    return hashlib.sha256(xml.encode("utf-8")).hexdigest()


class XmldsigSigner(Protocol):
    """Contrato do assinador XMLDSig.

    Implementações:
      * ``NotImplementedXmldsigSigner`` — fallback (default em dev/CI).
      * ``SignXmlSigner`` — real, requer grupo ``esocial`` instalado
        (lxml + signxml + cryptography).
    """

    def assinar(self, xml_canonico: str, *, id_referencia: str) -> bytes:
        """Aplica `<ds:Signature>` enveloped no XML e retorna bytes UTF-8.

        Args:
            xml_canonico: XML serializado por ``esocial_xml.serializar_para_xml``.
            id_referencia: valor do atributo ``Id`` do elemento eSocial
                evento (usado no ``<ds:Reference URI="#...">``).

        Raises:
            XmldsigSigningError: cert inválido, senha errada, biblioteca
                ausente.
        """
        ...


class NotImplementedXmldsigSigner:
    """Sentinela: grupo ``esocial`` não instalado ou flag opt-out.

    Levanta ``XmldsigSigningError`` se alguém tentar assinar. Service
    fail-soft já trata isso — mantém evento em ``status='preparado'`` e
    loga warning estruturado.
    """

    def __init__(self, motivo: str) -> None:
        self.motivo = motivo

    def assinar(self, xml_canonico: str, *, id_referencia: str) -> bytes:
        raise XmldsigSigningError(
            f"Assinador XMLDSig não disponível: {self.motivo}. "
            "Instale o grupo opt-in: `poetry install --with esocial`."
        )


class SignXmlSigner:
    """Adapter sobre `signxml` — assinatura XMLDSig W3C.

    Requer grupo opt-in ``esocial`` (instala lxml + signxml + cryptography).
    Imports são lazy — ``__init__`` só dispara se efetivamente
    instanciado, mantendo `import app.shared.crypto` barato em dev/CI.

    Constraints do eSocial (Manual de Orientação do Desenvolvedor v S-1.3):
      * Canonicalização exclusiva sem comentários
        (`http://www.w3.org/2001/10/xml-exc-c14n#`).
      * Digest SHA-256, assinatura RSA-SHA-256.
      * `<ds:Reference URI="#ID...">` aponta para o ``Id`` do `<evt*>`.
      * `<ds:Transforms>` contém **enveloped-signature** + **C14N exclusiva**.
      * `<ds:KeyInfo>` carrega ``<X509Data><X509Certificate>``.
    """

    def __init__(self, *, cert_p12_bytes: bytes, senha: str) -> None:
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
        except ImportError as exc:  # pragma: no cover - depende do grupo opt-in
            raise XmldsigSigningError(
                "Grupo 'esocial' não instalado (cryptography ausente). "
                "Rode: poetry install --with esocial"
            ) from exc

        try:
            chave, cert, ca_certs = pkcs12.load_key_and_certificates(
                cert_p12_bytes, senha.encode("utf-8")
            )
        except Exception as exc:
            raise XmldsigSigningError(
                f"Falha ao carregar certificado A1 (.p12): {type(exc).__name__}"
            ) from exc

        if chave is None or cert is None:
            raise XmldsigSigningError(
                "Certificado A1 sem chave privada ou cert principal (vazio?)"
            )

        self._chave = chave
        self._cert = cert
        self._ca_certs = ca_certs or []

    def assinar(self, xml_canonico: str, *, id_referencia: str) -> bytes:
        try:
            from lxml import etree
            from signxml import DigestAlgorithm, SignatureMethod, XMLSigner
        except ImportError as exc:  # pragma: no cover - depende do grupo opt-in
            raise XmldsigSigningError(
                "Grupo 'esocial' não instalado (lxml/signxml ausentes). "
                "Rode: poetry install --with esocial"
            ) from exc

        try:
            doc = etree.fromstring(xml_canonico.encode("utf-8"))
        except Exception as exc:
            raise XmldsigSigningError(
                f"XML inválido pra assinar: {type(exc).__name__}"
            ) from exc

        signer = XMLSigner(
            method="enveloped",
            signature_algorithm=SignatureMethod.RSA_SHA256,
            digest_algorithm=DigestAlgorithm.SHA256,
            c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
        )
        # signxml requer 'Id' attribute pra <ds:Reference URI="#...">.
        try:
            assinado = signer.sign(
                doc,
                key=self._chave,
                cert=self._cert,
                reference_uri=f"#{id_referencia}",
            )
        except Exception as exc:
            raise XmldsigSigningError(
                f"Falha XMLDSig (signxml): {type(exc).__name__}: {exc}"
            ) from exc

        return etree.tostring(assinado, encoding="utf-8", xml_declaration=False)  # type: ignore[no-any-return]


def construir_assinador(
    *,
    cert_p12_bytes: bytes | None,
    senha: str | None,
    transmissao_ativa: bool,
) -> XmldsigSigner:
    """Factory que escolhe entre SignXmlSigner real e fallback not-implemented.

    Returns:
        ``SignXmlSigner`` quando ``transmissao_ativa=True`` e cert+senha
        passados; ``NotImplementedXmldsigSigner`` caso contrário.

    §8.12 — opt-in explícito; mesmo com cert disponível, sem a flag o
    sistema mantém o evento em ``status='preparado'``.
    """
    if not transmissao_ativa:
        return NotImplementedXmldsigSigner(
            motivo="ESOCIAL_TRANSMISSAO_ATIVA=false (§8.12)"
        )
    if cert_p12_bytes is None or senha is None:
        return NotImplementedXmldsigSigner(
            motivo="certificado A1 ou senha ausentes pra esta empresa"
        )
    return SignXmlSigner(cert_p12_bytes=cert_p12_bytes, senha=senha)
