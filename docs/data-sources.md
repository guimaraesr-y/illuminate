# Fontes, APIs e o que já sabemos

Atualizado em 18/10/2026. Diferenciamos **catálogo identificado**, **esquema documentado** e **download/exploração efetivamente validado**. Não houve ingestão própria bem-sucedida do Parquet na preparação inicial.

## 1. Interrupções de Energia Elétrica nas Redes de Distribuição

- Fonte: https://dadosabertos.aneel.gov.br/dataset/interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao
- Abrangência: nacional, a partir de 2017; atualização informada como mensal.
- Granularidade geográfica: conjunto de unidades consumidoras.
- Granularidade temporal: instantes de interrupção em data/hora/minuto/segundo.
- O catálogo apresenta ZIP e Parquet por ano. O cadastro exclui áreas sob gestão de permissionárias (cooperativas).
- Conclusão: suporta reconstrução de séries, duração de eventos e indicadores agregados, **não** localiza o endereço específico onde faltou energia.

### Schema: campos candidatos a confirmar na versão baixada

Esquemas podem mudar. Um dicionário/referência histórica utiliza nomes como:
- `DatInicioInterrupcao`, `DatFimInterrupcao`: início/fim.
- `DscTipoInterrupcao`: classificação programada/não programada.
- `FatGeradorInterrupcao`: classificação de causa/fato gerador.
- `NumUnidadeConsumidora`: quantidade informada de unidades afetadas.
- `NumConsumidorConjunto`: denominador informado do conjunto.
- `SigAgente`: sigla do agente.

**NÃO** presumir que estes nomes/tipos estejam inalterados em 2026. Registrar esquema físico por arquivo antes de transformar.

### Amostra efetivamente disponível

Há referência a um relatório de terceiros com **dez registros reproduzidos** da base de 2024, expondo apenas identificador e nome do conjunto e uma data de geração, incluindo nomes como Atuba e MOSSORÓ III. A data de geração **não** é a data da interrupção. Isso **não** constitui validação de milhões de linhas ou qualidade da base; nenhum valor agregado municipal foi apurado por nós.

- Relato da amostra: https://rstudio-pubs-static.s3.amazonaws.com/1199520_5e3c8872d72d4303839d6af8445a76ee.html

## 2. Indicadores coletivos DEC/FEC

- Fonte: https://dadosabertos.aneel.gov.br/dataset/indicadores-coletivos-de-continuidade-dec-e-fec
- DEC: duração equivalente média de interrupção por unidade consumidora, tipicamente expressa em horas no período.
- FEC: frequência equivalente média de interrupção por unidade consumidora, expressa como número de interrupções no período.
- Para avaliar atendimento a limites regulatórios, alinhar período de referência, conjunto, indicador e regras de expurgo.
- **Não** somar DEC de conjuntos como se fosse duração total do município; médias requerem ponderações/denominadores adequados.

## 3. Ocorrências emergenciais

- Fonte: https://dadosabertos.aneel.gov.br/dataset/ocorrencias-emergenciais-nas-redes-de-distribuicao
- Fonte complementar para estudar ocorrências; não assumir equivalência linha-a-linha com registros de interrupções.
- Validar definições, chaves e janelas temporais antes de qualquer junção.

## 4. IndQual Município

- Fonte: https://dadosabertos.aneel.gov.br/dataset/indqual-municipio
- Útil para explorar a relação entre municípios e conjuntos.
- **Crítico:** relação possivelmente muitos-para-muitos e variável no tempo. Validar vigência, cobertura e denominadores; não duplicar contagens por join ingênuo.

## 5. CKAN: API de descoberta vs consulta de registros

O portal da ANEEL utiliza CKAN. A interface documentada do CKAN permite:
```bash
curl -fsSL 'https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao'
```

Parser esperado (contrato CKAN):
- `success`: booleano (verificar mesmo com HTTP 200).
- `result.resources[]`: metadados de recursos; identificar `format`, `url`, `id`, `last_modified`/campos análogos quando presentes.
- `error`: descrição em caso de falha.

Documentação: https://docs.ckan.org/en/2.12/api/index.html

**Status verificado:** o endpoint acima é o padrão da plataforma, mas a conexão ao domínio falhou no ambiente de elaboração. Isso **não comprova** sua disponibilidade real, ausência de autenticação, retorno por linha, limites ou schema. Não vender este endpoint como API de ocorrências. Quando executado com sucesso, salvar metadados, resposta e instante de coleta.

## 6. Checklist obrigatório antes da análise

1. Baixar uma partição anual e registrar checksum SHA-256 e URL final efetiva.
2. Executar `DESCRIBE SELECT * FROM read_parquet(...)` (ou inspecionar ZIP/CSV) e salvar nomes/tipos.
3. Contar linhas, nulos, duplicatas e chaves, distribuição de datas e agentes.
4. Inspecionar regras oficiais de expurgo; decidir comparabilidade com DEC/FEC publicado.
5. Validar mapeamento conjunto/município e estabilidade histórica.
6. Testar SQL agregador em um recorte RJ e conferir com indicador oficial.
7. Publicar metodologia, limitações e exemplos de ambiguidades.
