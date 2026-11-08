/* Thanh Long JSC — tương tác tối thiểu, không thư viện.
   Chỉ giữ các phần cần thiết: menu, header dính, slider, FAQ, lọc sản phẩm. */
(function () {
  'use strict';

  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var page = document.body.getAttribute('data-page') || '';

  /* ---------- menu: đánh dấu trang hiện tại ---------- */
  $$('[data-nav="' + page + '"]').forEach(function (a) {
    a.classList.add('active');
    a.setAttribute('aria-current', 'page');
  });

  /* ---------- header dính khi cuộn + nút lên đầu trang ---------- */
  var header = $('#header');
  var wrap = $('#headerWrap');
  var toTop = $('#toTop');
  var STICK_AT = 300;
  var ticking = false;
  function onScroll() {
    var y = window.scrollY;
    if (y > STICK_AT && !wrap.classList.contains('stuck')) {
      header.style.minHeight = header.offsetHeight + 'px';
      wrap.classList.add('stuck');
    } else if (y <= STICK_AT && wrap.classList.contains('stuck')) {
      wrap.classList.remove('stuck');
      header.style.minHeight = '';
    }
    toTop.classList.toggle('is-show', y > 600);
    ticking = false;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { window.requestAnimationFrame(onScroll); ticking = true; }
  }, { passive: true });
  onScroll();

  /* ---------- menu mobile trượt từ trái ---------- */
  var oc = $('#offcanvas');
  var toggle = $('#navToggle');
  function setMenu(open) {
    oc.classList.toggle('is-open', open);
    oc.setAttribute('aria-hidden', !open);
    toggle.setAttribute('aria-expanded', open);
    document.body.classList.toggle('is-locked', open);
    if (open) setTimeout(function () { $('.offcanvas__close', oc).focus(); }, 50);
    else toggle.focus();
  }
  toggle.addEventListener('click', function () { setMenu(true); });
  $$('[data-close]', oc).forEach(function (b) { b.addEventListener('click', function () { setMenu(false); }); });
  $$('.mnav a', oc).forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
  oc.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab' || !oc.classList.contains('is-open')) return;
    var f = $$('a, button, input', oc).filter(function (x) { return x.offsetParent; });
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  $$('.mnav__toggle', oc).forEach(function (b) {
    b.addEventListener('click', function () {
      var li = b.parentNode;
      var open = !li.classList.contains('is-open');
      li.classList.toggle('is-open', open);
      b.setAttribute('aria-expanded', open);
    });
  });
  window.addEventListener('resize', function () {
    if (window.innerWidth > 991 && oc.classList.contains('is-open')) setMenu(false);
  });

  /* ---------- slider banner (trang chủ) ---------- */
  var slider = $('#slider');
  if (slider) {
    var slides = $$('.slide', slider);
    var dots = $$('.slider__dots button', slider);
    var cur = 0;
    var timer;
    var go = function (i) {
      cur = (i + slides.length) % slides.length;
      slides.forEach(function (s, j) {
        s.classList.toggle('is-active', j === cur);
        s.setAttribute('aria-hidden', j !== cur);
        if (j === (cur + 1) % slides.length) $('img', s).loading = 'eager';
      });
      dots.forEach(function (d, j) {
        d.classList.toggle('is-active', j === cur);
        d.setAttribute('aria-selected', j === cur);
      });
    };
    var play = function () {
      clearInterval(timer);
      if (!reduced) timer = setInterval(function () { go(cur + 1); }, 6000);
    };
    $('.slider__arrow--prev', slider).addEventListener('click', function () { go(cur - 1); play(); });
    $('.slider__arrow--next', slider).addEventListener('click', function () { go(cur + 1); play(); });
    dots.forEach(function (d, j) { d.addEventListener('click', function () { go(j); play(); }); });
    slider.addEventListener('mouseenter', function () { clearInterval(timer); });
    slider.addEventListener('mouseleave', play);
    slider.addEventListener('focusin', function () { clearInterval(timer); });
    slider.addEventListener('focusout', play);
    var startX = null;
    slider.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
    slider.addEventListener('touchend', function (e) {
      if (startX === null) return;
      var dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 40) { go(cur + (dx < 0 ? 1 : -1)); play(); }
      startX = null;
    });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) clearInterval(timer); else play();
    });
    go(0);
    play();
  }

  /* ---------- hỏi đáp: mở một câu, đóng các câu khác ---------- */
  $$('.faq').forEach(function (faq) {
    var items = $$('.faq__item', faq);
    items.forEach(function (item) {
      var b = $('button', item);
      b.addEventListener('click', function () {
        var open = !item.classList.contains('is-open');
        items.forEach(function (o) {
          o.classList.remove('is-open');
          $('button', o).setAttribute('aria-expanded', 'false');
        });
        item.classList.toggle('is-open', open);
        b.setAttribute('aria-expanded', open);
      });
    });
  });

  /* ---------- lọc sản phẩm theo nhóm (trang Sản phẩm) ---------- */
  var filters = $$('.filter button');
  if (filters.length) {
    var cards = $$('[data-group]');
    var applyFilter = function (key, scroll) {
      var valid = filters.some(function (b) { return b.getAttribute('data-filter') === key; });
      if (!valid) key = 'all';
      filters.forEach(function (b) {
        var on = b.getAttribute('data-filter') === key;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', on);
      });
      cards.forEach(function (c) {
        var show = key === 'all' || c.getAttribute('data-group') === key;
        c.hidden = !show;
        if (show) { c.classList.remove('is-in'); void c.offsetWidth; c.classList.add('is-in'); }
      });
      if (scroll) $('#loc').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
    };
    filters.forEach(function (b) {
      b.addEventListener('click', function () {
        var key = b.getAttribute('data-filter');
        applyFilter(key);
        history.replaceState(null, '', key === 'all' ? location.pathname : '#' + key);
      });
    });
    var fromHash = function () {
      var h = location.hash.slice(1);
      if (h === 'day-chuyen') return;
      applyFilter(h || 'all', !!h);
    };
    window.addEventListener('hashchange', fromHash);
    fromHash();
  }

  /* ---------- chọn sẵn sản phẩm / công suất trong form báo giá ---------- */
  var qProduct = $('#q-product');
  var qCap = $('#q-cap');
  function pickOption(select, value) {
    if (!select || !value) return;
    $$('option', select).forEach(function (o) { if (o.value === value) select.value = value; });
  }
  if (qProduct) {
    $$('[data-pick]').forEach(function (a) {
      a.addEventListener('click', function () {
        pickOption(qProduct, a.getAttribute('data-pick'));
        if (a.hasAttribute('data-cap')) pickOption(qCap, a.getAttribute('data-cap'));
      });
    });
    var params = new URLSearchParams(location.search);
    pickOption(qProduct, params.get('sp'));
    pickOption(qCap, params.get('cap'));
  }

  window.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && oc.classList.contains('is-open')) setMenu(false);
  });
})();
