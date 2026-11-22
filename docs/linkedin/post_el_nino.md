# Post para o LinkedIn

**Imagem:** `docs/img/temperatura_6m_tendencia_3m.png`

---

🌡️ O El Niño de 2026-27 já é um dos mais fortes desde 1950 — e os dados das estações do INMET mostram o que isso pode significar para o Brasil nos próximos meses.

Nos últimos meses construí uma plataforma de dados climáticos no Databricks com mais de 26 anos de medições horárias do INMET (89,6 milhões de registros, 704 estações) cruzadas com o índice ENSO da NOAA. O gráfico abaixo é um dos resultados:

📈 O que os dados mostram
• Agosto/2026 ficou +1,5 °C acima da normal na média de 282 estações.
• Nos El Niños fortes anteriores (2009-10, 2015-16 e 2023-24), novembro a janeiro foram mais quentes que o normal. Aplicando esses análogos, a tendência é de +1,1 °C em novembro, diluindo até janeiro.
• O Norte já tem metade das estações em seca (SPI-3) e chuva em 71 % da normal; no Nordeste, os dias em onda de calor triplicaram.
• Já o Sul tende ao excesso de chuva: +29 % da normal nos últimos El Niños fortes.

⚠️ É uma tendência estatística baseada em episódios passados, não previsão do tempo. Para decisões, vale seguir os prognósticos do INMET/INPE.

🛠️ Por trás do gráfico
• Ingestão das APIs do INMET e da NOAA com Python e jobs serverless
• Arquitetura medalhão (bronze/silver/gold) no Unity Catalog, tudo como código
• Pipelines declarativos em SQL e Python, com controle de qualidade que pegou sensores com defeito (45 °C em Salvador no inverno, pluviômetros "travados" por meses)
• Índices climáticos calculados no Lakehouse: anomalias, ondas de calor com limiares locais, SPI e classificação do ENSO
• Dashboard com 5 páginas, testes e CI no GitHub

O código, a metodologia e a análise completa estão no GitHub: github.com/fredsoncabral/p_clima

Qual região você acha que vai sentir mais esse El Niño? 👇

#EngenhariaDeDados #DataEngineering #Databricks #AnaliseDeDados #ElNiño #Clima #INMET #Python #DataAnalytics

---

### Versão curta (opcional)

🌡️ El Niño muito forte + mais de 26 anos de dados do INMET: a tendência para o Brasil é de +1,1 °C acima da normal em novembro, calor e seca persistentes no Norte e no Nordeste e excesso de chuva no Sul. Construí essa análise com uma plataforma de dados no Databricks (bronze/silver/gold, SPI, ondas de calor, ENSO). Tendência estatística, não previsão do tempo. Código e metodologia: github.com/fredsoncabral/p_clima

#EngenhariaDeDados #Databricks #ElNiño #Clima
