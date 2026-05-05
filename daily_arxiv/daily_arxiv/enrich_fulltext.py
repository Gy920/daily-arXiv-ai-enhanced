#!/usr/bin/env python3
"""Enrich crawled arXiv JSONL records with text extracted from arXiv source."""

import argparse
import gzip
import io
import json
import os
import re
import sys
import tarfile
from pathlib import Path
from typing import Optional

import requests


DEFAULT_MAX_CHARS = 12000
REQUEST_TIMEOUT = 90


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to the crawled JSONL file")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=int(os.environ.get("FULL_TEXT_MAX_CHARS", DEFAULT_MAX_CHARS)),
        help="Maximum extracted full-text characters per paper",
    )
    return parser.parse_args()


def load_jsonl(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def save_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def strip_latex_comments(text: str) -> str:
    # Remove unescaped percent comments line by line.
    cleaned = []
    for line in text.splitlines():
        cleaned.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(cleaned)


def remove_latex_preamble(text: str) -> str:
    begin = re.search(r"\\begin\{document\}", text)
    end = re.search(r"\\end\{document\}", text)
    if begin:
        text = text[begin.end() :]
    if end:
        text = text[: end.start()]
    return text


def remove_latex_environments(text: str) -> str:
    drop_envs = (
        "figure",
        "figure*",
        "table",
        "table*",
        "algorithm",
        "algorithm*",
        "equation",
        "equation*",
        "align",
        "align*",
        "tikzpicture",
    )
    for env in drop_envs:
        pattern = rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}"
        text = re.sub(pattern, " ", text, flags=re.DOTALL)
    return text


def latex_to_text(text: str) -> str:
    text = strip_latex_comments(text)
    text = remove_latex_preamble(text)
    text = remove_latex_environments(text)
    text = re.sub(r"\\(section|subsection|subsubsection|paragraph|subparagraph)\*?\{([^{}]+)\}", r"\n\n\2\n", text)
    text = re.sub(r"\\(title|caption|author|date|label|ref|cite|citep|citet|footnote)\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r" \2 ", text)
    text = re.sub(r"\\(textbf|textit|emph|texttt|underline)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\[#$%&_^~]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def score_tex_name(name: str) -> int:
    lower = name.lower()
    score = 0
    if lower.endswith(".tex"):
        score += 10
    if Path(lower).name in {"main.tex", "paper.tex", "article.tex"}:
        score += 30
    if "appendix" in lower or "supp" in lower:
        score -= 20
    if "main" in lower:
        score += 10
    return score


def extract_tex_files(blob: bytes) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile() or not member.name.endswith(".tex"):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                files.append((member.name, extracted.read().decode("utf-8", errors="ignore")))
            return files
    except tarfile.TarError:
        pass

    try:
        text = gzip.decompress(blob).decode("utf-8", errors="ignore")
        return [("source.tex", text)]
    except OSError:
        return []


def expand_inputs(main_text: str, tex_by_name: dict[str, str]) -> str:
    def replace_input(match: re.Match) -> str:
        raw_name = match.group(2).strip()
        candidates = [raw_name, f"{raw_name}.tex"]
        for name in list(tex_by_name):
            if name in candidates or name.endswith("/" + candidates[0]) or name.endswith("/" + candidates[-1]):
                return "\n" + tex_by_name[name] + "\n"
        return " "

    pattern = r"\\(input|include)\{([^{}]+)\}"
    previous = None
    expanded = main_text
    for _ in range(4):
        if expanded == previous:
            break
        previous = expanded
        expanded = re.sub(pattern, replace_input, expanded)
    return expanded


def select_full_latex(tex_files: list[tuple[str, str]]) -> Optional[tuple[str, str]]:
    if not tex_files:
        return None

    tex_by_name = dict(tex_files)
    main_candidates = sorted(
        tex_files,
        key=lambda item: (score_tex_name(item[0]), len(item[1])),
        reverse=True,
    )

    for name, text in main_candidates:
        if "\\begin{document}" in text or "\\input{" in text or "\\include{" in text:
            return name, expand_inputs(text, tex_by_name)

    combined = "\n\n".join(text for name, text in sorted(tex_files))
    return "combined_tex_sources", combined


def fetch_full_text(arxiv_id: str, max_chars: int) -> tuple[str, str]:
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    tex_files = extract_tex_files(response.content)
    selected = select_full_latex(tex_files)
    if selected is None:
        return "", "no_tex_source"

    source_name, latex = selected
    text = latex_to_text(latex)
    if max_chars > 0:
        text = text[:max_chars]
    return text, source_name


def main() -> int:
    args = parse_args()
    rows = load_jsonl(args.data)
    enriched = 0

    for row in rows:
        arxiv_id = row.get("id")
        if not arxiv_id:
            continue
        try:
            full_text, source_name = fetch_full_text(arxiv_id, args.max_chars)
            if full_text:
                row["full_text"] = full_text
                row["full_text_source"] = source_name
                enriched += 1
                print(
                    f"Enriched {arxiv_id}: {len(full_text)} chars from {source_name}",
                    file=sys.stderr,
                )
            else:
                print(f"No full text extracted for {arxiv_id}: {source_name}", file=sys.stderr)
        except Exception as exc:
            row["full_text_error"] = str(exc)[:300]
            print(f"Failed to enrich {arxiv_id}: {exc}", file=sys.stderr)

    save_jsonl(args.data, rows)
    print(f"Full-text enrichment completed: {enriched}/{len(rows)} papers", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
