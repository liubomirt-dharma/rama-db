(() => {
  const dialog = document.createElement('dialog');
  dialog.className = 'share-dialog';
  dialog.setAttribute('aria-labelledby', 'share-title');
  dialog.innerHTML = `<form method="dialog"><h2 id="share-title">Поделиться</h2><button aria-label="Закрыть меню">×</button></form>
    <label>Ссылка на материал<input type="url" readonly></label>
    <div class="share-links"><button data-copy>Скопировать</button><button data-native>Ещё…</button>
    <a data-facebook target="_blank" rel="noopener noreferrer">Facebook</a>
    <a data-telegram target="_blank" rel="noopener noreferrer">Telegram</a>
    <a data-whatsapp target="_blank" rel="noopener noreferrer">WhatsApp</a></div>
    <p role="status"></p>`;
  const input = dialog.querySelector('input');
  const status = dialog.querySelector('[role=status]');
  const native = dialog.querySelector('[data-native]');
  let title = '';
  document.addEventListener('click', event => {
    const button = event.target.closest('button[data-share-url]');
    if (!button) return;
    // Relative addresses also support local previews and project Pages under a subpath.
    input.value = new URL(button.dataset.shareUrl, location.href).href;
    title = button.dataset.shareTitle || document.title;
    const url = encodeURIComponent(input.value);
    dialog.querySelector('[data-facebook]').href = 'https://www.facebook.com/sharer/sharer.php?u=' + url;
    dialog.querySelector('[data-telegram]').href = 'https://t.me/share/url?url=' + url + '&text=' + encodeURIComponent(title);
    dialog.querySelector('[data-whatsapp]').href = 'https://wa.me/?text=' + encodeURIComponent(title + ' ' + input.value);
    status.textContent = '';
    native.hidden = typeof navigator.share !== 'function';
    if (!dialog.isConnected) document.body.append(dialog);
    dialog.showModal();
  });
  dialog.querySelector('[data-copy]').onclick = async () => {
    try {
      await navigator.clipboard.writeText(input.value);
      status.textContent = 'Ссылка скопирована';
    } catch {
      input.focus();
      input.select();
      status.textContent = 'Скопируйте выделенную ссылку';
    }
  };
  native.onclick = async () => {
    try { await navigator.share({title, url:input.value}); }
    catch (error) { if (error.name !== 'AbortError') status.textContent = 'Выберите другой способ отправки'; }
  };
})();
