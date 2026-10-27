/* Progressive enhancements for the existing Jinja workspace; no framework dependency. */
(function () {
  function init() {
    const themeStylesheet = document.querySelector('link[href="/static/studio.css"]');
    const toolbar = document.querySelector('.topbar-right');
    if (themeStylesheet && toolbar) {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'top-chip studio-theme-toggle';
      const readPreference = () => {
        try { return localStorage.getItem('studio-theme') || 'dark'; }
        catch (_) { return 'dark'; }
      };
      const applyTheme = (theme) => {
        const light = theme === 'light';
        themeStylesheet.disabled = light;
        toggle.textContent = light ? '☾ Dark mode' : '☼ Light mode';
        toggle.setAttribute('aria-label', light ? 'Switch to dark mode' : 'Switch to light mode');
        toggle.setAttribute('aria-pressed', String(!light));
        document.documentElement.style.colorScheme = light ? 'light' : 'dark';
        try { localStorage.setItem('studio-theme', theme); } catch (_) {}
      };
      toggle.addEventListener('click', () => applyTheme(themeStylesheet.disabled ? 'dark' : 'light'));
      toolbar.appendChild(toggle);
      applyTheme(readPreference());
    }

    const workspaceActions = ['/clean', '/analyze', '/design', '/run-full-system'];
    document.querySelectorAll('form').forEach((form) => {
      const action = new URL(form.getAttribute('action') || location.pathname, location.href).pathname;
      if ((form.method || 'get').toLowerCase() !== 'post' || !workspaceActions.includes(action)) return;
      let submitting = false;
      form.addEventListener('submit', (event) => {
        if (submitting) { event.preventDefault(); return; }
        submitting = true;
        const status = document.createElement('p');
        status.className = 'studio-processing';
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');
        status.textContent = 'Processing your request. Your original data is preserved.';
        form.appendChild(status);
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((button) => {
          button.disabled = true;
          if (button.tagName === 'BUTTON') button.textContent = 'Processing…';
        });
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
