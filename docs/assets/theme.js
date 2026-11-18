// Applied before paint; an explicit choice also survives blocked storage in-memory.
(() => {
  'use strict';
  const labels = { light: 'Paper', dark: 'Ink', sand: 'Sand', moss: 'Moss', slate: 'Slate', clay: 'Clay' };
  const media = matchMedia('(prefers-color-scheme: dark)');
  let choice = 'system';
  try {
    const saved = localStorage.getItem('folio-theme');
    if (saved === 'system' || Object.hasOwn(labels, saved)) choice = saved;
  } catch (_) { /* Browser storage is optional. */ }
  function apply() {
    document.documentElement.dataset.theme = choice === 'system' ? (media.matches ? 'dark' : 'light') : choice;
    dispatchEvent(new CustomEvent('folio:themechange'));
  }
  window.FolioTheme = {
    labels,
    get choice() { return choice; },
    set(value) {
      choice = value === 'system' || Object.hasOwn(labels, value) ? value : 'system';
      try { localStorage.setItem('folio-theme', choice); } catch (_) { /* Optional. */ }
      apply();
    }
  };
  media.addEventListener('change', () => { if (choice === 'system') apply(); });
  apply();
})();
