# Visualização geoespacial e mapa 3D

## Decisão arquitetural (ADR-001): 2D first, 3D optional

**Status:** proposta aprovada para exploração visual, condicionada à validação geográfica.

### Intenção

Criar uma experiência visual memorável para o Brasil, sem criar falsa precisão. A interface prioriza a exploração histórica e a compreensão da qualidade do fornecimento; o 3D é uma forma de visualizar indicadores, não uma simulação física de blecautes.

### Implementação sugerida

- Base: **MapLibre GL JS** (WebGL), com suporte a inclinação e extrusões estilizadas.
- Sobreposições: polígonos GeoJSON/tiles geográficos de fonte licenciada (IBGE ou equivalente), normalizados no pipeline, **somente em geografias para as quais haja indicadores coerentes**.
- Alternativa para camadas mais pesadas: deck.gl, se houver volume e necessidade técnica.
- 2D: coroplético por métrica escolhida; escala, legenda, unidade, período, cobertura e aviso geográfico sempre visíveis.
- 3D: `fill-extrusion` (altura = métrica ou transformação explicitada) + cor por variação; câmera inclinada, animações discretas.
- Modo tabela/grafico acessível com os mesmos filtros e valores.

### Por que não acender pontos de apagão nas ruas?

A base de interrupções é organizada por conjunto de unidades consumidoras e não necessariamente contém coordenadas de ocorrências residenciais. Um conjunto pode abranger mais de um município; um município pode conter múltiplos conjuntos. Pontos aleatórios no mapa induziriam ao erro.

### Alternativas de representação

| Nível | Segurança metodológica | Recomendação |
|---|---|---|
| Distribuidora / série de indicador por conjunto | Alta, com correspondência validada | MVP |
| Município / indicador regional oficial | Depende de fonte e denominadores | Depois da validação |
| Extrusão 3D de polígonos regionais | Requer mesma geometria da métrica | Evolução |
| Pontos de interrupção por bairro/rua | Não suportado sem geocodificação confiável | Não implementar |

### Interação

1. País / estado / distribuidora → filtros.
2. Alternar DEC, FEC, variação histórica e cobertura.
3. Explorar tempo com slider: usar períodos fechados e indicar publicação parcial.
4. Selecionar área: cards com série, limites aplicáveis, fonte e nível geográfico.
5. Alternar 2D/3D sem mudar o valor dos dados.
6. Exportar URL de análise e tabela com proveniência.

### Performance

- Pré-agregar séries temporais; geometrias simplificadas/tiles; carregamento progressivo.
- 3D desligado em dispositivo de baixa capacidade e com movimento reduzido.
- Acessibilidade: fallback 2D, legenda textual e tabela navigável por teclado.

### Experimentos a validar

- Precisão da relação conjunto ↔ município.
- Existência de indicador de continuidade oficial no nível municipal.
- Regras de generalização espacial que não escondam a incompletude.
- Diferença entre extrusão por valor absoluto e escalas normalizadas.
- Custo de GPU, tempo de render e consumo em aparelhos móveis.
