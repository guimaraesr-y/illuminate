# Prova de dados ANEEL — conjuntos associados ao RJ

Período dos eventos e indicadores: **2025**, mensal. Nível: **conjunto elétrico + agente**, selecionado por associação com RJ no snapshot IndQual de 09/09/2026. Não é uma estimativa municipal nem uma reconstrução completa da cobertura histórica do estado.

Fonte: ANEEL, recursos oficiais identificados por URL, período de referência da análise, coleta e SHA-256 em [manifest.json](manifest.json). Atribuição e licença ODbL dos dados são preservadas; a MIT do código não altera seus termos.

- [Tabela completa](rj-2025.csv): 2.352 linhas, incluindo 114 com indicador oficial e sem eventos observados; ausência não é zero.
- [Amostra](rj-sample.csv): 24 linhas com eventos e indicadores, agregadas e sem dados de unidades consumidoras individuais.
- [Qualidade](quality.json): 9.715.372 registros físicos nacionais, 18.146 duplicatas integrais, períodos, nulos, anomalias e cardinalidades.
- [Proveniência, unidades e hash do SQL](analysis.json).
- [Verificação da reprodução offline](verification.json).
- [Método, hipóteses e comparação observada](../../docs/methodology.md).
- [Comandos de reprodução](../../docs/stage0.md).

As colunas `*_official_*` representam valores oficiais. As colunas `*_candidate_*` são contribuições exploratórias, com hipóteses e divergências documentadas, e não devem ser rotuladas como DEC/FEC regulatórios calculados pelo Illuminate.
