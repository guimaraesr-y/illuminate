# Plano de implementação — Etapa 1

Plano aprovado no chat em 25/10/2026, baseado na issue #3. Execução local, com revisão independente ao final.

## Arquitetura

Python + DuckDB prepara um bundle RJ verificado, preservando o método stage0-v2. PostgreSQL guarda snapshots imutáveis, dimensões identificadas por agente/conjunto, indicadores oficiais e agregados exploratórios separados. A publicação usa staging e transação; uma seleção ativa por escopo aponta para o snapshot publicado, sem apagar históricos. psycopg gerencia conexões e COPY; migrações SQL têm checksum e lock.

## Tarefas e validação

- [x] Infra: Compose, ambiente de exemplo, migrações e índices. Testar banco vazio e migração repetida.
- [x] Preparação DuckDB: manifesto fixado ou coleta nova, contratos de esquema, exportação canônica com hashes. Fixtures verificam NULL, identidade composta e deduplicação integral.
- [x] Persistência: source_resource, ingestion_run, snapshots, dimensões e proveniência. Testar ingestão repetida e rejeição de bundle alterado.
- [x] Publicação: staging, transação, lock por escopo e ponteiro ativo. Testar rollback, correção retroativa e histórico consultável.
- [x] Leitura: séries mensais com metadados e flags geográficas; anuais derivados ponderados por NumCon e explicitamente distintos de valores anuais publicados. Nunca somar médias de conjuntos para inventar média da distribuidora.
- [x] Integração: PostgreSQL real com fixtures no CI, comparação do snapshot RJ real com a referência da Etapa 0, comandos documentados.

## Decisões de execução

- PostgreSQL local em container; nenhum serviço de produção será alterado.
- Arquivos raw permanecem fora do banco e do Git.
- Uma execução repetida pode acrescentar auditoria, mas não altera fatos/dimensões do snapshot nem contagens analíticas.
- Nova versão da fonte e mudança de método geram identidade distinta de snapshot. Falhas de carga não mudam o ponteiro ativo.

## Verificações de execução

- Banco PostgreSQL 17.6 real: migrações repetidas, 0/NULL, idempotência, concorrência, COPY interrompido e correção retroativa foram exercitados por fixtures.
- Snapshot real da Etapa 0: carga de 9.408 indicadores e 2.352 agregados; comparação por chave/valor com fontes de mesmo SHA.
- Revisão independente identificou três problemas: refresh parcial, agentes presentes só em interrupções e cobertura de meses somente NumCon. Os três foram reproduzidos por testes antes da correção.
- Os anuais são derivados ponderados por NumCon mensal e rotulados como tais; não afirmam reproduzir valores anuais diretamente publicados pela ANEEL.
