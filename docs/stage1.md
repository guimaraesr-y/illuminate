# Etapa 1 — PostgreSQL reproduzível

O pipeline prepara um bundle pequeno a partir dos arquivos oficiais verificados, carrega staging e publica um snapshot em uma transação. O PostgreSQL não recebe os milhões de registros físicos de interrupção. A implementação atual é verificada para **RJ / 2025**, com filtros opcionais de agente, conjunto e mês.

## Subir do zero

Requisitos: Docker com engine Linux ativo, uv e Python 3.13. Na raiz do projeto:

```sh
cp .env.example .env
docker compose up -d --wait
uv sync --locked
uv run --env-file .env python -m pipelines.aneel.postgres migrate
uv run --env-file .env python -m pipelines.aneel.postgres ingest --manifest reports/stage0/manifest.json
uv run --env-file .env python -m pipelines.aneel.postgres compare --bundle data/stage1-bundle
```

No PowerShell, use `Copy-Item .env.example .env`. Os valores do exemplo servem exclusivamente ao ambiente local; `.env` não é versionado. A porta padrão é 55432 em loopback; altere `POSTGRES_PORT` e `DATABASE_URL` juntos em caso de conflito. A CLI recebe `DATABASE_URL` ou `--dsn`, e `--schema` permite isolar ambientes no mesmo banco. Nunca é necessário informar senha em um arquivo de código.

A ingestão com `--manifest` exige os hashes originais; se a ANEEL substituir os arquivos e eles não estiverem no cache, ela falha explicitamente. Os arquivos já coletados são reutilizados somente depois de verificação. O comando de migração é repetível, usa lock e rejeita alterações de checksum em migrações aplicadas.

## Preparar e carregar separadamente

```sh
uv run --locked python -m pipelines.aneel.postgres prepare --root data/aneel --output data/stage1-bundle
uv run --env-file .env python -m pipelines.aneel.postgres load --bundle data/stage1-bundle
uv run --env-file .env python -m pipelines.aneel.postgres load --bundle data/stage1-bundle
```

`prepare` não precisa de PostgreSQL nem rede. Confere bytes e contratos físicos, preserva a deduplicação integral do cenário stage0-v2, distingue 0/NULL e usa o SQL validado na Etapa 0. O bundle contém CSVs canônicos, referência, hashes, escopo, fontes e método. A identidade considera recursos + hashes, papéis das fontes, transformação, SQL, escopo e arquivos analíticos; a simples mudança da data de download não cria fatos duplicados. O carregador verifica os bytes efetivamente consumidos pelo COPY, mesmo se outro processo alterar o diretório.

`load` aplica migrações e registra uma execução. O mesmo snapshot retorna `reused`; pode adicionar auditoria, mas não modifica fatos nem reativa uma versão antiga sobre uma correção mais recente. Uma nova identidade publica novas linhas históricas. Staging, fatos, dimensões e troca dos ponteiros ativos são transacionais, com lock por schema. Em erro de carga, o snapshot anterior continua ativo; o registro de falha conserva os metadados da entrada. Uma interrupção abrupta do processo pode deixar a auditoria como `running`, mas PostgreSQL desfaz a transação não confirmada. Erros de descoberta/download/preparação ocorrem antes da auditoria da carga e encerram a CLI sem publicar dados.

A cobertura canônica inclui também meses contendo somente NumCon: seus indicadores e eventos permanecem NULL, preservando a população observada para diagnóstico. A ambiguidade de agente é avaliada pela união das associações nas interrupções e indicadores antes dos filtros opcionais, inclusive quando um agente existe somente em uma das fontes.

## Nova coleta e correção retroativa

```sh
uv run --env-file .env python -m pipelines.aneel.postgres ingest --refresh
uv run --env-file .env python -m pipelines.aneel.postgres ingest --manifest data/correcao/manifest.json --agent "ENEL RJ" --start-month 3 --end-month 3 --output data/marco-corrigido
```

`--refresh` baixa e verifica novamente os recursos selecionados, arquiva o manifesto anterior em `data/aneel/manifest-history/` e preserva os raw antigos pelo SHA-256. O manifesto ativo é trocado por rename somente após concluir a coleta; uma falha intermediária mantém o anterior completo. Mesmo URL com bytes novos gera uma versão rastreável. `--manifest` e `--refresh` são mutuamente exclusivos. Sem ambos, um manifesto local existente é usado; se não existir, ocorre descoberta inicial.

Uma publicação substitui os ponteiros ativos apenas no escopo declarado, inclusive quando uma chave antiga deixa de existir na correção. O histórico permanece em `analysis_snapshot` e nas tabelas por snapshot. Use agente e conjunto juntos para desambiguar códigos; somente `--set-id` seleciona todos os agentes observados com esse código. Diretórios diferentes para preparações simultâneas evitam trabalho descartado por conflito de arquivos; um conflito de hashes impede publicação.

## Consultar

```sh
uv run --env-file .env python -m pipelines.aneel.postgres series --agent "EMR" --set-id 13746
uv run --env-file .env python -m pipelines.aneel.postgres series --agent "EMR" --set-id 13746 --annual
```

Views no schema `illuminate`:

- `official_monthly`: indicadores mensais oficiais atualmente publicados, fontes, coleta, método e flags de ausência/ambiguidade.
- `official_monthly_history`: valores de todos os snapshots, consultáveis por `snapshot_id`.
- `exploratory_monthly`: contribuições candidatas e contagens do cenário deduplicado, separadas dos indicadores oficiais.
- `official_annual`: **anuais derivados de indicadores mensais oficiais**, identificados por `data_kind=derived_from_official_monthly`; não são valores anuais diretamente publicados pela ANEEL.

As consultas por distribuidora filtram séries de seus conjuntos: não calculam uma média entre conjuntos, não estimam valores municipais e não rateiam conjuntos multi-UF. Veja exemplos em `pipelines/aneel/postgres/queries.sql`.

## Regra anual

Para DEC/FEC por **mesmo agente/conjunto/ano**, a derivação usa `sum(valor_mensal * NumCon_mensal) / avg(NumCon_mensal)`. `NumCon` vem do próprio arquivo oficial de indicadores, não do denominador de cada evento. A view exige os 12 meses com valores e consumidores positivos, mesmo SQL/transformação e mesmo método; do contrário, retorna valor anual NULL e flags de cobertura/método. Zero é valor observado válido. Revisões de fonte podem coexistir nos meses; todas as versões e datas de coleta são expostas.

A ponderação temporal é descrita na [Resolução ANEEL 24/2000, art. 6º](https://www2.aneel.gov.br/cedoc/res2000024.pdf) como referência matemática histórica e na [publicação de indicadores da Coopersul](https://coopersulrs.com.br/indicadores.php). Essas referências não demonstram equivalência integral à apuração regulatória vigente de um valor anual publicado. A implementação não afirma essa equivalência, nem usa soma simples quando a população varia. A conferência com a Etapa 0 cobre os valores mensais; não existe referência anual validada nesse relatório.

## Testes e evidência real

```sh
uv run --locked python -m unittest discover -s pipelines/tests -v
uv run --env-file .env python -m unittest discover -s pipelines/tests -v
```

Sem `ILLUMINATE_TEST_DATABASE_URL`, os testes PostgreSQL são explicitamente pulados. Com a variável, cada teste cria e remove somente um schema `test_<uuid>` próprio, preservando o schema de desenvolvimento. O CI tem jobs de fixtures e PostgreSQL 17.6, sem coletar dados da ANEEL.

Os testes cobrem migração repetida/checksum, COPY interrompido, rollback, NULL/zero, concorrência, snapshots corrigidos, replay antigo, identidade composta, N:N/multi-UF e denominadores anuais. O relatório `reports/stage1/reconciliation.json` compara as 2.352 chaves mensais e os valores persistidos com a Etapa 0, exige os mesmos hashes das três fontes primárias e registra diferenças e tolerância.

## Parar e limpar em desenvolvimento

`docker compose down` para o serviço preserva o volume. Para reconstruir deliberadamente o banco local do zero, `docker compose down -v` remove o volume desse projeto Compose; depois execute novamente os comandos de inicialização. Não é uma operação necessária para repetir ingestões. Raw e bundles ficam fora do Git em `data/`, independentemente do volume PostgreSQL.
