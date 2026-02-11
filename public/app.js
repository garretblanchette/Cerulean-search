/* ============================================
   Cerulean Search — App Logic
   ============================================ */

// ---- Helpers ----

function splitCsv(s) {
  return (s || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

// ---- State ----

const state = {
  no_commerce: true,
  prefer_official: true,
  synthesize: false,
  recent: false,
  provider: 'brave',
  hasSearched: false,
};

// ---- UI References ----

const $q        = document.getElementById('q');
const $go       = document.getElementById('go');
const $app      = document.getElementById('app');
const $filters  = document.getElementById('filters');
const $status   = document.getElementById('status');
const $synth    = document.getElementById('synthesis');
const $results  = document.getElementById('results');
const $provider = document.getElementById('provider');
const $homeBtn  = document.getElementById('home-btn');

// ---- Filter Chip Logic ----

document.querySelectorAll('.chip[data-key]').forEach(chip => {
  chip.addEventListener('click', () => {
    const key = chip.dataset.key;
    state[key] = !state[key];
    chip.classList.toggle('active', state[key]);
  });
});

if ($provider) {
  $provider.addEventListener('change', () => {
    state.provider = $provider.value;
  });
}

// ---- Home Button ----

if ($homeBtn) {
  $homeBtn.addEventListener('click', () => {
    $app.classList.remove('has-results');
    $app.classList.add('landing');
    $results.innerHTML = '';
    $synth.innerHTML = '';
    $synth.classList.add('hidden');
    $status.classList.add('hidden');
    $status.textContent = '';
    $q.value = '';
    $q.focus();
    state.hasSearched = false;
  });
}

// ---- Layout transitions ----

function enterResultsMode() {
  $app.classList.remove('landing');
  $app.classList.add('has-results');
  $filters.classList.remove('hidden');
  state.hasSearched = true;
}

function setStatus(text, searching) {
  if (!$status) return;
  $status.classList.remove('hidden');
  if (searching) {
    $status.innerHTML = '<span class="spinner"></span>' + text;
    $status.classList.add('searching');
  } else {
    $status.textContent = text;
    $status.classList.remove('searching');
  }
}

// ---- Render Synthesis ----

function renderSynthesis(syn) {
  if (!$synth) return;
  $synth.innerHTML = '';
  if (!syn || syn.length === 0) {
    $synth.classList.add('hidden');
    return;
  }
  $synth.classList.remove('hidden');
  $synth.appendChild(el('h2', null, 'Summary'));

  const ul = el('ul');
  syn.forEach(b => {
    const li = el('li');
    li.textContent = b.text;
    const cites = (b.cites || []).map(i => String(i)).join(', ');
    if (cites) {
      const span = el('span', 'cites', '[' + cites + ']');
      li.appendChild(span);
    }
    ul.appendChild(li);
  });
  $synth.appendChild(ul);
}

// ---- Render Results ----

function renderResults(results) {
  if (!$results) return;
  $results.innerHTML = '';

  if (!results || results.length === 0) {
    $results.appendChild(el('div', 'no-results', 'No results found.'));
    return;
  }

  results.forEach((r, idx) => {
    const card = el('div', 'result');
    card.style.animationDelay = (idx * 0.04) + 's';

    // URL line (like Google)
    const cite = el('div', 'cite-url', r.domain);
    card.appendChild(cite);

    // Title
    const title = el('div', 'title');
    const a = document.createElement('a');
    a.href = r.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = r.title;
    title.appendChild(a);
    card.appendChild(title);

    // Snippet
    if (r.snippet) {
      card.appendChild(el('div', 'snippet', r.snippet));
    }

    // Meta row: score + date + reason pills
    const meta = el('div', 'meta-row');

    const scoreBadge = el('span', 'score-badge', Number(r.score).toFixed(2));
    meta.appendChild(scoreBadge);

    if (r.published) {
      meta.appendChild(el('span', 'date-badge', r.published));
    }

    if (r.reasons && r.reasons.length) {
      const reasons = el('span', 'reasons');
      r.reasons.forEach(x => {
        reasons.appendChild(el('span', 'pill', x));
      });
      meta.appendChild(reasons);
    }

    card.appendChild(meta);
    $results.appendChild(card);
  });
}

// ---- Search ----

async function runSearch() {
  const q = ($q || {}).value || '';
  if (!q.trim()) return;

  // Show filters on first search
  if (!state.hasSearched) {
    $filters.classList.remove('hidden');
  }

  enterResultsMode();
  setStatus('Searching\u2026', true);

  const payload = {
    q: q.trim(),
    provider: state.provider,
    count: 10,
    no_commerce: state.no_commerce,
    prefer_official: state.prefer_official,
    prefer_recent_days: state.recent ? 30 : null,
    block_domains: [],
    allow_domains: [],
    synthesize: state.synthesize,
    fetch_top_n: state.synthesize ? 3 : 0,
  };

  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const t = await res.text();
      setStatus('Error: ' + res.status, false);
      renderResults([]);
      console.error(t);
      return;
    }

    const data = await res.json();
    setStatus(data.results.length + ' results', false);
    renderSynthesis(data.synthesis);
    renderResults(data.results);
  } catch (e) {
    setStatus('Error: request failed', false);
    renderResults([]);
    console.error(e);
  }
}

// ---- Event Listeners ----

$go.addEventListener('click', runSearch);
$q.addEventListener('keydown', e => {
  if (e.key === 'Enter') runSearch();
});

// Focus the search input on load
$q.focus();
