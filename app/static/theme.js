(() => {
  let theme = 'light';
  try { theme = localStorage.getItem('tankflix-theme') === 'dark' ? 'dark' : 'light'; } catch { /* Optional storage. */ }
  const button = document.getElementById('theme-toggle');
  function apply() {
    document.documentElement.setAttribute('data-theme', theme);
    if (button) {
      button.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
      button.setAttribute('aria-pressed', String(theme === 'dark'));
    }
  }
  apply();
  button?.addEventListener('click', () => {
    theme = theme === 'light' ? 'dark' : 'light';
    try { localStorage.setItem('tankflix-theme', theme); } catch { /* The current theme still works. */ }
    apply();
  });
})();
