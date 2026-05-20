from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.shared.types import JsonObject


@dataclass
class EvalCase:
    """Caso de avaliação carregado de um arquivo JSONL."""

    id: str
    dados: JsonObject


@dataclass
class EvalMetrics:
    """Resultado agregado de uma rodada de avaliação."""

    total: int = 0
    corretos: int = 0
    incorretos: int = 0
    erros: int = 0
    detalhes: list[JsonObject] = field(default_factory=list)

    @property
    def acuracia(self) -> float:
        if self.total == 0:
            return 0.0
        return self.corretos / self.total

    def adicionar(self, caso_id: str, correto: bool, detalhe: str = "") -> None:
        self.total += 1
        if correto:
            self.corretos += 1
        else:
            self.incorretos += 1
        self.detalhes.append({"id": caso_id, "correto": correto, "detalhe": detalhe})

    def adicionar_erro(self, caso_id: str, erro: str) -> None:
        self.total += 1
        self.erros += 1
        self.detalhes.append({"id": caso_id, "correto": False, "erro": erro})

    def relatorio(self, nome: str, threshold: float) -> str:
        status = "✅ PASSOU" if self.acuracia >= threshold else "❌ FALHOU"
        return (
            f"{status} [{nome}] "
            f"acurácia={self.acuracia:.1%} "
            f"({self.corretos}/{self.total} corretos, {self.erros} erros) "
            f"threshold={threshold:.0%}"
        )


def carregar_casos(caminho: Path) -> list[EvalCase]:
    """Carrega casos de avaliação de um arquivo JSONL (uma linha = um JSON)."""
    casos: list[EvalCase] = []
    for i, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        try:
            dados: JsonObject = json.loads(linha)
            casos.append(EvalCase(id=dados.get("id", f"caso-{i}"), dados=dados))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido na linha {i} de {caminho}: {e}") from e
    return casos
