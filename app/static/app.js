/* 論脈 RONMYAKU — フロントエンド（ビルドレス・素のJS）
   - 論文一覧の絞り込み（/papers）
   - 脈図の描画・ボトムシート（/）
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
    supports: "#2fa26b",
    contradicts: "#d9463e",
    same_as: "#4c82d8",
    extends: "#8a8f98",
  };
  const REL_STYLES = { same_as: "dashed", extends: "dotted" };
  const KIND_SHAPES = {
    experimental: "ellipse",
    theoretical: "diamond",
    opinion: "round-rectangle",
  };
  const CONF_WIDTHS = { high: 3, medium: 2.2, low: 1.3 };

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

  const url = "/api/graph" + (boot.initialTopic ? "?topic=" + encodeURIComponent(boot.initialTopic) : "");
  fetch(url)
    .then((r) => r.json())
    .then(init)
    .catch(() => {
      const empty = document.getElementById("graph-empty");
      empty.querySelector(".graph-empty__title").textContent = "グラフデータを取得できませんでした";
      empty.hidden = false;
    });

  function init(data) {
    if (data.elements.nodes.length === 0) {
      document.getElementById("graph-empty").hidden = false;
      return;
    }

    const cy = cytoscape({
      container: cyEl,
      elements: data.elements,
      wheelSensitivity: 0.2,
      style: [
        {
          selector: "node",
          style: {
            shape: (n) => KIND_SHAPES[n.data("kind")] || "ellipse",
            "background-color": (n) => `hsl(${n.data("hue")}, 45%, 60%)`,
            width: 26,
            height: 26,
            label: "data(label)",
            "font-size": 9,
            color: "#e9ecf1",
            "text-outline-color": "#191c22",
            "text-outline-width": 2,
            "text-wrap": "wrap",
            "text-max-width": 110,
            "text-valign": "bottom",
            "text-margin-y": 6,
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#ffffff" },
        },
        {
          selector: "edge",
          style: {
            width: (e) => CONF_WIDTHS[e.data("confidence")] || 2,
            "line-color": (e) => REL_COLORS[e.data("type")] || "#8a8f98",
            "line-style": (e) => REL_STYLES[e.data("type")] || "solid",
            "curve-style": "bezier",
            "target-arrow-shape": (e) => (e.data("type") === "same_as" ? "none" : "triangle"),
            "target-arrow-color": (e) => REL_COLORS[e.data("type")] || "#8a8f98",
            "arrow-scale": 0.9,
            opacity: 0.9,
          },
        },
        { selector: "edge:selected", style: { opacity: 1, width: 4 } },
      ],
      layout: {
        name: data.meta.layout,
        animate: !reducedMotion,
        padding: 40,
      },
    });

    cy.one("layoutstop", () => {
      if (!focusId) return;
      const node = cy.getElementById(focusId);
      if (node.nonempty()) {
        node.select();
        cy.animate({ center: { eles: node }, zoom: 1.4, duration: reducedMotion ? 0 : 300 });
        showClaim(focusId);
      }
    });

    cy.on("tap", "node", (e) => showClaim(e.target.id()));
    cy.on("tap", "edge", (e) => showRelation(cy, e.target.data()));
    cy.on("tap", (e) => { if (e.target === cy) closeSheet(); });

    document.getElementById("fab-fit").addEventListener("click", () => cy.fit(undefined, 40));
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
      el("span", "badge badge--conf", boot.relationLabels[d.type] || d.type),
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
