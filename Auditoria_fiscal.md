  ---
  Resultado da Auditoria

  4 CRITICAL · 3 MAJOR · 3 MINOR

  ---
  ❌ CRITICAL 1 — cnpj_emitente="" no NotasRepo.criar_nfse()

  Arquivo: app/modules/notas/repo.py:27

  doc = DocumentoFiscal(
      ...
      cnpj_emitente="",   # ← BUG: campo obrigatório vazio
      valor_total=valor_total,

  O CNPJ do emitente é obrigatório no registro fiscal e no XML da NFS-e. O método criar_nfse()
  recebe empresa_id mas não recupera empresa.cnpj para preencher o campo.

  Consequência: Todo documento emitido via Sprint 5 terá cnpj_emitente em branco no banco.
  Auditoria fiscal detectaria isso trivialmente — a nota existe mas não tem emitente
  identificado.

  Fix:

  async def criar_nfse(
      self,
      *,
      tenant_id: UUID,
      empresa_id: UUID,
      cnpj_emitente: str,   # ← adicionar parâmetro
      focus_ref: str,
      numero_rps: str,
      valor_total: Decimal,
      status: str = "processando",
  ) -> DocumentoFiscal:
      doc = DocumentoFiscal(
          ...
          cnpj_emitente=cnpj_emitente,   # ← usar empresa.cnpj

  E no service, passar cnpj_emitente=empresa.cnpj.

  ---
  ❌ CRITICAL 2 — numero_rps não-sequencial (colisão + rejeição pela prefeitura)

  Arquivo: app/modules/notas/service.py:77

  numero_rps = str(uuid.uuid4().int)[:9]

  uuid4().int é um inteiro de 128 bits. Os primeiros 9 dígitos são um número pseudo-aleatório
  sem garantia de unicidade por empresa e sem sequencialidade.

  Por que isso é crítico:

  1. Exigência legal: A maioria das prefeituras (com base na ABNT NBR 15032 e ISS-e municipal)
  exige que o número RPS seja sequencial contínuo por empresa. Números aleatórios geram rejeição
   automática no SEFAZ municipal.
  2. Colisão: Com ~10⁹ espaço amostral e probabilidade de duplicata crescente a cada nota
  emitida (birthday paradox), colisões são questão de tempo.
  3. Audit trail quebrado: A sequência RPS é o documento que permite rastrear todas as notas
  entre lotes de transmissão.

  Fix correto: Sequencial controlado por empresa no banco:

  # Em Empresa (models.py)
  proximo_numero_rps: Mapped[int] = mapped_column(
      Integer, nullable=False, server_default="1"
  )

  # No service, dentro de transação com SELECT FOR UPDATE
  async def _alocar_numero_rps(session: AsyncSession, empresa_id: UUID) -> str:
      stmt = (
          select(Empresa)
          .where(Empresa.id == empresa_id)
          .with_for_update()   # lock otimista por linha
      )
      empresa = (await session.execute(stmt)).scalar_one()
      numero = empresa.proximo_numero_rps
      empresa.proximo_numero_rps += 1
      return str(numero).zfill(9)

  Isso requer migration adicional.

  ---
  ❌ CRITICAL 3 — Alíquota ISS aceita 0% (viola LC 116/2003, art. 8-A)

  Arquivo: app/modules/notas/schemas.py:30

  aliquota_iss: Decimal = Field(
      ge=Decimal("0"),    # ← aceita 0%
      le=Decimal("5"),
      description="...Máximo 5% (LC 116/2003 §8º).",
  )

  Lei aplicável: LC 116/2003, art. 8-A, §1º (incluído pela LC 157/2016):

  ▎ "A alíquota mínima do Imposto sobre Serviços de Qualquer Natureza é de 2% (dois por cento)."

  O STF já declarou inconstitucionais diversas leis municipais que tentaram adotar ISS abaixo de
   2% (RE 592905, ADI 5098 e outros).

  Exceções legítimas para alíquota 0%:
  - Exportação de serviços para o exterior (LC 116/2003, art. 2º, I) — imunidade, não alíquota
  zero
  - Isenções municipais — mas essas devem ser explicitadas como natureza_operacao=3 (isento),
  não como alíquota 0%

  Fix:

  aliquota_iss: Decimal = Field(
      ge=Decimal("2"),    # mínimo constitucional (LC 116/2003, art. 8-A)
      le=Decimal("5"),
      description=(
          "Alíquota ISS em percentual. Mínimo 2% (LC 116/2003, art. 8-A), "
          "máximo 5% (art. 8º, II). Para exportação de serviços usar natureza_operacao=2."
      ),
  )

  ---
  ❌ CRITICAL 4 — date.today() sem timezone no payload Focus NFe

  Arquivo: app/modules/notas/service.py:40

  "data_emissao": __import__("datetime")
      .date.today()
      .isoformat(),

  date.today() retorna a data do sistema operacional sem timezone. Em servidor UTC (AWS, GCP,
  Docker padrão):
  - Às 21h00 de Brasília = 00h00 UTC do dia seguinte
  - A data_emissao registrada seria "amanhã" para qualquer NFS-e emitida após 21h em SP

  Consequência: A NFS-e aparece no SEFAZ com data de emissão futura, gerando rejeição ou
  inconsistência no livro fiscal.

  Fix:

  from datetime import datetime
  from zoneinfo import ZoneInfo

  TZ_BR = ZoneInfo("America/Sao_Paulo")

  "data_emissao": datetime.now(TZ_BR).date().isoformat(),

  E remover todos os __import__() inline — violam convenções do projeto (logs, imports no topo).

  ---
  ⚠️  MAJOR 1 — ISS não validado contra alíquota do município

  Arquivo: app/modules/notas/service.py e schemas.py

  O schema aceita qualquer alíquota entre 2% e 5% sem verificar se bate com a alíquota real do
  município da empresa. O Focus NFe vai rejeitar a NFS-e se a alíquota enviada divergir da
  tabela da prefeitura (a maioria dos municípios integrados tem alíquota fixa por código de
  serviço LC 116).

  Risco:
  - Alíquota enviada 2%, prefeitura cobra 3% → SEFAZ rejeita → cliente não emite nota → multa
  por não emissão
  - Ou pior: prefeitura aceita, cliente cobra errado do tomador → passivo tributário

  Fix mínimo para o MVP: Adicionar aviso no response:

  # No EmitirNfseOut
  aviso_iss: str | None = Field(
      default=(
          "Confirme a alíquota ISS com a legislação do seu município "
          "antes de emitir. Alíquotas incorretas geram rejeição da nota."
      )
  )

  Fix correto (Sprint 6+): Tabela aliquota_iss_municipal com municipio_ibge + servico_lc116 +
  aliquota + valid_from/valid_to — SCD Type 2 como as demais tabelas tributárias.

  ---
  ⚠️  MAJOR 2 — _CNAES_VEDADOS_SN incompleta (risco de classificação errada de regime)

  Arquivo: app/modules/empresa/onboarding.py:53

  A lista inclui instituições financeiras mas falta grande parte dos CNAEs vedados ao Simples
  Nacional pelo art. 17 da LC 123/2006. CNAEs ausentes relevantes para PMEs:

  # Profissões regulamentadas vedadas (art. 17, XI + Resolução CGSN 140/2018, art. 15)
  "6911701",  # Advocacia (vedado se sócio é advogado com CNPJ de PJ)
  "6920602",  # Contabilidade — ATENÇÃO: na lista de _CNAES_ANEXO_III mas NÃO é vedado ao SN
               # escritórios de contabilidade SÃO permitidos no SN
  "6612601",  # Corretores de seguros (vedado)
  "6621501",  # Seguradoras (vedado — já na lista, correto)
  "4221901",  # Importação de combustíveis (vedado)
  "4731800",  # Comércio varejista combustíveis (vedado para MEI)

  Erro adicional encontrado: 6920602 (Contabilidade) está em _CNAES_ANEXO_III na linha 94.
  Contabilidade não é vedada ao Simples Nacional — escritórios de contabilidade são permitidos e
   tipicamente enquadrados no Anexo III ou V dependendo do Fator R. Isso está correto na lista
  de vedações (ausente), mas pode confundir.

  Risco: Uma empresa vedada ao SN sendo classificada como Simples Nacional no onboarding →
  regime errado desde o início → multa por recolhimento incorreto.

  ---
  ⚠️  MAJOR 3 — cpf_tomador sem validação de dígitos verificadores

  Arquivo: app/modules/notas/schemas.py:45

  cpf_tomador: str | None = Field(
      default=None,
      min_length=11,
      max_length=11,
      pattern=r"^\d{11}$",   # ← só valida formato, não algoritmo
  )

  CPF com 11 dígitos mas inválido (ex: 11111111111) passa na validação e vai no XML da NFS-e. O
  SEFAZ municipal pode aceitar ou rejeitar dependendo do município.

  Fix: Adicionar field_validator com o algoritmo CPF (dois dígitos verificadores, pesos 10-2 e
  11-2).

  ---
  ℹ️  MINOR 1 — __import__() inline em 3 arquivos (anti-padrão do projeto)

  Arquivos: app/modules/notas/repo.py, app/modules/notas/service.py,
  app/modules/whatsapp/router.py

  # repo.py linha 18
  emitida_em=__import__("datetime").datetime.now(
      __import__("zoneinfo").ZoneInfo("America/Sao_Paulo")
  ),

  Viola convenção do projeto (from __future__ import annotations + imports no topo). Além disso,
   __import__ inline é avaliado a cada chamada, é menos legível e mais difícil de mockar em
  testes.

  ---
  ℹ️  MINOR 2 — Limite MEI não cobre MEI Transportador Autônomo

  Arquivo: app/modules/empresa/onboarding.py:26

  _LIMITE_MEI = Decimal("81000.00")

  Desde a Lei Complementar 188/2021, o MEI Transportador Autônomo tem limite de R$251.600/ano.
  Uma empresa com porte=MEI e faturamento entre R$81k e R$251k poderia ser MEI Transportador
  (CNAE 4930201 ou similar) mas seria classificada incorretamente.

  Impacto baixo no MVP (poucos casos), mas deve entrar como TODO no backlog.

  ---
  ℹ️  MINOR 3 — natureza_operacao=3 (isento) sem restrições adicionais

  Arquivo: app/modules/notas/schemas.py:19

  natureza_operacao: int = Field(ge=1, le=6, ...)

  Aceitar natureza_operacao=4 (imune) ou natureza_operacao=5/6 (exigibilidade suspensa por
  decisão judicial/administrativa) sem exigir documentação de embasamento (número do processo,
  etc.) cria risco de uso indevido.

  Para o MVP, considerar restringir a {1, 2} até que o módulo de compliance esteja implementado:

  natureza_operacao: Literal[1, 2] = Field(
      description="1=Tributação no município, 2=Tributação fora do município. "
      "Casos de isenção/imunidade requerem módulo de compliance (Sprint 6+).",
  )

  ---
  Resumo Executivo

  #: 1
  Severidade: ❌ CRITICAL
  Arquivo: notas/repo.py
  Problema: cnpj_emitente="" — registro sem emitente
  Fix urgente?: Sim, antes de qualquer demo
  ────────────────────────────────────────
  #: 2
  Severidade: ❌ CRITICAL
  Arquivo: notas/service.py
  Problema: RPS não-sequencial — rejeição pela prefeitura
  Fix urgente?: Sim, sequencial por empresa
  ────────────────────────────────────────
  #: 3
  Severidade: ❌ CRITICAL
  Arquivo: notas/schemas.py
  Problema: ISS aceita 0% (mínimo legal é 2%)
  Fix urgente?: Sim, ge=Decimal("2")
  ────────────────────────────────────────
  #: 4
  Severidade: ❌ CRITICAL
  Arquivo: notas/service.py
  Problema: date.today() sem TZ — data errada após 21h
  Fix urgente?: Sim, datetime.now(TZ_BR).date()
  ────────────────────────────────────────
  #: 5
  Severidade: ⚠️  MAJOR
  Arquivo: notas/service.py
  Problema: ISS não validado contra município
  Fix urgente?: MVP: aviso no response
  ────────────────────────────────────────
  #: 6
  Severidade: ⚠️  MAJOR
  Arquivo: empresa/onboarding.py
  Problema: CNAEs vedados incompletos
  Fix urgente?: Expandir lista
  ────────────────────────────────────────
  #: 7
  Severidade: ⚠️  MAJOR
  Arquivo: notas/schemas.py
  Problema: CPF tomador sem validação de dígitos
  Fix urgente?: Adicionar field_validator
  ────────────────────────────────────────
  #: 8
  Severidade: ℹ️  MINOR
  Arquivo: 3 arquivos
  Problema: __import__ inline — anti-padrão
  Fix urgente?: Refatorar imports
  ────────────────────────────────────────
  #: 9
  Severidade: ℹ️  MINOR
  Arquivo: empresa/onboarding.py
  Problema: MEI Transportador (R$251k) não coberto
  Fix urgente?: Backlog
  ────────────────────────────────────────
  #: 10
  Severidade: ℹ️  MINOR
  Arquivo: notas/schemas.py
  Problema: natureza_operacao 3-6 sem restrição
  Fix urgente?: Restringir para MVP
