# Illuminate

**Tornando visível a qualidade da energia no Brasil.**

O **Illuminate** é um projeto open source para explorar a continuidade do fornecimento de energia elétrica no Brasil a partir de dados públicos da Agência Nacional de Energia Elétrica (ANEEL).

> **Status: Etapa 0 — prova de dados.** Há um pipeline local Python + DuckDB, manifesto verificável e análise reproduzível de uma partição anual de 2025. A arquitetura de produção e a interface continuam como propostas. Consulte o [relatório e instruções](docs/stage0.md).

## Reproduzir a prova de dados

Requer [uv](https://docs.astral.sh/uv/) e Python 3.13. Execute na raiz do repositório:

```sh
uv sync --locked
uv run --locked python -m unittest discover -s pipelines/tests
uv run --locked python -m pipelines.aneel.collect --manifest reports/stage0/manifest.json
uv run --locked python -m pipelines.aneel.analysis
```

A coleta usa URLs oficiais e exige os hashes do manifesto publicado. Se a ANEEL substituir um arquivo, a reprodução falha explicitamente em vez de publicar números diferentes silenciosamente. O modo `collect` sem `--manifest` faz uma descoberta nova. Arquivos volumosos ficam em `data/` (ignorado pelo Git); o SQL, manifesto, relatórios e tabelas pequenas são versionados. Reserve cerca de 5 GiB livres para dados e temporários; DuckDB limita a memória a 2 GB.

A tabela `reports/stage0/rj-2025.csv` representa **conjuntos associados ao RJ no cadastro coletado**, com eventos de 2025. Essa associação não comprova abrangência municipal histórica. Indicadores oficiais e contribuições exploratórias têm colunas e unidades distintas.

## A pergunta central

**A continuidade do fornecimento de energia está melhorando no Brasil? Essa evolução é uniforme entre regiões e distribuidoras?**

Investigaremos duração e frequência das interrupções, padrões temporais, comparações regionais e limites regulatórios, com rastreabilidade até a fonte original.

O Illuminate **não é** um mapa de faltas de energia em tempo real, não localiza a residência afetada e não atribui causalidade ou responsabilidade sem evidências.

## Experiência proposta

1. **Explorar** séries históricas e regiões geográficas com um mapa interativo.
2. **Compreender** DEC/FEC, cobertura, temporalidade e limitações de cada medida.
3. **Comparar** períodos, conjuntos elétricos e distribuidoras em bases metodologicamente compatíveis.
4. **Compartilhar** URLs reproduzíveis incluindo filtros, recortes, versões e proveniência dos dados.

**Mapa 3D:** direção visual desejada, porém opcional e progressiva. A primeira versão terá mapa 2D com indicadores e legenda; no 3D, extrusões mostrarão métricas em geografias comprovadamente vinculadas aos dados. **Jamais usaremos o mapa para simular ocorrências em nível de bairro/rua sem evidência espacial.**

## Dados oficiais

| Fonte | Propósito | Status |
| --- | --- | --- |
| [ANEEL — Interrupções nas redes de distribuição](https://dadosabertos.aneel.gov.br/dataset/interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao) | Registros por interrupção/conjunto; arquivo anual em ZIP/Parquet | Parquet 2025 baixado e inspecionado |
| [ANEEL — Indicadores DEC/FEC](https://dadosabertos.aneel.gov.br/dataset/indicadores-coletivos-de-continuidade-dec-e-fec) | Duração e frequência médias e limites regulatórios | Parquet 2020–2029 inspecionado; consulta mensal de 2025 |
| [ANEEL — Ocorrências emergenciais](https://dadosabertos.aneel.gov.br/dataset/ocorrencias-emergenciais-nas-redes-de-distribuicao) | Contexto operacional complementar | Fonte identificada; validação pendente |
| [ANEEL — IndQual Município](https://dadosabertos.aneel.gov.br/dataset/indqual-municipio) | Relação município ↔ conjuntos | Cadastro de 09/09/2026; N:N confirmado, vigência histórica ausente |

**Importante:** a ANEEL informa que o conjunto de interrupções não inclui áreas geridas por permissionárias (cooperativas). A granularidade oficial é o *conjunto de unidades consumidoras*, não residência, bairro ou município. Atualizações do catálogo são mensais, não em tempo real.

O portal usa CKAN: `package_show` retornou metadados das quatro fontes. `datastore_search` retornou registros para os recursos testados de IndQual e indicadores, mas 404 para o Parquet 2025 de interrupções. A disponibilidade depende do recurso; quotas e equivalência de conteúdo com os arquivos não foram estabelecidas. Consulte [fontes e limitações](docs/data-sources.md).

## Arquitetura proposta

```text
CKAN metadata / ANEEL Parquet, ZIP + dicionários
                       |
                discovery worker
                       |
                 raw immutable
                       |
            Python + DuckDB / Polars
                validation & ETL
                       |
           normalized analytical tables
                 PostgreSQL
                       |
               aggregate / API
                       |
         Next.js + MapLibre GL JS
         2D first, optional 3D
```

- **Ingestão:** baixar por URL de recurso descoberta via CKAN, controlar hash, tamanho, última modificação e erros; guardar original imutável.
- **Transformação:** detectar esquema, validar chaves, datas, unidades e cardinalidade, normalizar em lotes, registrar linhagem.
- **Dados:** PostgreSQL para consultas do produto; PostGIS somente quando geometrias licenciadas/validáveis forem incorporadas; DuckDB/Parquet para agregações offline.
- **Web/API:** Next.js, endpoint de série temporal e filtros por distribuidora/conjunto; municípios apenas com vínculo temporal/geográfico confiável.
- **Operação:** ingestão incremental, logs estruturados, testes de qualidade, snapshots de releases e cache de agregados.

Detalhes: [arquitetura](docs/architecture.md), [modelo de dados](docs/data-model.md) e [visualização 3D](docs/visualization.md).

## Escopo MVP (primeiro RJ)

1. Inventariar recursos e esquemas oficiais, baixar uma partição anual e documentar amostra reproduzível.
2. Calcular e conferir DEC/FEC de conjuntos elétricos do RJ em 2020–2025 (não projetar resultados sem dados).
3. Construir API de séries históricas e um painel 2D que explicite as limitações da associação com municípios.
4. Comparar períodos, explicar indicadores e exportar proveniência.
5. Validar desempenho e correção, só então testar modo 3D.

Ver [roadmap](docs/roadmap.md).

## Contribuição

Contribuições são bem-vindas em conectores, testes de qualidade, metodologia de indicadores, acessibilidade e visualização. Antes de propor interpretações, anexe consulta reproduzível, data de extração e fonte pública. Não publique dados residenciais ou atribuições indevidas a pessoas/empresas.

**Código:** MIT (licença do repositório). **Dados de terceiros:** seguem suas próprias licenças, termos de atribuição e condições de redistribuição; a licença MIT não altera esses termos.
