"""Monitor cadastral RFB + Sintegra (Sprint 11 PR3).

Persiste snapshots da situação cadastral CNPJ (RFB) e da inscrição estadual
(Sintegra) por UF. Append-only — cada sync gera nova linha, preservando o
histórico de mudanças (suspensão, baixa, retomada).
"""
