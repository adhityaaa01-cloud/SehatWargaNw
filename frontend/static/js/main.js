// Shared, one-shot map loading; CSS reserves the existing map dimensions.
window.SehatWarga = (() => {
  let mapPromise;
  function loadMapLibrary() {
    if (window.mapboxgl) return Promise.resolve(window.mapboxgl);
    if (!mapPromise) mapPromise = new Promise((resolve,reject) => {
      const script = document.createElement('script');
      script.src = 'https://api.mapbox.com/mapbox-gl-js/v3.25.0/mapbox-gl.js';
      const fail = () => {clearTimeout(timer);script.remove();mapPromise=null;reject(new Error('Mapbox tidak dapat dimuat'));};
      const timer = setTimeout(fail,12000);
      script.onload = () => {clearTimeout(timer);resolve(window.mapboxgl);};
      script.onerror = fail;
      document.head.append(script);
    });
    return mapPromise;
  }
  function whenNearViewport(element, callback) {
    let observer;
    let started = false;
    const cancel = () => { started = true; observer?.disconnect(); };
    const start = () => {
      if (started || !element.isConnected) return;
      started = true;
      observer?.disconnect();
      callback();
    };
    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) start();
      }, { rootMargin: '200px' });
      observer.observe(element);
    } else start();
    return { start, cancel };
  }
  return { loadMapLibrary, whenNearViewport };
})();

document.addEventListener('DOMContentLoaded', () => {
  if (document.documentElement.dataset.mainInitialized) return;
  document.documentElement.dataset.mainInitialized = 'true';
  const nav = document.getElementById('site-navigation');
  const toggle = document.getElementById('nav-toggle');
  const close = document.getElementById('nav-close');
  const overlay = document.getElementById('nav-overlay');
  const backgrounds = [document.querySelector('main'), document.querySelector('footer'), document.querySelector('.navbar-brand'), toggle];
  const mobile = window.matchMedia('(max-width:1023px)');
  function setOpen(open) {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('nav-open', open);
    overlay.hidden = !open;
    backgrounds.forEach(el => { if(el) el.inert = open; });
    if(open) { nav.setAttribute('role','dialog'); nav.setAttribute('aria-modal','true'); requestAnimationFrame(() => { if(nav.classList.contains('is-open')) close.focus(); }); }
    else { nav.removeAttribute('role'); nav.removeAttribute('aria-modal'); if(mobile.matches) toggle.focus(); }
  }
  toggle.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
  close.addEventListener('click', () => setOpen(false));
  overlay.addEventListener('click', () => setOpen(false));
  mobile.addEventListener('change', () => setOpen(false));
  nav.addEventListener('click', e => { if(mobile.matches && e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', e => {
    if(e.key === 'Escape') {
      if(nav.classList.contains('is-open')) setOpen(false);
      document.querySelectorAll('.nav-dropdown[open]').forEach(d => { d.open=false; d.querySelector('summary').focus(); });
    }
    if(e.key === 'Tab' && nav.classList.contains('is-open')) {
      const focusable = [...nav.querySelectorAll('a,button,input:not([type="hidden"]),summary')].filter(el => el.getClientRects().length && getComputedStyle(el).visibility === 'visible' && !el.disabled && !el.closest('details:not([open]) .dropdown-panel'));
      if(!focusable.length) { e.preventDefault(); return; }
      const first=focusable[0], last=focusable[focusable.length-1];
      if(!nav.contains(document.activeElement)) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
      else if(e.shiftKey && document.activeElement===first) { e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement===last) { e.preventDefault(); first.focus(); }
    }
  });
  document.addEventListener('click', e => document.querySelectorAll('.nav-dropdown[open]').forEach(d => { if(!d.contains(e.target)) d.open=false; }));
  document.querySelectorAll('.data-table').forEach(table => {
    const headers=[...table.querySelectorAll('thead th')].map(h=>h.textContent.trim());
    table.classList.add('mobile-cards');
    table.querySelectorAll('tbody tr').forEach(row=> [...row.children].forEach((cell,i)=> {cell.dataset.label=headers[i] || ''; }));
  });
  document.querySelectorAll('.form-group').forEach((group,i) => {
    const field=group.querySelector('input:not([type="hidden"]),select,textarea');
    if(!field) return;
    const label=group.querySelector('label');
    field.id ||= `field-${i}`;
    if(label && !label.htmlFor) label.htmlFor=field.id;
    const descriptions=[...group.querySelectorAll('.form-error,.form-hint')];
    descriptions.forEach((el,j)=>{ el.id ||= `${field.id}-hint-${j}`; if(el.classList.contains('form-error')) el.setAttribute('role','alert'); });
    if(descriptions.length) field.setAttribute('aria-describedby',descriptions.map(el=>el.id).join(' '));
    if(group.querySelector('.form-error')) field.setAttribute('aria-invalid','true');
  });
  document.querySelectorAll('form[method="POST"]').forEach(form => form.addEventListener('submit',e=> {
    if(e.defaultPrevented) return;
    if(form.dataset.submitting) { e.preventDefault(); return; }
    form.dataset.submitting='true'; form.setAttribute('aria-busy','true');
    // Keep named submit controls enabled so their values still reach the server.
    form.querySelectorAll('button[type="submit"]').forEach(button=> { if(!button.name) {button.disabled=true; button.dataset.label=button.textContent; button.textContent='Memproses…';} });
  }));
  window.addEventListener('pageshow',()=>document.querySelectorAll('form[data-submitting]').forEach(form=> {delete form.dataset.submitting; form.removeAttribute('aria-busy'); form.querySelectorAll('button[data-label]').forEach(b=>{b.disabled=false;b.textContent=b.dataset.label;});}));


  const hero = document.querySelector('.hero-section');
  const heroMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (hero && 'animate' in Element.prototype && !heroMotion.matches) {
    const elements = ['.eyebrow', 'h1', '.hero-description', '.hero-actions', '.hero-note']
      .map(selector => hero.querySelector(selector)).filter(Boolean);
    // Move the whole text column together so its left edge stays aligned.
    const movement = hero.querySelector('.hero-content').animate([
      { transform: 'translateX(-32px)' },
      { transform: 'translateX(0)' }
    ], { duration: 650, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'backwards' });
    const animations = [movement, ...elements.map((element, index) => element.animate([
      { opacity: 0 }, { opacity: 1 }
    ], { duration: 650, delay: index * 110, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'backwards' }))];
    hero.addEventListener('focusin', () => animations.forEach(animation => animation.cancel()));
    heroMotion.addEventListener('change', event => {
      if (event.matches) animations.forEach(animation => animation.cancel());
    });
  }

});
