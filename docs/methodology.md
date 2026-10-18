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

## Exemplo de teste de qualidade (a implementar)

- `end_at >= start_at`, duração não negativa.
- Quantidades numéricas sem valores negativos; zero e missing tratados distintamente.
- Chaves normalizadas e esquemas versionados.
- Sem duplicidade de ingestão para o mesmo checksum/recurso.
- Soma das alocações geográficas consistente e sem dupla contagem.
- Resultado de período validado contra DEC/FEC publicado para o mesmo recorte.

## Mensagem pública

**Illuminate torna estatísticas públicas da continuidade elétrica mais acessíveis e reproduzíveis.** Não é serviço de alerta em tempo real, não garante cobertura por residência e não classifica distribuidoras como 'boas' ou 'ruins' sem uma metodologia explícita.

## Divulgação dos dados

Cada visualização terá painel "Como foi calculado" e fonte oficial clicável. Toda hipótese exploratória deve ser apresentada como hipótese até avaliação.
