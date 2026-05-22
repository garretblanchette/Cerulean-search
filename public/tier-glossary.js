// tier-glossary.js
// Registers glossary bubbles for quality tiers, source-type badges, and
// the Likely AI heuristic badge. Strips the .cer-term underline
// decoration when nested inside a badge pill. Loaded after glossary.js.
// Depends on window.cerulean.

(function () {
  if (!window.cerulean || typeof window.cerulean.addGlossaryTerm !== 'function') {
    console.warn('[tier-glossary] window.cerulean not ready; glossary.js missing or not yet loaded.');
    return;
  }

  // Quality tiers (3, with face emojis).
  window.cerulean.addGlossaryTerm('tier-high-quality', {
    title: '\ud83e\udd13 High quality',
    body: "Strong query match plus official-source bonus (.gov, .edu, docs.*, etc.). The ranking score is high. Does not directly measure editorial process or factual accuracy."
  });

  window.cerulean.addGlossaryTerm('tier-good', {
    title: '\ud83d\ude0a Good',
    body: "Solid query relevance, no penalty signals triggered. Mid-tier ranking score. The page is on-topic but has not earned the official-source bonus."
  });

  window.cerulean.addGlossaryTerm('tier-fair', {
    title: '\ud83d\ude10 Fair',
    body: "Mid-tier ranking score. Basic relevance, no official-source bonus, no penalty signals triggered. The classifier doesn't have anything stronger to say either way."
  });

  // Source-type badges (10 categories, text only).
  window.cerulean.addGlossaryTerm('src-news', {
    title: 'News',
    body: "Mainstream news outlets, newspapers, broadcast sites. Editorial process and bylines typical. Coverage angle and slant vary by outlet."
  });

  window.cerulean.addGlossaryTerm('src-reference', {
    title: 'Reference',
    body: "Encyclopedic and definitional sources. Wikipedia, dictionaries, MDN, SEP. Aims for aggregated knowledge rather than original reporting."
  });

  window.cerulean.addGlossaryTerm('src-academic', {
    title: 'Academic',
    body: "Peer-reviewed papers, university research, arxiv preprints. Methodology disclosed. Strongest signal of vetted information when present."
  });

  window.cerulean.addGlossaryTerm('src-gov', {
    title: 'Official',
    body: ".gov, .edu, or canonical project sites. Authoritative on themselves. Not neutral on contested topics where the entity has a stake."
  });

  window.cerulean.addGlossaryTerm('src-community', {
    title: 'Community',
    body: "Forums, Reddit, Stack Overflow, Q&A. Real human discussion. Quality swings wildly. Sometimes the best answer, sometimes the worst."
  });

  window.cerulean.addGlossaryTerm('src-docs', {
    title: 'Docs',
    body: "Software documentation, API references, technical specs. Authoritative for the product being documented. Usually accurate on factual matters."
  });

  window.cerulean.addGlossaryTerm('src-shopping', {
    title: 'Shopping',
    body: "Product pages and e-commerce listings. Commercial intent. Reviews may be filtered by the platform. Treat ratings skeptically."
  });

  window.cerulean.addGlossaryTerm('src-video', {
    title: 'Video',
    body: "YouTube and other video hosts. Content quality unpredictable. Better for tutorials and demonstrations than for written research."
  });

  window.cerulean.addGlossaryTerm('src-health', {
    title: 'Health',
    body: "Medical and health-information sites. Quality varies wildly. Confirm with primary sources or licensed practitioners for clinical decisions."
  });

  window.cerulean.addGlossaryTerm('src-ai-slop', {
    title: 'AI Content',
    body: "Page shows strong signals of AI generation. Could be wholly synthetic or AI-assisted. Cross-check facts before relying on it."
  });

  // Likely AI heuristic badge.
  window.cerulean.addGlossaryTerm('likely-ai', {
    title: 'Likely AI',
    body: "Heuristic estimate that this page is significantly AI-generated. Imperfect signal. Technical writing and structured prose can trigger false positives."
  });

  // Strip default cer-term underline decoration inside any badge.
  var style = document.createElement('style');
  style.setAttribute('data-tier-glossary', 'true');
  style.textContent = [
    '.trust-badge .cer-term,',
    '.src-badge .cer-term,',
    '.ai-warn-badge .cer-term,',
    '.quality-badge .cer-term,',
    '.tier-badge .cer-term,',
    '.badge-quality .cer-term,',
    '[class*="quality-"] .cer-term {',
    '  border-bottom: none !important;',
    '  text-decoration: none !important;',
    '  cursor: help;',
    '  color: inherit;',
    '}',
    '.trust-badge .cer-term:focus-visible,',
    '.src-badge .cer-term:focus-visible,',
    '.ai-warn-badge .cer-term:focus-visible,',
    '.quality-badge .cer-term:focus-visible,',
    '.tier-badge .cer-term:focus-visible,',
    '.badge-quality .cer-term:focus-visible,',
    '[class*="quality-"] .cer-term:focus-visible {',
    '  outline: 2px solid currentColor;',
    '  outline-offset: 2px;',
    '  border-radius: 2px;',
    '}'
  ].join('\n');
  document.head.appendChild(style);
})();
