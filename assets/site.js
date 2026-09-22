'use strict';

// No video source is attached until the visitor presses Play.
document.querySelectorAll('.player').forEach(player => {
  const video = player.querySelector('video');
  const button = player.querySelector('.play-button');
  const error = player.querySelector('.video-error');
  const buttonLabel = button.innerHTML;
  let playRequest = 0;
  const resetButton = () => {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.innerHTML = buttonLabel;
  };
  button.addEventListener('click', async () => {
    const request = ++playRequest;
    error.hidden = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.textContent = 'Loading…';
    if (!video.getAttribute('src')) video.src = video.dataset.src;
    video.controls = true;
    try {
      await video.play();
    } catch (reason) {
      if (request !== playRequest) return;
      // Pausing during startup rejects play() with AbortError. Scrolling away,
      // switching clips, or hiding the tab is not a media loading failure.
      error.hidden = reason.name === 'AbortError';
      button.hidden = false;
    } finally {
      if (request === playRequest) resetButton();
    }
  });
  video.addEventListener('play', () => {
    error.hidden = true;
    document.querySelectorAll('video').forEach(other => { if (other !== video) other.pause(); });
  });
  // Keep a stable loading button until playback actually starts. The earlier
  // 'play' event can arrive before even the first frame has loaded.
  video.addEventListener('playing', () => {
    error.hidden = true;
    button.hidden = true;
    resetButton();
  });
  video.addEventListener('error', () => {
    error.hidden = false;
    button.hidden = false;
    resetButton();
  });
});

// Pause hidden/offscreen clips; scrolling never starts playback.
const videoObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => { if (!entry.isIntersecting) entry.target.pause(); });
}, {threshold: 0});
document.querySelectorAll('video').forEach(video => videoObserver.observe(video));
document.addEventListener('visibilitychange', () => {
  if (document.hidden) document.querySelectorAll('video').forEach(video => video.pause());
});
document.querySelectorAll('details').forEach(details => {
  details.addEventListener('toggle', () => {
    if (!details.open) details.querySelectorAll('video').forEach(video => video.pause());
  });
});

const dialog = document.querySelector('#figure-dialog');
let lastFigureLink;
document.querySelectorAll('[data-zoom]').forEach(link => {
  link.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || !dialog.showModal) return;
    event.preventDefault();
    lastFigureLink = link;
    const source = link.querySelector('img');
    const image = dialog.querySelector('img');
    image.src = source.src; image.alt = source.alt;
    dialog.querySelector('p').textContent = link.closest('figure').querySelector('figcaption').textContent;
    dialog.showModal(); document.body.classList.add('dialog-open');
  });
});
dialog.querySelector('button').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => {
  const bounds = dialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
});
dialog.addEventListener('close', () => {
  document.body.classList.remove('dialog-open');
  if (lastFigureLink) lastFigureLink.focus({preventScroll:true});
});
