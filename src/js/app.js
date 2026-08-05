/* =============================================================================
   ЦЕНТРАГРО ПЛЮС — interaction layer
   No framework, no dependencies. Everything is IntersectionObserver or a direct
   event handler; there is not a single scroll listener in this file, because
   scroll handlers are what make a page like this stutter.
   ============================================================================= */
(function () {
  'use strict';

  var doc = document;
  var root = doc.documentElement;
  var LANG = root.getAttribute('lang') || 'uk';
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function on(el, ev, fn, opt) { el && el.addEventListener(ev, fn, opt || false); }
  function all(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }
  function one(sel, ctx) { return (ctx || doc).querySelector(sel); }

  /* ---------------------------------------------------------------------------
     1. Reveal on enter — one observer for the whole page.
     --------------------------------------------------------------------------- */
  var revealTargets = '[data-r], .cap__card, .fan, .plan, .stats';

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-in');
        io.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });

    all(revealTargets).forEach(function (el) { io.observe(el); });
  } else {
    all(revealTargets).forEach(function (el) { el.classList.add('is-in'); });
  }

  /* ---------------------------------------------------------------------------
     2. Sticky header — driven by a 1px sentinel, not by scroll position.
     --------------------------------------------------------------------------- */
  var hdr = one('.hdr');
  var sentinel = one('.sentinel');

  if (hdr && sentinel && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      hdr.classList.toggle('is-stuck', !entries[0].isIntersecting);
    }, { threshold: 0 }).observe(sentinel);
  }

  /* ---------------------------------------------------------------------------
     3. Mobile drawer
     --------------------------------------------------------------------------- */
  var burger = one('.burger');
  var drawer = one('.drawer');

  function setDrawer(open) {
    doc.body.classList.toggle('nav-open', open);
    doc.body.style.overflow = open ? 'hidden' : '';
    if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (drawer) drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
  }

  on(burger, 'click', function () {
    setDrawer(!doc.body.classList.contains('nav-open'));
  });

  all('.drawer__link, .drawer a').forEach(function (a) {
    on(a, 'click', function () { setDrawer(false); });
  });

  on(doc, 'keydown', function (e) {
    if (e.key === 'Escape' && doc.body.classList.contains('nav-open')) {
      setDrawer(false);
      burger && burger.focus();
    }
  });

  /* ---------------------------------------------------------------------------
     4. Crop panels — one open at a time, click everywhere, hover on desktop.
     --------------------------------------------------------------------------- */
  var crops = all('.crop');
  var hoverOpens = window.matchMedia('(hover: hover) and (min-width: 64rem)');

  function openCrop(target) {
    crops.forEach(function (c) {
      c.setAttribute('aria-expanded', c === target ? 'true' : 'false');
    });
  }

  crops.forEach(function (c) {
    on(c, 'click', function () { openCrop(c); });
    on(c, 'focus', function () { if (hoverOpens.matches) openCrop(c); });
    on(c, 'mouseenter', function () { if (hoverOpens.matches) openCrop(c); });
  });

  /* ---------------------------------------------------------------------------
     5. Scroll rails (testimonials) — native scrolling, JS only moves it.
     --------------------------------------------------------------------------- */
  all('[data-rail]').forEach(function (rail) {
    var group = rail.closest('section') || doc;
    var prev = one('[data-rail-prev]', group);
    var next = one('[data-rail-next]', group);
    var card = rail.firstElementChild;

    function step() {
      if (!card) return rail.clientWidth * 0.8;
      var gap = parseFloat(getComputedStyle(rail).columnGap || '20') || 20;
      return card.getBoundingClientRect().width + gap;
    }

    function sync() {
      var max = rail.scrollWidth - rail.clientWidth - 2;
      if (prev) prev.disabled = rail.scrollLeft <= 2;
      if (next) next.disabled = rail.scrollLeft >= max;
    }

    on(prev, 'click', function () { rail.scrollBy({ left: -step(), behavior: 'smooth' }); });
    on(next, 'click', function () { rail.scrollBy({ left: step(), behavior: 'smooth' }); });
    on(rail, 'scroll', sync, { passive: true });
    sync();
  });

  /* ---------------------------------------------------------------------------
     6. Counters — count up once, formatted for the active locale.
     --------------------------------------------------------------------------- */
  var fmt = (function () {
    try { return new Intl.NumberFormat(LANG === 'uk' ? 'uk-UA' : 'en-GB'); }
    catch (err) { return { format: function (n) { return String(n); } }; }
  })();

  function countUp(el) {
    var target = parseFloat(el.getAttribute('data-count'));
    if (isNaN(target)) return;
    var suffix = el.getAttribute('data-suffix') || '';

    if (REDUCED) {
      el.textContent = fmt.format(target) + suffix;
      return;
    }

    var dur = 1250;
    var t0 = performance.now();

    function frame(now) {
      var p = Math.min((now - t0) / dur, 1);
      // easeOutExpo — fast start, long settle, reads as "counting up"
      var e = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
      el.textContent = fmt.format(Math.round(target * e)) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  if ('IntersectionObserver' in window) {
    var ioCount = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        countUp(e.target);
        ioCount.unobserve(e.target);
      });
    }, { threshold: 0.5 });
    all('[data-count]').forEach(function (el) { ioCount.observe(el); });
  } else {
    all('[data-count]').forEach(countUp);
  }

  /* ---------------------------------------------------------------------------
     7. Hero fan parallax — pointer only, rAF-coalesced, never on touch.
     --------------------------------------------------------------------------- */
  var fan = one('.fan');
  var fine = window.matchMedia('(hover: hover) and (pointer: fine) and (min-width: 56.25rem)');

  if (fan && fine.matches && !REDUCED) {
    var queued = false, mx = 0, my = 0;

    function apply() {
      queued = false;
      fan.style.setProperty('--tilt-y', (mx * 4.5).toFixed(2) + 'deg');
      fan.style.setProperty('--tilt-x', (my * -2.2).toFixed(2) + 'deg');
    }

    on(window, 'pointermove', function (e) {
      mx = (e.clientX / window.innerWidth) * 2 - 1;
      my = (e.clientY / window.innerHeight) * 2 - 1;
      if (!queued) { queued = true; requestAnimationFrame(apply); }
    }, { passive: true });
  }

  /* ---------------------------------------------------------------------------
     8. Marquee — set a constant pixel speed, pause when out of view.
     --------------------------------------------------------------------------- */
  all('.marquee').forEach(function (m) {
    var track = one('.marquee__track', m);
    if (!track) return;

    function tune() {
      // the track holds the list twice, so one loop = half its width
      var loop = track.scrollWidth / 2;
      if (loop > 0) track.style.setProperty('--d', (loop / 42).toFixed(1) + 's');
    }
    tune();

    var rt;
    on(window, 'resize', function () {
      clearTimeout(rt);
      rt = setTimeout(tune, 200);
    }, { passive: true });

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        m.classList.toggle('is-out', !entries[0].isIntersecting);
      }, { threshold: 0 }).observe(m);
    }
  });

  /* ---------------------------------------------------------------------------
     9. Active section in the nav
     --------------------------------------------------------------------------- */
  var navLinks = all('.nav__link[href^="#"]');

  if (navLinks.length && 'IntersectionObserver' in window) {
    var map = {};
    navLinks.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      var sec = id && doc.getElementById(id);
      if (sec) map[id] = a;
    });

    var ioNav = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var a = map[e.target.id];
        if (!a) return;
        if (e.isIntersecting) {
          navLinks.forEach(function (l) { l.removeAttribute('aria-current'); });
          a.setAttribute('aria-current', 'true');
        }
      });
    }, { rootMargin: '-45% 0px -50% 0px' });

    Object.keys(map).forEach(function (id) { ioNav.observe(doc.getElementById(id)); });
  }

  /* ---------------------------------------------------------------------------
     10. Forms — this is a demo build with no backend, so say so honestly
         instead of pretending to submit.
     --------------------------------------------------------------------------- */
  all('[data-demo-form]').forEach(function (form) {
    on(form, 'submit', function (e) {
      e.preventDefault();
      var ok = one('.form__ok', form);
      if (ok) {
        ok.classList.add('is-on');
        ok.setAttribute('role', 'status');
      }
      form.querySelector('button[type="submit"]').disabled = true;
    });
  });
})();
