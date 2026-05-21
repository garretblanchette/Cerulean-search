/* ============================================
   Cerulean Search — App Logic v0.3.0
   Instant answers, trust indicators, dark mode
   ============================================ */

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const SOURCE_LABELS = { news:'News', reference:'Reference', wiki_community:'Fan Wiki', academic:'Academic', gov:'Official', forum:'Forum', social:'Social', video:'Video', docs:'Docs', code:'Code', blog:'Blog', commerce:'Shop', reviews:'Reviews', press:'Press Release', health:'Health', recipe:'Recipe', learning:'Learning', ai_slop:'AI Content', other:'Other' };
const state = {
  no_commerce: true, prefer_official: true, synthesize: false,
  recent: false, provider: 'brave', hasSearched: false,
  dark: false,
};
try { state.dark = localStorage.getItem('cerulean-dark') === 'true'; } catch(e) {}

let _lastSearchTime = 0, _searchInFlight = false, _debounceTimer = null;
const SEARCH_COOLDOWN_MS = 2000, DEBOUNCE_MS = 400;

const $q = document.getElementById('q');
const $go = document.getElementById('go');
const $app = document.getElementById('app');
const $filters = document.getElementById('filters');
const $status = document.getElementById('status');
const $synth = document.getElementById('synthesis');
const $results = document.getElementById('results');
const $provider = document.getElementById('provider');
const $homeBtn = document.getElementById('home-btn');
const $darkBtn = document.getElementById('dark-toggle');
const $instant = document.getElementById('instant-answer');

/* ---- Dark Mode ---- */
function applyDark(on) {
  document.documentElement.classList.toggle('dark', on);
  state.dark = on;
  try { localStorage.setItem('cerulean-dark', on); } catch(e) {}
  if ($darkBtn) $darkBtn.textContent = on ? '\u2600\uFE0F' : '\uD83C\uDF19';
}
applyDark(state.dark);
if ($darkBtn) $darkBtn.addEventListener('click', () => applyDark(!state.dark));

/* ---- Chips ---- */
document.querySelectorAll('.chip[data-key]').forEach(chip => {
  chip.addEventListener('click', () => {
    const key = chip.dataset.key;
    state[key] = !state[key];
    chip.classList.toggle('active', state[key]);
  });
});
if ($provider) $provider.addEventListener('change', () => { state.provider = $provider.value; });

/* ---- Home ---- */
if ($homeBtn) $homeBtn.addEventListener('click', () => {
  $app.classList.remove('has-results'); $app.classList.add('landing');
  $results.innerHTML = ''; $synth.innerHTML = '';
  $synth.classList.add('hidden'); $status.classList.add('hidden'); $status.textContent = '';
  if ($instant) { $instant.innerHTML = ''; $instant.classList.add('hidden'); }
  $q.value = ''; $q.focus(); state.hasSearched = false;
});

/* ---- Layout ---- */
function enterResultsMode() {
  $app.classList.remove('landing'); $app.classList.add('has-results');
  $filters.classList.remove('hidden'); state.hasSearched = true;
}
function setStatus(text, searching) {
  if (!$status) return;
  $status.classList.remove('hidden');
  if (searching) { $status.innerHTML = '<span class="spinner"></span>' + text; $status.classList.add('searching'); }
  else { $status.textContent = text; $status.classList.remove('searching'); }
}

/* ======== INSTANT ANSWERS ======== */

function tryInstantAnswer(query) {
  if (!$instant) return;
  $instant.innerHTML = ''; $instant.classList.add('hidden');
  const q = query.trim();
  const ql = q.toLowerCase();
  const math = tryMath(ql);
  if (math !== null) { showInstant('Calculator', math, '\uD83D\uDD22'); return; }
  const conv = tryConversion(ql);
  if (conv !== null) { showInstant('Conversion', conv, '\uD83D\uDCCF'); return; }
  const color = tryColor(ql);
  if (color !== null) { showInstantHTML('Color', color, '\uD83C\uDFA8'); return; }
}

function showInstant(label, text, icon) {
  $instant.innerHTML = ''; $instant.classList.remove('hidden');
  const card = el('div', 'instant-card');
  const hdr = el('div', 'instant-header');
  hdr.appendChild(el('span', 'instant-icon', icon));
  hdr.appendChild(el('span', 'instant-label', label));
  card.appendChild(hdr);
  card.appendChild(el('div', 'instant-body', text));
  $instant.appendChild(card);
}

function showInstantHTML(label, html, icon) {
  $instant.innerHTML = ''; $instant.classList.remove('hidden');
  const card = el('div', 'instant-card');
  const hdr = el('div', 'instant-header');
  hdr.appendChild(el('span', 'instant-icon', icon));
  hdr.appendChild(el('span', 'instant-label', label));
  card.appendChild(hdr);
  const body = el('div', 'instant-body');
  body.innerHTML = html;
  card.appendChild(body);
  $instant.appendChild(card);
}

function tryMath(q) {
  let expr = q.replace(/^(what is|what's|calculate|compute|eval|solve)\s+/i, '')
              .replace(/[=?]/g, '').replace(/x/g, '*').replace(/\u00f7/g, '/').replace(/\^/g, '**').trim();
  if (!/^[\d\s+\-*/().,%^]+$/.test(expr) || !/\d/.test(expr)) return null;
  expr = expr.replace(/(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)/gi, '($1/100)*$2');
  try {
    const r = Function('"use strict"; return (' + expr + ')')();
    if (typeof r === 'number' && isFinite(r)) {
      const fmt = r % 1 === 0 ? r.toLocaleString() : parseFloat(r.toFixed(8)).toLocaleString();
      return expr.replace(/\*\*/g, '^').replace(/\*/g, ' \u00d7 ') + ' = ' + fmt;
    }
  } catch(e) {}
  return null;
}

function tryConversion(q) {
  const m = q.match(/^([\d.]+)\s*(km|mi|miles?|kg|lbs?|pounds?|\u00b0?[cf]|celsius|fahrenheit|cm|inches?|in|ft|feet|m|meters?|oz|grams?|g|liters?|l|gallons?|gal)\s+(?:to|in|as)\s+(km|mi|miles?|kg|lbs?|pounds?|\u00b0?[cf]|celsius|fahrenheit|cm|inches?|in|ft|feet|m|meters?|oz|grams?|g|liters?|l|gallons?|gal)$/i);
  if (!m) return null;
  const val = parseFloat(m[1]), from = m[2].toLowerCase().replace(/s$/, ''), to = m[3].toLowerCase().replace(/s$/, '');
  const C = {
    'km-mi':v=>v*0.621371,'mi-km':v=>v*1.60934,'mile-km':v=>v*1.60934,
    'kg-lb':v=>v*2.20462,'lb-kg':v=>v*0.453592,'pound-kg':v=>v*0.453592,
    'cm-in':v=>v*0.393701,'in-cm':v=>v*2.54,'inch-cm':v=>v*2.54,
    'm-ft':v=>v*3.28084,'ft-m':v=>v*0.3048,'meter-ft':v=>v*3.28084,'feet-m':v=>v*0.3048,
    'oz-g':v=>v*28.3495,'g-oz':v=>v*0.035274,'gram-oz':v=>v*0.035274,
    'l-gal':v=>v*0.264172,'gal-l':v=>v*3.78541,'liter-gal':v=>v*0.264172,'gallon-l':v=>v*3.78541,
    'c-f':v=>v*9/5+32,'f-c':v=>(v-32)*5/9,'celsius-fahrenheit':v=>v*9/5+32,'fahrenheit-celsius':v=>(v-32)*5/9,
    '\u00b0c-\u00b0f':v=>v*9/5+32,'\u00b0f-\u00b0c':v=>(v-32)*5/9,
  };
  const fn = C[from+'-'+to];
  if (!fn) return null;
  return val + ' ' + m[2] + ' = ' + parseFloat(fn(val).toFixed(4)) + ' ' + m[3];
}

function tryColor(q) {
  const m = q.match(/^(?:color|colour|hex)\s*(#[0-9a-f]{3,8}|rgb\(.+?\))$/i);
  if (!m) return null;
  return '<div style="display:flex;align-items:center;gap:12px"><div style="width:48px;height:48px;border-radius:8px;background:'+m[1]+';border:1px solid rgba(128,128,128,0.3)"></div><code style="font-size:16px">'+m[1]+'</code></div>';
}

/* ======== TRUST INDICATORS ======== */

function getTrustSignals(score, reasons) {
  const s = [];
  for (const r of (reasons || [])) {
    if (r.startsWith('official:')) s.push({label:'Official source', cls:'trust-good'});
    else if (r.startsWith('commerce:')) s.push({label:'Commercial', cls:'trust-warn'});
    else if (r.startsWith('tracking:')) s.push({label:'Has trackers', cls:'trust-warn'});
    else if (r.startsWith('blocklisted:')) s.push({label:'Blocked', cls:'trust-bad'});
  }
  if (score >= 0.7) s.unshift({label:'High quality', cls:'trust-good'});
  else if (score >= 0.4) s.unshift({label:'Good', cls:'trust-ok'});
  else if (score >= 0) s.unshift({label:'Fair', cls:'trust-muted'});
  return s;
}

/* ======== RENDER ======== */

function renderSynthesis(syn) {
  if (!$synth) return; $synth.innerHTML = '';
  if (!syn || !syn.length) { $synth.classList.add('hidden'); return; }
  $synth.classList.remove('hidden');
  $synth.appendChild(el('h2', null, 'Summary'));
  const ul = el('ul');
  syn.forEach(b => {
    const li = el('li'); li.textContent = b.text;
    const cites = (b.cites||[]).map(String).join(', ');
    if (cites) li.appendChild(el('span','cites','['+cites+']'));
    ul.appendChild(li);
  });
  $synth.appendChild(ul);
}

function renderResults(results) {
  if (!$results) return; $results.innerHTML = '';
  if (!results || !results.length) { $results.appendChild(el('div','no-results','No results found.')); return; }
  results.forEach((r, idx) => {
    const card = el('div', 'result');
    card.style.animationDelay = (idx * 0.04) + 's';
    const citeRow = el('div', 'cite-url');
    const favicon = document.createElement('img');
    favicon.className = 'favicon';
    favicon.src = 'https://www.google.com/s2/favicons?domain=' + r.domain + '&sz=16';
    favicon.alt = '';
    favicon.width = 16; favicon.height = 16;
    favicon.onerror = function() { this.style.display = 'none'; };
    citeRow.appendChild(favicon);
    citeRow.appendChild(document.createTextNode(r.domain));
    card.appendChild(citeRow);
    const title = el('div', 'title');
    const a = document.createElement('a');
    a.href = r.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.textContent = r.title;
    title.appendChild(a);
    card.appendChild(title);
    if (r.snippet) card.appendChild(el('div', 'snippet', r.snippet));
    const meta = el('div', 'meta-row');
    getTrustSignals(r.score, r.reasons).forEach(sig => {
      meta.appendChild(el('span', 'trust-badge ' + sig.cls, sig.label));
    });
    if (r.source_type && r.source_type !== 'other') meta.appendChild(el('span', 'src-badge src-' + r.source_type, SOURCE_LABELS[r.source_type] || r.source_type));
    if (r.published) meta.appendChild(el('span', 'date-badge', r.published));
    card.appendChild(meta);
    $results.appendChild(card);
  });
}

/* ======== SEARCH ======== */

async function runSearch() {
  const q = ($q||{}).value||'';
  if (!q.trim()) return;
  if (_searchInFlight) return;
  const now = Date.now(), elapsed = now - _lastSearchTime;
  if (elapsed < SEARCH_COOLDOWN_MS) { setStatus('Please wait...', false); return; }
  _searchInFlight = true; _lastSearchTime = now;
  if (!state.hasSearched) $filters.classList.remove('hidden');
  enterResultsMode();
  tryInstantAnswer(q);
  setStatus('Searching\u2026', true);
  const payload = {
    q: q.trim(), provider: state.provider, count: 10,
    no_commerce: state.no_commerce, prefer_official: state.prefer_official,
    prefer_recent_days: state.recent ? 30 : null,
    block_domains: [], allow_domains: [],
    synthesize: state.synthesize, fetch_top_n: state.synthesize ? 3 : 0,
  };
  try {
    const res = await fetch('/api/search', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload),
    });
    if (res.status === 429) { setStatus('Too many searches \u2014 please wait', false); return; }
    if (!res.ok) { setStatus('Error: '+res.status, false); renderResults([]); return; }
    const data = await res.json();
    const cached = data.meta && data.meta.cached;
    setStatus(data.results.length + ' results' + (cached ? ' \u00b7 instant' : ''), false);
    renderSynthesis(data.synthesis);
    renderResults(data.results);
  } catch(e) { setStatus('Error: request failed', false); renderResults([]); console.error(e); }
  finally { _searchInFlight = false; }
}

function debouncedSearch() { clearTimeout(_debounceTimer); _debounceTimer = setTimeout(runSearch, DEBOUNCE_MS); }
$go.addEventListener('click', runSearch);
$q.addEventListener('keydown', e => { if (e.key==='Enter') debouncedSearch(); });
$q.focus();
