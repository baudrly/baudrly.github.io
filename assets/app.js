/* Generic renderer. Edit tabs.json and content/, not this file.
 * Tab HTML is sanitized by scripts/build.py, never taken from URL/user input.
 */
(() => {
  'use strict';
  const site = window.SITE;
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function safeURL(value) {
    if (typeof value !== 'string' || !value.trim()) return '';
    try {
      const url = new URL(value, location.href);
      if (['https:', 'http:'].includes(url.protocol) || (location.protocol === 'file:' && url.protocol === 'file:')) return url.href;
    } catch (_) { /* Omit malformed links. */ }
    return '';
  }
  const enabledTabs = (site?.tabs || []).filter(tab => tab.enabled !== false);
  const nav = $('[role=tablist]');
  const main = $('#main');
  nav.replaceChildren();
  main.replaceChildren();
  if (!enabledTabs.length) {
    main.append(el('p', 'empty-state', 'No tabs enabled. Enable a tab in tabs.json and rebuild.'));
    return;
  }
  const notes = [];
  enabledTabs.forEach(tab => {
    const a = el('a', '', tab.label);
    a.id = `tab-${tab.id}`;
    a.href = `#${tab.id}`;
    a.setAttribute('role', 'tab');
    a.setAttribute('aria-controls', tab.id);
    nav.append(a);
    const panel = el('section', 'tab-panel');
    panel.id = tab.id;
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', a.id);
    panel.tabIndex = 0;
    panel.append(el('h1', '', tab.title || tab.label));
    const body = el('div', 'page-content');
    body.innerHTML = tab.html || ''; // Trusted, sanitized build output only.
    panel.append(body);
    if (tab.notes?.length) {
      const list = el('div', 'note-list');
      tab.notes.forEach(note => {
        const entry = { ...note, tabId: tab.id, route: `note-${tab.id}--${note.id}` };
        notes.push(entry);
        const article = el('article', 'note');
        const button = el('button', '', 'Read note');
        button.append(el('span', '', '↗'));
        button.lastChild.setAttribute('aria-hidden', 'true');
        button.setAttribute('aria-label', `Read ${note.title}`);
        button.addEventListener('click', () => navigate(entry.route));
        article.append(el('p', 'eyebrow', `${note.category || 'Note'}${note.sample ? ' · sample note' : ''}`), el('h2', '', note.title), el('p', '', note.excerpt || ''), button);
        list.append(article);
      });
      panel.append(list);
    }
    main.append(panel);
  });
  document.title = site.title || `${site.name} — Personal site`;
  const names = { email: 'Email', github: 'GitHub', linkedin: 'LinkedIn', keybase: 'Keybase', orcid: 'ORCID', researchgate: 'ResearchGate', pypi: site.pypiLabel || 'PyPI', agents: 'AI agents', rss: 'RSS feed for notes' };
  $$('[data-social]').forEach(node => {
    const key = node.dataset.social;
    const agentTab = site.agentsTab || 'agents';
    const value = key === 'rss' ? (site.feedURL || './notes.xml') : key === 'agents' ? `#${agentTab}` : site[key];
    const emailOK = typeof site.email === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(site.email);
    const url = key === 'email' ? (emailOK ? `mailto:${site.email}` : '') : safeURL(value);
    if (key === 'agents' && !enabledTabs.some(tab => tab.id === agentTab)) { node.remove(); return; }
    if (!url || (key === 'rss' && !notes.length)) { node.remove(); return; }
    const a = el('a', 'social-icon');
    a.href = url;
    a.dataset.social = key;
    a.setAttribute('aria-label', names[key]);
    a.title = names[key];
    a.append(...node.childNodes);
    node.replaceWith(a);
  });

  const noteDialog = $('#note-dialog');
  const searchDialog = $('#search-dialog');
  const searchInput = $('#search-input');
  const tabs = $$('[role=tab]');
  const fallback = enabledTabs.some(tab => tab.id === site.defaultTab) ? site.defaultTab : enabledTabs[0].id;
  const findNote = route => notes.find(note => route === note.route || route === `note-${note.id}` || route.startsWith(`${note.route}--`));
  function showNote(note) {
    $('#note-title').textContent = note.title;
    $('#note-category').textContent = `${note.category || 'Note'}${note.sample ? ' · sample' : ''}`;
    const body = $('#note-body');
    body.innerHTML = note.html;

    if (!noteDialog.open) noteDialog.showModal();
    noteDialog.scrollTop = 0;
  }
  function syncRoute() {
    const id = location.hash.slice(1);
    const note = findNote(id);
    let target = document.getElementById(id);
    const targetPanel = target?.closest('.tab-panel');
    const panel = note?.tabId || targetPanel?.id || (enabledTabs.some(tab => tab.id === id) ? id : fallback);
    $$('.tab-panel').forEach(node => { node.hidden = node.id !== panel; });
    tabs.forEach(tab => {
      const selected = tab.getAttribute('aria-controls') === panel;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    if (note) {
      showNote(note);
      target = document.getElementById(id);
      if (target && $('#note-body').contains(target)) {
        target.tabIndex = -1;
        target.focus();
      }
    }
    else if (noteDialog.open) noteDialog.close();
    if (target && target.tagName === 'DETAILS') target.open = true;
    for (let parent = target?.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
  }
  function navigate(id) {
    if (location.hash !== `#${id}`) history.pushState(null, '', `#${id}`);
    syncRoute();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', event => { event.preventDefault(); navigate(tab.getAttribute('aria-controls')); });
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      tabs[next].focus();
      navigate(tabs[next].getAttribute('aria-controls'));
    });
  });
  noteDialog.addEventListener('close', () => {
    const note = findNote(location.hash.slice(1));
    if (note) history.replaceState(null, '', `#${note.tabId}`);
  });
  const searchIndex = enabledTabs.flatMap(tab => [
    ...(tab.search?.length ? tab.search : [{ title: tab.title, text: tab.text || '', target: tab.id }]).map(item => ({ ...item, kind: tab.label })),
    ...notes.filter(note => note.tabId === tab.id).map(note => ({ title: note.title, text: `${note.excerpt} ${note.text}`, target: note.route, kind: tab.label }))
  ]);
  function renderSearch() {
    const terms = searchInput.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const matches = terms.length ? searchIndex.filter(item => terms.every(term => `${item.title} ${item.text}`.toLowerCase().includes(term))) : searchIndex;
    $('#search-results').replaceChildren();
    $('#search-status').textContent = terms.length ? `${matches.length} ${matches.length === 1 ? 'result' : 'results'}` : 'Browse everything, or start typing.';
    if (!matches.length) $('#search-results').append(el('p', 'search-status', 'No matches. Try a page title or a broader term.'));
    matches.forEach(item => {
      const button = el('button', 'search-result');
      button.append(el('span', '', item.kind), el('strong', '', item.title));
      button.addEventListener('click', () => {
        searchDialog.close();
        navigate(item.target);
        const target = document.getElementById(item.target);
        if (target) { target.tabIndex = -1; target.focus(); }
      });
      $('#search-results').append(button);
    });
  }
  function openSearch() {
    if ($$('dialog[open]').length) return;
    searchInput.value = '';
    renderSearch();
    searchDialog.showModal();
    searchInput.focus();
  }
  $('.search-toggle').addEventListener('click', openSearch);
  searchInput.addEventListener('input', renderSearch);
  searchInput.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); searchDialog.close(); }
  });
  document.addEventListener('keydown', event => {
    if (!event.target.closest('input,textarea,select,[contenteditable=true]') && event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !noteDialog.open) {
      event.preventDefault(); openSearch();
    }
  });
  $$('.close-dialog').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  $$('dialog').forEach(dialog => dialog.addEventListener('click', event => {
    const r = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) dialog.close();
  }));
  function themeUI() {
    $$('.theme-option input').forEach(input => { input.checked = input.value === window.FolioTheme.choice; });
    $('#theme-toggle').title = `Appearance: ${window.FolioTheme.labels[document.documentElement.dataset.theme]}`;
    $('meta[name=theme-color]').content = getComputedStyle(document.documentElement).getPropertyValue('--paper').trim();
  }
  $('#theme-toggle').addEventListener('click', () => {
    themeUI();
    $('#theme-dialog').showModal();
  });
  $$('.theme-option input').forEach(input => input.addEventListener('change', () => window.FolioTheme.set(input.value)));
  addEventListener('folio:themechange', themeUI);
  addEventListener('hashchange', syncRoute);
  addEventListener('popstate', syncRoute);
  syncRoute();
  themeUI();
})();
