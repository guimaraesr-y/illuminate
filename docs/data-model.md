# Modelo analítico PostgreSQL — Etapa 1

Este é o modelo canônico implementado em `pipelines/aneel/postgres/migrations/`, não o esquema físico da ANEEL. Os arquivos oficiais continuam imutáveis em Parquet/CSV e não são importados indiscriminadamente por evento.

| Entidade | Identidade | Propósito |
| --- | --- | --- |
| `source_resource` | resource_id + SHA-256 | Versão física, URL original/efetiva, tamanho, coleta, período no rótulo e metadados |
| `ingestion_run` | UUID | Auditoria da carga, status, erro e bundle de entrada; conservada mesmo em rollback |
| `analysis_snapshot` | fingerprint semântico | Escopo, hashes, SQL, transformação, método stage1 e método analítico stage0 |
| `snapshot_resource` | snapshot + papel | Vínculo de fonte por domínio: indicadores, interrupções e municípios |
| `distributor` | snapshot + agente | Sigla normalizada, nome observado e CNPJ textual com zeros preservados |
| `electrical_set` | snapshot + agente + conjunto | Nome no snapshot, UFs, ambiguidade entre agentes e ausência de vigência histórica |
| `municipality` | snapshot + código | Nome e UF observados; sem geometria |
| `set_municipality_link` | snapshot + código do conjunto na fonte + município | Associação geográfica observada, data do cadastro e vigência conhecida/desconhecida |
| `continuity_indicator` | snapshot + agente + conjunto + mês + código | DEC/FEC/DECIND/FECIND mensais oficiais, unidade, qualidade e NumCon oficial mensal |
| `interruption_aggregate` | snapshot + agente + conjunto + mês | Contagens observadas e contribuições candidatas, separadas dos indicadores oficiais |
| `active_partition` | agente + conjunto + mês | Ponteiro para o snapshot atualmente publicado naquela partição |
| `schema_migration` | nome do arquivo | Checksum e data de aplicação das migrações |

## Proveniência e versões

Cada fato aponta para seu conjunto no snapshot e para o papel de fonte. `snapshot_resource` resolve o resource_id e hash registrados em `source_resource`; o snapshot contém também todas as fontes e dicionários do manifesto. A versão da transformação é um SHA-256 do código de preparação e normalização, além do hash do SQL e dos CSVs canônicos. A data de uma nova tentativa de download não duplica conteúdo idêntico.

As dimensões são versionadas por snapshot. Não se presume continuidade da sigla, nome ou código do conjunto entre snapshots, nem identidade global apenas pelo `set_id`. As chaves e os índices das séries incluem agente, conjunto, indicador e período.

## Geografia e cardinalidade

IndQual não possui agente nem vigência histórica. `set_municipality_link` conserva essa limitação: `source_set_id` não é uma chave estrangeira para um conjunto arbitrário de uma distribuidora. `association_status=set_code_only` identifica o vínculo observado. `snapshot_date` é a geração do cadastro, enquanto `valid_from`/`valid_to` continuam NULL quando desconhecidos.

O conjunto recebe `agent_link_ambiguous=true` quando o código aparece com mais de um agente na união das associações observadas nas interrupções e indicadores de 2025, antes dos filtros de agente, e `association_temporal_unknown=true` neste adaptador. As UFs são agregadas antes de qualquer junção analítica. Não se somam eventos após relação N:N nem se alocam indicadores entre municípios/UFs. O cadastro carregado inclui municípios de MG/SP ligados a conjuntos associados ao RJ: não representa apenas municípios fluminenses.

## Valores, ausência e unidades

`continuity_indicator.value=0` é um valor oficial observado. NULL com `quality_status=not_observed` significa falta de valor para aquela chave; não é zero. O spine mensal inclui meses com indicador e sem evento. `interruption_aggregate.event_rows` fica NULL com `observation_status=not_observed`; as demais medidas também ficam NULL.

Contagens são BIGINT, valores publicados e contribuições são DOUBLE PRECISION, preservando a representação da fonte DuckDB. A reconciliação usa tolerância absoluta explícita; a carga real conferida teve diferença zero. As contribuições mantêm os filtros stage0-v2 e não são DEC/FEC oficiais.

## Séries e publicação

- `official_monthly` seleciona as partições ativas e expõe versões, unidades, coleta, métodos e flags de ausência.
- `official_monthly_history` permite consultar qualquer snapshot sem sobrescrever resultados anteriores.
- `exploratory_monthly` contém contagens e contribuições próprias.
- `official_annual` identifica `data_kind=derived_from_official_monthly`, com regra ponderada por NumCon, 12 meses válidos e fontes/métodos explícitos. Não armazena nem afirma reproduzir um valor anual diretamente publicado pela ANEEL.

Uma correção usa staging e transação, com lock de publicação. As partições ativas são trocadas apenas depois das validações. A mesma identidade de snapshot é reutilizada; uma correção ganha outra identidade e conserva o histórico. Voltar a carregar um snapshot antigo é um no-op para a publicação, preservando a correção mais recente.

Instruções, testes, limitações anuais e limpeza local: [stage1.md](stage1.md).
