# Validação real — Etapa 1

`reconciliation.json` compara o snapshot PostgreSQL com `reports/stage0/rj-2025.csv`, usando os mesmos SHA-256 das fontes primárias e o método analítico stage0-v2. Foram conferidas **2.352 chaves mensais**, com diferença numérica máxima **zero** nos campos comparados.

Contagens canônicas do snapshot:

| Tabela | Linhas |
| --- | ---: |
| distributor | 6 |
| electrical_set | 196 |
| municipality | 100 |
| set_municipality_link | 489 |
| continuity_indicator | 9.408 |
| interruption_aggregate | 2.352 |

Os 100 municípios incluem UFs vizinhas vinculadas a conjuntos associados ao RJ; não são 100 municípios fluminenses. As tabelas representam o escopo com dados mensais disponíveis, não todo o cadastro nacional IndQual.

`idempotence.json` registra fingerprints das tabelas antes/depois do replay, status `reused` e identidade idêntica após preparar novamente o pipeline completo. Auditorias de tentativa podem aumentar, mas os fatos e dimensões do snapshot permanecem iguais.

Testes de fixture e PostgreSQL real cobrem também correção retroativa, concorrência, COPY interrompido, rollback, ambos os lados da relação agente/conjunto, cobertura apenas NumCon, manifesto de refresh interrompido e regras anuais com denominadores. Os anuais são derivados ponderados, separados dos valores mensais diretamente publicados; não há referência anual na Etapa 0 para validar equivalência regulatória integral.

Reprodução, comandos e limites: [docs/stage1.md](../../docs/stage1.md).
