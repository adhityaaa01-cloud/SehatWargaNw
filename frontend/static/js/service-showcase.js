// One dwell timer and one transition at a time; no timers run offscreen.
(() => {
  const carousel = document.querySelector('[data-service-showcase]');
  if (!carousel) return;
  const slides = [...carousel.querySelectorAll('.service-slide')];
  const controls = carousel.querySelector('.showcase-controls');
  const previous = carousel.querySelector('[data-showcase-previous]');
  const next = carousel.querySelector('[data-showcase-next]');
  const play = carousel.querySelector('[data-showcase-play]');
  const counter = carousel.querySelector('[data-slide-count]');
  const status = carousel.querySelector('[data-showcase-status]');
  const steps = [...carousel.querySelectorAll('.showcase-step')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const dwell = 4000;
  const duration = 480;
  let index = 0;
  let visible = false;
  let hovered = false;
  let focused = carousel.contains(document.activeElement);
  let suspended = false;
  let paused = motion.matches;
  let dwellTimer;
  let transitionTimer;
  let finishTransition;

  function stopTimer() {
    window.clearTimeout(dwellTimer);
    dwellTimer = undefined;
    carousel.classList.remove('is-playing');
  }

  function renderControls() {
    counter.textContent = `${String(index + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
    steps.forEach((step, i) => {
      step.classList.toggle('is-current', i === index);
      step.classList.toggle('is-complete', i < index);
    });
    carousel.classList.toggle('is-paused', paused);
    const label = paused ? 'Putar otomatis' : 'Jeda otomatis';
    play.setAttribute('aria-label', label);
  }

  function schedule() {
    stopTimer();
    if (!visible || document.hidden || suspended || hovered || focused || paused || finishTransition) return;
    // Reset the CSS progress animation along with the single dwell timer.
    void carousel.offsetWidth;
    carousel.classList.add('is-playing');
    dwellTimer = window.setTimeout(() => move(1, false), dwell);
  }

  function move(direction, manual) {
    stopTimer();
    if (finishTransition) return; // Repeated clicks cannot start overlapping transitions.
    const outgoing = slides[index];
    const incomingIndex = (index + direction + slides.length) % slides.length;
    const incoming = slides[incomingIndex];
    incoming.hidden = false;
    // Resolve the parked state before starting the CSS transition.
    void incoming.offsetWidth;
    outgoing.inert = true;
    outgoing.setAttribute('aria-hidden', 'true');
    incoming.inert = false;
    incoming.removeAttribute('aria-hidden');
    index = incomingIndex;
    renderControls();
    previous.setAttribute('aria-disabled', 'true');
    next.setAttribute('aria-disabled', 'true');

    const settle = () => {
      if (finishTransition !== settle) return;
      window.clearTimeout(transitionTimer);
      incoming.removeEventListener('transitionend', onEnd);
      outgoing.hidden = true;
      outgoing.classList.remove('is-leaving');
      finishTransition = undefined;
      previous.removeAttribute('aria-disabled');
      next.removeAttribute('aria-disabled');
      schedule();
    };
    const onEnd = event => {
      if (event.target === incoming && event.propertyName === 'transform') settle();
    };
    finishTransition = settle;
    incoming.addEventListener('transitionend', onEnd);
    outgoing.classList.replace('is-current', 'is-leaving');
    incoming.classList.add('is-current');
    if (manual) status.textContent = incoming.getAttribute('aria-label');
    if (motion.matches || !visible || document.hidden) settle();
    else transitionTimer = window.setTimeout(settle, duration + 80);
  }

  slides.forEach((slide, i) => {
    slide.hidden = i !== 0;
    slide.inert = i !== 0;
    if (i !== 0) slide.setAttribute('aria-hidden', 'true');
  });
  slides[0].classList.add('is-current');
  carousel.classList.add('is-enhanced');
  controls.hidden = false;
  renderControls();

  previous.addEventListener('click', () => move(-1, true));
  next.addEventListener('click', () => move(1, true));
  play.addEventListener('click', () => {
    paused = !paused;
    renderControls();
    schedule();
  });
  carousel.addEventListener('pointerenter', event => {
    if (event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
    hovered = true;
    schedule();
  });
  carousel.addEventListener('pointerleave', () => { hovered = false; schedule(); });
  carousel.addEventListener('pointercancel', () => { hovered = false; schedule(); });
  carousel.addEventListener('focusin', () => { focused = true; schedule(); });
  carousel.addEventListener('focusout', () => {
    // Wait for focus to reach its destination, without moving it ourselves.
    queueMicrotask(() => { focused = carousel.contains(document.activeElement); schedule(); });
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) finishTransition?.();
    schedule();
  });
  motion.addEventListener('change', event => {
    if (event.matches) {
      paused = true;
      finishTransition?.();
      renderControls();
    }
    schedule();
  });
  window.addEventListener('pagehide', () => {
    suspended = true;
    stopTimer();
    finishTransition?.();
  });
  window.addEventListener('pageshow', () => { suspended = false; schedule(); });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting && entries[0].intersectionRatio >= .25;
      if (!visible) finishTransition?.();
      schedule();
    }, { threshold: [0, .25] });
    observer.observe(carousel);
  }
  // Without IntersectionObserver the controls still work; autoplay stays off.
})();
