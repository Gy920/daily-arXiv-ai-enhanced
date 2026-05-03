#!/usr/bin/env python3
"""Filter crawled arXiv papers by repository-level keywords."""

import argparse
import json
import os
import re
import sys
from typing import Iterable


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to the crawled JSONL file")
    return parser.parse_args()


def parse_keywords(raw_keywords: str) -> list[str]:
    return [
        keyword.strip()
        for keyword in raw_keywords.split(",")
        if keyword.strip()
    ]


def normalize_text(value) -> str:
    if isinstance(value, list):
        return " ".join(normalize_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def searchable_text(paper: dict) -> str:
    fields: Iterable[str] = (
        "id",
        "title",
        "summary",
        "comment",
        "categories",
        "authors",
    )
    return "\n".join(normalize_text(paper.get(field, "")) for field in fields)


def keyword_matches(text: str, keyword: str) -> bool:
    # Phrase keywords such as "world model" should match as plain substrings.
    # Short acronyms should match whole tokens to avoid accidental hits.
    if len(keyword) <= 4 and re.fullmatch(r"[A-Za-z0-9.+-]+", keyword):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return keyword.lower() in text.lower()


def load_jsonl(path: str) -> list[dict]:
    papers: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                papers.append(json.loads(line))
    return papers


def save_jsonl(path: str, papers: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for paper in papers:
            f.write(json.dumps(paper, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    keywords = parse_keywords(os.environ.get("KEYWORDS", ""))

    if not os.path.exists(args.data):
        print(f"Data file not found: {args.data}", file=sys.stderr)
        return 2

    papers = load_jsonl(args.data)
    if not keywords:
        print(
            f"KEYWORDS is not set; keeping all {len(papers)} papers",
            file=sys.stderr,
        )
        return 0

    filtered = []
    seen_ids = set()
    for paper in papers:
        paper_id = paper.get("id", "")
        if paper_id in seen_ids:
            continue
        seen_ids.add(paper_id)

        text = searchable_text(paper)
        matched_keywords = [
            keyword for keyword in keywords if keyword_matches(text, keyword)
        ]
        if matched_keywords:
            paper["matched_keywords"] = matched_keywords
            filtered.append(paper)

    save_jsonl(args.data, filtered)
    print(
        f"Keyword filter kept {len(filtered)} of {len(papers)} papers "
        f"using {len(keywords)} keywords",
        file=sys.stderr,
    )
    if filtered:
        for paper in filtered[:20]:
            print(
                f"- {paper.get('id', '')}: {paper.get('title', '')} "
                f"[{', '.join(paper.get('matched_keywords', [])[:5])}]",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
