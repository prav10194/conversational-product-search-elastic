const results = document.getElementById("results");
const input = document.getElementById("input");

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // textContent: never inject HTML from data
  return e;
}

function showOnly(...nodes) {
  results.replaceChildren(...nodes); // each search replaces the previous results
  results.scrollTop = 0;
}

function productCard(p) {
  const c = el("div", "card");
  c.appendChild(el("div", "name", p.name));
  c.appendChild(el("div", "meta", `${p.brand} · ${p.size} · ${p.aisle}`));
  c.appendChild(el("div", "price", `$${p.price.toFixed(2)}`));
  const tags = el("div", "tags");
  (p.diet_tags || []).forEach(t => tags.appendChild(el("span", "pill", t)));
  c.appendChild(tags);
  c.appendChild(el("div", "score", `★ ${p.rating} · score ${p._score == null ? "-" : p._score.toFixed(3)}`));
  return c;
}

function details(summary, obj) {
  const d = el("details");
  d.appendChild(el("summary", "", summary));
  d.appendChild(el("pre", "", JSON.stringify(obj, null, 2)));
  return d;
}

function renderPipeline(steps, source) {
  const panel = document.getElementById("pipeline");
  panel.replaceChildren(el("h2", "", "How your query was built"));
  panel.appendChild(el("div", `badge ${source}`, source === "claude" ? "Understood by Claude" : "Understood by built-in rules (no LLM key)"));
  steps.forEach((s, i) => {
    const box = el("div", "step");
    const head = el("div", "step-head");
    head.appendChild(el("span", "num", String(i + 1)));
    head.appendChild(el("span", "", s.title));
    box.appendChild(head);
    (s.lines || []).forEach(l => box.appendChild(el("div", "line", l)));
    if (s.code) box.appendChild(el("pre", "", JSON.stringify(s.code, null, 2)));
    panel.appendChild(box);
    if (i < steps.length - 1) panel.appendChild(el("div", "arrow", "↓"));
  });
}

async function send(text) {
  input.value = text; // keep what you searched for in the box on top
  showOnly(el("p", "hint", `Searching for "${text}"…`));
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text, store: store.value, mode: mode.value}),
    });
    const data = await res.json();
    if (!res.ok) { showOnly(el("p", "error", data.error || "Something went wrong.")); return; }
    const parts = [el("div", "reply", data.reply)];
    if (data.products.length) {
      const grid = el("div", "grid");
      data.products.forEach(p => grid.appendChild(productCard(p)));
      parts.push(grid);
    }
    if (data.brands.length) {
      parts.push(el("div", "facets", "Brands: " + data.brands.map(b => `${b.brand} (${b.count})`).join(", ")));
    }
    parts.push(el("div", "under", `understood by ${data.understanding} · ${data.mode || "no search"} · ${data.took_ms} ms`));
    showOnly(...parts);
    renderPipeline(data.pipeline || [], data.understanding);
  } catch (e) {
    showOnly(el("p", "error", "Can't reach the server."));
  }
}

document.getElementById("composer").addEventListener("submit", e => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  send(text);
});
document.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => send(b.textContent)));

fetch("/api/health").then(r => r.json()).then(h => {
  const dot = document.getElementById("health");
  dot.classList.add(h.ok ? "ok" : "bad");
  dot.title = h.ok ? `Elasticsearch ${h.elasticsearch} · Claude ${h.claude ? "on" : "off (rules)"}` : h.error;
}).catch(() => document.getElementById("health").classList.add("bad"));
