(() => {
  const frame = document.querySelector('.watch-player');
  const rows = document.querySelectorAll('[data-seconds]');
  const raw = new URLSearchParams(location.search).get('t');
  const active = [...rows].find(row => row.dataset.seconds === raw);
  if (active) {
    frame.src += '?start=' + active.dataset.seconds;
    active.setAttribute('aria-current', 'time');
    document.querySelector('[data-current-chapter]').textContent = active.querySelector('.chapter-name').textContent;
    document.querySelector('[data-youtube]').href = active.querySelector('.youtube-time').href;
    const share = document.querySelector('[data-current-share]');
    share.dataset.shareUrl = active.querySelector('.time-link').href;
    share.dataset.shareTitle = active.querySelector('.chapter-name').textContent;
  }
})();
