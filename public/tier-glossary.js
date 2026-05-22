// tier-glossary.js
// Registers quality-tier glossary bubbles for the four classifier labels.
// Strips the .cer-term underline decoration when nested inside a quality
// badge pill. Loaded after glossary.js. Depends on window.cerulean.

(function () {
  if (!window.cerulean || typeof window.cerulean.addGlossaryTerm !== 'function') {
    console.warn('[tier-glossary] window.cerulean not ready; glossary.js missing or not yet loaded.');
    return;
  }

  window.cerulean.addGlossaryTerm('tier-high-quality', {
    title: '\ud83e\udd13 High quality',
    body: "Editorial process is visible. Bylines, dates, corrections. Or a primary source: court filings, datasets, official reports. Or an established reference like Wikipedia or MDN. Original content. Real organization or named author behind it."
  });

  window.cerulean.addGlossaryTerm('tier-good', {
    title: '\ud83d\ude0a Good',
    body: "Most positive signals present, one or two missing. Indie blog with original writing. Smaller publication with light editorial markers. Substantive community thread. Sits between editorial High quality and operational Fair."
  });

  window.cerulean.addGlossaryTerm('tier-fair', {
    title: '\ud83e\udd14 Fair',
    body: "Clears the legitimacy bar, fails the editorial bar. Real entity, original content, SSL, structured data. No bylined writing, no curation, no original reporting. Often a single-entity homepage that's well-built but not a list or guide."
  });

  window.cerulean.addGlossaryTerm('tier-padded-generic', {
    title: '\ud83e\udd28 Padded / Generic',
    body: "Page structure signals problems. Padded out beyond substance, or templated for keyword coverage, or both. Common shapes: SEO content farm articles, aggregator repackaging, AI-generated bloat, interchangeable keyword shells. Hidden by default unless filters are relaxed. Not necessarily malicious. Often just optimized for ranking rather than for you."
  });

  var style = document.createElement('style');
  style.setAttribute('data-tier-glossary', 'true');
  style.textContent = [
    '.quality-badge .cer-term,',
    '.tier-badge .cer-term,',
    '.badge-quality .cer-term,',
    '[class*="quality-"] .cer-term {',
    '  border-bottom: none !important;',
    '  text-decoration: none !important;',
    '  cursor: help;',
    '  color: inherit;',
    '}',
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
