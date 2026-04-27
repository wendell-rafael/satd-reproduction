# SATD Reproduction Study

Reprodução do estudo **"An Exploratory Study on Self-Admitted Technical Debt"**
(Potdar & Shihab, ICSME 2014) usando os datasets **SATDAUG** e **PENTACET**.

---

## Visão Geral

Este repositório reproduz as três perguntas de pesquisa (RQ) do artigo original,
evitando a necessidade de minerar os repositórios do zero ao usar datasets
públicos já disponíveis.

| RQ | Pergunta | Dataset |
|----|----------|---------|
| RQ1 | Qual a quantidade de SATD nos projetos? | SATDAUG (artefato CC, status=original) |
| RQ2 | Por que o SATD é introduzido? (Experiência do dev) | PENTACET |
| RQ3 | Quanto SATD é removido? (Evolução entre releases) | Clonagem dos 3 projetos originais |

---

## Estrutura do Repositório

```
satd-reproduction/
├── data/
│   ├── satdaug_cc_original.csv       # CC do SATDAUG filtrado (apenas original)
│   └── pentacet_satd_sample.tsv      # Amostra do PENTACET
├── src/
│   ├── rq1_analysis.py               # Análise RQ1
│   ├── rq2_analysis.py               # Análise RQ2
│   └── rq3_analysis.py               # Análise RQ3
├── results/
│   ├── rq1_distribution.csv
│   ├── rq1_pattern_coverage.csv
│   ├── rq2_contributor_vs_satd.csv
│   ├── rq2_scatter.png
│   ├── rq3_eclipse_removal.csv
│   ├── rq3_argouml_removal.csv
│   └── rq3_apache_removal.csv
├── requirements.txt
└── README.md
```

---

## Instalação

```bash
pip install -r requirements.txt
```

---

## Datasets

### SATDAUG (RQ1)

- **URL**: <https://zenodo.org/records/10521909>
- **Formato**: 4 arquivos CSV (um por artefato: CC, IS, PS, CM)
- **Artefato usado**: CC (source code comments)
- **Filtro aplicado**: `status == 'original'` (remove dados aumentados sinteticamente pelo AugGPT)
- **Colunas relevantes**: `text`, `class` (SATD ou Not-SATD), `type` (C/D, DOC, TES, REQ)

O script `rq1_analysis.py` tenta baixar o arquivo automaticamente. Se o download
automático falhar, baixe manualmente o CSV do artefato CC e salve em
`data/satdaug_cc_original.csv`.

### PENTACET (RQ2)

- **URL**: <https://github.com/M3SOulu/pentacet>
- **Formato**: dump PostgreSQL ou arquivo TSV de comentários SATD
- **Colunas relevantes**: `COMMENTCONTENT`, `SATDAFFLICTION`, `SATDFEATURE`,
  `CONTRIBUTORCOUNT`, `PROJECTLOC`

O script `rq2_analysis.py` tenta baixar o TSV automaticamente. Se falhar, configure
o banco PostgreSQL conforme as instruções do repositório PENTACET, exporte os dados
em TSV e salve em `data/pentacet_satd_sample.tsv`.

---

## RQ1 — Quantidade de SATD nos projetos

**Objetivo**: Reproduzir a Tabela III do artigo — percentual de SATD nos
comentários de código-fonte.

**Passos executados pelo script**:
1. Baixa o CSV do artefato CC do SATDAUG (Zenodo)
2. Filtra apenas `status == 'original'`
3. Calcula distribuição SATD vs. Not-SATD por tipo de comentário
4. Verifica cobertura dos 62 padrões originais do artigo sobre o dataset

**Execução**:
```bash
python src/rq1_analysis.py
```

**Saídas**:
- `results/rq1_distribution.csv` — contagem e % por tipo de SATD
- `results/rq1_pattern_coverage.csv` — cobertura dos 62 padrões nos dados

**Referência (artigo original)**: 2,4% – 31,0% dos arquivos com SATD,
dependendo do projeto.

---

## RQ2 — Por que o SATD é introduzido? (Experiência do desenvolvedor)

**Objetivo**: Reproduzir parcialmente a Tabela IV do artigo — relação entre
experiência do desenvolvedor e quantidade de SATD introduzida.

**Passos executados pelo script**:
1. Carrega o TSV do PENTACET
2. Agrupa instâncias SATD por projeto
3. Usa `CONTRIBUTORCOUNT` como proxy de experiência da equipe por projeto
4. Calcula correlação de Spearman entre `CONTRIBUTORCOUNT` e `%SATD` por projeto
5. Gera scatter plot: eixo X = tamanho da equipe, eixo Y = % de comentários SATD

**Execução**:
```bash
python src/rq2_analysis.py
```

**Saídas**:
- `results/rq2_contributor_vs_satd.csv` — estatísticas por projeto
- `results/rq2_scatter.png` — gráfico de dispersão

### ⚠️ Limitação conhecida (RQ2)

O PENTACET **não possui git blame por linha de comentário**. Portanto, a análise
de RQ2 é feita **ao nível de projeto** (experiência média da equipe vs. densidade
de SATD), e não ao nível de commit individual como no artigo original. Esta
limitação deve ser considerada ao interpretar os resultados.

---

## RQ3 — Quanto SATD é removido? (Análise de evolução)

**Objetivo**: Reproduzir as Tabelas VII, VIII e IX do artigo — taxa de remoção
de SATD entre releases consecutivas.

**Projetos e releases analisados**:
| Projeto | Releases |
|---------|----------|
| Eclipse | 3.0 → 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 |
| ArgoUML | 0.20 → 0.22 → 0.24 → 0.26 → 0.28 → 0.30 → 0.32 → 0.34 |
| Apache httpd | 1.3.x → 2.0.x → 2.2.x → 2.4.x |

**Passos executados pelo script**:
1. Clona os repositórios originais
2. Extrai comentários SATD (por padrão de texto) em cada tag de release
3. Verifica permanência dos comentários entre releases (match por arquivo + texto)
4. Calcula % de SATD removido por par de releases

**Execução**:
```bash
python src/rq3_analysis.py
```

> ⚠️ **Atenção**: A RQ3 requer clonar os repositórios completos, o que pode
> demorar vários minutos dependendo da conexão.

**Saídas**:
- `results/rq3_eclipse_removal.csv`
- `results/rq3_argouml_removal.csv`
- `results/rq3_apache_removal.csv`

---

## Padrões SATD utilizados

Os 62 padrões originais de Potdar & Shihab (2014) estão definidos em
`src/rq1_analysis.py` (lista `SATD_PATTERNS`). Incluem termos como:
`hack`, `fixme`, `todo`, `workaround`, `ugly`, `kludge`, `temporary`,
`not sure`, `broken`, `refactor`, `technical debt`, entre outros.

Fonte: <http://users.encs.concordia.ca/~eshihab/data/ICSME2014/satd.html>

---

## Referências

- **Artigo original**: Potdar, A., & Shihab, E. (2014). An Exploratory Study on
  Self-Admitted Technical Debt. *ICSME 2014*.
- **SATDAUG**: Sutoyo, E., & Capiluppi, A. (2024). SATDAUG – An Augmented
  Dataset for Detecting Self-Admitted Technical Debt. *MSR 2024*.
  <https://zenodo.org/records/10521909>
- **PENTACET**: Sridharan, M., et al. (2023). PENTACET.
  <https://github.com/M3SOulu/pentacet>
