const menuButton = document.querySelector('.menu-button');
const navLinks = document.querySelector('.nav-links');
menuButton?.addEventListener('click', () => {
  const open = navLinks.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
});
navLinks?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
  navLinks.classList.remove('open');
  menuButton?.setAttribute('aria-expanded', 'false');
}));

const tour = document.querySelector('#market-tour');
const loopOption = document.querySelector('#tour-loop');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
function applyMotionPreference() {
  loopOption.checked = !reducedMotion.matches;
  tour.loop = loopOption.checked;
}
applyMotionPreference();
reducedMotion.addEventListener('change', applyMotionPreference);
loopOption.addEventListener('change', () => { tour.loop = loopOption.checked; });
// Audio is removed from the MP4 itself; muted also documents the intended playback.
tour.muted = true;

const showcasesButton = document.querySelector('#tour-showcases');
showcasesButton.addEventListener('click', () => {
  const jumpToShowcases = () => {
    tour.currentTime = 97;
    tour.play().catch(() => { tour.focus(); });
  };
  if (tour.readyState >= 1) jumpToShowcases();
  else {
    tour.addEventListener('loadedmetadata', jumpToShowcases, { once: true });
    tour.load();
  }
});
