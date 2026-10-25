# Etapa 0 — reprodução e interpretação

Esta entrega implementa a [issue #1](https://github.com/guimaraesr-y/illuminate/issues/1): descoberta oficial, download integral de uma partição anual, esquema físico, qualidade, relação geográfica e uma consulta DuckDB. A análise é local, sem serviços ou banco de produção.

## Executar

Instale uv e execute os quatro comandos da seção de reprodução do README. `uv.lock` fixa dependências, inclusive transitivas. Nenhum caminho absoluto do ambiente de coleta é necessário.

- `pipelines.aneel.collect --manifest reports/stage0/manifest.json`: baixa os sete recursos pelos URLs fixados, verifica SHA-256 e tamanho e preserva a identidade do snapshot original. Reutiliza arquivos locais apenas após verificação. Recurso alterado na origem gera erro: a ANEEL não garante retenção dessa versão.
- `pipelines.aneel.collect`: consulta os quatro pacotes CKAN e baixa a seleção de recursos da Etapa 0. Um cache já existente é verificado e reutilizado; para uma coleta nova, use `--root data/nova-coleta`. Não substitua o snapshot publicado sem revisar os resultados.
- `pipelines.aneel.analysis`: verifica os arquivos, aplica o contrato de esquema confirmado e executa o profiling e `pipelines/aneel/sql/rj.sql`. Não precisa de rede. Use `--root` e `--output` para outros diretórios.

O download aceita somente HTTP 200 completo, exige tamanho compatível com Content-Length quando informado, calcula SHA-256 e só então move o temporário para o nome imutável pelo hash. Retoma uma tentativa reiniciando-a; não concatena respostas parciais. Há até três tentativas e timeouts. Os caminhos do manifesto são relativos à raiz de dados.

## Artefatos

| Arquivo | Conteúdo |
| --- | --- |
| `reports/stage0/manifest.json` | Recursos oficiais, URLs, licença, períodos nos nomes dos recursos, datas, tamanhos e hashes |
| `reports/stage0/catalog/` | Respostas reais de package_show e testes da API de registros |
| `pipelines/aneel/schema-contract.json` | Nomes e tipos físicos confirmados; incompatibilidades interrompem a execução |
| `reports/stage0/quality.json` | Contagens, nulos, duplicatas, datas, agentes, motivos, cardinalidades e comparação |
| `reports/stage0/distribution-by-set.csv` | Distribuição dos registros por agente/conjunto |
| `reports/stage0/rj-2025.csv` | Tabela mensal completa do recorte por conjunto e agente |
| `reports/stage0/rj-2025-raw.csv` | Mesmo SQL e filtros, preservando todas as linhas físicas da fonte |
| `reports/stage0/rj-dedup-sensitivity.csv` | Contagens e contribuições com/sem deduplicação, com deltas por conjunto/mês |
| `reports/stage0/rj-multi-uf.csv` | Todos os conjuntos do snapshot ligados a RJ e outra UF, com contagem de registros observados |
| `reports/stage0/rj-sample.csv` | Primeiras 24 linhas ordenadas com eventos e indicador oficial disponível |
| `reports/stage0/analysis.json` | Período, nível geográfico, unidades, versão metodológica e hashes de SQL/tabela |
| `reports/stage0/verification.json` | Hashes dos resultados conferidos numa segunda execução offline |
| `reports/stage0/dictionary-*.txt` | Texto dos dicionários oficiais; o PDF original é identificado no manifesto |

Os dados são da ANEEL, sob a licença própria registrada no manifesto (ODbL); a MIT do código não os relicencia. As tabelas publicadas são agregadas por conjunto e não expõem unidades consumidoras individuais.

## Interpretação da tabela

Cada linha é `(agent, set_id, year, month)`. `event_rows` conta registros reportados após remover somente duplicatas integrais, e não ocorrências únicas demonstradas. `invalid_rows` conta intervalos/quantidades afetadas inválidos ou ausentes. Não se presume que a ordem de interrupção seja chave única.

A deduplicação é um cenário analítico, sem comprovação de que repetições integrais sejam erro de exportação. O arquivo bruto imutável é preservado e `rj-2025-raw.csv` publica o cenário alternativo com o mesmo SQL. `rj-dedup-sensitivity.csv` contém ambos os valores e a diferença **bruto menos deduplicado**, sem somar indicadores de conjuntos diferentes. Deltas nulos continuam nulos quando não há contribuição; o resumo em `quality.json` usa limiar absoluto de `1e-10` apenas para contar diferenças numéricas, sem significado regulatório. As 18.146 repetições nacionais não estão no recorte RJ deste snapshot: ambos os cenários têm 800.098 registros. A ordem de agregação gera diferenças de ponto flutuante de até `8,89e-15` h/UC e `1,87e-14` interrupções/UC, preservadas na tabela; nenhuma diferença ultrapassa o limiar.

`dec_official_h_per_uc`, `fec_official_per_uc`, `decind_official_h_per_uc` e `fecind_official_per_uc` são valores oficiais do Parquet de indicadores, para a mesma chave e mês. Nulo significa ausência, não zero. Meses presentes apenas nos indicadores são preservados, com `event_rows` nulo; não se inventa contagem zero. Chaves oficiais ambíguas interrompem a consulta.

`duration_candidate_h_per_uc` e `frequency_candidate_per_uc` são somas exploratórias de contribuições por registro: duração × unidades atingidas / consumidores informados no registro, e unidades atingidas / consumidores informados. A seleção exige duração de pelo menos 180 segundos, quantidade atingida não negativa e não superior ao denominador, denominador positivo, tipo `Não Programada` e código físico `IdeMotivoInterrupcao = 0`. `candidate_rows` registra quantas linhas entraram. Ausência de contribuições elegíveis fica nula.

**Essas contribuições não são DEC/FEC regulatórios reconstruídos.** O dicionário antigo nomeia um campo de expurgo que não existe com esse nome no Parquet. O filtro por código zero é uma hipótese operacional explícita, sem equivalência semântica comprovada com o campo antigo. Os denominadores podem variar entre registros. Não se afirma compatibilidade integral com expurgos, origem interna/externa, população e apuração regulatória.

As diferenças `duration_delta_vs_decind` e `frequency_delta_vs_fecind` subtraem as parcelas oficiais DECIND/FECIND das contribuições candidatas. A comparação permite observar divergências, sem declarar equivalência ou corrigir a publicação oficial.

## Geografia e tempo

IndQual tem data de geração de 2026, sem início/fim de vigência. O filtro usa `EXISTS` sobre conjuntos ligados a `SigUF = RJ`, evitando que a relação N:N multiplique eventos. Não distribui valores pelos municípios, nem pondera médias municipais. O resultado não representa necessariamente todos e apenas os conjuntos historicamente fluminenses de 2025, nem o estado inteiro.

As colunas `linked_ufs`, `linked_uf_count` e `is_multi_uf` tornam a ambiguidade territorial visível nas tabelas mensais, inclusive em meses somente com indicador oficial. O catálogo de vínculos é agrupado por conjunto antes da junção, sem multiplicar linhas. Há 20 conjuntos ligados ao RJ e outra UF; 6 aparecem nos registros de 2025 e somam 48.780 linhas (aproximadamente 6,1% do recorte). O inventário inclui os outros 14 conjuntos com `observed_event_rows=0`, o que significa nenhum registro observado nesse arquivo, não ausência comprovada de interrupções. Esses conjuntos não devem receber uma representação exclusiva do RJ em mapas futuros; mantêm-se identificados, sem rateio ou exclusão automática.

Os timestamps físicos são `TIMESTAMP` sem timezone. São preservados como publicados: não há conversão implícita para UTC nem suposição sobre horário civil. As datas de coleta do manifesto são UTC com offset. O recorte usa o ano do início; um término em 2026 é mantido e não significa que a partição de 2025 esteja incompleta.

## Validação

Os testes usam fixtures sintéticas, identificadas como tal e nunca publicadas como estatísticas oficiais. Cobrem download truncado/parcial, erro CKAN, hash, origem alterada, esquema incompatível, chave oficial ambígua, intervalos inválidos, denominador zero, atingidos acima da população, mês somente oficial, cobertura anual parcial e relação N:N. A publicação exige eventos nos 12 meses: isso detecta cobertura temporal grosseira, sem comprovar que todas as interrupções reais foram reportadas. A integração real é exercitada pelo pipeline sobre os arquivos completos e pela reprodução offline do resultado.

O workflow `.github/workflows/data-tests.yml` executa `uv sync --locked` e os testes de fixture em PRs, pushes para `main` e disparo manual. Não executa coleta nem baixa arquivos da ANEEL. Os testes incluem sensibilidade com repetição física, preservação de alimentadores distintos, conjunto multi-UF e sinalização de mês somente oficial. A agregação real usa uma thread para preservar a ordem de soma em ponto flutuante na reprodução com a versão fixada do DuckDB. `verification.json` registra os hashes conferidos em uma segunda análise offline.

O hash do SQL usa texto UTF-8 com finais de linha normalizados para LF. Os hashes dos resultados usam bytes integrais. `.gitattributes` impede conversões de finais de linha nos relatórios, preservando a evidência em clones.
