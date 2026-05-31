"""Cliente DOU (Diário Oficial da União) — Sprint 19.5 PR3.

Apenas leitura. O DOU expõe uma API JSON semi-pública (sem SLA) em
``https://www.in.gov.br/consulta?q=...`` que permite buscar matérias por
termos. Quando a API muda (já mudou antes), o worker cai em fallback
graceful sem quebrar — pendência ``[externo]`` registrada na sprint.
"""

from __future__ import annotations
