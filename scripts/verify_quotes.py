"""クレームの quote が PDF 本文に実在するかを機械検証する。

LLM 抽出の宿命として捏造引用（幻覚）が混入しうるため、quote を pdftotext の
出力と照合する。表記ゆれ（改行ハイフネーション・スモールキャップの空白・
リガチャ・記号差）に耐えるよう、両者を「英数字のみ・小文字」に正規化して
部分文字列判定する。

使い方:
    uv run python scripts/verify_quotes.py [paper_id]   # 省略時は全論文
PDF が無い arXiv 論文は自動ダウンロードを試みる。エラー時 exit 1。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.storage import load_vault


def normalize(text: str) -> str:
    """英数字のみ・小文字に正規化する（空白・ハイフン・記号の差異を吸収）。"""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold() if ch.isalnum())


def pdf_text(paper_id: str, arxiv_id: str | None) -> str | None:
    """論文 PDF のテキストを返す。無ければ arXiv からダウンロードを試みる。"""
    pdf = config.DATA_DIR / "pdfs" / f"{paper_id}.pdf"
    if not pdf.exists() and arxiv_id:
        pdf.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "curl",
                "-sL",
                "--max-time",
                "60",
                f"https://arxiv.org/pdf/{arxiv_id}",
                "-o",
                str(pdf),
            ],
            check=False,
        )
    if not pdf.exists() or pdf.stat().st_size == 0:
        return None
    result = subprocess.run(
        ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def main() -> int:
    if shutil.which("pdftotext") is None:
        print("NG: pdftotext がありません（sudo apt-get install -y poppler-utils）")
        return 1

    target = sys.argv[1] if len(sys.argv) > 1 else None
    vault = load_vault()
    papers = [p for p in vault.papers if target is None or p.id == target]
    if target and not papers:
        print(f"NG: 論文が見つかりません: {target}")
        return 1

    errors: list[str] = []
    skipped: list[str] = []
    checked = 0
    for paper in papers:
        text = pdf_text(paper.id, paper.arxiv_id)
        if text is None:
            skipped.append(f"{paper.id}: PDF が取得できないため検証スキップ")
            continue
        ntext = normalize(text)
        for claim in paper.claims:
            checked += 1
            if normalize(claim.quote) not in ntext:
                errors.append(f"{claim.id}: quote が PDF 本文に見つからない: “{claim.quote[:60]}…”")

    for msg in skipped:
        print(f"WARN: {msg}")
    if errors:
        print(f"NG: {len(errors)} 件の quote が本文と照合できず（捏造・転記ミスの疑い）")
        for msg in errors:
            print(f"  - {msg}")
        return 1
    print(
        f"OK: {checked} 件の quote すべてが PDF 本文に実在（論文 {len(papers) - len(skipped)} 本）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
