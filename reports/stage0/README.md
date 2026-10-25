# Prova de dados ANEEL — conjuntos associados ao RJ

Período dos eventos e indicadores: **2025**, mensal. Nível: **conjunto elétrico + agente**, selecionado por associação com RJ no snapshot IndQual de 09/09/2026. Não é uma estimativa municipal nem uma reconstrução completa da cobertura histórica do estado.

Fonte: ANEEL, recursos oficiais identificados por URL, período de referência da análise, coleta e SHA-256 em [manifest.json](manifest.json). Atribuição e licença ODbL dos dados são preservadas; a MIT do código não altera seus termos.

- [Tabela completa](rj-2025.csv): 2.352 linhas, incluindo 114 com indicador oficial e sem eventos observados; ausência não é zero.
- [Cenário bruto](rj-2025-raw.csv) e [sensibilidade à deduplicação](rj-dedup-sensitivity.csv): mesmo recorte e filtros, com/sem remoção de repetições integrais. Ambos têm 800.098 registros; as diferenças de ponto flutuante são inferiores a `2e-14`, sem alteração de contagens.
- [Inventário multi-UF](rj-multi-uf.csv): 20 conjuntos associados ao RJ e outra UF, dos quais 6 têm registros no arquivo de 2025 (48.780 linhas, cerca de 6,1% do recorte). As tabelas mensais sinalizam a ambiguidade com `is_multi_uf` e `linked_ufs`.
- [Amostra](rj-sample.csv): 24 linhas com eventos e indicadores, agregadas e sem dados de unidades consumidoras individuais.
- [Qualidade](quality.json): 9.715.372 registros físicos nacionais, 18.146 duplicatas integrais, períodos, nulos, anomalias e cardinalidades.
- [Proveniência, unidades e hash do SQL](analysis.json).
- [Verificação da reprodução offline](verification.json).
- [Método, hipóteses e comparação observada](../../docs/methodology.md).
- [Comandos de reprodução](../../docs/stage0.md).

As colunas `*_official_*` representam valores oficiais. As colunas `*_candidate_*` são contribuições exploratórias, com hipóteses e divergências documentadas, e não devem ser rotuladas como DEC/FEC regulatórios calculados pelo Illuminate.

A deduplicação não foi demonstrada como correção de erros de exportação; é um cenário publicado ao lado do bruto. Conjuntos multi-UF são preservados e sinalizados, sem atribuição exclusiva ao RJ nem pesos de rateio. Versão metodológica: `stage0-v2`.
