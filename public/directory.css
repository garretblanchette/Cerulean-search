let allBuilders = [];

async function loadBuilders() {
  try {
    const res = await fetch('/data/builders.json');
    allBuilders = await res.json();
    render();
  } catch (e) {
    document.getElementById('dir-count').textContent = 'Failed to load builders.';
    console.error(e);
  }
}

function getFilters() {
  return {
    city: document.getElementById('filter-city').value,
    industry: document.getElementById('filter-industry').value,
    search: document.getElementById('filter-search').value.trim().toLowerCase()
  };
}

function applyFilters(builders, f) {
  return builders.filter(b => {
    if (f.city && b.city !== f.city) return false;
    if (f.industry && b.industry !== f.industry) return false;
    if (f.search) {
      const hay = (b.name + ' ' + b.building).toLowerCase();
      if (!hay.includes(f.search)) return false;
    }
    return true;
  });
}

function cardHTML(b) {
  const teaser = b.story.split('. ')[0] + '.';
  const badge = b.looking_for_collaborators
    ? '<span class="dir-badge">Looking for collaborators</span>'
    : '';
  return `
    <a class="dir-card" href="/builder?slug=${encodeURIComponent(b.slug)}">
      ${badge}
      <h2 class="dir-card-name">${b.name}</h2>
      <div class="dir-card-meta">
        <span class="dir-card-city">${b.city}</span>
        <span class="dir-card-sep">·</span>
        <span class="dir-card-industry">${b.industry}</span>
      </div>
      <p class="dir-card-building">${b.building}</p>
      <p class="dir-card-teaser">${teaser}</p>
    </a>
  `;
}

function render() {
  const filtered = applyFilters(allBuilders, getFilters());
  const grid = document.getElementById('dir-grid');
  const empty = document.getElementById('dir-empty');
  const count = document.getElementById('dir-count');

  count.textContent = `${filtered.length} ${filtered.length === 1 ? 'builder' : 'builders'} across nine cities`;

  if (filtered.length === 0) {
    grid.innerHTML = '';
    grid.classList.add('hidden');
    empty.classList.remove('hidden');
  } else {
    grid.innerHTML = filtered.map(cardHTML).join('');
    grid.classList.remove('hidden');
    empty.classList.add('hidden');
  }
}

function resetFilters() {
  document.getElementById('filter-city').value = '';
  document.getElementById('filter-industry').value = '';
  document.getElementById('filter-search').value = '';
  render();
}

function setupDarkToggle() {
  const btn = document.getElementById('dark-toggle');
  btn.addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
    const isDark = document.documentElement.classList.contains('dark');
    localStorage.setItem('cerulean-dark', isDark ? '1' : '0');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupDarkToggle();
  document.getElementById('filter-city').addEventListener('change', render);
  document.getElementById('filter-industry').addEventListener('change', render);
  document.getElementById('filter-search').addEventListener('input', render);
  document.getElementById('reset-filters').addEventListener('click', resetFilters);
  loadBuilders();
});