function splitCsv(s){
  return (s || "")
    .split(",")
    .map(x => x.trim().toLowerCase())
    .filter(Boolean);
}

function setStatus(t){
  const el = document.getElementById("status");
  el.textContent = t;
}

function el(tag, cls, text){
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function renderSynthesis(syn){
  const box = document.getElementById("synthesis");
  box.innerHTML = "";
  if (!syn || syn.length === 0){
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  box.appendChild(el("h2", null, "Synthesis"));
  const ul = el("ul");
  syn.forEach(b => {
    const li = el("li");
    li.textContent = b.text;
    const cites = (b.cites || []).map(i => String(i)).join(", ");
    if (cites){
      const span = el("span", "cites", ` [${cites}]`);
      li.appendChild(span);
    }
    ul.appendChild(li);
  });
  box.appendChild(ul);
}

function renderResults(results){
  const root = document.getElementById("results");
  root.innerHTML = "";
  if (!results || results.length === 0){
    root.appendChild(el("div", "result", "No results."));
    return;
  }

  results.forEach((r, idx) => {
    const card = el("div", "result");

    const top = el("div", "top");
    const h = el("div");
    const title = el("div", "title");
    const a = document.createElement("a");
    a.href = r.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = `${idx+1}. ${r.title}`;
    title.appendChild(a);

    const meta = el("div", "meta", `${r.domain} · score ${Number(r.score).toFixed(2)}${r.published ? " · " + r.published : ""}`);

    h.appendChild(title);
    h.appendChild(meta);

    const snippet = el("div", "snippet", r.snippet || "");

    const reasons = el("div", "reasons");
    if (r.reasons && r.reasons.length){
      r.reasons.forEach(x => {
        reasons.appendChild(el("span", "pill", x));
      });
    }

    top.appendChild(h);
    card.appendChild(top);
    card.appendChild(snippet);
    if (r.reasons && r.reasons.length) card.appendChild(reasons);

    root.appendChild(card);
  });
}

async function runSearch(){
  const q = document.getElementById("q").value.trim();
  if (!q) return;

  const provider = document.getElementById("provider").value;
  const no_commerce = document.getElementById("no_commerce").checked;
  const prefer_official = document.getElementById("prefer_official").checked;
  const synthesize = document.getElementById("synthesize").checked;
  const fetch_top_n = Number(document.getElementById("fetch_top_n").value || 0);

  const recent_days_raw = document.getElementById("recent_days").value.trim();
  const prefer_recent_days = recent_days_raw ? Number(recent_days_raw) : null;

  const block_domains = splitCsv(document.getElementById("block").value);
  const allow_domains = splitCsv(document.getElementById("allow").value);

  setStatus("Searching…");

  const payload = {
    q,
    provider,
    count: 10,
    no_commerce,
    prefer_official,
    prefer_recent_days,
    block_domains,
    allow_domains,
    synthesize,
    fetch_top_n
  };

  try{
    const res = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if (!res.ok){
      const t = await res.text();
      setStatus(`Error: ${res.status}`);
      renderSynthesis([]);
      renderResults([]);
      console.error(t);
      return;
    }
    const data = await res.json();
    setStatus(`Done · ${data.results.length} results`);
    renderSynthesis(data.synthesis);
    renderResults(data.results);
  } catch (e){
    setStatus("Error: request failed");
    renderSynthesis([]);
    renderResults([]);
    console.error(e);
  }
}

document.getElementById("go").addEventListener("click", runSearch);
document.getElementById("q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runSearch();
});
