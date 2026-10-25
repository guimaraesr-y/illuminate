# Fontes, APIs e esquema confirmado

Coleta em 22/10/2026 (Brasília; timestamps UTC no manifesto). Evidências: `reports/stage0/catalog/`, `manifest.json`, `quality.json` e `pipelines/aneel/schema-contract.json`. Os esquemas abaixo foram inspecionados nos arquivos oficiais completos.

## Catálogo e registros

`https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=<slug>` retornou HTTP 200 e `success=true` para as quatro fontes. As respostas integrais preservam recursos, formatos, URLs, metadados temporais e licença. Os dicionários consultados informam atualização mensal. As licenças declaradas são ODbL; os títulos diferem entre cadastros. As requisições não exigiram autenticação; quotas não foram estabelecidas.

Os testes separados de `datastore_search?resource_id=...&limit=1` constam em `record-api-probes.json`:

| Recurso | Evidência |
| --- | --- |
| Interrupções Parquet 2025, `691de320-cb3d-471b-b9ec-8c1b86af8c83` | HTTP 404, `success=false` |
| IndQual CSV, `3f841488-80a8-42f2-a6ca-e0c593b228de` | HTTP 200, registro retornado |
| Indicadores ZIP 2020–2029, `4493985c-baea-429c-9df5-3030422c71d7` | HTTP 200, registro retornado |

A API não é somente de metadados, mas a disponibilidade de registros depende do recurso. O teste não comprova equivalência entre datastore e arquivo; a análise usa downloads integrais verificados.

## Interrupções

Fonte: [Interrupções nas redes de distribuição](https://dadosabertos.aneel.gov.br/dataset/interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao).

Parquet anual 2025 completo: **272.507.818 bytes**, **9.715.372 linhas físicas**. URL original/efetiva, hash, coleta, ETag e Last-Modified estão no manifesto. O catálogo separa dicionários até dezembro/2025 e a partir de janeiro/2026; usamos o histórico.

| Campos físicos | Tipo DuckDB | Semântica / limite |
| --- | --- | --- |
| `DatGeracaoConjuntoDados` | DATE | Geração da publicação, não ocorrência |
| `IdeConjuntoUnidadeConsumidora` | BIGINT | Identificador do conjunto |
| `DscConjuntoUnidadeConsumidora` | VARCHAR | Nome do conjunto, adicional ao dicionário |
| `DscAlimentadorSubestacao`, `DscSubestacaoDistribuicao` | VARCHAR | Descrições operacionais |
| `NumOrdemInterrupcao` | VARCHAR | Ordem reportada; unicidade não presumida |
| `DscTipoInterrupcao` | VARCHAR | Programada / Não Programada |
| `IdeMotivoInterrupcao` | BIGINT | Código observado; divergência de nome com dicionário |
| `DatInicioInterrupcao`, `DatFimInterrupcao` | TIMESTAMP | Sem timezone; preservados sem conversão |
| `DscFatoGeradorInterrupcao` | VARCHAR | Fato gerador registrado |
| `NumNivelTensao`, `NumUnidadeConsumidora`, `NumConsumidorConjunto`, `NumAno` | BIGINT | Tensão, atingidos, consumidores do conjunto e ano |
| `NomAgenteRegulado`, `SigAgente` | VARCHAR | Nome/sigla; trim da sigla para correspondência |
| `NumCPFCNPJ` | BIGINT | Identificador do agente, não quantidade; ausente no recorte publicado |

**Divergências:** o dicionário chama o motivo de `IdeMotivoExpurgo` e o fato gerador de `FatGeradorInterrupcao`; o Parquet usa `IdeMotivoInterrupcao` e `DscFatoGeradorInterrupcao`. O dicionário descreve expurgos 0–8, mas coincidência de valores não prova equivalência entre os campos. O filtro por código zero é uma hipótese explícita, não uma reconstrução regulatória validada.

O dicionário exclui interrupções de permissionárias/cooperativas. A granularidade não demonstra endereço ou experiência de uma residência. Removem-se somente linhas integralmente idênticas; a identidade natural de uma ocorrência permanece sem validação.

## Indicadores DEC/FEC

Fonte: [Indicadores coletivos de continuidade](https://dadosabertos.aneel.gov.br/dataset/indicadores-coletivos-de-continuidade-dec-e-fec).

O rótulo 2020–2029 é uma partição de publicação, não comprova preenchimento de anos futuros. O arquivo tem **5.137.778 linhas**; a consulta usa `AnoIndice=2025` e períodos mensais 1–12. Também foram baixados o dicionário de continuidade e o domínio dos indicadores.

Esquema: `DatGeracaoConjuntoDados` DATE; `IdeConjUndConsumidoras`, `NumCNPJ`, `AnoIndice`, `NumPeriodoIndice` BIGINT; `DscConjUndConsumidoras`, `SigAgente`, `SigIndicador` VARCHAR; `VlrIndiceEnviado` DOUBLE. O CSV de domínio é UTF-8, delimitado por `;`.

Chave analítica: agente normalizado + conjunto + ano + mês + indicador. Ambiguidade nessa chave interrompe a análise após remover somente repetições integrais. Os valores oficiais ficam separados dos cálculos próprios e com unidades explícitas. O dicionário remete ao Módulo 8 do PRODIST; não se presume que uma fórmula simplificada reproduza suas regras.

## IndQual Município

Fonte: [IndQual Município](https://dadosabertos.aneel.gov.br/dataset/indqual-municipio).

CSV com `;`, lido como Latin-1, **42.699 linhas**. Campos textuais preservados: `DatGeracaoConjuntoDados`, `IdeConjUnidConsumidoras`, `CodMunicipio`, `NomMunicipio`, `SigUF`. A grafia do identificador difere do dicionário e do Parquet DEC/FEC. O conjunto é convertido explicitamente para BIGINT; códigos municipais continuam textuais.

Geração observada: **09/09/2026**. Não há vigência histórica nem participações/ponderações. A relação N:N foi confirmada, inclusive com conjuntos ligados a várias UFs. Selecionar conjuntos com vínculo ao RJ no snapshot não atribui indicadores a municípios de 2025.

## Ocorrências emergenciais

Fonte: [Ocorrências emergenciais](https://dadosabertos.aneel.gov.br/dataset/ocorrencias-emergenciais-nas-redes-de-distribuicao).

O pacote e seus recursos foram inventariados. Não houve download analítico nem junção com interrupções nesta etapa; não se presume equivalência entre registros.

## Reprodução

Consulte [Etapa 0](stage0.md) para comandos, saídas, geografia, hipóteses e comparação. Uma revisão retroativa pode alterar bytes no mesmo URL. Os hashes fixam a versão usada, mas não garantem sua retenção pela ANEEL: sem o arquivo correspondente, a reprodução falha explicitamente.
