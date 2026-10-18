# Modelo de dados (proposta inicial)

Não é o schema oficial da ANEEL. É uma estrutura canônica **a ser ajustada após inspeção real dos arquivos**.

## Entidades e granularidade

| Entidade | Chave proposta | Granularidade | Observações |
|---|---|---|---|
| `source_resource` | `id` | recurso/versionamento CKAN | URL, período, hash, horário de coleta, licença |
| `distributor` | `agent_key` | distribuidora | Sigla e eventual identificador oficial |
| `electrical_set` | `set_key`, validade | conjunto elétrico histórico | Códigos podem mudar; versionar atributos |
| `municipality` | `ibge_code` | município | geometria externa precisa proveniência |
| `set_municipality_link` | conjunto + município + vigência | associação histórica | potencialmente N:N; não assumir participação do consumo |
| `interruption_event` | `source_version` + identidade natural verificada | interrupção reportada | começo/fim, categoria, afetados; evitar chave inventada |
| `continuity_indicator` | conjunto + período + indicador + versão | DEC/FEC oficial | guardar métrica, limite e unidade se disponíveis |
| `quality_check` | execução + regra | inspeção de qualidade | nome da regra, evidência, contagens |
| `analysis_snapshot` | UUID | análise publicada | hash de consulta e versão do método |

## Campos candidatos para evento

```text
event_id                string (interno, não presumir ID nativo)
source_resource_id       string
set_key                  string
agent_key                string
start_at                 timestamp with timezone policy explicit
end_at                   timestamp with timezone policy explicit
duration_seconds         bigint nullable / derived
affected_units           bigint nullable
set_consumer_count       bigint nullable
interruption_type        string nullable
cause_category           string nullable
reported_at              timestamp nullable
```

A política de timezone depende do padrão real da fonte. Não interpretar uma data sem timezone como UTC de forma automática.

## Definições essenciais

- **Duração de evento:** `end_at - start_at`, se ambos válidos e `end_at >= start_at`.
- **Unidades consumidoras-hora (candidata):** `sum(duration_hours * affected_units)`, **apenas após** confirmar a semântica dos registros e deduplicação; não equivale a horas reais de uma casa.
- **DEC/FEC:** preferir inicialmente valores oficiais publicados, com as regras regulatórias e expurgos de cada período.
- **Município:** não atribuir a um município inteiro o indicador de um conjunto de abrangência intermunicipal sem fonte apropriada e ponderações justificadas.
- **Taxa de variação:** respeitar períodos completos (2026 parcial não comparável diretamente a 2025 completo).

## Modelagem física sugerida

PostgreSQL com índices por `(set_key, reference_period)`, `(agent_key, reference_period)` e partição temporal para volume histórico. Colunas de proveniência em todas as tabelas derivadas. Views/materializações com versionamento por `methodology_version` e `source_resource_id`.

PostGIS apenas para geometrias de fontes identificadas e com vínculo explícito à métrica.
