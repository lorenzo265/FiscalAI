"""ECF — Escrituração Contábil Fiscal (Sprint 16 PR2).

Arquivo ``.txt`` pipe-delimited entregue anualmente à RFB via PVA até o
último dia útil de julho do ano seguinte ao da escrituração. Cobertura
do MVP: empresas **Lucro Presumido** (perfil-alvo da Fase 3).

Blocos completamente cobertos:

* **Bloco 0** — abertura + identificação tributária.
* **Bloco J** — plano de contas + mapeamento referencial RFB.
* **Bloco K** — saldos contábeis dos períodos de apuração trimestrais.
* **Bloco P** — apuração Lucro Presumido (registros principais P010/P030/
  P100/P200/P300/P400).
* **Bloco Y** — informações gerais da PJ (receita por atividade).
* **Bloco 9** — totalizadores.

Blocos emitidos apenas com abertura/encerramento (`IND_DAD='1'` — sem
dados — quando vazios):

* C (vinculação a ECD) — populado se a ECD do ano existe; senão IND_DAD=1.
* E (incentivos fiscais), L/M/N (Lucro Real), Q (Lucro Arbitrado),
  T (imune/isenta), U (PJ exterior), V (incentivos AC), W (intervenção
  Estatal), X (encerramento).

Fundamento normativo:

* IN RFB 2.004/2021 (consolida a ECF).
* Manual ECF v10 (ADE Cofis 51/2024).
* Lei 9.249/1995 (presunção e adicional IRPJ).
* Lei 7.689/1988 (CSLL).
* LC 123/2006 art. 18-A §13 (MEI dispensa).

**Out-of-scope (Fase 5)**:

* Lucro Real (blocos M, N, L completos).
* Imunes / isentas (bloco T detalhado).
* PJ com atividade no exterior (bloco U detalhado).
* Lucro Arbitrado (bloco Q detalhado).
"""
