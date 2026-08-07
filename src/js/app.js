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
  var reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  var REDUCED = reducedQuery.matches;
  var finePointerQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
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

  // A system preference can change while the page is open. Rebooting is the
  // safest way to tear down scrubbed timelines and Lenis without leaving stale
  // transforms behind.
  on(reducedQuery, 'change', function () { window.location.reload(); });

  var refreshFrame = 0;
  function scheduleRefresh() {
    if (!window.ScrollTrigger) return;
    cancelAnimationFrame(refreshFrame);
    refreshFrame = requestAnimationFrame(function () { window.ScrollTrigger.refresh(); });
  }

  var lang = doc.documentElement.getAttribute('lang') || 'uk';
  var numberFormatter;
  try {
    numberFormatter = new Intl.NumberFormat(lang === 'uk' ? 'uk-UA' : 'en-GB');
  } catch (e) {
    numberFormatter = { format: function (n) { return String(n); } };
  }
  /* The locale-correct way to print a counter's final value. Deliberately NOT
     used by settleCounters() below: every non-animating branch has always
     printed the raw digits, so a visitor with reduced motion reads "14200"
     where everyone else reads "14 200". Wiring this in would fix that
     inconsistency and change what those visitors see, which is a decision for
     the owner and not a side effect of a performance pass. Kept here because it
     is where that fix belongs when it is signed off. */
  function renderCounterFinal(el) {
    var target = parseFloat(el.getAttribute('data-count'));
    if (isNaN(target)) return;
    el.textContent = numberFormatter.format(target) + (el.getAttribute('data-suffix') || '');
  }

  /* Final values for every branch that never animates them — the reduced-motion
     and no-GSAP paths, and the failsafe. One helper so a future change cannot
     move one of them and leave the others behind. Formatting is byte-for-byte
     what the reduced-motion branch already produced; see above. */
  function settleCounters() {
    all('[data-count]').forEach(function (el) {
      var t = parseFloat(el.getAttribute('data-count'));
      if (!isNaN(t)) el.textContent = t + (el.getAttribute('data-suffix') || '');
    });
  }

  /* =========================================================================
     0. Smooth scrolling. Lenis drives ScrollTrigger rather than running beside
        it, otherwise the two disagree about scroll position and scrubbed
        animations jitter.
     ========================================================================= */
  var lenis = null;
  var lenisTick = null;

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
      lenisTick = function (time) { if (lenis && !doc.hidden) lenis.raf(time * 1000); };
      window.gsap.ticker.add(lenisTick);
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

     Every entrance here is fromTo, never from. `gsap.from()` captures the
     element's *current* value as the destination at the moment the tween is
     built, and renders the start state immediately. Combine that with the
     ScrollTrigger.refresh() this page fires whenever a lazy image lands or the
     layout changes, and a from-tween can re-record its own start state as its
     destination — the element then animates to where it began and simply stays
     there. That is exactly what pinned every testimonial card 52px low, and it
     would have done the same to the stats grid and the news cards. Spelling
     both ends out removes the ambiguity for good.

     Every entrance animates `opacity`, never GSAP's `autoAlpha`. autoAlpha is
     opacity plus `visibility`, and the visibility half is what put most of the
     page's text outside the accessibility tree: an unrevealed section was not
     merely invisible, it was unreadable to a screen reader and unreachable by
     tab, and 22 of this page's 23 headings were missing from the tree until
     something scrolled. Opacity alone renders identically — the flash guard in
     05-motion.css moved to `opacity: 0` to match — while leaving the node in
     the tree and in the tab order, so focus can enter it, the browser scrolls
     it into view, and its own trigger fires. Do not trade that back for the
     convenience of one property name.
     ========================================================================= */
  /* Each pass below is its own function purely so boot() can spend them across
     several idle callbacks. Their bodies are unchanged and the array order is
     the order they used to be called in — see the ordering note in boot(),
     which explains why that is not cosmetic. */
  function revealPasses() {
    var gsap = window.gsap;
    var ST = window.ScrollTrigger;
    return [
      function revealHeadlines() {
      /* --- headlines, word by word ----------------------------------------- */
      all('[data-split]:not([data-page-title])').forEach(function (el) {
        var words = splitWords(el);
        if (!words.length) return;
        gsap.set(el, { opacity: 1 });
        /* fromTo, not from — see the note above initReveal(). */
        gsap.fromTo(words,
          { yPercent: 116, opacity: 0 },
          {
            yPercent: 0,
            opacity: 1,
            duration: DUR.lg,
            ease: EASE.expo,
            stagger: STAGGER.word,
            scrollTrigger: { trigger: el, start: 'top 88%', once: true },
          });
      });
      },
      function revealGeneric() {
      /* --- generic fade-up, with optional group stagger -------------------- */
      all('[data-r]').forEach(function (el) {
        var mode = el.getAttribute('data-r') || 'up';
        var from = { opacity: 0 };
        var to = {
          opacity: 1, x: 0, y: 0, scale: 1,
          duration: DUR.lg, ease: EASE.out,
          delay: parseFloat(el.getAttribute('data-delay') || 0),
          scrollTrigger: { trigger: el, start: 'top 90%', once: true },
        };
        if (mode === 'up' || mode === '') from.y = 44;
        if (mode === 'left') from.x = -44;
        if (mode === 'right') from.x = 44;
        if (mode === 'in') { from.scale = 0.94; from.y = 24; }
        if (mode === 'none') from.y = 0;
        gsap.fromTo(el, from, to);
      });
      },
      function revealStaggers() {
      /* --- containers whose children come in one after another ------------- */
      all('[data-stagger]').forEach(function (box) {
        var kids = box.children.length ? Array.prototype.slice.call(box.children) : [];
        if (!kids.length) return;
        gsap.fromTo(kids,
          { y: 52, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: DUR.lg,
            ease: EASE.out,
            stagger: parseFloat(box.getAttribute('data-stagger')) || STAGGER.normal,
            scrollTrigger: { trigger: box, start: 'top 86%', once: true },
          });
      });
      },
      function revealCards() {
      /* --- cards: lift and settle ------------------------------------------ */
      all('[data-card]').forEach(function (card) {
        gsap.fromTo(card,
          { y: 60, scale: 0.955, opacity: 0 },
          {
            y: 0,
            scale: 1,
            opacity: 1,
            duration: DUR.xl,
            ease: EASE.expo,
            scrollTrigger: { trigger: card, start: 'top 88%', once: true },
          });
      });
      },
      function revealCapacity() {
      /* --- capacity lifecycle and data visualizations ---------------------- */
      all('[data-capacity-card]').forEach(function (card) {
        var inView = false;
        function syncCapacity() { card.classList.toggle('is-active', inView && !doc.hidden); }
        if (ST) ST.create({
          trigger: card, start: 'top bottom', end: 'bottom top',
          onToggle: function (self) { inView = self.isActive; syncCapacity(); },
        });
        on(doc, 'visibilitychange', syncCapacity);
      });
      },
      function revealBars() {
      all('[data-bars]').forEach(function (box) {
        // The template's own storage panel: the split track wipes open from the
        // left, then the facility rows slide in from the right behind it.
        var tl = gsap.timeline({
          scrollTrigger: { trigger: box, start: 'top 85%', once: true },
        });
        tl.fromTo(all('.frac__seg', box),
          { scaleX: 0 },
          { scaleX: 1, duration: .9, ease: 'power2.inOut', stagger: .12 });
        tl.fromTo(all('.grow', box),
          { x: 20, opacity: 0 },
          { x: 0, opacity: 1, duration: .4, ease: EASE.soft, stagger: .1 }, '-=.35');
      });
      },
      function revealSignals() {
      all('.svc-signal').forEach(function (box) {
        gsap.fromTo(all('.svc-signal__track i', box),
          { scaleX: 0 },
          {
            scaleX: 1,
            duration: DUR.lg,
            ease: EASE.expo,
            stagger: STAGGER.tight,
            scrollTrigger: { trigger: box, start: 'top 90%', once: true },
          });
      });
      },
      function revealStatCards() {
      all('[data-stat-card]').forEach(function (card) {
        gsap.fromTo(all('.stats-card__spark i, .stats-card__plot i', card),
          { scaleY: 0 },
          {
            scaleY: 1,
            duration: DUR.lg,
            ease: EASE.back,
            stagger: STAGGER.tight,
            scrollTrigger: { trigger: card, start: 'top 90%', once: true },
          });
      });
      },
      function revealRouteMaps() {
      all('[data-route-map]').forEach(function (map) {
        var routes = all('.ukraine-map__route', map);
        var points = all('.ukraine-map__point', map);
        var hub = one('.ukraine-map__hub', map);

        // NOTE: never tween a transform on the marker <g> elements. Each one is
        // positioned by transform="translate(x y)", and GSAP takes ownership of
        // `transform` the moment it touches it — the markers drifted up and left
        // of their own coordinates, which is what made every route look like it
        // stopped short of its city. Opacity on the group, scale on the inner
        // circles (which carry transform-box: fill-box), and the translate is
        // never in play.
        function popMarker(g, at) {
          tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: DUR.sm }, at);
          tl.fromTo(all('circle', g), { scale: 0.4 },
            { scale: 1, duration: DUR.md, ease: EASE.back }, at);
        }

        var tl = gsap.timeline({
          // Later than the old 'top 80%': the map has to be properly in view
          // before anything starts, or the drawing is over before it is looked at.
          scrollTrigger: { trigger: map, start: 'top 68%', once: true },
        });

        if (hub) popMarker(hub, 0);

        // Each route draws, and its city lands as the line arrives — so the
        // sequence reads as grain leaving the elevator rather than four lines
        // switching on. Slow on purpose: 3.2s each, 0.75s apart.
        var DRAW = 3.2;
        var STEP = 0.75;
        routes.forEach(function (route, i) {
          var at = 0.35 + i * STEP;
          tl.fromTo(route, { strokeDashoffset: 1 },
            { strokeDashoffset: 0, duration: DRAW, ease: 'power1.inOut' }, at);
          // Pair by place, never by document order: the generator emits the four
          // routes in dispatch order and the four labels in reading order, so
          // index-matching lit up Vinnytsia when the Kyiv line arrived.
          var place = route.getAttribute('data-place');
          var marker = place
            ? one('.ukraine-map__point[data-place="' + place + '"]', map)
            : points[i];
          if (marker) popMarker(marker, at + DRAW * 0.82);
        });

        // Once drawn, a bright segment keeps running the length of each arc on
        // its own period, so the map is never quite still.
        var periods = [9, 11.5, 13, 10.5];
        var tail = 0.35 + routes.length * STEP + DRAW;
        routes.forEach(function (route, i) {
          var spark = route.cloneNode(false);
          spark.setAttribute('class', 'ukraine-map__spark');
          spark.removeAttribute('filter');
          route.parentNode.insertBefore(spark, route.nextSibling);
          gsap.set(spark, { opacity: 0 });
          var loop = gsap.timeline({ repeat: -1, delay: tail + i * 0.5, paused: true });
          loop.set(spark, { opacity: .95, strokeDashoffset: 1 });
          loop.to(spark, { strokeDashoffset: 0, duration: periods[i % 4] * .38, ease: 'none' });
          loop.set(spark, { opacity: 0 });
          loop.to({}, { duration: periods[i % 4] * .62 });
          if (ST) {
            ST.create({
              trigger: map, start: 'top bottom', end: 'bottom top',
              onToggle: function (self) {
                if (self.isActive && !doc.hidden) loop.play();
                else loop.pause();
              },
            });
          }
        });
      });
      },
      function revealCharts() {
      all('[data-chart]').forEach(function (box) {
        var cols = all('.chart__fill', box);
        // The quiet years stay hidden until hovered; fading them in here would
        // override the CSS that keeps them out of the way.
        var vals = all('.chart__val:not(.chart__val--quiet)', box);
        var tl = gsap.timeline({
          scrollTrigger: { trigger: box, start: 'top 85%', once: true },
        });
        tl.fromTo(cols, { scaleY: 0 },
          { scaleY: 1, duration: DUR.md, ease: EASE.back, stagger: 0.12 });
        tl.to(vals, { opacity: 1, duration: DUR.sm, stagger: 0.12 }, '-=' + DUR.md);
      });
      },
      function revealOrbits() {
      all('[data-orbit]').forEach(function (box) {
        var rings = all('.radar__ring', box);
        var routes = all('.radar__route', box);
        var hub = one('.radar__hub', box);
        var pins = all('.radar__pin', box);
        var nodes = all('.radar__node', box);
        var tl = gsap.timeline({
          scrollTrigger: { trigger: box, start: 'top 82%', once: true },
        });
        // The field settles first, then the routes draw outward from the hub, and
        // only then do the destinations appear — the order tells the story the
        // card is about: everything leaves from one place.
        tl.fromTo(rings, { scale: 0.6, opacity: 0 },
          { scale: 1, opacity: 1, duration: DUR.md, ease: EASE.back, stagger: 0.1 });
        if (hub) {
          tl.fromTo(hub, { scale: 0.5, opacity: 0 },
            { scale: 1, opacity: 1, duration: DUR.md, ease: EASE.back }, '-=' + DUR.sm);
        }
        tl.fromTo(routes, { opacity: 0 }, { opacity: 1, duration: DUR.sm }, '-=' + DUR.xs);
        tl.fromTo(nodes, { scale: 0, opacity: 0 },
          { scale: 1, opacity: 1, duration: DUR.sm, ease: EASE.back, stagger: 0.08 }, '-=' + DUR.xs);
        tl.fromTo(pins, { y: 8, opacity: 0 },
          { y: 0, opacity: 1, duration: DUR.md, ease: EASE.out, stagger: 0.09 },
          '-=' + DUR.sm);
      });
      },
      function revealLabRows() {
      /* --- lab rows -------------------------------------------------------- */
      all('[data-lab]').forEach(function (box) {
        gsap.fromTo(all('.gmetric', box),
          { y: 12, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: DUR.md,
            ease: EASE.out,
            stagger: .08,
            scrollTrigger: { trigger: box, start: 'top 86%', once: true },
          });
      });
      },
      function revealSettle() {
      if (ST) scheduleRefresh();
      },
    ];
  }

  /* =========================================================================
     3. Parallax — scrubbed, so images drift with the scroll rather than
        popping when they enter.
     ========================================================================= */
  /* The drift is +/- amount/2 percent of the element's own height, so at rest
     the element has to be that much bigger than its frame or one end of the
     travel uncovers a strip of the card behind it. Scaling from the centre by
     1 + amount/100 grows it by exactly amount/2 percent per edge — the travel.

     This value is shared with the reveal timeline below. Both tweens write to
     the same `transform`, so if the reveal settled at scale 1 while the
     parallax expected 1 + amount/100, the reveal would silently cancel the
     compensation and the strip would come straight back. One helper, one
     resting scale, no way for the two to disagree. */
  function parallaxCover(el) {
    if (!el || !el.getAttribute) return 1;
    var raw = el.getAttribute('data-parallax');
    if (raw === null) return 1;
    var amount = parseFloat(raw);
    return isNaN(amount) ? 1 : 1 + amount / 100;
  }

  /* Section photographs drift by default; [data-parallax] tunes the amount.
     This must run before any reveal timeline is built, because those read the
     attribute to decide where the image comes to rest. While it lived inside
     initParallax() an already-decoded image built its reveal first, settled at
     scale 1, and the drift then slid it clean off the edge of its frame. */
  function tagParallaxTargets() {
    all('.post img, .svc__ph img, .parcel img, .contact-photo img').forEach(function (im) {
      if (!im.closest('[data-parallax]')) im.setAttribute('data-parallax', '7');
    });
  }

  function initParallax() {
    var gsap = window.gsap;
    all('[data-parallax]').forEach(function (el) {
      var amount = parseFloat(el.getAttribute('data-parallax')) || 12;
      var cover = parallaxCover(el);
      gsap.fromTo(el,
        { yPercent: -amount / 2, scale: cover },
        {
          yPercent: amount / 2,
          scale: cover,
          ease: 'none',
          force3D: true,
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
     3b. Image reveal — a clip-path wipe with the photograph counter-scaling
         behind it. This is the single effect that most separates a page that
         "fades in" from one that feels composed: the frame opens while the
         image settles, so the two motions resolve together.
     ========================================================================= */
  var REVEAL_IMG = [
    '.about__ph', '.post', '.member__ph', '.svc__ph',
    '.contact-photo', '.quote__ph', '.step__ph', '.parcel', '.vcard__ph',
  ].join(',');

  function initImageReveal() {
    var gsap = window.gsap;
    all(REVEAL_IMG).forEach(function (frame) {
      var img = frame.querySelector('img');
      var started = false;
      function buildReveal() {
        if (started) return;
        started = true;
        var tl = gsap.timeline({
          scrollTrigger: { trigger: frame, start: 'top 88%', once: true },
        });
        tl.fromTo(frame,
          { clipPath: 'inset(0% 0% 100% 0%)' },
          { clipPath: 'inset(0% 0% 0% 0%)', duration: 1.25, ease: EASE.expo }, 0);
        if (img) {
          // Settle at the parallax cover scale, not at 1 — see parallaxCover().
          var rest = parallaxCover(img);
          tl.fromTo(img, { scale: rest * 1.16 },
            { scale: rest, duration: 1.6, ease: EASE.expo }, 0);
        }
        scheduleRefresh();
      }
      if (!img || img.complete) return buildReveal();
      if (typeof img.decode === 'function') {
        img.decode().catch(function () {}).then(buildReveal);
      } else {
        on(img, 'load', buildReveal, { once: true });
        on(img, 'error', buildReveal, { once: true });
      }
    });
  }

  /* =========================================================================
     3c. Magnetic buttons — the arrow badge leans toward the cursor. Pointer
         devices only, and it releases on leave so it never sticks.
     ========================================================================= */
  function initMagnetic() {
    var gsap = window.gsap;
    if (!finePointerQuery.matches) return;

    all('.btn').forEach(function (btn) {
      var badge = one('.btn__badge', btn);
      if (!badge) return;
      var qx = gsap.quickTo(badge, 'x', { duration: 0.5, ease: 'power3.out' });
      var qy = gsap.quickTo(badge, 'y', { duration: 0.5, ease: 'power3.out' });

      on(btn, 'pointermove', function (e) {
        var r = btn.getBoundingClientRect();
        qx((e.clientX - (r.left + r.width / 2)) * 0.18);
        qy((e.clientY - (r.top + r.height / 2)) * 0.35);
      });
      on(btn, 'pointerleave', function () { qx(0); qy(0); });
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
      var speed = parseFloat(row.getAttribute('data-speed')) || 55;
      var track = one('.marq__track', row) || row.firstElementChild;
      var group = track && one('.marq__group', track);
      if (!track || !group) return;

      var loop = 0;
      var tween = null;
      var inView = true;
      var held = false;

      function syncPlayback() {
        if (!tween) return;
        if (doc.hidden || !inView || held) tween.pause();
        else tween.play();
      }

      function build() {
        if (tween) tween.kill();
        all('[data-auto-clone]', track).forEach(function (clone) { clone.remove(); });
        var styles = window.getComputedStyle(track);
        var gap = parseFloat(styles.columnGap || styles.gap || '0') || 0;
        loop = group.getBoundingClientRect().width + gap;
        if (!loop) return;
        var safety = 0;
        while (track.scrollWidth < row.clientWidth * 2.15 && safety < 12) {
          var clone = group.cloneNode(true);
          clone.setAttribute('aria-hidden', 'true');
          clone.setAttribute('data-auto-clone', '');
          track.appendChild(clone);
          safety += 1;
        }
        gsap.set(track, { x: dir < 0 ? 0 : -loop });
        tween = gsap.to(track, {
          x: dir < 0 ? -loop : 0,
          duration: loop / speed,
          ease: 'none',
          repeat: -1,
        });
        syncPlayback();
      }
      build();

      if (typeof window.ResizeObserver !== 'undefined') {
        var resizeTimer = 0;
        var marqueeObserver = new window.ResizeObserver(function () {
          clearTimeout(resizeTimer);
          resizeTimer = setTimeout(build, 120);
        });
        marqueeObserver.observe(group);
        marqueeObserver.observe(row);
      } else {
        on(window, 'resize', build, { passive: true });
      }

      if (window.ScrollTrigger) {
        window.ScrollTrigger.create({
          trigger: row,
          start: 'top bottom',
          end: 'bottom top',
          onToggle: function (self) { inView = self.isActive; syncPlayback(); },
        });
      }
      if (row.hasAttribute('data-marquee-hover')) {
        on(row, 'mouseenter', function () { held = true; syncPlayback(); });
        on(row, 'mouseleave', function () { held = false; syncPlayback(); });
        on(row, 'focusin', function () { held = true; syncPlayback(); });
        on(row, 'focusout', function () { held = false; syncPlayback(); });
      }
      on(doc, 'visibilitychange', syncPlayback);
    });
  }

  function initPartnerOrbit() {
    all('[data-partner-orbit]').forEach(function (orbit) {
      var inView = false;
      function sync() {
        orbit.classList.toggle('is-spinning', inView && !doc.hidden);
      }
      if (window.ScrollTrigger) {
        window.ScrollTrigger.create({
          trigger: orbit,
          start: 'top bottom',
          end: 'bottom top',
          onToggle: function (self) { inView = self.isActive; sync(); },
        });
      } else {
        inView = true;
        sync();
      }
      on(doc, 'visibilitychange', sync);
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
    var mediaImg = media && one('img', media);
    var copy = one('.hero__in', hero);
    var ornament = one('.hero__fan, .card-rail, .hero__foot', hero);

    if (media) {
      tl.fromTo(media, { scale: 1.07, opacity: 0 },
        { scale: 1, opacity: 1, duration: 1.8 }, 0);
    }
    if (title) {
      var words = splitWords(title);
      gsap.set(title, { opacity: 1 });
      tl.fromTo(words,
        { yPercent: 116, opacity: 0 },
        { yPercent: 0, opacity: 1, duration: DUR.xl, stagger: STAGGER.word }, 0.15);
      tl.fromTo(all('.hero-glyph', title),
        { scale: 0, rotate: -24, opacity: 0 },
        { scale: 1, rotate: 0, opacity: 1, duration: DUR.md, ease: EASE.back }, 0.45);
    }
    if (sub.length) {
      tl.fromTo(sub, { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: DUR.lg, stagger: 0.1 }, 0.5);
    }
    if (fanItems.length) {
      hero.classList.add('fan-ready');
      tl.fromTo(fanItems, { y: 90, opacity: 0 },
        { y: 0, opacity: 1, duration: DUR.xl, stagger: 0.075 }, 0.6);
    }

    tl.eventCallback('onComplete', function () {
      // Hand the fan's resting transform back to the stylesheet. GSAP leaves an
      // inline transform behind when the entrance finishes, and an inline
      // transform outranks the :hover rule in 05-motion.css, so the cards
      // simply never popped — the same collision the mobile rail already works
      // around with `transform: none !important`. clearProps is scoped to the
      // transform channel so the tween's opacity:1 stays inline and the
      // no-JS / reduced-motion contract (nothing left hidden) is untouched.
      if (fanItems.length) gsap.set(fanItems, { clearProps: 'transform,translate,rotate,scale' });
      if (!window.ScrollTrigger) return;
      var compact = window.matchMedia('(max-width: 56.25rem)').matches;
      var depth = gsap.timeline({
        scrollTrigger: {
          trigger: hero,
          start: 'top top',
          end: 'bottom top',
          scrub: compact ? 0.35 : 0.8,
          invalidateOnRefresh: true,
        },
      });
      if (mediaImg) depth.to(mediaImg, { yPercent: compact ? 4 : 8, scale: compact ? 1.035 : 1.075, ease: 'none' }, 0);
      if (copy) depth.to(copy, { yPercent: compact ? -3 : -9, opacity: compact ? 0.72 : 0.42, ease: 'none' }, 0);
      if (ornament) depth.to(ornament, { yPercent: compact ? -2 : -13, ease: 'none' }, 0);
    });
  }

  function initPageHero() {
    var gsap = window.gsap;
    all('[data-page-hero]').forEach(function (hero) {
      var title = one('[data-page-title]', hero);
      var items = all('[data-page-item]', hero);
      var media = one('[data-page-media]', hero);
      var image = media && one('img', media);
      var tl = gsap.timeline({ defaults: { ease: EASE.expo } });

      if (media) {
        tl.fromTo(media, { clipPath: 'inset(0 0 100% 0)' },
          { clipPath: 'inset(0 0 0% 0)', duration: 1.35 }, 0);
      }
      // The page hero runs its own drift below, symmetric about zero, so the
      // image has to rest oversized by the same rule the shared parallax uses:
      // travel each way is HERO_DRIFT/2 percent, so cover it with 1 + drift/100.
      var HERO_DRIFT = 10;
      var heroRest = 1 + HERO_DRIFT / 100;
      if (image) {
        tl.fromTo(image, { scale: heroRest * 1.12 },
          { scale: heroRest, duration: 1.65 }, 0);
      }
      if (title) {
        var words = splitWords(title);
        gsap.set(title, { opacity: 1 });
        tl.fromTo(words, { yPercent: 116, opacity: 0 },
          { yPercent: 0, opacity: 1, duration: DUR.xl, stagger: STAGGER.word }, 0.12);
        tl.fromTo(all('.ichip', title), { scale: 0, rotate: -24 },
          { scale: 1, rotate: 0, duration: DUR.md, ease: EASE.back }, 0.4);
      }
      if (items.length) {
        tl.fromTo(items, { y: 30, opacity: 0 },
          { y: 0, opacity: 1, duration: DUR.lg, stagger: .1 }, .45);
      }

      if (image && window.ScrollTrigger) {
        gsap.fromTo(image,
          { yPercent: -HERO_DRIFT / 2, scale: heroRest },
          {
            yPercent: HERO_DRIFT / 2,
            scale: heroRest,
            ease: 'none',
            force3D: true,
            scrollTrigger: { trigger: hero, start: 'top bottom', end: 'bottom top', scrub: .65 },
          });
      }
    });
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
      scheduleRefresh();
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
      // Legacy nodes still carry the unit as a suffix string; the stat cards
      // now hold it in a sibling element, so there the counter owns nothing but
      // the digits and cannot disturb the unit's typography or line box.
      var suffix = el.getAttribute('data-suffix') || '';
      // Larger figures count for longer, so magnitude is felt and not just read.
      var dur = parseFloat(el.getAttribute('data-dur')) || 2;

      if (REDUCED || !hasGSAP) {
        el.textContent = fmt.format(target) + suffix;
        return;
      }
      var obj = { v: 0 };
      gsap.to(obj, {
        v: target,
        duration: dur,
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

    /* mobile drawer — focus is trapped inside the modal surface and page
       content is made inert while it is open. */
    var burger = one('.burger');
    var drawer = one('.drawer');
    var main = one('main');
    var footerWrap = one('.footer-wrap');
    var focusBeforeDrawer = null;
    function drawerFocusables() {
      if (!drawer) return [];
      return all('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', drawer);
    }
    function setDrawer(open) {
      doc.body.classList.toggle('nav-open', open);
      if (lenis) open ? lenis.stop() : lenis.start();
      doc.body.style.overflow = open ? 'hidden' : '';
      if (main) main.inert = open;
      if (footerWrap) footerWrap.inert = open;
      if (burger) {
        burger.setAttribute('aria-expanded', open ? 'true' : 'false');
        burger.setAttribute('aria-label', burger.getAttribute(open ? 'data-label-close' : 'data-label-open') || 'Menu');
      }
      if (drawer) drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
      if (open) {
        focusBeforeDrawer = doc.activeElement;
        var targets = drawerFocusables();
        requestAnimationFrame(function () { (targets[0] || drawer).focus(); });
      } else if (focusBeforeDrawer && typeof focusBeforeDrawer.focus === 'function') {
        focusBeforeDrawer.focus();
      }
    }
    on(burger, 'click', function () {
      setDrawer(!doc.body.classList.contains('nav-open'));
    });
    all('.drawer a').forEach(function (a) {
      on(a, 'click', function () { setDrawer(false); });
    });
    on(doc, 'keydown', function (e) {
      if (!doc.body.classList.contains('nav-open')) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        setDrawer(false);
        return;
      }
      if (e.key !== 'Tab') return;
      var targets = drawerFocusables();
      if (!targets.length) return;
      var first = targets[0];
      var last = targets[targets.length - 1];
      if (e.shiftKey && doc.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && doc.activeElement === last) {
        e.preventDefault(); first.focus();
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

    /* Exclusive, animated FAQ accordion. Opening one item closes the previous
       item in the same group; native details semantics remain intact. */
    all('.faq').forEach(function (group) {
      var details = all('details', group);
      function setExpanded(detail, expanded) {
        var summary = one('summary', detail);
        if (summary) summary.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      }
      function animateDetail(detail, openState) {
        var panel = one('.faq__a', detail);
        if (!panel) { detail.open = openState; setExpanded(detail, openState); return; }
        if (detail._faqAnimation) detail._faqAnimation.cancel();
        if (REDUCED || typeof panel.animate !== 'function') {
          detail.open = openState; setExpanded(detail, openState); scheduleRefresh(); return;
        }
        if (openState) detail.open = true;
        var from = openState ? 0 : panel.scrollHeight;
        var to = openState ? panel.scrollHeight : 0;
        panel.style.overflow = 'hidden';
        detail._faqAnimation = panel.animate(
          [{ height: from + 'px', opacity: openState ? 0 : 1 },
           { height: to + 'px', opacity: openState ? 1 : 0 }],
          { duration: 420, easing: 'cubic-bezier(.16,1,.3,1)' }
        );
        setExpanded(detail, openState);
        detail._faqAnimation.onfinish = function () {
          if (!openState) detail.open = false;
          panel.style.height = '';
          panel.style.overflow = '';
          panel.style.opacity = '';
          detail._faqAnimation = null;
          scheduleRefresh();
        };
      }
      details.forEach(function (detail) {
        setExpanded(detail, detail.open);
        var summary = one('summary', detail);
        on(summary, 'click', function (e) {
          e.preventDefault();
          var shouldOpen = !detail.open;
          if (shouldOpen) details.forEach(function (other) {
            if (other !== detail && other.open) animateDetail(other, false);
          });
          animateDetail(detail, shouldOpen);
        });
      });
    });

    /* Demo forms have no backend. Native constraint validation still runs; a
       valid submission then explains the demo state instead of pretending data
       was sent anywhere. */
    all('[data-demo-form]').forEach(function (form) {
      on(form, 'input', function () {
        var ok = one('.form__ok', form);
        if (ok) ok.classList.remove('is-on');
      });
      on(form, 'submit', function (e) {
        e.preventDefault();
        if (!form.checkValidity()) {
          form.reportValidity();
          var invalid = one(':invalid', form);
          if (invalid) invalid.focus();
          return;
        }
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

     The init passes used to run back to back inside one DOMContentLoaded
     callback: 83 ScrollTriggers and 137 tweens built in a single 551ms task on
     a 4x-throttled phone. Total Blocking Time only counts what a task spends
     past 50ms, so one 551ms task costs 501ms while ten 55ms tasks cost 50 —
     the work is the same, the blocking is not. So the passes are spent across
     idle callbacks instead of run in one breath.

     Three properties this must preserve, in descending order of how badly
     losing them would hurt:

       1. Order. tagParallaxTargets() must have tagged every image before any
          reveal timeline reads data-parallax off it. When that tagging lived
          inside initParallax() an already-decoded image built its reveal first,
          settled at scale 1, and the drift then slid it clean off the edge of
          its frame. The queue is drained strictly front to back, one pass at a
          time, and never reordered to fill a gap.
       2. The first screen. initSmoothScroll, tagParallaxTargets, initHero,
          initPageHero and initMarquees stay synchronous. A visitor is looking at
          the hero while this runs, and an idle callback's worth of delay in its
          opening timeline is visible where the same delay further down the page
          is not.
          initMarquees is in that list for a measured reason, not by category.
          v2's card rail and v3's logo bar are both inside the hero, and building
          a marquee changes its track's height. The webfont swap reflows the hero
          at ~340ms; whether the rail had been built by then decides how much of
          the viewport that one reflow moves. Queued, it landed on either side of
          the swap depending on the run and v2's desktop CLS read 0.028 or 0.068
          at random. Synchronous, the rail is always in place first and the figure
          is 0.028 every time — the same as before this change. The reflow itself
          is a separate, pre-existing problem.
       3. One refresh at the end. ScrollTrigger.refresh() is expensive and it is
          called once, after the last pass, not per pass.
     ========================================================================= */

  /* requestIdleCallback yields to input and paint, which is the whole point;
     Safari lacks it, and there setTimeout(0) still breaks the long task into
     separate tasks even though it does not wait for idle. */
  var idle = typeof window.requestIdleCallback === 'function'
    ? function (fn) { window.requestIdleCallback(fn, { timeout: 250 }); }
    : function (fn) { setTimeout(fn, 0); };

  function drainQueue(queue, done) {
    var i = 0;
    var settled = false;

    function runOne() {
      var pass = queue[i++];
      // A pass that throws must not stall the ones behind it. Before this the
      // whole chain was one statement list, so the first exception left the
      // rest of the page hidden for good.
      try { pass(); } catch (e) { /* keep draining */ }
    }

    function settle() {
      if (settled) return;
      settled = true;
      while (i < queue.length) runOne();
      done();
    }

    function step(deadline) {
      if (settled) return;
      do {
        if (i >= queue.length) { settle(); return; }
        runOne();
      } while (deadline && typeof deadline.timeRemaining === 'function'
               && deadline.timeRemaining() > 8);
      if (i >= queue.length) settle();
      else idle(step);
    }

    idle(step);

    /* Safety net. A visitor who starts scrolling immediately must not meet a
       half-initialised page, and requestIdleCallback can be starved for a long
       time on a busy main thread — a slow third-party-free page is still a page
       decoding six hero images. At 2500ms the remainder runs synchronously
       whatever it costs, because a visible page late beats a blank one on time.
       This sits deliberately below the 3000ms no-motion failsafe, so on a
       healthy page the queue always finishes first and the failsafe never
       fires. */
    setTimeout(settle, 2500);
  }

  function boot() {
    initChrome();
    initCrops();

    if (REDUCED || !hasGSAP) {
      // show everything in its final state
      doc.documentElement.classList.add('no-motion');
      settleCounters();
      return;
    }

    armMotionFailsafe();
    window.gsap.registerPlugin(window.ScrollTrigger);
    window.gsap.config({ nullTargetWarn: false });

    initSmoothScroll();
    tagParallaxTargets();
    initHero();
    initPageHero();
    initMarquees();

    var queue = revealPasses().concat([
      initImageReveal, initMagnetic, initParallax,
      initPartnerOrbit, initCounters,
    ]);

    drainQueue(queue, function () {
      /* Set only now that every pass is in place. The class had been set before
         the first pass ran, which made it useless as a health signal: a boot
         that died in the middle still looked ready. Nothing styles on it — it
         exists so the failsafe below can tell a finished page from a stalled
         one. */
      doc.documentElement.classList.add('motion-ready');
      window.ScrollTrigger.refresh();
    });

    // late webfont/image sizing changes would otherwise leave triggers stale
    on(window, 'load', function () { window.ScrollTrigger.refresh(); });
  }

  /* Last line of defence. The REDUCED/!hasGSAP branch above covers a library
     that never arrived; this covers one that arrived and then threw somewhere
     the per-pass catch could not help — a GSAP version bump changing an API,
     say. Without it the flash guard's `opacity: 0` is permanent and the page is
     blank below the hero forever. On a healthy page the queue settles by 2500ms
     and this never runs. */
  function armMotionFailsafe() {
    setTimeout(function () {
      var root = doc.documentElement;
      if (root.classList.contains('motion-ready')) return;
      root.classList.add('no-motion');
      settleCounters();
    }, 3000);
  }

  if (doc.readyState === 'loading') {
    on(doc, 'DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
