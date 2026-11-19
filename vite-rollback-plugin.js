export default function rollbackPlugin() {
  return {
    name: 'vite-rollback-plugin',
    enforce: 'pre',
    transformIndexHtml(html) {
      const script = `
<script>
(function() {
  function inject(overlay) {
    if (overlay.querySelector('.rollback-banner')) return;
    const banner = document.createElement('div');
    banner.className = 'rollback-banner';
    banner.innerHTML = '<div style="background:#ff6b6b;color:#fff;padding:15px;font-family:sans-serif;font-size:14px;border-bottom:3px solid #ff4757;">' +
      '<strong>🚨 Фронтенд сломан?</strong> Откройте <a href="http://127.0.0.1:8080/rollback" target="_blank" style="color:#fff;text-decoration:underline;font-weight:bold;background:rgba(255,255,255,0.2);padding:2px 6px;border-radius:4px;">http://127.0.0.1:8080/rollback</a> и нажмите «Откатить»' +
      ' <a href="http://127.0.0.1:8080/rollback" target="_blank" style="display:inline-block;background:#fff;color:#ff6b6b;padding:5px 10px;border-radius:6px;text-decoration:none;font-weight:bold;margin-left:10px;">↩️ Открыть откат</a></div>';
    if (overlay.shadowRoot) overlay.shadowRoot.insertBefore(banner, overlay.shadowRoot.firstChild);
    else overlay.insertBefore(banner, overlay.firstChild);
  }
  const obs = new MutationObserver(m => m.forEach(mut => mut.addedNodes.forEach(n => {
    if (n.tagName === 'VITE-ERROR-OVERLAY' || (n.classList && n.classList.contains('vite-error-overlay'))) inject(n);
  })));
  obs.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('load', () => { const o = document.querySelector('vite-error-overlay, .vite-error-overlay'); if (o) inject(o); });
})();
</script>`;
      return html.replace('</head>', script + '</head>');
    }
  };
}
