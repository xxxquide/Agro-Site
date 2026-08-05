/* =============================================================================
   ЦЕНТРАГРО ПЛЮС — motion and interaction layer
   GSAP + ScrollTrigger for scroll-linked motion, Lenis for inertial scrolling.

   Why GSAP here and not the previous hand-rolled IntersectionObserver layer:
   the earlier pass animated only on enter/exit, so nothing could be tied to
   scroll *progress*. Parallax, the marquees and the hero fan all read as
   "snapping into place" instead of moving with the page. ScrollTrigger's scrub
   gives real scroll-linked motion, and Lenis smooths the wheel input that
   drives it — together they are what makes the source template feel soft.

   Every timing lives in DUR/EASE below so the whole site can be re-paced from
   one place. Everything is skipped wholesale under prefers-reduced-motion.
   ============================================================================= */
(function () {
  'use strict';

  var doc = document;
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasGSAP = typeof window.gsap !== 'undefined';

  /* --- shared pacing ------------------------------------------------------- */
  var DUR = { xs: 0.35, sm: 0.55, md: 0.9, lg: 1.15, xl: 1.5 };
  var EASE = {
    out: 'power3.out',
    soft: 'power2.out',
    expo: 'expo.out',
    back: 'back.out(1.5)',
  };
  var STAGGER = { tight: 0.05, word: 0.045, normal: 0.09, loose: 0.14 };

  function all(sel, ctx) {
    return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel));
  }
  function one(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function on(el, ev, fn, opt) { el && el.addEventListener(ev, fn, opt || false); }

  /* =========================================================================
     0. Smooth scrolling. Lenis drives ScrollTrigger rather than running beside
        it, otherwise the two disagree about scroll position and scrubbed
        animations jitter.
     ========================================================================= */
  var lenis = null;

  function initSmoothScroll() {
    if (REDUCED || typeof window.Lenis === 'undefined') return;

    lenis = new window.Lenis({
      duration: 1.05,
      easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
      smoothWheel: true,
      syncTouch: false,        // native momentum on touch feels better than faked
      touchMultiplier: 1.6,
      wheelMultiplier: 1,
    });

    if (hasGSAP && window.ScrollTrigger) {
      lenis.on('scroll', window.ScrollTrigger.update);
      window.gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
      window.gsap.ticker.lagSmoothing(0);
    } else {
      requestAnimationFrame(function raf(t) { lenis.raf(t); requestAnimationFrame(raf); });
    }
  }

  /* =========================================================================
     1. Word splitter for headline reveals.
        Walks text nodes only, so inline markup such as <span class="soft">
        survives and keeps its styling.
     ========================================================================= */
  function splitWords(el) {
    if (el.dataset.split === 'done') return all('.w', el);
    var walker = doc.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach(function (node) {
      var text = node.nodeValue;
      if (!text.trim()) return;
      var frag = doc.createDocumentFragment();
      text.split(/(\s+)/).forEach(function (chunk) {
        if (!chunk) return;
        if (/^\s+$/.test(chunk)) {
          frag.appendChild(doc.createTextNode(chunk));
        } else {
          var outer = doc.createElement('span');
          outer.className = 'w';
          var inner = doc.createElement('span');
          inner.className = 'w__i';
          inner.textContent = chunk;
          outer.appendChild(inner);
          frag.appendChild(outer);
        }
      });
      node.parentNode.replaceChild(frag, node);
    });

    el.dataset.split = 'done';
    return all('.w__i', el);
  }

  /* =========================================================================
     2. Reveals
     ========================================================================= */
  function revealAll() {
    var gsap = window.gsap;
    var ST = window.ScrollTrigger;

    /* --- headlines, word by word ----------------------------------------- */
    all('[data-split]').forEach(function (el) {
      var words = splitWords(el);
      if (!words.length) return;
      gsap.set(el, { autoAlpha: 1 });
      gsap.from(words, {
        yPercent: 116,
        autoAlpha: 0,
        duration: DUR.lg,
        ease: EASE.expo,
        stagger: STAGGER.word,
        scrollTrigger: { trigger: el, start: 'top 88%', once: true },
      });
    });

    /* --- generic fade-up, with optional group stagger -------------------- */
    all('[data-r]').forEach(function (el) {
      var mode = el.getAttribute('data-r') || 'up';
      var from = { autoAlpha: 0, duration: DUR.lg, ease: EASE.out };
      if (mode === 'up' || mode === '') from.y = 44;
      if (mode === 'left') from.x = -44;
      if (mode === 'right') from.x = 44;
      if (mode === 'in') { from.scale = 0.94; from.y = 24; }
      if (mode === 'none') from.y = 0;
      from.delay = parseFloat(el.getAttribute('data-delay') || 0);
      from.scrollTrigger = { trigger: el, start: 'top 90%', once: true };
      gsap.from(el, from);
    });

    /* --- containers whose children come in one after another ------------- */
    all('[data-stagger]').forEach(function (box) {
      var kids = box.children.length ? Array.prototype.slice.call(box.children) : [];
      if (!kids.length) return;
      gsap.from(kids, {
        y: 52,
        autoAlpha: 0,
        duration: DUR.lg,
        ease: EASE.out,
        stagger: parseFloat(box.getAttribute('data-stagger')) || STAGGER.normal,
        scrollTrigger: { trigger: box, start: 'top 86%', once: true },
      });
    });

    /* --- cards: lift and settle ------------------------------------------ */
    all('[data-card]').forEach(function (card) {
      gsap.from(card, {
        y: 60,
        scale: 0.955,
        autoAlpha: 0,
        duration: DUR.xl,
        ease: EASE.expo,
        scrollTrigger: { trigger: card, start: 'top 88%', once: true },
      });
    });

    /* --- progress bars, chart columns, orbit ----------------------------- */
    all('[data-bars]').forEach(function (box) {
      var fills = all('.bars__fill', box);
      gsap.fromTo(fills,
        { scaleX: 0 },
        {
          scaleX: 1,
          duration: DUR.xl,
          ease: EASE.expo,
          stagger: STAGGER.loose,
          scrollTrigger: { trigger: box, start: 'top 85%', once: true },
        });
    });

    all('[data-chart]').forEach(function (box) {
      var cols = all('.chart__fill', box);
      var vals = all('.chart__val', box);
      var tl = gsap.timeline({
        scrollTrigger: { trigger: box, start: 'top 85%', once: true },
      });
      tl.fromTo(cols, { scaleY: 0 },
        { scaleY: 1, duration: DUR.md, ease: EASE.back, stagger: 0.12 });
      tl.to(vals, { autoAlpha: 1, duration: DUR.sm, stagger: 0.12 }, '-=' + DUR.md);
    });

    all('[data-orbit]').forEach(function (box) {
      var rings = all('.orbit__ring', box);
      var hub = one('.orbit__hub', box);
      var pills = all('.orbit__pill', box);
      var tl = gsap.timeline({
        scrollTrigger: { trigger: box, start: 'top 82%', once: true },
      });
      tl.fromTo(rings, { scale: 0.55, autoAlpha: 0 },
        { scale: 1, autoAlpha: 1, duration: DUR.md, ease: EASE.back, stagger: 0.1 });
      if (hub) {
        tl.fromTo(hub, { scale: 0.5, autoAlpha: 0 },
          { scale: 1, autoAlpha: 1, duration: DUR.md, ease: EASE.back }, '-=' + DUR.sm);
      }
      tl.fromTo(pills, { scale: 0.6, autoAlpha: 0 },
        { scale: 1, autoAlpha: 1, duration: DUR.md, ease: EASE.back, stagger: 0.1 },
        '-=' + DUR.sm);
      tl.add(function () { box.classList.add('is-spinning'); });
    });

    /* --- lab rows -------------------------------------------------------- */
    all('[data-lab]').forEach(function (box) {
      gsap.from(all('.lab__row', box), {
        x: 26,
        autoAlpha: 0,
        duration: DUR.lg,
        ease: EASE.out,
        stagger: STAGGER.normal,
        scrollTrigger: { trigger: box, start: 'top 86%', once: true },
      });
    });

    if (ST) ST.refresh();
  }

  /* =========================================================================
     3. Parallax — scrubbed, so images drift with the scroll rather than
        popping when they enter.
     ========================================================================= */
  function initParallax() {
    var gsap = window.gsap;
    all('[data-parallax]').forEach(function (el) {
      var amount = parseFloat(el.getAttribute('data-parallax')) || 12;
      gsap.fromTo(el,
        { yPercent: -amount / 2 },
        {
          yPercent: amount / 2,
          ease: 'none',
          scrollTrigger: {
            trigger: el.parentElement || el,
            start: 'top bottom',
            end: 'bottom top',
            scrub: true,
          },
        });
    });
  }

  /* =========================================================================
     4. Marquees — one implementation for logo rows, tag rows and the card
        rail. The track holds its content twice; a modifier wraps x so the loop
        is seamless at any width.
     ========================================================================= */
  function initMarquees() {
    var gsap = window.gsap;

    all('[data-marquee]').forEach(function (row) {
      var dir = row.getAttribute('data-marquee') === 'right' ? 1 : -1;
      var speed = parseFloat(row.getAttribute('data-speed')) || 55; // px per second
      var track = one('.marq__track', row) || row.firstElementChild;
      if (!track) return;

      var loop = 0;
      var tween = null;

      function build() {
        if (tween) tween.kill();
        loop = track.scrollWidth / 2;
        if (!loop) return;
        gsap.set(track, { x: dir < 0 ? 0 : -loop });
        tween = gsap.to(track, {
          x: dir < 0 ? -loop : 0,
          duration: loop / speed,
          ease: 'none',
          repeat: -1,
          modifiers: {
            x: function (x) {
              var v = parseFloat(x) % loop;
              return (dir < 0 ? v : v - loop) + 'px';
            },
          },
        });
      }
      build();

      var rt;
      on(window, 'resize', function () {
        clearTimeout(rt);
        rt = setTimeout(build, 220);
      }, { passive: true });

      // pause off-screen and while hovered, so it never fights the reader
      if (window.ScrollTrigger) {
        window.ScrollTrigger.create({
          trigger: row,
          start: 'top bottom',
          end: 'bottom top',
          onToggle: function (self) {
            if (!tween) return;
            self.isActive ? tween.play() : tween.pause();
          },
        });
      }
      if (row.hasAttribute('data-marquee-hover')) {
        on(row, 'mouseenter', function () { tween && tween.timeScale(0.25); });
        on(row, 'mouseleave', function () { tween && tween.timeScale(1); });
      }
    });
  }

  /* =========================================================================
     5. Hero opening sequence — runs on load, not on scroll.
     ========================================================================= */
  function initHero() {
    var gsap = window.gsap;
    var hero = one('[data-hero]');
    if (!hero) return;

    var tl = gsap.timeline({ defaults: { ease: EASE.expo } });
    var title = one('[data-hero-title]', hero);
    var sub = all('[data-hero-item]', hero);
    var fanItems = all('.fan__item', hero);
    var media = one('[data-hero-media]', hero);

    if (media) {
      tl.fromTo(media, { scale: 1.09, autoAlpha: 0 },
        { scale: 1, autoAlpha: 1, duration: 1.8 }, 0);
    }
    if (title) {
      var words = splitWords(title);
      gsap.set(title, { autoAlpha: 1 });
      tl.from(words, {
        yPercent: 116, autoAlpha: 0, duration: DUR.xl, stagger: STAGGER.word,
      }, 0.15);
    }
    if (sub.length) {
      tl.from(sub, { y: 30, autoAlpha: 0, duration: DUR.lg, stagger: 0.1 }, 0.5);
    }
    if (fanItems.length) {
      hero.classList.add('fan-ready');
      tl.from(fanItems, {
        y: 90, autoAlpha: 0, duration: DUR.xl, stagger: 0.075,
      }, 0.6);
    }
  }

  /* =========================================================================
     6. Crop panels — slow, hover-intent driven. The previous build opened on
        raw mouseenter with a 0.62s transition, which is what read as a snap.
     ========================================================================= */
  function initCrops() {
    var panels = all('.crop');
    if (!panels.length) return;
    var wide = window.matchMedia('(hover: hover) and (min-width: 64rem)');
    var timer = null;

    function open(target) {
      panels.forEach(function (p) {
        p.setAttribute('aria-expanded', p === target ? 'true' : 'false');
      });
      if (window.ScrollTrigger) window.ScrollTrigger.refresh();
    }

    panels.forEach(function (p) {
      on(p, 'click', function () { clearTimeout(timer); open(p); });
      on(p, 'focus', function () { if (wide.matches) open(p); });
      on(p, 'mouseenter', function () {
        if (!wide.matches) return;
        clearTimeout(timer);
        timer = setTimeout(function () { open(p); }, 130);  // hover intent
      });
      on(p, 'mouseleave', function () { clearTimeout(timer); });
    });
  }

  /* =========================================================================
     7. Counters
     ========================================================================= */
  function initCounters() {
    var gsap = window.gsap;
    var lang = doc.documentElement.getAttribute('lang') || 'uk';
    var fmt;
    try {
      fmt = new Intl.NumberFormat(lang === 'uk' ? 'uk-UA' : 'en-GB');
    } catch (e) {
      fmt = { format: function (n) { return String(n); } };
    }

    all('[data-count]').forEach(function (el) {
      var target = parseFloat(el.getAttribute('data-count'));
      if (isNaN(target)) return;
      var suffix = el.getAttribute('data-suffix') || '';

      if (REDUCED || !hasGSAP) {
        el.textContent = fmt.format(target) + suffix;
        return;
      }
      var obj = { v: 0 };
      gsap.to(obj, {
        v: target,
        duration: 2,
        ease: 'power2.out',
        onUpdate: function () {
          el.textContent = fmt.format(Math.round(obj.v)) + suffix;
        },
        scrollTrigger: { trigger: el, start: 'top 92%', once: true },
      });
    });
  }

  /* =========================================================================
     8. Header, drawer, rails, forms — plain interaction, no motion library
     ========================================================================= */
  function initChrome() {
    /* sticky header state from a 1px sentinel */
    var hdr = one('.hdr');
    var sentinel = one('.sentinel');
    if (hdr && sentinel && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (e) {
        hdr.classList.toggle('is-stuck', !e[0].isIntersecting);
      }, { threshold: 0 }).observe(sentinel);
    }

    /* mobile drawer */
    var burger = one('.burger');
    var drawer = one('.drawer');
    function setDrawer(open) {
      doc.body.classList.toggle('nav-open', open);
      if (lenis) open ? lenis.stop() : lenis.start();
      doc.body.style.overflow = open ? 'hidden' : '';
      if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (drawer) drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    }
    on(burger, 'click', function () {
      setDrawer(!doc.body.classList.contains('nav-open'));
    });
    all('.drawer a').forEach(function (a) {
      on(a, 'click', function () { setDrawer(false); });
    });
    on(doc, 'keydown', function (e) {
      if (e.key === 'Escape' && doc.body.classList.contains('nav-open')) {
        setDrawer(false);
        burger && burger.focus();
      }
    });

    /* in-page anchors need to go through Lenis, or they jump */
    all('a[href^="#"]').forEach(function (a) {
      on(a, 'click', function (e) {
        var id = a.getAttribute('href');
        if (!id || id === '#') return;
        var target = doc.querySelector(id);
        if (!target) return;
        e.preventDefault();
        if (lenis) lenis.scrollTo(target, { offset: -80, duration: 1.4 });
        else target.scrollIntoView({ behavior: 'smooth' });
      });
    });

    /* horizontal rails */
    all('[data-rail]').forEach(function (rail) {
      var group = rail.closest('section') || doc;
      var prev = one('[data-rail-prev]', group);
      var next = one('[data-rail-next]', group);
      function step() {
        var card = rail.firstElementChild;
        if (!card) return rail.clientWidth * 0.8;
        var gap = parseFloat(getComputedStyle(rail).columnGap || '24') || 24;
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

    /* accordion (FAQ) uses <details>; keep ScrollTrigger in sync on toggle */
    all('details').forEach(function (d) {
      on(d, 'toggle', function () {
        if (window.ScrollTrigger) window.ScrollTrigger.refresh();
      });
    });

    /* demo forms have no backend — say so instead of faking a submit */
    all('[data-demo-form]').forEach(function (form) {
      on(form, 'submit', function (e) {
        e.preventDefault();
        var ok = one('.form__ok', form);
        if (ok) { ok.classList.add('is-on'); ok.setAttribute('role', 'status'); }
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
      });
    });

    /* Active nav link while scrolling. Only applies to links that point at a
       section on THIS page; the page-level current link is set server-side with
       aria-current="page" and must not be overwritten. */
    var navLinks = all('.nav__link[href*="#"]:not([aria-current="page"])');
    if (navLinks.length && 'IntersectionObserver' in window) {
      var map = {};
      navLinks.forEach(function (a) {
        var hash = (a.getAttribute('href') || '').split('#')[1];
        var sec = hash && doc.getElementById(hash);
        if (sec) map[hash] = a;
      });
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          navLinks.forEach(function (l) { l.removeAttribute('aria-current'); });
          var a = map[en.target.id];
          if (a) a.setAttribute('aria-current', 'true');
        });
      }, { rootMargin: '-45% 0px -50% 0px' });
      Object.keys(map).forEach(function (id) { io.observe(doc.getElementById(id)); });
    }
  }

  /* =========================================================================
     boot
     ========================================================================= */
  function boot() {
    initChrome();
    initCrops();

    if (REDUCED || !hasGSAP) {
      // show everything in its final state
      doc.documentElement.classList.add('no-motion');
      all('[data-count]').forEach(function (el) {
        var t = parseFloat(el.getAttribute('data-count'));
        if (!isNaN(t)) el.textContent = t + (el.getAttribute('data-suffix') || '');
      });
      return;
    }

    window.gsap.registerPlugin(window.ScrollTrigger);
    window.gsap.config({ nullTargetWarn: false });
    doc.documentElement.classList.add('motion-ready');

    initSmoothScroll();
    initHero();
    revealAll();
    initParallax();
    initMarquees();
    initCounters();

    // late webfont/image sizing changes would otherwise leave triggers stale
    on(window, 'load', function () { window.ScrollTrigger.refresh(); });
  }

  if (doc.readyState === 'loading') {
    on(doc, 'DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
