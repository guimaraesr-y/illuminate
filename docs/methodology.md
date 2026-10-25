# Metodologia, interpretações e cuidados

## O que queremos demonstrar

**Hipótese, não conclusão:** a evolução dos indicadores de continuidade do fornecimento de energia no Brasil não é uniforme entre regiões e distribuidoras. Queremos medir a magnitude e persistência dessas diferenças e explicar os limites de cada comparação.

## Indicadores

- **DEC:** duração equivalente de interrupção por unidade consumidora no período (horas/unidade).
- **FEC:** frequência equivalente de interrupção por unidade consumidora no período (interrupções/unidade).
- Metas e limites: usar o indicador, período e conjunto corretos, conforme referência regulatória.
- Taxas, médias ou somatórios próprios são distintos de indicadores regulatórios; rotular adequadamente.

## Regras para publicar uma comparação

1. Declarar período, nível geográfico, abrangência, versão da fonte, critérios de exclusão e unidade.
2. Conferir se indicadores de diferentes conjuntos são comparáveis; considerar condições e limites regulatórios.
3. Uma associação entre conjunto e município **não** concede direito de duplicar um evento por cada município vinculado.
4. Não converter uma média de conjunto em experiência pessoal, nem um evento em ponto geográfico fictício.
5. Se dados de cooperativas/permissionárias não estiverem presentes, declarar a ausência na cobertura.
6. Causas registradas não demonstram, por si, negligência ou responsabilidade; evitar afirmações causais sem investigação.
7. 2026 parcial: não comparar contagens absolutas contra um ano completo sem normalização explícita.
8. Registrar incertezas, campos ausentes, inconsistências e revisões retroativas da publicação.

## Testes de qualidade

- `end_at >= start_at`, duração não negativa.
- Quantidades numéricas sem valores negativos; zero e missing tratados distintamente.
- Chaves normalizadas e esquemas versionados.
- Sem duplicidade de ingestão para o mesmo checksum/recurso.
- Soma das alocações geográficas consistente e sem dupla contagem.
- Resultado de período validado contra DEC/FEC publicado para o mesmo recorte.

## Etapa 0 — método executado

A reprodução, SQL, unidades e filtros estão em [stage0.md](stage0.md). Os arquivos de evidência ficam em `reports/stage0/`. A implementação local não equivale à conclusão da engenharia de dados de produção.

### Dados observados

- Interrupções 2025: 9.715.372 linhas físicas; 18.146 repetições integrais removidas, restando 9.697.226 registros. Há observações nos 12 meses e nenhum início fora de 2025.
- Inícios entre 01/01/2025 00:00:00 e 31/12/2025 23:59:26. O término mais tardio é 28/01/2026 15:37:16, preservado no ano de início.
- Nenhum intervalo negativo nem timestamp ausente; 109.635 intervalos de duração zero. Esses zeros são reportados, mas não entram na contribuição com duração mínima de 180 segundos.
- Há 49 registros com atingidos acima do denominador informado. Eles são reportados e excluídos das contribuições, sem corrigir os valores originais.
- Após deduplicação integral, há 331.711 grupos agente/conjunto/ordem com mais de uma linha (609.811 linhas excedentes nessa chave candidata). Isso demonstra que ela não identifica univocamente um registro; não autoriza descartar essas linhas como duplicatas de ocorrência.
- O cadastro municipal de 09/09/2026 contém 42.699 vínculos: 6.135 conjuntos com mais de um município, 5.560 municípios com mais de um conjunto e 91 conjuntos com vínculos em mais de uma UF.
- O snapshot associa 527 conjuntos a 92 municípios do RJ em 1.169 vínculos. Destes, 193 conjuntos têm registros na partição de interrupções, totalizando 800.098 linhas após deduplicação integral. Isso mede correspondência entre fontes, não cobertura histórica comprovada do estado.

### Sensibilidade à deduplicação

As 18.146 repetições integrais nacionais não têm identidade natural validada; removê-las é uma escolha de cenário, não uma correção de exportação comprovada. O bruto original permanece imutável, e o mesmo SQL é executado com todas as linhas em `rj-2025-raw.csv`, além do cenário deduplicado de `rj-2025.csv`.

`rj-dedup-sensitivity.csv` publica contagens e contribuições dos dois cenários, com diferenças bruto menos deduplicado por agente/conjunto/mês. No snapshot atual, o RJ contém **800.098 registros em ambos**, com **zero alterações nas contagens mensais**. As diferenças máximas absolutas são `8,881784197001252e-15` h/UC e `1,865174681370263e-14` interrupções/UC, decorrentes da ordem de soma em ponto flutuante, sem diferenças acima de `1e-10` (limiar numérico, não regulatório). Isso não demonstra que a deduplicação seja válida em outros recortes ou futuras versões. Diferenças físicas em colunas como alimentador são preservadas antes da projeção analítica.

### Ambiguidade entre UFs

Dos 527 conjuntos ligados ao RJ no snapshot, **20 também têm vínculo com outra UF**. Seis aparecem nos eventos de 2025: conjuntos **13053, 15087, 15088, 15089, 15090 e 15091**, somando **48.780 registros (cerca de 6,1% do recorte)**. Os cinco primeiros têm vínculo MG/RJ; o conjunto 15091 tem MG/RJ/SP. O inventário completo, incluindo conjuntos sem registros observados, está em `rj-multi-uf.csv`.

As tabelas mensais publicam `linked_ufs`, `linked_uf_count` e `is_multi_uf`, inclusive nas linhas somente com indicador oficial. São atributos do snapshot, não uma delimitação geográfica histórica. Esses conjuntos não devem aparecer em mapas como exclusivos do RJ, e não há pesos para distribuir seus valores entre UFs. Mantê-los sinalizados evita descartar conjuntos inteiros sem evidência de qual parte pertence a cada estado.

### Comparação com publicação oficial

As contribuições exploratórias são comparadas às parcelas oficiais DECIND/FECIND para agente, conjunto e mês idênticos, sem equipará-las aos indicadores. O DEC/FEC oficial completo também é exibido em colunas próprias. Somar contribuições sem demonstrar expurgos e denominadores não reconstrói automaticamente o DEC/FEC regulatório.

Exemplo observado: **EMR, conjunto 13746, janeiro/2025**, associado ao RJ no snapshot. Unidade da comparação de duração: horas por unidade consumidora.

| Medida | Valor |
| --- | ---: |
| Registros de interrupção após deduplicação | 111 |
| Registros elegíveis para a contribuição candidata | 95 |
| Contribuição de duração candidata | 0,854355883602 |
| DECIND oficial | 0,85 |
| Diferença candidata menos oficial | +0,004355883602 |
| DEC oficial completo | 0,90 |
| Contribuição de frequência candidata | 0,230458793543 |
| FECIND oficial | 0,23 |
| FEC oficial completo | 0,24 |

Referências: recursos `691de320-cb3d-471b-b9ec-8c1b86af8c83` (interrupções) e `d7f70fb1-725c-4748-afeb-65c6a78df550` (indicadores), identificados por URL e hash no manifesto. O SQL é `pipelines/aneel/sql/rj.sql` e a tabela está em `reports/stage0/rj-2025.csv`.

No recorte, 2.238 linhas mensais têm eventos e DECIND oficial correspondente. A diferença de duração varia de aproximadamente -0,121391 a +0,252144 h/UC; 2.208 diferenças têm módulo de até 0,01 h/UC. Esse limiar é uma descrição do resultado, não uma tolerância regulatória. Arredondamento dos valores oficiais pode explicar diferenças pequenas, mas não foi demonstrado como causa de cada divergência.

A tabela conserva também 114 linhas com indicadores oficiais e sem eventos observados. Os eventos ficam nulos, não zero. A diferença de cobertura entre fontes, incluindo a exclusão de permissionárias da base de interrupções, deve ser considerada; não se atribui uma causa específica a cada ausência sem validação.

### Hipóteses e limitações

O dicionário histórico descreve `IdeMotivoExpurgo`; o Parquet contém `IdeMotivoInterrupcao`. A seleção de código zero é exploratória. O dicionário lista, entre outros motivos, emergência (3), dia crítico (6), alívio de carga ONS (7) e origem externa (8). Não foi comprovada a equivalência semântica completa entre os nomes, nem reproduzido todo o PRODIST aplicável ao período.

O denominador do registro pode variar ao longo do mês; a análise não substitui esse campo por população atual nem presume um denominador regulatório mensal. A identidade natural da ocorrência e a vigência histórica conjunto/município continuam pendentes. Nenhum resultado é publicado como indicador municipal, residencial ou ranking.

## Mensagem pública

**Illuminate torna estatísticas públicas da continuidade elétrica mais acessíveis e reproduzíveis.** Não é serviço de alerta em tempo real, não garante cobertura por residência e não classifica distribuidoras como 'boas' ou 'ruins' sem uma metodologia explícita.

## Divulgação dos dados

Cada visualização terá painel "Como foi calculado" e fonte oficial clicável. Toda hipótese exploratória deve ser apresentada como hipótese até avaliação.
