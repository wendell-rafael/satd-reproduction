"""
RQ3 — Quanto SATD é removido? (Análise de evolução entre releases)
===================================================================
Reproduz as Tabelas VII, VIII e IX do artigo Potdar & Shihab (2014):
taxa de remoção de SATD entre releases consecutivas nos três projetos originais.

Esta análise requer clonar os repositórios e verificar a permanência dos
comentários SATD identificados entre releases.

Projetos e releases analisados:
  - Eclipse:  3.0 → 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7
  - ArgoUML:  0.20 → 0.22 → 0.24 → 0.26 → 0.28 → 0.30 → 0.32 → 0.34
  - Apache httpd: 1.3.x → 2.0.x → 2.2.x → 2.4.x

Saídas:
  results/rq3_eclipse_removal.csv
  results/rq3_argouml_removal.csv
  results/rq3_apache_removal.csv
"""

import os
import re
import sys
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
REPOS_DIR = os.path.join(DATA_DIR, "repos")

# Projetos: (nome, url_git, [(tag_inicial, tag_final), ...])
PROJECTS = {
    "eclipse": {
        "url": "https://github.com/eclipse-platform/eclipse.platform",
        # Eclipse is a Java project
        "extensions": (".java",),
        "releases": [
            ("R3_0", "R3_1"),
            ("R3_1", "R3_2"),
            ("R3_2", "R3_3"),
            ("R3_3", "R3_4"),
            ("R3_4", "R3_5"),
            ("R3_5", "R3_6"),
            ("R3_6", "R3_7"),
        ],
    },
    "argouml": {
        "url": "https://github.com/argouml-tigris-org/argouml",
        # ArgoUML is a Java project
        "extensions": (".java",),
        "releases": [
            ("v0_20", "v0_22"),
            ("v0_22", "v0_24"),
            ("v0_24", "v0_26"),
            ("v0_26", "v0_28"),
            ("v0_28", "v0_30"),
            ("v0_30", "v0_32"),
            ("v0_32", "v0_34"),
        ],
    },
    "apache": {
        "url": "https://github.com/apache/httpd",
        # Apache httpd is a C project
        "extensions": (".c", ".h"),
        "releases": [
            ("2.0.65", "2.2.34"),
            ("2.2.34", "2.4.0"),
            ("2.4.0", "2.4.58"),
        ],
    },
}

# Os 62 padrões do artigo original (importados do rq1_analysis)
sys.path.insert(0, os.path.dirname(__file__))
try:
    from rq1_analysis import SATD_PATTERNS
except ImportError:
    SATD_PATTERNS = [
        "hack", "fixme", "todo", "workaround", "is problematic",
        "this isn't very solid", "probably a bug", "ugly", "kludge",
        "bandaid", "quick fix", "temporary", "not sure", "revisit",
        "needs work", "broken", "bad", "dirty", "incomplete",
        "not implemented", "hardcoded", "placeholder", "stub",
        "technical debt", "refactor",
    ]

_PATTERN_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in SATD_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(REPOS_DIR, exist_ok=True)


def _run(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Executa um comando shell e retorna o resultado."""
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=check
    )


def clone_or_update_repo(name: str, url: str) -> str:
    """
    Clona o repositório em REPOS_DIR/<name> se ainda não existir.
    Retorna o caminho local do repositório.
    """
    repo_path = os.path.join(REPOS_DIR, name)
    if os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"[INFO] Repositório já existe: {repo_path}; atualizando tags...")
        _run(["git", "fetch", "--tags", "--quiet"], cwd=repo_path, check=False)
    else:
        print(f"[INFO] Clonando {url} em {repo_path}...")
        _run(["git", "clone", "--quiet", url, repo_path])
        _run(["git", "fetch", "--tags", "--quiet"], cwd=repo_path, check=False)
    return repo_path


def list_tags(repo_path: str) -> List[str]:
    """Lista todas as tags do repositório."""
    result = _run(["git", "tag", "--list"], cwd=repo_path)
    return [t.strip() for t in result.stdout.splitlines() if t.strip()]


def resolve_tag(repo_path: str, tag_hint: str) -> Optional[str]:
    """
    Tenta resolver um hint de tag para uma tag existente no repositório.
    Aceita correspondências parciais (prefixo).
    """
    tags = list_tags(repo_path)
    # Correspondência exata
    if tag_hint in tags:
        return tag_hint
    # Correspondência case-insensitive
    for t in tags:
        if t.lower() == tag_hint.lower():
            return t
    # Correspondência parcial (prefixo)
    matches = [t for t in tags if t.startswith(tag_hint) or tag_hint in t]
    if matches:
        return sorted(matches)[0]
    return None


def extract_satd_comments_at_tag(
    repo_path: str, tag: str, extensions: Tuple[str, ...] = (".java", ".c", ".h")
) -> List[Dict]:
    """
    Para um determinado tag/commit, lista todos os comentários de código-fonte
    que contêm padrões SATD.

    Usa `git ls-tree` + `git show` para percorrer os arquivos sem fazer checkout.
    Retorna lista de dicts: {file, line_no, text}.
    """
    resolved = resolve_tag(repo_path, tag)
    if resolved is None:
        print(f"[WARN] Tag não encontrada para '{tag}' em {repo_path}. Pulando.")
        return []

    print(f"[INFO] Extraindo SATD em tag {resolved}...")

    # Lista arquivos com extensões relevantes nesse commit
    result = _run(
        ["git", "ls-tree", "-r", "--name-only", resolved],
        cwd=repo_path,
        check=False,
    )
    if result.returncode != 0:
        print(f"[WARN] Erro ao listar árvore para {resolved}: {result.stderr}")
        return []

    files = [
        f.strip()
        for f in result.stdout.splitlines()
        if f.strip().endswith(extensions)
    ]

    satd_comments = []
    for filepath in files:
        content_result = _run(
            ["git", "show", f"{resolved}:{filepath}"],
            cwd=repo_path,
            check=False,
        )
        if content_result.returncode != 0:
            continue

        content = content_result.stdout
        lines = content.splitlines()
        for line_no, line in enumerate(lines, start=1):
            if _PATTERN_RE.search(line):
                satd_comments.append(
                    {
                        "file": filepath,
                        "line_no": line_no,
                        "text": line.strip(),
                    }
                )

    print(f"[INFO] Encontrados {len(satd_comments)} comentários SATD em {resolved}")
    return satd_comments


def compute_removal(
    satd_from: List[Dict],
    satd_to: List[Dict],
) -> Tuple[int, float]:
    """
    Calcula o número e a taxa de remoção de SATD entre duas releases.

    Considera que um comentário SATD foi removido se o texto exato não aparece
    na release seguinte no mesmo arquivo (match por arquivo + texto normalizado).

    Retorna (removed_count, removal_rate_pct).
    """
    if not satd_from:
        return 0, 0.0

    # Cria conjunto de (arquivo, texto_normalizado) para a release destino
    to_keys = {
        (d["file"], d["text"].lower().strip())
        for d in satd_to
    }

    removed = sum(
        1
        for d in satd_from
        if (d["file"], d["text"].lower().strip()) not in to_keys
    )

    rate = round(100 * removed / len(satd_from), 2)
    return removed, rate


def analyze_project(name: str, config: Dict) -> pd.DataFrame:
    """
    Analisa um projeto e calcula a taxa de remoção de SATD por par de releases.
    Retorna DataFrame com colunas: release_from, release_to, satd_from,
    satd_to, removed, removal_rate_pct.
    """
    repo_path = clone_or_update_repo(name, config["url"])
    extensions: Tuple[str, ...] = config.get("extensions", (".java", ".c", ".h"))

    rows = []
    cache: Dict[str, List[Dict]] = {}

    for tag_from, tag_to in config["releases"]:
        # Extrai SATD na release inicial (usa cache se já calculado)
        if tag_from not in cache:
            cache[tag_from] = extract_satd_comments_at_tag(
                repo_path, tag_from, extensions
            )
        satd_from = cache[tag_from]

        # Extrai SATD na release final
        if tag_to not in cache:
            cache[tag_to] = extract_satd_comments_at_tag(
                repo_path, tag_to, extensions
            )
        satd_to = cache[tag_to]

        removed, removal_rate = compute_removal(satd_from, satd_to)

        rows.append(
            {
                "release_from": tag_from,
                "release_to": tag_to,
                "satd_from": len(satd_from),
                "satd_to": len(satd_to),
                "removed": removed,
                "removal_rate_pct": removal_rate,
            }
        )
        print(
            f"[RQ3] {name}: {tag_from} → {tag_to} | "
            f"SATD inicial: {len(satd_from)}, final: {len(satd_to)}, "
            f"removido: {removed} ({removal_rate}%)"
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main():
    ensure_dirs()

    for name, config in PROJECTS.items():
        print(f"\n{'='*60}")
        print(f"[RQ3] Analisando projeto: {name.upper()}")
        print(f"{'='*60}")

        try:
            df = analyze_project(name, config)
        except Exception as exc:
            print(f"[ERROR] Falha ao analisar {name}: {exc}")
            df = pd.DataFrame(
                columns=[
                    "release_from", "release_to", "satd_from",
                    "satd_to", "removed", "removal_rate_pct",
                ]
            )

        out_path = os.path.join(RESULTS_DIR, f"rq3_{name}_removal.csv")
        df.to_csv(out_path, index=False)
        print(f"[RQ3] Resultado salvo em: {out_path}")
        if not df.empty:
            print(df.to_string(index=False))
            avg_rate = df["removal_rate_pct"].mean()
            print(f"[RQ3] Taxa média de remoção ({name}): {avg_rate:.2f}%")


if __name__ == "__main__":
    main()
