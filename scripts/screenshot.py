"""UI のスクリーンショットを撮る開発用ツール。

使い方: uv run python scripts/screenshot.py [出力ディレクトリ]
サーバ（http://127.0.0.1:8124）が起動している前提。
モバイル（iPhone 14 相当）とデスクトップの両方で主要ページを撮影する。
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8124"
PAGES = [
    ("graph", "/?topic=cot-reasoning", 3500),
    ("papers", "/papers", 800),
    ("paper_detail", "/papers/arxiv-2310.01798", 800),
    ("claim_detail", "/claims/arxiv-2303.17651-c03", 800),
]
VIEWPORTS = [
    (
        "mobile",
        {
            "viewport": {"width": 390, "height": 844},
            "device_scale_factor": 2,
            "is_mobile": True,
        },
    ),
    ("desktop", {"viewport": {"width": 1280, "height": 800}}),
]


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ronmyaku_shots")
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp_name, vp in VIEWPORTS:
            ctx = browser.new_context(**vp)
            page = ctx.new_page()
            for name, path, settle_ms in PAGES:
                page.goto(BASE + path, wait_until="networkidle")
                page.wait_for_timeout(settle_ms)  # グラフレイアウトの静定を待つ
                dst = out_dir / f"{name}_{vp_name}.png"
                page.screenshot(path=str(dst))
                print(dst)
            ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
