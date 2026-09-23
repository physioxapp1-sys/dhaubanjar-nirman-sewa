/* Dhaubanjar Nirman Sewa — site interactions */
(function () {
  'use strict';

  var $  = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- current year ---------- */
  var year = $('#year');
  if (year) year.textContent = new Date().getFullYear();

  /* ---------- sticky header ---------- */
  var header = $('#header');
  var toTop = $('#toTop');
  function onScroll() {
    var y = window.scrollY;
    header.classList.toggle('is-stuck', y > 20);
    if (toTop) toTop.classList.toggle('is-visible', y > 600);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- mobile menu ---------- */
  var menuBtn = $('#menuBtn');
  var nav = $('#nav');
  function closeMenu() {
    nav.classList.remove('is-open');
    menuBtn.setAttribute('aria-expanded', 'false');
    menuBtn.setAttribute('aria-label', 'Open menu');
  }
  menuBtn.addEventListener('click', function () {
    var open = nav.classList.toggle('is-open');
    menuBtn.setAttribute('aria-expanded', String(open));
    menuBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  });

  /* ---------- services dropdown ---------- */
  var dd = $('.has-dropdown');
  var ddToggle = $('.dropdown-toggle');
  if (dd && ddToggle) {
    ddToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = dd.classList.toggle('is-open');
      ddToggle.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', function (e) {
      if (!dd.contains(e.target)) {
        dd.classList.remove('is-open');
        ddToggle.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        dd.classList.remove('is-open');
        ddToggle.setAttribute('aria-expanded', 'false');
        closeMenu();
      }
    });
  }

  /* close the mobile menu after picking a link */
  $$('#nav a').forEach(function (a) {
    a.addEventListener('click', function () {
      closeMenu();
      if (dd) dd.classList.remove('is-open');
    });
  });

  /* ---------- reveal on scroll ---------- */
  var revealables = $$('.reveal');
  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealables.forEach(function (el) { el.classList.add('is-in'); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, i) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        el.style.transitionDelay = Math.min(i * 90, 360) + 'ms';
        el.classList.add('is-in');
        revealObserver.unobserve(el);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });
    revealables.forEach(function (el) { revealObserver.observe(el); });
  }

  /* ---------- animated stat counters ---------- */
  var counters = $$('[data-count]');
  function runCounter(el) {
    var target = parseInt(el.dataset.count, 10) || 0;
    var suffix = el.dataset.suffix || '+';
    if (reduceMotion) { el.textContent = target + suffix; return; }
    var start = performance.now();
    var dur = 1500;
    (function tick(now) {
      var p = Math.min((now - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    })(start);
  }
  if ('IntersectionObserver' in window) {
    var countObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        runCounter(entry.target);
        countObserver.unobserve(entry.target);
      });
    }, { threshold: 0.6 });
    counters.forEach(function (el) { countObserver.observe(el); });
  } else {
    counters.forEach(runCounter);
  }

  /* ---------- scroll spy ---------- */
  var navLinks = $$('.nav-link[href^="#"]');
  var sections = navLinks
    .map(function (l) { return document.getElementById(l.getAttribute('href').slice(1)); })
    .filter(Boolean);

  if ('IntersectionObserver' in window && sections.length) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        navLinks.forEach(function (l) {
          l.classList.toggle('is-active', l.getAttribute('href') === '#' + entry.target.id);
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach(function (s) { spy.observe(s); });
  }

  /* ---------- testimonial slider ---------- */
  var slides = $$('.tm');
  var dots = $('#tmDots');
  if (slides.length && dots) {
    var index = 0;
    var timer = null;

    slides.forEach(function (_, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', 'Testimonial ' + (i + 1));
      if (i === 0) b.classList.add('is-active');
      b.addEventListener('click', function () { show(i); restart(); });
      dots.appendChild(b);
    });

    function show(i) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (s, n) { s.classList.toggle('is-active', n === index); });
      $$('button', dots).forEach(function (d, n) { d.classList.toggle('is-active', n === index); });
    }
    function restart() {
      if (reduceMotion) return;
      clearInterval(timer);
      timer = setInterval(function () { show(index + 1); }, 6500);
    }
    restart();

    var tmWrap = $('.testimonial');
    tmWrap.addEventListener('mouseenter', function () { clearInterval(timer); });
    tmWrap.addEventListener('mouseleave', restart);
  }

  /* ---------- portfolio filter ---------- */
  var filters = $$('.filter');
  var projects = $$('.project');
  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var cat = btn.dataset.filter;
      filters.forEach(function (b) {
        var on = b === btn;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', String(on));
      });
      projects.forEach(function (p) {
        p.classList.toggle('is-hidden', cat !== 'all' && p.dataset.cat !== cat);
      });
    });
  });

  /* ---------- forms ---------- */
  var emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  var phoneRe = /^[+()\d][\d\s\-()]{6,}$/;

  function fieldError(input) {
    var value = input.value.trim();
    if (input.required && !value) return 'This field is required.';
    if (value && input.type === 'email' && !emailRe.test(value)) return 'Enter a valid email address.';
    if (value && input.type === 'tel' && !phoneRe.test(value)) return 'Enter a valid phone number.';
    return '';
  }

  function wireForm(form, note, successMsg) {
    if (!form) return;
    var fields = $$('input, textarea, select', form);

    fields.forEach(function (input) {
      input.addEventListener('blur', function () { validate(input); });
      input.addEventListener('input', function () {
        if (input.classList.contains('is-invalid')) validate(input);
      });
    });

    function validate(input) {
      var msg = fieldError(input);
      input.classList.toggle('is-invalid', !!msg);
      var slot = input.parentElement.querySelector('.err');
      if (slot) slot.textContent = msg;
      return !msg;
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var ok = true;
      var firstBad = null;
      fields.forEach(function (input) {
        if (!validate(input)) { ok = false; if (!firstBad) firstBad = input; }
      });

      if (!ok) {
        note.textContent = 'Please check the highlighted fields.';
        if (firstBad) firstBad.focus();
        return;
      }

      var endpoint = form.dataset.endpoint;
      if (!endpoint) {
        /* Never show a success message we cannot back up - a visitor who
           believes they made contact and hears nothing is worse off than
           one who is told to phone. */
        note.textContent = 'Online enquiries are not available yet — '
          + 'please call +977 9841042319.';
        return;
      }
      var btn = $('button[type="submit"]', form);
      var label = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Sending…';

      var payload = {};
      fields.forEach(function (input) {
        if (input.name) payload[input.name] = input.value.trim();
      });

      fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload)
      }).then(function (res) {
        return res.json().then(function (body) { return { ok: res.ok, body: body }; });
      }).then(function (r) {
        if (!r.ok) {
          /* DRF returns {field: [messages]} - surface them on the fields. */
          var shown = false;
          Object.keys(r.body || {}).forEach(function (key) {
            var input = $('[name="' + key + '"]', form);
            var msg = [].concat(r.body[key]).join(' ');
            if (input) {
              input.classList.add('is-invalid');
              var slot = input.parentElement.querySelector('.err');
              if (slot) { slot.textContent = msg; shown = true; }
            }
          });
          note.textContent = shown
            ? 'Please check the highlighted fields.'
            : 'Sorry, something went wrong — please call +977 9841042319.';
          return;
        }
        form.reset();
        note.textContent = (r.body && r.body.detail) || successMsg;
        setTimeout(function () { note.textContent = ''; }, 8000);
      }).catch(function () {
        note.textContent = 'Could not reach the server — please call +977 9841042319.';
      }).then(function () {
        btn.disabled = false;
        btn.textContent = label;
      });
    });
  }

  wireForm($('#contactForm'), $('#contactNote'), 'Enquiry received. Our team will reply within one working day.');
})();
