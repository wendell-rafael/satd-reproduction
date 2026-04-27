"""
RQ2 — Por que o SATD é introduzido? (Experiência do desenvolvedor)
===================================================================
Reproduz parcialmente a Tabela IV do artigo Potdar & Shihab (2014) usando o
dataset PENTACET, correlacionando CONTRIBUTORCOUNT (proxy de experiência da
equipe) com a densidade de SATD por projeto.

Limitação conhecida: O PENTACET não possui git blame por linha de comentário.
A análise é feita ao nível de projeto (experiência média da equipe vs. densidade
de SATD), não ao nível de commit individual como no artigo original.

Saídas:
  results/rq2_contributor_vs_satd.csv  — correlação por projeto
  results/rq2_scatter.png              — gráfico de dispersão
"""

import os
import sys
import urllib.request
from typing import Dict

import pandas as pd
from scipy import stats

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False
    print("[WARN] matplotlib/seaborn não disponíveis; gráfico não será gerado.")

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

PENTACET_LOCAL = os.path.join(DATA_DIR, "pentacet_satd_sample.tsv")

# URL do arquivo TSV principal do PENTACET no GitHub
PENTACET_URL = (
    "https://raw.githubusercontent.com/M3SOulu/pentacet/main/satd_comments.tsv"
)
PENTACET_ALT_URLS = [
    "https://raw.githubusercontent.com/M3SOulu/pentacet/master/satd_comments.tsv",
    "https://raw.githubusercontent.com/M3SOulu/pentacet/main/data/satd_comments.tsv",
    "https://raw.githubusercontent.com/M3SOulu/pentacet/master/data/satd_comments.tsv",
]

# Colunas esperadas do PENTACET
COL_COMMENT = "COMMENTCONTENT"
COL_SATD_AFFLICTION = "SATDAFFLICTION"
COL_SATD_FEATURE = "SATDFEATURE"
COL_CONTRIBUTOR = "CONTRIBUTORCOUNT"
COL_LOC = "PROJECTLOC"
COL_PROJECT = "PROJECTID"


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)


def download_pentacet(force: bool = False) -> str:
    """
    Tenta baixar o arquivo TSV do PENTACET do GitHub.

    Retorna o caminho local. Raises FileNotFoundError se falhar e não existir local.
    """
    if os.path.exists(PENTACET_LOCAL) and not force:
        print(f"[INFO] Usando arquivo local: {PENTACET_LOCAL}")
        return PENTACET_LOCAL

    for url in [PENTACET_URL] + PENTACET_ALT_URLS:
        try:
            print(f"[INFO] Tentando baixar PENTACET de: {url}")
            urllib.request.urlretrieve(url, PENTACET_LOCAL)
            print(f"[INFO] PENTACET baixado e salvo em: {PENTACET_LOCAL}")
            return PENTACET_LOCAL
        except Exception as exc:
            print(f"[WARN] Falha: {exc}")

    raise FileNotFoundError(
        "Não foi possível baixar o PENTACET. "
        "Baixe manualmente de https://github.com/M3SOulu/pentacet e salve em: "
        f"{PENTACET_LOCAL}"
    )


def load_pentacet(path: str) -> pd.DataFrame:
    """Carrega o TSV do PENTACET."""
    try:
        df = pd.read_csv(path, sep="\t", low_memory=False)
    except Exception:
        # Tenta com separador genérico
        df = pd.read_csv(path, sep=None, engine="python", low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    print(f"[INFO] PENTACET carregado: {len(df)} linhas, colunas: {list(df.columns)}")
    return df


def _find_column(df: pd.DataFrame, *candidates):
    """Busca a primeira coluna que corresponda a qualquer candidato (case-insensitive)."""
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]
    return None


# ---------------------------------------------------------------------------
# Análise RQ2
# ---------------------------------------------------------------------------


def build_project_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa instâncias por projeto e calcula:
      - n_comments: total de comentários
      - n_satd: total de comentários SATD
      - pct_satd: % de comentários SATD
      - contributor_count: número de contribuidores (média do grupo)
      - project_loc: LOC do projeto (média do grupo)
    """
    proj_col = _find_column(df, COL_PROJECT, "projectid", "project_id", "project")
    satd_col = _find_column(
        df, COL_SATD_AFFLICTION, "satdaffliction", "is_satd", "satd", "class"
    )
    contrib_col = _find_column(
        df, COL_CONTRIBUTOR, "contributorcount", "contributors", "team_size"
    )
    loc_col = _find_column(df, COL_LOC, "projectloc", "loc", "project_loc")

    if proj_col is None:
        raise ValueError(
            "Coluna de identificação de projeto não encontrada. "
            f"Colunas disponíveis: {list(df.columns)}"
        )
    if satd_col is None:
        raise ValueError(
            "Coluna de rótulo SATD não encontrada. "
            f"Colunas disponíveis: {list(df.columns)}"
        )
    if contrib_col is None:
        print("[WARN] Coluna CONTRIBUTORCOUNT não encontrada; análise de correlação limitada.")

    # Determina se cada linha é SATD
    satd_vals = df[satd_col]
    if pd.api.types.is_string_dtype(satd_vals) or satd_vals.dtype == object:
        is_satd = satd_vals.fillna("").astype(str).str.strip().str.upper().isin(
            ["SATD", "1", "YES", "TRUE", "POSITIVE"]
        )
    else:
        is_satd = satd_vals.astype(bool)

    df = df.copy()
    df["_is_satd"] = is_satd

    # Build per-project aggregates step by step to avoid multi-level column issues
    base = (
        df.groupby(proj_col)["_is_satd"]
        .agg(n_satd="sum", n_comments="count")
        .reset_index()
        .rename(columns={proj_col: "project"})
    )

    extra_cols: Dict[str, str] = {}  # original_col -> friendly_name
    if contrib_col is not None:
        extra_cols[contrib_col] = "contributor_count"
    if loc_col is not None:
        extra_cols[loc_col] = "project_loc"

    if extra_cols:
        extra_agg = {col: "first" for col in extra_cols}
        extra = (
            df.groupby(proj_col)
            .agg(extra_agg)
            .reset_index()
            .rename(columns={proj_col: "project", **extra_cols})
        )
        grouped = base.merge(extra, on="project", how="left")
    else:
        grouped = base

    grouped["pct_satd"] = grouped.apply(
        lambda r: round(100 * r["n_satd"] / r["n_comments"], 4)
        if r["n_comments"] > 0
        else 0.0,
        axis=1,
    )

    return grouped


def compute_spearman(summary: pd.DataFrame):
    """
    Calcula a correlação de Spearman entre contributor_count e pct_satd.
    Retorna (rho, p_value) ou (None, None) se a coluna não existir.
    """
    if "contributor_count" not in summary.columns:
        print("[WARN] Coluna contributor_count não disponível para correlação.")
        return None, None

    valid = summary.dropna(subset=["contributor_count", "pct_satd"])
    if len(valid) < 3:
        print("[WARN] Dados insuficientes para calcular correlação de Spearman.")
        return None, None

    rho, p = stats.spearmanr(valid["contributor_count"], valid["pct_satd"])
    return rho, p


def plot_scatter(summary: pd.DataFrame, output_path: str):
    """Gera o gráfico de dispersão: contributor_count vs. pct_satd."""
    if not HAS_PLOT:
        print("[WARN] Gráfico não gerado (matplotlib indisponível).")
        return

    if "contributor_count" not in summary.columns:
        print("[WARN] Coluna contributor_count ausente; gráfico não gerado.")
        return

    valid = summary.dropna(subset=["contributor_count", "pct_satd"])

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.scatterplot(
        data=valid,
        x="contributor_count",
        y="pct_satd",
        alpha=0.7,
        ax=ax,
    )
    ax.set_xlabel("Número de Contribuidores (proxy de experiência da equipe)")
    ax.set_ylabel("% de Comentários SATD")
    ax.set_title("RQ2 — Experiência da equipe vs. Densidade de SATD\n(por projeto)")

    # Linha de tendência
    if len(valid) >= 3:
        slope, intercept, *_ = stats.linregress(
            valid["contributor_count"], valid["pct_satd"]
        )
        x_range = pd.Series(
            [valid["contributor_count"].min(), valid["contributor_count"].max()]
        )
        ax.plot(x_range, slope * x_range + intercept, "r--", label="Tendência linear")
        ax.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"[RQ2] Gráfico salvo em: {output_path}")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main():
    ensure_dirs()

    # 1. Obter dados
    try:
        tsv_path = download_pentacet()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    # 2. Carregar dados
    df = load_pentacet(tsv_path)

    # 3. Resumo por projeto
    try:
        summary = build_project_summary(df)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    # 4. Salvar CSV
    out_csv = os.path.join(RESULTS_DIR, "rq2_contributor_vs_satd.csv")
    summary.to_csv(out_csv, index=False)
    print(f"\n[RQ2] Resumo por projeto salvo em: {out_csv}")
    print(summary.head(20).to_string(index=False))

    # 5. Correlação de Spearman
    rho, p = compute_spearman(summary)
    if rho is not None:
        print(
            f"\n[RQ2] Correlação de Spearman (contributor_count vs. pct_satd): "
            f"rho={rho:.4f}, p={p:.4f}"
        )
        significance = "significativa" if p < 0.05 else "não significativa"
        print(f"[RQ2] Correlação {significance} (α=0.05)")

    # 6. Gráfico
    out_png = os.path.join(RESULTS_DIR, "rq2_scatter.png")
    plot_scatter(summary, out_png)


if __name__ == "__main__":
    main()
