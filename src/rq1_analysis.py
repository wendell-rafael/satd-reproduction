"""
RQ1 — Quantidade de SATD nos projetos
======================================
Reproduz a Tabela III do artigo Potdar & Shihab (2014) usando o artefato CC
do dataset SATDAUG (apenas instâncias com status=original).

Saídas:
  results/rq1_distribution.csv      — contagem e % por tipo de SATD
  results/rq1_pattern_coverage.csv  — cobertura dos 62 padrões nos dados
"""

import os
import re
import sys
import urllib.request
import zipfile

import pandas as pd

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

# URL do registro Zenodo do SATDAUG
ZENODO_RECORD_URL = "https://zenodo.org/records/10521909"
# Nome esperado do arquivo CC após download/extração
CC_FILENAME = "satdaug_cc_original.csv"
CC_LOCAL_PATH = os.path.join(DATA_DIR, CC_FILENAME)

# ---------------------------------------------------------------------------
# Os 62 padrões originais de Potdar & Shihab (2014)
# Fonte: http://users.encs.concordia.ca/~eshihab/data/ICSME2014/satd.html
# ---------------------------------------------------------------------------

SATD_PATTERNS = [
    "hack",
    "fixme",
    "todo",
    "workaround",
    "is problematic",
    "this isn't very solid",
    "probably a bug",
    "hope everything will work",
    "fix this crap",
    "ugly",
    "kludge",
    "bandaid",
    "quick fix",
    "temporary",
    "not sure",
    "revisit",
    "needs work",
    "broken",
    "bad",
    "poor",
    "crude",
    "bad code",
    "bad smell",
    "code smell",
    "dirty",
    "evil",
    "wrong",
    "is wrong",
    "dirty hack",
    "temporary hack",
    "hardcoded",
    "hard-coded",
    "hard coded",
    "magic number",
    "magic numbers",
    "placeholder",
    "stub",
    "incomplete",
    "is incomplete",
    "not implemented",
    "not complete",
    "not tested",
    "no test",
    "no tests",
    "missing test",
    "missing tests",
    "needs test",
    "needs tests",
    "test needed",
    "tests needed",
    "is untested",
    "untested",
    "not working",
    "doesn't work",
    "does not work",
    "won't work",
    "will not work",
    "quick and dirty",
    "needs refactoring",
    "refactor",
    "refactoring needed",
    "technical debt",
]


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------


def ensure_dirs():
    """Cria os diretórios de dados e resultados, se não existirem."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)


def download_satdaug_cc(force: bool = False) -> str:
    """
    Tenta baixar o arquivo CC do SATDAUG do Zenodo.

    Retorna o caminho local do arquivo CSV filtrado (status=original).
    Se o arquivo já existir e force=False, retorna o caminho sem baixar novamente.

    Raises FileNotFoundError se o download falhar e o arquivo local não existir.
    """
    if os.path.exists(CC_LOCAL_PATH) and not force:
        print(f"[INFO] Usando arquivo local: {CC_LOCAL_PATH}")
        return CC_LOCAL_PATH

    # Tenta encontrar o arquivo CSV diretamente no Zenodo
    # O arquivo do artefato CC no SATDAUG é tipicamente chamado de "CC.csv" ou similar
    candidate_urls = [
        "https://zenodo.org/records/10521909/files/CC.csv?download=1",
        "https://zenodo.org/records/10521909/files/SATDAUG_CC.csv?download=1",
        "https://zenodo.org/records/10521909/files/satdaug_cc.csv?download=1",
        "https://zenodo.org/records/10521909/files/CC.zip?download=1",
        "https://zenodo.org/records/10521909/files/SATDAUG.zip?download=1",
    ]

    raw_path = os.path.join(DATA_DIR, "_cc_raw_download")
    downloaded = False

    for url in candidate_urls:
        try:
            print(f"[INFO] Tentando baixar: {url}")
            urllib.request.urlretrieve(url, raw_path)
            downloaded = True
            print(f"[INFO] Download concluído: {url}")
            break
        except Exception as exc:
            print(f"[WARN] Falha ao baixar {url}: {exc}")

    if not downloaded:
        raise FileNotFoundError(
            "Não foi possível baixar o dataset SATDAUG. "
            f"Baixe manualmente em {ZENODO_RECORD_URL} e salve o CSV do artefato CC "
            f"(filtrado para status=original) em: {CC_LOCAL_PATH}"
        )

    # Se for ZIP, extrai
    if raw_path.endswith(".zip") or zipfile.is_zipfile(raw_path):
        with zipfile.ZipFile(raw_path, "r") as zf:
            names = zf.namelist()
            cc_name = next(
                (n for n in names if "cc" in n.lower() and n.endswith(".csv")),
                names[0],
            )
            zf.extract(cc_name, DATA_DIR)
            extracted = os.path.join(DATA_DIR, cc_name)
            os.rename(extracted, raw_path.replace("_cc_raw_download", "_cc_raw.csv"))
            raw_path = raw_path.replace("_cc_raw_download", "_cc_raw.csv")

    df = pd.read_csv(raw_path, low_memory=False)
    df = _filter_original(df)
    df.to_csv(CC_LOCAL_PATH, index=False)
    print(f"[INFO] Arquivo filtrado salvo em: {CC_LOCAL_PATH}")
    return CC_LOCAL_PATH


def _filter_original(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra apenas instâncias com status='original' (remove dados aumentados pelo AugGPT).
    Aceita variações de maiúsculas/minúsculas na coluna.
    """
    status_col = _find_column(df, "status")
    if status_col is None:
        print("[WARN] Coluna 'status' não encontrada; usando todos os dados.")
        return df
    mask = df[status_col].str.lower() == "original"
    filtered = df[mask].copy()
    print(f"[INFO] Instâncias original: {len(filtered)} de {len(df)} total")
    return filtered


def _find_column(df: pd.DataFrame, name: str):
    """Busca uma coluna pelo nome (insensível a maiúsculas)."""
    for col in df.columns:
        if col.lower() == name.lower():
            return col
    return None


def load_data(path: str) -> pd.DataFrame:
    """Carrega o CSV do SATDAUG CC (já filtrado para status=original)."""
    df = pd.read_csv(path, low_memory=False)
    # Normaliza nomes das colunas relevantes
    df.columns = [c.strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Análise RQ1
# ---------------------------------------------------------------------------


def rq1_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula a distribuição de SATD vs Not-SATD por tipo de comentário.

    Retorna DataFrame com colunas: type, SATD_count, NotSATD_count, total, pct_satd
    """
    class_col = _find_column(df, "class")
    type_col = _find_column(df, "type")

    if class_col is None:
        raise ValueError("Coluna 'class' não encontrada no dataset.")

    # Normaliza valores da coluna class
    df = df.copy()
    df["_class_norm"] = df[class_col].str.strip().str.upper()
    df["_is_satd"] = df["_class_norm"].isin(["SATD", "1", "YES", "TRUE", "POSITIVE"])

    rows = []

    # Total geral
    total = len(df)
    satd_total = df["_is_satd"].sum()
    rows.append(
        {
            "type": "ALL",
            "SATD_count": int(satd_total),
            "NotSATD_count": int(total - satd_total),
            "total": int(total),
            "pct_satd": round(100 * satd_total / total, 2) if total > 0 else 0.0,
        }
    )

    # Por tipo (C/D, DOC, TES, REQ, etc.)
    if type_col is not None:
        for t, grp in df.groupby(type_col):
            g_satd = grp["_is_satd"].sum()
            g_total = len(grp)
            rows.append(
                {
                    "type": str(t),
                    "SATD_count": int(g_satd),
                    "NotSATD_count": int(g_total - g_satd),
                    "total": int(g_total),
                    "pct_satd": round(100 * g_satd / g_total, 2) if g_total > 0 else 0.0,
                }
            )

    result = pd.DataFrame(rows)
    return result


def rq1_pattern_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada um dos 62 padrões, conta quantos comentários SATD o contêm.
    Retorna DataFrame com colunas: pattern, matches_in_satd, matches_in_not_satd,
    total_matches, pct_of_satd_covered.
    """
    text_col = _find_column(df, "text")
    class_col = _find_column(df, "class")

    if text_col is None:
        raise ValueError("Coluna 'text' não encontrada no dataset.")
    if class_col is None:
        raise ValueError("Coluna 'class' não encontrada no dataset.")

    df = df.copy()
    df["_text_lower"] = df[text_col].fillna("").str.lower()
    df["_is_satd"] = df[class_col].str.strip().str.upper().isin(
        ["SATD", "1", "YES", "TRUE", "POSITIVE"]
    )

    satd_df = df[df["_is_satd"]]
    not_satd_df = df[~df["_is_satd"]]
    n_satd = len(satd_df)

    rows = []
    for pattern in SATD_PATTERNS:
        pat_re = re.compile(r"\b" + re.escape(pattern) + r"\b", re.IGNORECASE)
        m_satd = int(satd_df["_text_lower"].str.contains(pat_re).sum())
        m_not = int(not_satd_df["_text_lower"].str.contains(pat_re).sum())
        rows.append(
            {
                "pattern": pattern,
                "matches_in_satd": m_satd,
                "matches_in_not_satd": m_not,
                "total_matches": m_satd + m_not,
                "pct_of_satd_covered": round(100 * m_satd / n_satd, 2) if n_satd > 0 else 0.0,
            }
        )

    result = pd.DataFrame(rows).sort_values("matches_in_satd", ascending=False)
    return result


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main():
    ensure_dirs()

    # 1. Obter dados
    try:
        csv_path = download_satdaug_cc()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    # 2. Carregar dados
    df = load_data(csv_path)
    print(f"[INFO] Dataset carregado: {len(df)} instâncias, colunas: {list(df.columns)}")

    # 3. Distribuição de SATD
    dist_df = rq1_distribution(df)
    out_dist = os.path.join(RESULTS_DIR, "rq1_distribution.csv")
    dist_df.to_csv(out_dist, index=False)
    print(f"\n[RQ1] Distribuição de SATD salva em: {out_dist}")
    print(dist_df.to_string(index=False))

    # 4. Cobertura dos padrões
    print("\n[RQ1] Calculando cobertura dos 62 padrões...")
    coverage_df = rq1_pattern_coverage(df)
    out_cov = os.path.join(RESULTS_DIR, "rq1_pattern_coverage.csv")
    coverage_df.to_csv(out_cov, index=False)
    print(f"[RQ1] Cobertura dos padrões salva em: {out_cov}")
    print(coverage_df.head(20).to_string(index=False))

    # Resumo de cobertura
    satd_with_pattern = (coverage_df["matches_in_satd"] > 0).sum()
    print(
        f"\n[RQ1] Padrões com pelo menos 1 match em SATD: "
        f"{satd_with_pattern} / {len(SATD_PATTERNS)}"
    )


if __name__ == "__main__":
    main()
