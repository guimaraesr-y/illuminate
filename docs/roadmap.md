# Roadmap de descoberta à primeira versão

## Etapa 0 — Fontes e prova de dados

- [ ] Testar CKAN `package_show` e registrar respostas reais.
- [ ] Baixar Parquet/ZIP de um ano e salvar SHA-256, tamanho e metadata.
- [ ] Documentar colunas, tipos, número de linhas, nulidade, períodos e schema drift.
- [ ] Obter as fontes DEC/FEC e IndQual Município e validar suas chaves.
- [ ] Investigar disponibilidade de indicadores oficiais em nível municipal.
- [ ] Publicar notebook/query DuckDB reproduzível com um recorte do RJ.

**Critério de saída:** uma tabela real validada, com proveniência; zero números demonstrativos publicados como reais.

## Etapa 1 — Engenharia de dados

- [ ] Python + DuckDB para importação determinística.
- [ ] Modelo canônico com fonte e versão.
- [ ] Testes contra duplicação, timestamps inválidos e denominadores.
- [ ] Postgres + agregados mensais/anuais.
- [ ] Comparar indicadores calculados com os oficiais, documentando divergências.

**Critério de saída:** reconstruir séries de conjuntos elétricos com testes automatizados.

## Etapa 2 — Produto público MVP

- [ ] Site Next.js responsivo com pesquisa por distribuidora/conjunto.
- [ ] Painel de série DEC/FEC, explicações, limites regulatórios e fonte.
- [ ] Mapa 2D apenas nas geografias cuja atribuição for validada.
- [ ] Consulta compartilhável contendo versão da metodologia e dados.
- [ ] Indicadores de cobertura e qualidade dos dados.

**Critério de saída:** responder como evoluiu a continuidade no RJ em um recorte documentado.

## Etapa 3 — Mapa 3D e expansão

- [ ] POC MapLibre extrusions com dados agregados (não pontos residenciais).
- [ ] Fallback 2D, acessibilidade e performance mobile.
- [ ] Expandir para outros estados e novos períodos.
- [ ] Examinar ocorrências emergenciais e causas, mantendo metodologias separadas.
- [ ] Abrir guias de contribuição e fixtures de conectores.

## Fora do MVP

- Alertas de faltas de luz em tempo real.
- Estimativas por CEP, residência ou bairro sem fonte adequada.
- Ranking definitivo de distribuidoras, previsão de apagão ou acusação de má gestão.
- IA para interpretar causas, sem avaliação e validação humana.

## Ideias de comunicação

- Primeiro post: 'O que a ANEEL mede quando diz que uma região ficou sem energia?'
- Segundo: 'Mapas bonitos podem mentir: o desafio de comparar municípios e conjuntos elétricos'.
- Terceiro: benchmark e reprodutibilidade do ETL Parquet → DuckDB → Postgres.
