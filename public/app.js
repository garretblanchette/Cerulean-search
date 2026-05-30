/* ============================================
   Cerulean Search — App Logic v0.4.0
   Segmented mode, summarize, source-type filters
   ============================================ */

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const SOURCE_LABELS = { news:'News', reference:'Reference', academic:'Academic', gov:'Official', community:'Forum', docs:'Docs', commercial:'Commercial', video:'Video', health:'Health', ai_slop:'AI Content' };
const TIER_TERMS   = { 'High quality': {term:'tier-high-quality', emoji:'\ud83e\udd13'}, 'Good': {term:'tier-good', emoji:'\ud83d\ude0a'}, 'Low confidence': {term:'tier-fair', emoji:'\ud83d\ude10'} };
const SOURCE_TERMS = { news:'src-news', reference:'src-reference', academic:'src-academic', gov:'src-gov', community:'src-community', docs:'src-docs', commercial:'src-commercial', video:'src-video', health:'src-health', ai_slop:'src-ai-slop' };
// Source role: how close the source sits to original evidence (the journalistic / library-science axis).
// Derived from source type; primary = original record, secondary = reporting/analysis, tertiary = synthesis.
const SOURCE_ROLE = {
  gov:        { label:'Primary source',   cls:'role-primary',   note:'Original record or official communication from the entity itself.' },
  academic:   { label:'Primary source',   cls:'role-primary',   note:'Original research or scholarship.' },
  docs:       { label:'Primary source',   cls:'role-primary',   note:'Official documentation from the source.' },
  news:       { label:'Secondary source', cls:'role-secondary', note:'Reporting and analysis of events the author did not originate.' },
  community:  { label:'Secondary source', cls:'role-secondary', note:'Discussion and commentary.' },
  video:      { label:'Secondary source', cls:'role-secondary', note:'Creator coverage or commentary.' },
  commercial: { label:'Secondary source', cls:'role-secondary', note:'Vendor or product material.' },
  reference:  { label:'Tertiary source',  cls:'role-tertiary',  note:'Encyclopedic synthesis of other sources.' },
  health:     { label:'Tertiary source',  cls:'role-tertiary',  note:'Consumer-health synthesis.' },
  ai_slop:    { label:'Tertiary source',  cls:'role-tertiary',  note:'Aggregated or AI-generated synthesis.' },
};

function trustBadge(cls, term, label, emoji) {
  const badge = el('span', cls);
  if (emoji) {
    const eEl = el('span');
    eEl.setAttribute('aria-hidden', 'true');
    eEl.textContent = emoji + ' ';
    badge.appendChild(eEl);
  }
  const t = el('span', 'cer-term');
  t.setAttribute('data-term', term);
  t.setAttribute('tabindex', '0');
  t.textContent = label;
  badge.appendChild(t);
  return badge;
}

/* ---- State (single source of truth) ---- */
const LS = {
  read(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  write(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};

const state = {
  mode:         LS.read('cer.mode', 'boost'),        // 'boost' | 'unfiltered'
  summarize:    LS.read('cer.summarize', false),
  provider:     LS.read('cer.provider', 'brave'),
  sourceTypes:  LS.read('cer.sourceTypes', []),      // array of source_type keys
  // Dark uses the legacy `cerulean-dark` key as raw string for compat with
  // cornerstone pages, which read/write the same key with values 'true'/'false'.
  dark:         (function(){ try { const v = localStorage.getItem('cerulean-dark'); if (v === 'true') return true; if (v === 'false') return false; return null; } catch(e) { return null; } })(),
  hasSearched:  false,
  lastResults:  null,
};

/* ---- DOM refs ---- */
const $q = document.getElementById('q');
const $go = document.getElementById('go');
const $app = document.getElementById('app');
const $controls = document.getElementById('controls');
const $sourceFilters = document.getElementById('source-filters');
const $overflowBtn = document.getElementById('overflow-btn');
const $status = document.getElementById('status');
const $synth = document.getElementById('synthesis');
const $results = document.getElementById('results');
const $provider = document.getElementById('provider');
const $homeBtn = document.getElementById('home-btn');
const $darkBtn = document.getElementById('dark-toggle');
const $instant = document.getElementById('instant-answer');

let _lastSearchTime = 0, _searchInFlight = false, _debounceTimer = null;
const SEARCH_COOLDOWN_MS = 2000, DEBOUNCE_MS = 400;

/* ---- Dark Mode ---- */
function applyDark(on) {
  document.documentElement.classList.toggle('dark', on === true);
  document.documentElement.classList.toggle('light-forced', on === false);
  state.dark = on;
  try { localStorage.setItem('cerulean-dark', on === true ? 'true' : 'false'); } catch(e) {}
  if ($darkBtn) $darkBtn.textContent = on === true ? '\u2600\uFE0F' : '\uD83C\uDF19';
}
applyDark(state.dark === null ? false : state.dark);
if ($darkBtn) $darkBtn.addEventListener('click', () => applyDark(!(state.dark === true)));

/* ---- Segmented control (mode) ---- */
function setMode(mode) {
  state.mode = mode;
  LS.write('cer.mode', mode);
  document.querySelectorAll('.seg-btn').forEach(b => {
    const active = b.dataset.mode === mode;
    b.classList.toggle('active', active);
    b.setAttribute('aria-checked', active ? 'true' : 'false');
  });
  if (state.hasSearched) runSearch();
}
document.querySelectorAll('.seg-btn').forEach(b => {
  b.addEventListener('click', () => setMode(b.dataset.mode));
});
setMode(state.mode);

/* ---- Summarize chip ---- */
const $summarizeChip = document.getElementById('chip-summarize');
function setSummarize(on) {
  state.summarize = on;
  LS.write('cer.summarize', on);
  $summarizeChip.classList.toggle('active', on);
  $summarizeChip.setAttribute('aria-pressed', on ? 'true' : 'false');
  if (state.lastResults) renderResults(state.lastResults);
  if (state.hasSearched) runSearch();
}
$summarizeChip.addEventListener('click', () => setSummarize(!state.summarize));
$summarizeChip.classList.toggle('active', state.summarize);
$summarizeChip.setAttribute('aria-pressed', state.summarize ? 'true' : 'false');

/* ---- Provider ---- */
if ($provider) {
  $provider.value = state.provider;
  $provider.addEventListener('change', () => {
    state.provider = $provider.value;
    LS.write('cer.provider', state.provider);
    if (state.hasSearched) runSearch();
  });
}

/* ---- Overflow + source-type filters ---- */
function setOverflow(open) {
  $sourceFilters.hidden = !open;
  $overflowBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  $overflowBtn.classList.toggle('active', open);
}
$overflowBtn.addEventListener('click', () => {
  setOverflow($sourceFilters.hidden);
});

document.querySelectorAll('.src-chip').forEach(chip => {
  const key = chip.dataset.src;
  const active = state.sourceTypes.includes(key);
  chip.classList.toggle('active', active);
  chip.setAttribute('aria-pressed', active ? 'true' : 'false');
  chip.addEventListener('click', () => {
    const i = state.sourceTypes.indexOf(key);
    if (i >= 0) state.sourceTypes.splice(i, 1);
    else state.sourceTypes.push(key);
    LS.write('cer.sourceTypes', state.sourceTypes);
    const on = i < 0;
    chip.classList.toggle('active', on);
    chip.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (state.lastResults) renderResults(state.lastResults);
  });
});

/* If any source types are persisted active, auto-open the overflow panel */
if (state.sourceTypes.length > 0) setOverflow(true);

/* ---- Home button ---- */
if ($homeBtn) $homeBtn.addEventListener('click', () => {
  $app.classList.remove('has-results'); $app.classList.add('landing');
  $results.innerHTML = ''; $synth.innerHTML = '';
  $synth.classList.add('hidden'); $status.classList.add('hidden'); $status.textContent = '';
  if ($instant) { $instant.innerHTML = ''; $instant.classList.add('hidden'); }
  $q.value = ''; $q.focus(); state.hasSearched = false; state.lastResults = null;
});

/* ---- Layout transitions ---- */
function enterResultsMode() {
  $app.classList.remove('landing'); $app.classList.add('has-results');
  $controls.classList.remove('hidden');
  state.hasSearched = true;
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
  const q = query.trim().toLowerCase();
  const math = tryMath(q);
  if (math !== null) { showInstant('Calculator', math, '\uD83D\uDD22'); return; }
  const conv = tryConversion(q);
  if (conv !== null) { showInstant('Conversion', conv, '\uD83D\uDCCF'); return; }
  const color = tryColor(q);
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

/* ======== TRUST SIGNALS ======== */

function getTrustSignals(score, reasons) {
  const s = [];
  for (const r of (reasons || [])) {
    if (r.startsWith('official:')) s.push({label:'Official source', cls:'trust-good'});
    else if (r.startsWith('tracking:')) s.push({label:'Has trackers', cls:'trust-warn'});
    else if (r.startsWith('blocklisted:')) s.push({label:'Blocked', cls:'trust-bad'});
  }
  if (score >= 0.7)      s.unshift({label:'High quality', cls:'trust-good'});
  else if (score >= 0.4) s.unshift({label:'Good',          cls:'trust-ok'});
  else if (score >= 0)   s.unshift({label:'Low confidence',          cls:'trust-muted'});
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

function filterResults(results) {
  let f = results || [];
  // Always hide high-confidence AI content (filter is on by default, no chip).
  f = f.filter(r => (r.ai_likelihood || 0) < 0.7);
  if (state.sourceTypes.length) {
    f = f.filter(r => state.sourceTypes.includes(r.source_type));
  }
  return f;
}

function renderResults(results) {
  state.lastResults = results;

  // Cache-migration: legacy 'shopping' → 'commercial'
  results = (results || []).map(r => {
    if (r && r.source_type === 'shopping') r.source_type = 'commercial';
    return r;
  });

  const total = results.length;
  results = filterResults(results);
  const hidden = total - results.length;

  if (!$results) return;
  $results.innerHTML = '';

  if (hidden > 0) {
    $results.appendChild(el('div', 'filter-note', hidden + ' result' + (hidden===1?'':'s') + ' hidden by filters'));
  }
  if (!results.length) {
    $results.appendChild(el('div', 'no-results', 'No results found.'));
    return;
  }

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

    // Topic callout (only when Summarize is on and backend returned a topic)
    if (state.summarize && r.topic) {
      const topic = el('div', 'topic-callout');
      topic.appendChild(el('span', 'topic-label', 'Topic'));
      topic.appendChild(el('span', 'topic-body', r.topic));
      card.appendChild(topic);
    }

    const meta = el('div', 'meta-row');
    // Lead with source classification — the journalistic angle: role first, then type.
    const role = SOURCE_ROLE[r.source_type];
    if (role) {
      const rb = el('span', 'role-badge ' + role.cls, role.label);
      rb.title = role.note;
      meta.appendChild(rb);
    }
    if (r.source_type && r.source_type !== 'other') {
      const stTerm = SOURCE_TERMS[r.source_type];
      const stLabel = SOURCE_LABELS[r.source_type] || r.source_type;
      if (stTerm) meta.appendChild(trustBadge('src-badge src-' + r.source_type, stTerm, stLabel, null));
      else meta.appendChild(el('span', 'src-badge src-' + r.source_type, stLabel));
    }
    // Quality signal, secondary to the source classification.
    getTrustSignals(r.score, r.reasons).forEach(sig => {
      const tm = TIER_TERMS[sig.label];
      if (tm) meta.appendChild(trustBadge('trust-badge ' + sig.cls, tm.term, sig.label, tm.emoji));
      else meta.appendChild(el('span', 'trust-badge ' + sig.cls, sig.label));
    });
    if (r.source_type !== 'commercial' && Array.isArray(r.reasons) && r.reasons.some(x => String(x).startsWith('commerce:'))) {
      meta.appendChild(trustBadge('src-badge src-commercial src-secondary', 'src-commercial', 'Commercial', null));
    }
    if ((r.ai_likelihood || 0) >= 0.4) meta.appendChild(trustBadge('ai-warn-badge', 'likely-ai', 'Likely AI', null));
    if (r.published) meta.appendChild(el('span', 'date-badge', r.published));
    card.appendChild(meta);

    $results.appendChild(card);
  });

  if (window.cerulean && typeof window.cerulean.refreshGlossary === 'function') {
    window.cerulean.refreshGlossary();
  }
}

/* ======== SEARCH ======== */

async function runSearch() {
  const q = ($q || {}).value || '';
  if (!q.trim()) return;
  if (_searchInFlight) return;
  const now = Date.now();
  if (now - _lastSearchTime < SEARCH_COOLDOWN_MS) { setStatus('Please wait...', false); return; }
  _searchInFlight = true; _lastSearchTime = now;

  if (!state.hasSearched) $controls.classList.remove('hidden');
  enterResultsMode();
  tryInstantAnswer(q);
  setStatus('Searching\u2026', true);

  const boost = state.mode === 'boost';
  const payload = {
    q: q.trim(),
    provider: state.provider,
    count: 10,
    // Quality Boost mode applies official-source preference and commerce demotion.
    // Unfiltered mode passes through with relevance + dedup + tracking penalty only.
    no_commerce: boost,
    prefer_official: boost,
    quality_boost: boost,
    prefer_recent_days: null,
    block_domains: [], allow_domains: [],
    // Backend uses `synthesize` for the topic generation pipeline.
    synthesize: state.summarize,
    fetch_top_n: state.summarize ? 3 : 0,
  };

  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (res.status === 429) { setStatus('Too many searches \u2014 please wait', false); return; }
    if (!res.ok) { setStatus('Error: ' + res.status, false); renderResults([]); return; }
    const data = await res.json();
    const cached = data.meta && data.meta.cached;
    setStatus(data.results.length + ' results' + (cached ? ' \u00b7 instant' : ''), false);
    renderSynthesis(data.synthesis);
    renderResults(data.results);
  } catch (e) {
    setStatus('Error: request failed', false);
    renderResults([]);
    console.error(e);
  } finally {
    _searchInFlight = false;
  }
}

function debouncedSearch() { clearTimeout(_debounceTimer); _debounceTimer = setTimeout(runSearch, DEBOUNCE_MS); }
$go.addEventListener('click', runSearch);
$q.addEventListener('keydown', e => { if (e.key === 'Enter') debouncedSearch(); });
$q.focus();
