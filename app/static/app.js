/* 論脈 RONMYAKU — フロントエンド（ビルドレス・素のJS）
   - 論文一覧の絞り込み（/papers）
   - 脈図の描画・ボトムシート（/）
   脈図のレイアウトはドメイン構造そのもの: 論文カラム（左→右が時系列）×
   クレームカードの縦積み。座標はここで決定論的に計算する（物理レイアウト不使用）。
   DOM 生成は textContent ベース（innerHTML にデータを入れない）。 */
(() => {
  "use strict";

  /* ---------- 汎用 ---------- */
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  /* ---------- 論文一覧の絞り込み ---------- */
  const filter = document.getElementById("paper-filter");
  if (filter) {
    filter.addEventListener("input", () => {
      const q = filter.value.trim().toLowerCase();
      document.querySelectorAll("#paper-cards .card").forEach((card) => {
        card.hidden = q !== "" && !card.dataset.haystack.includes(q);
      });
    });
  }

  /* ---------- 脈図 ---------- */
  const cyEl = document.getElementById("cy");
  if (!cyEl || typeof cytoscape === "undefined") return;

  const boot = JSON.parse(document.getElementById("bootstrap").textContent);
  const focusId = new URLSearchParams(location.search).get("focus");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const REL_COLORS = {
    supports: "#3fbc7e",
    contradicts: "#e85950",
    same_as: "#5b93ea",
    extends: "#9aa1ab",
  };
  const REL_STYLES = { same_as: "dashed", extends: "dotted" };
  const CONF_WIDTHS = { high: 3.2, medium: 2.4, low: 1.6 };

  // カラムレイアウトの寸法（クレームカードの座標計算に使う）
  const CARD_W = 200;
  const CARD_H = 68;
  const ROW_H = CARD_H + 26;
  const COL_W = CARD_W + 110;

  const sheet = document.getElementById("sheet");
  const sheetBody = document.getElementById("sheet-body");
  const backdrop = document.getElementById("sheet-backdrop");
  const openSheet = () => {
    sheet.hidden = false;
    backdrop.hidden = false;
    requestAnimationFrame(() => sheet.classList.add("is-open"));
  };
  const closeSheet = () => {
    sheet.classList.remove("is-open");
    backdrop.hidden = true;
    setTimeout(() => { sheet.hidden = true; }, reducedMotion ? 0 : 220);
  };
  document.getElementById("sheet-close").addEventListener("click", closeSheet);
  backdrop.addEventListener("click", closeSheet);

  const params = new URLSearchParams();
  if (boot.questionId) params.set("question", boot.questionId);
  else if (boot.initialTopic) params.set("topic", boot.initialTopic);
  const url = "/api/graph" + (params.size ? "?" + params.toString() : "");
  fetch(url)
    .then((r) => r.json())
    .then(init)
    .catch(() => {
      const empty = document.getElementById("graph-empty");
      empty.querySelector(".graph-empty__title").textContent = "グラフデータを取得できませんでした";
      empty.hidden = false;
    });

  // 日本語はスペースが無く Cytoscape の text-wrap では折り返せないため、
  // 全角=1 / 半角=0.55 の見なし幅で行を組み、\n を挿入して手動で折り返す
  function wrapLabel(text, unitsPerLine, maxLines) {
    const lines = [];
    let line = "";
    let width = 0;
    for (const ch of text) {
      const w = ch.charCodeAt(0) > 0x2000 ? 1 : 0.55;
      if (width + w > unitsPerLine && line !== "") {
        lines.push(line);
        if (lines.length === maxLines) return lines.join("\n").slice(0, -1) + "…";
        line = "";
        width = 0;
      }
      line += ch;
      width += w;
    }
    if (line) lines.push(line);
    return lines.join("\n");
  }

  function init(data) {
    if (data.meta.node_count === 0) {
      document.getElementById("graph-empty").hidden = false;
      return;
    }

    // preset layout: クレームカードだけ座標を持ち、論文（親）は子から自動算出される
    const positions = {};
    for (const n of data.elements.nodes) {
      if (n.data.parent !== undefined) {
        positions[n.data.id] = { x: n.data.order * COL_W, y: n.data.seq * ROW_H };
        n.data.label = wrapLabel(n.data.summary, 15, 3);
      }
    }

    const cy = cytoscape({
      container: cyEl,
      elements: data.elements,
      autoungrabify: true,
      style: [
        {
          // クレームカード
          selector: "node:childless",
          style: {
            shape: "round-rectangle",
            width: CARD_W,
            height: CARD_H,
            "background-color": "#2a3140",
            "border-width": 1.2,
            "border-color": "#46516a",
            label: "data(label)",
            "font-family": "Hiragino Sans, Noto Sans JP, sans-serif",
            "font-size": 11,
            color: "#dfe4ec",
            "text-wrap": "wrap",
            "text-max-width": CARD_W - 22,
            "text-valign": "center",
            "text-halign": "center",
          },
        },
        {
          // 問いレンズ時: stance で枠色（肯定=緑 / 否定=赤 / 条件付き=琥珀）
          selector: "node:childless[stance]",
          style: {
            "border-width": 2.5,
            "border-color": (n) =>
              ({ affirms: "#3fbc7e", denies: "#e85950", qualifies: "#d99a2b" })[n.data("stance")] ||
              "#46516a",
          },
        },
        {
          selector: "node:childless:selected",
          style: { "border-width": 2.5, "border-color": "#ffffff", "background-color": "#333c50" },
        },
        {
          // 論文カラム（compound 親）
          selector: "node:parent",
          style: {
            shape: "round-rectangle",
            "background-color": (n) => `hsl(${n.data("hue")}, 35%, 32%)`,
            "background-opacity": 0.16,
            "border-width": 1.2,
            "border-color": (n) => `hsl(${n.data("hue")}, 40%, 48%)`,
            padding: 16,
            label: "data(label)",
            "font-family": "Hiragino Sans, Noto Sans JP, sans-serif",
            "font-size": 15,
            "font-weight": 700,
            color: (n) => `hsl(${n.data("hue")}, 55%, 78%)`,
            "text-valign": "top",
            "text-halign": "center",
            "text-margin-y": -10,
          },
        },
        {
          selector: "node:parent:selected",
          style: { "border-width": 2, "border-color": "#ffffff" },
        },
        {
          selector: "edge",
          style: {
            width: (e) => CONF_WIDTHS[e.data("confidence")] || 2.4,
            "line-color": (e) => REL_COLORS[e.data("type")] || "#9aa1ab",
            "line-style": (e) => REL_STYLES[e.data("type")] || "solid",
            "curve-style": "unbundled-bezier",
            "control-point-distances": (e) => edgeArc(e),
            "control-point-weights": 0.5,
            "target-arrow-shape": (e) => (e.data("type") === "same_as" ? "none" : "triangle"),
            "target-arrow-color": (e) => REL_COLORS[e.data("type")] || "#9aa1ab",
            "arrow-scale": 1.1,
            opacity: 0.95,
          },
        },
        { selector: "edge:selected", style: { opacity: 1, width: 4.5 } },
      ],
      layout: { name: "preset", positions, fit: true, padding: 28 },
    });

    // スマホでは全体フィットだと読めないため、最初のカラム（最古の論文）が
    // 読める倍率で左上から開始する。右へパンすると時系列に読み進められる
    const vw = cyEl.clientWidth;
    if (vw < 700 && !focusId) {
      const z = Math.min(1.4, vw / (COL_W + 50));
      cy.zoom(z);
      cy.pan({ x: (CARD_W / 2 + 45) * z, y: 95 * z });
    }

    // 離れたカラムを結ぶエッジは途中のカラムを避けて上に弧を描く
    function edgeArc(e) {
      const span = Math.abs(e.source().data("order") - e.target().data("order"));
      return span >= 2 ? -(span * 55) : -30;
    }

    if (focusId) {
      const node = cy.getElementById(focusId);
      if (node.nonempty()) {
        node.select();
        cy.center(node);
        cy.zoom({ level: 1.1, position: node.position() });
        showClaim(focusId);
      }
    }

    cy.on("tap", "node:childless", (e) => showClaim(e.target.id()));
    cy.on("tap", "node:parent", (e) => {
      // カラム余白（見出し含む）のタップで論文詳細へ
      location.href = "/papers/" + encodeURIComponent(e.target.id());
    });
    cy.on("tap", "edge", (e) => showRelation(cy, e.target.data()));
    cy.on("tap", (e) => { if (e.target === cy) closeSheet(); });

    document.getElementById("fab-fit").addEventListener("click", () => cy.fit(undefined, 28));
  }

  /* ---------- シート描画 ---------- */
  function showClaim(claimId) {
    fetch("/api/claims/" + encodeURIComponent(claimId))
      .then((r) => r.json())
      .then((c) => {
        sheetBody.replaceChildren(...claimFragment(c));
        openSheet();
        sheet.scrollTop = 0;
      });
  }

  function claimFragment(c) {
    const out = [];

    const line = el("p", "claimline");
    line.append(
      el("span", "badge badge--" + c.kind, boot.kindLabels[c.kind] || c.kind),
      el("span", "badge badge--conf", "確度 " + (boot.confidenceLabels[c.confidence] || c.confidence)),
    );
    out.push(line);

    const title = el("h2", "card__title");
    const titleLink = el("a", "", c.summary_ja);
    titleLink.href = "/claims/" + encodeURIComponent(c.id);
    title.append(titleLink);
    out.push(title);

    const paperLine = el("p", "sheet__paper");
    const paperLink = el("a", "", c.paper.title);
    paperLink.href = "/papers/" + encodeURIComponent(c.paper.id);
    paperLine.append(paperLink);
    out.push(paperLine);

    const quote = el("blockquote", "quote", c.quote + " ");
    quote.append(el("cite", "", "§" + c.evidence.section + (c.evidence.pages ? " · p." + c.evidence.pages : "")));
    out.push(quote);

    if (c.evidence.conditions) out.push(el("p", "confnote", "条件: " + c.evidence.conditions));
    if (c.evidence.metrics.length) {
      const m = c.evidence.metrics[0];
      const rest = c.evidence.metrics.length > 1 ? ` 他${c.evidence.metrics.length - 1}件` : "";
      out.push(el("p", "confnote", `結果: ${m.name} ${m.value}` + (m.baseline ? `（baseline ${m.baseline}）` : "") + rest));
    }

    if (c.questions && c.questions.length) {
      out.push(el("p", "sheet__kicker", "この主張が答える問い"));
      const qlist = el("ul", "answers");
      for (const ql of c.questions) {
        const item = el("li", "answer" + (ql.stance ? " answer--" + ql.stance : ""));
        item.append(el("p", "answer__q", ql.text_ja));
        const ans = el("p", "answer__text");
        if (ql.stance) ans.append(el("span", "answer__stance", boot.stanceLabels[ql.stance] || ql.stance));
        ans.append(document.createTextNode(ql.answer_ja));
        item.append(ans);
        qlist.append(item);
      }
      out.push(qlist);
    }

    if (c.relations.length) {
      out.push(el("p", "sheet__kicker", "関係 " + c.relations.length + "件"));
      const list = el("ul", "rels");
      for (const r of c.relations) {
        const item = el("li", "rel rel--" + r.type);
        item.append(el("span", "rel__type", (boot.relationLabels[r.type] || r.type) + (r.direction === "out" ? "する" : "される")));
        const link = el("a", "", r.other.summary_ja);
        link.href = "/claims/" + encodeURIComponent(r.other.claim_id);
        item.append(link);
        item.append(el("p", "rel__rationale", r.rationale_ja));
        list.append(item);
      }
      out.push(list);
    } else {
      out.push(el("p", "sheet__kicker", "まだ他の論文と接続していません"));
    }
    return out;
  }

  function showRelation(cy, d) {
    const from = cy.getElementById(d.source).data();
    const to = cy.getElementById(d.target).data();
    const out = [];

    const line = el("p", "claimline");
    line.append(
      el("span", "badge badge--rel-" + d.type, boot.relationLabels[d.type] || d.type),
      el("span", "badge badge--conf", "確度 " + (boot.confidenceLabels[d.confidence] || d.confidence)),
    );
    out.push(line);

    const list = el("ul", "rels");
    for (const [node, label] of [[from, "From"], [to, "To"]]) {
      const item = el("li", "rel rel--" + d.type);
      item.append(el("span", "rel__type", label));
      const link = el("a", "", node.summary);
      link.href = "/claims/" + encodeURIComponent(node.id);
      item.append(link, el("p", "rel__paper", node.paper_title));
      list.append(item);
    }
    out.push(list);
    out.push(el("p", "rel__rationale", d.rationale));

    sheetBody.replaceChildren(...out);
    openSheet();
  }
})();
