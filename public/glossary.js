/* ==========================================================================
   Cerulean Glossary Tooltips
   --------------------------------------------------------------------------
   Wraps inline terms marked with .cer-term[data-term="..."] with a
   terminal-style tooltip panel on hover/tap/focus.

   Pairs with glossary.css.

   To add a new term:
     1. Add an entry to CER_GLOSSARY below
     2. Mark the term in HTML:
        <span class="cer-term" tabindex="0" data-term="new-key">visible text</span>

   To add a term at runtime (after DOMContentLoaded):
     window.cerulean.addGlossaryTerm('key', { term: 'Label', def: 'Definition' });
     window.cerulean.refreshGlossary();
   ========================================================================== */

(function() {
  'use strict';

  // ==========================================================================
  // GLOSSARY ENTRIES
  // Edit, add, or remove terms here. Organized by category for clarity;
  // ordering doesn't affect behavior.
  // ==========================================================================
  const CER_GLOSSARY = {

    // ---- Source roles (the primary classification axis) ----

    "primary-source": {
      term: "primary source",
      def: "The original document, dataset, or record. The court filing itself, not the news article about it. The scientific paper, not the press release describing it."
    },
    "secondary-source": {
      term: "secondary source",
      def: "Analysis or interpretation of primary sources. Most editorial journalism, academic books and review articles, biographies, expert commentary. A reporter writing about a court ruling, not the ruling itself."
    },
    "tertiary-source": {
      term: "tertiary source",
      def: "A summary or synthesis of secondary sources. Encyclopedias, Wikipedia, dictionary entries, listicles, 'what is X' guides. Useful for orientation, not for verification."
    },

    // ---- Source types (the entity-producing-it axis) ----

    "journalism": {
      term: "journalism",
      def: "Content produced with an editorial process: visible bylines, fact-checking, corrections published when errors surface. Distinguished from commercial content masquerading as news."
    },
    "academic": {
      term: "academic",
      def: "Content from research institutions, academic publishers, or peer-reviewed venues. Universities, journals, working papers. Carries its own editorial process (peer review) distinct from journalism."
    },
    "reference": {
      term: "reference",
      def: "Encyclopedic works that synthesize existing knowledge into structured entries. Wikipedia, MDN, Stanford Encyclopedia of Philosophy. Almost always tertiary in role."
    },
    "indie": {
      term: "indie",
      def: "Personal sites built by individuals, not companies. Blogs, neocities, github.io pages, IndieWeb participants. Made because someone wanted to make it, not because anyone paid them to."
    },
    "community": {
      term: "community",
      def: "Forums, comment threads, collective discussion spaces. Reddit, Hacker News, Stack Overflow. The signal is people arguing in public, which is its own kind of editorial process."
    },
    "commercial": {
      term: "commercial",
      def: "Corporate sites, product pages, marketing materials. A company describing its own product is commercial; a journalist describing the same product is journalism. The distinction is who is paying."
    },
    "primary-source-publisher": {
      term: "primary-source publisher",
      def: "An entity that hosts raw primary materials: government data portals, court databases, academic journals, statute repositories. Hosts the source itself, not analysis of it."
    },
    "aggregator": {
      term: "aggregator",
      def: "A site that does not create original content. Collects content from elsewhere and republishes or links to it. Often ranks above the original source it is aggregating."
    },
    "seo-farm": {
      term: "SEO farm",
      def: "Sites that exist to rank in search results, not to inform readers. AI-generated content, thin affiliates, listicle factories. The signal is the absence of any reason for the content to exist besides ranking."
    },

    // ---- Methodology vocabulary ----

    "editorial-process": {
      term: "editorial process",
      def: "The chain of checks a piece of writing goes through. Newsrooms do it hierarchically: editor, fact-checker, publisher. Wikipedia does it communally: edits, reverts, talk pages. Both are editorial processes."
    },
    "acrl-framework": {
      term: "ACRL Framework",
      def: "The Association of College and Research Libraries' Framework for Information Literacy. The current professional standard for teaching source evaluation in higher education."
    },
    "craap-test": {
      term: "CRAAP test",
      def: "Currency, Relevance, Authority, Accuracy, Purpose. A widely taught checklist for evaluating sources, especially in undergraduate research. Easier to teach than the ACRL Framework, less nuanced."
    },
    "beam-framework": {
      term: "BEAM framework",
      def: "Background, Exhibit, Argument, Method. Joseph Bizup's framework for how sources function inside a research argument, not just what they are. A source's role depends on how the writer uses it."
    },
    "information-literacy": {
      term: "information literacy",
      def: "The ability to find, evaluate, and use information responsibly. The library science discipline that produces frameworks like ACRL, CRAAP, and BEAM. The thing Cerulean operationalizes at search scale."
    },

    // ---- Search and web vocabulary ----

    "seo": {
      term: "SEO",
      def: "Search Engine Optimization. The industry of structuring websites to rank higher in Google's results. Multibillion-dollar in scale. The reason recipe sites have 2000 words of personal history before the recipe."
    },
    "ranking": {
      term: "ranking",
      def: "Where a result shows up in search results. Page 1, position 1 is the top hit. The thing the entire SEO industry exists to manipulate."
    },
    "algorithm": {
      term: "algorithm",
      def: "The ranking system a search engine uses to decide which results to show and in what order. Updated constantly. Closely guarded. The thing SEO firms reverse-engineer for a living."
    },
    "content-farm": {
      term: "content farm",
      def: "A website that publishes huge volumes of low-quality articles engineered to rank in search results. Made for Google, not readers. Increasingly AI-generated. Monetized by ads or affiliate links."
    },
    "ai-slop": {
      term: "AI slop",
      def: "The flood of AI-generated content that has hit the web since 2023. Articles, recipes, reviews, news summaries, all generated by language models and published at scale. Often says nothing in a lot of words."
    },
    "small-web": {
      term: "small web",
      def: "The part of the internet built by individuals instead of companies. Personal blogs, hobby sites, project pages, small forums. Made because someone wanted to make it. Mostly invisible in modern search."
    },
    "content-marketing": {
      term: "content marketing",
      def: "Articles, videos, or guides published by a company to attract customers. The 'blog' section of a corporate website. Looks like journalism, functions as advertising."
    },
    "metasearch": {
      term: "metasearch engine",
      def: "A search engine that does not have its own index. Sends your query to other search engines like Google, Bing, Brave, or DuckDuckGo, then combines their results. Cerulean is one."
    },
    "self-hosted": {
      term: "self-hosted",
      def: "Software you run on your own server instead of using someone else's service. Maximum control and privacy, maximum maintenance burden."
    },
    "index": {
      term: "index",
      def: "The database a search engine builds by crawling the web. Google has one. Bing has one. Most indie search engines do not; they use someone else's."
    }
  };

  // ==========================================================================
  // RULE STRING
  // The horizontal divider between the prompt and definition. Built once
  // from box-drawing characters so it scales with the panel width visually.
  // ==========================================================================
  const RULE = '\u2500'.repeat(24);

  // ==========================================================================
  // INITIALIZATION
  // ==========================================================================

  const initializedTerms = new WeakSet();

  function initTerm(el) {
    if (initializedTerms.has(el)) return;

    const key = el.dataset.term;
    const entry = CER_GLOSSARY[key];
    if (!entry) {
      console.warn('[glossary] No entry for term: ' + key);
      return;
    }
    initializedTerms.add(el);

    const bubble = document.createElement('span');
    bubble.className = 'cer-bubble';
    bubble.setAttribute('role', 'tooltip');

    bubble.innerHTML =
      '<span class="cer-bubble-content">' +
        '<span class="cer-bubble-prompt">&gt; <span class="cer-bubble-term">' + entry.term + '</span></span>' +
        '<span class="cer-bubble-rule">' + RULE + '</span>' +
        '<span class="cer-bubble-def">' + entry.def + '<span class="cer-bubble-cursor"></span></span>' +
      '</span>';

    el.appendChild(bubble);

    const checkFlip = function() {
      const rect = el.getBoundingClientRect();
      el.classList.toggle('cer-flip', rect.top < 200);
    };

    el.addEventListener('mouseenter', checkFlip);
    el.addEventListener('focus', checkFlip);

    el.addEventListener('click', function(e) {
      e.stopPropagation();
      document.querySelectorAll('.cer-term.is-active').forEach(function(other) {
        if (other !== el) other.classList.remove('is-active');
      });
      checkFlip();
      el.classList.toggle('is-active');
    });

    el.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        el.click();
      } else if (e.key === 'Escape') {
        el.classList.remove('is-active');
        el.blur();
      }
    });
  }

  function refreshGlossary() {
    document.querySelectorAll('.cer-term').forEach(initTerm);
  }

  // Dismiss active bubble on outside click
  document.addEventListener('click', function() {
    document.querySelectorAll('.cer-term.is-active').forEach(function(el) {
      el.classList.remove('is-active');
    });
  });

  // ==========================================================================
  // PUBLIC API
  // ==========================================================================
  window.cerulean = window.cerulean || {};
  window.cerulean.glossary = CER_GLOSSARY;
  window.cerulean.addGlossaryTerm = function(key, entry) {
    CER_GLOSSARY[key] = entry;
  };
  window.cerulean.refreshGlossary = refreshGlossary;

  // ==========================================================================
  // RUN ON DOM READY
  // ==========================================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refreshGlossary);
  } else {
    refreshGlossary();
  }
})();
