/* Smart content: hành vi dùng chung của bài (slider, tab, phóng to ảnh, video, hiện dần khi cuộn).
 * Nạp ở trang có bài Smart content và trong khung xem trước của trang quản trị. */
(function () {
  'use strict';

  function each(root, sel, fn) {
    Array.prototype.forEach.call(root.querySelectorAll(sel), fn);
  }

  function slider(el) {
    var track = el.querySelector('[data-smc-track]');
    if (!track) return;
    var prev = el.querySelector('[data-smc-prev]');
    var next = el.querySelector('[data-smc-next]');
    var dots = el.querySelector('[data-smc-dots]');
    var slides = Array.prototype.slice.call(track.children);

    function pages() {
      return Math.max(1, Math.round(track.scrollWidth / Math.max(1, track.clientWidth)));
    }
    function current() {
      return Math.min(pages() - 1, Math.round(track.scrollLeft / Math.max(1, track.clientWidth)));
    }
    function go(i) {
      track.scrollTo({ left: i * track.clientWidth, behavior: 'smooth' });
    }
    function buildDots() {
      if (!dots) return;
      var n = pages();
      if (dots.children.length === n) return;
      dots.innerHTML = '';
      for (var i = 0; i < n; i++) {
        var b = document.createElement('button');
        b.type = 'button';
        b.setAttribute('aria-label', String(i + 1));
        b.addEventListener('click', go.bind(null, i));
        dots.appendChild(b);
      }
    }
    function sync() {
      buildDots();
      var c = current();
      var atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
      if (dots) {
        Array.prototype.forEach.call(dots.children, function (d, i) {
          d.classList.toggle('is-active', i === c);
        });
      }
      var per = Math.max(1, Math.round(slides.length / pages()));
      slides.forEach(function (s, i) {
        s.classList.toggle('is-active', Math.floor(i / per) === c);
      });
      if (prev) prev.disabled = track.scrollLeft <= 2;
      if (next) next.disabled = atEnd;
    }

    if (prev) prev.addEventListener('click', function () { go(current() - 1); });
    if (next) next.addEventListener('click', function () { go(current() + 1); });
    var t;
    track.addEventListener('scroll', function () {
      clearTimeout(t);
      t = setTimeout(sync, 60);
    }, { passive: true });
    window.addEventListener('resize', sync);
    sync();
  }

  function tabs(el) {
    var btns = Array.prototype.slice.call(el.querySelectorAll('[data-smc-tab]'));
    var panels = Array.prototype.slice.call(el.querySelectorAll('[data-smc-panel]'));
    function show(key) {
      btns.forEach(function (b) {
        var on = b.getAttribute('data-smc-tab') === key;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      panels.forEach(function (p) {
        p.hidden = p.getAttribute('data-smc-panel') !== key;
      });
    }
    btns.forEach(function (b) {
      b.addEventListener('click', function () { show(b.getAttribute('data-smc-tab')); });
    });
    if (btns[0]) show(btns[0].getAttribute('data-smc-tab'));
  }

  function zoomSrc(el) {
    if (el.tagName === 'A') return el.getAttribute('href');
    return el.currentSrc || el.getAttribute('src');
  }

  function lightbox(items, index) {
    var box = document.createElement('div');
    box.className = 'smc-lb';
    box.innerHTML = '<img alt=""><button type="button" class="smc-lb-close">×</button>' +
      (items.length > 1 ? '<button type="button" class="smc-lb-prev">‹</button><button type="button" class="smc-lb-next">›</button><div class="smc-lb-count"></div>' : '');
    var L = { close: 'Đóng', prev: 'Ảnh trước', next: 'Ảnh sau' };
    [['.smc-lb-close', L.close], ['.smc-lb-prev', L.prev], ['.smc-lb-next', L.next]].forEach(function (b) {
      var btn = box.querySelector(b[0]);
      if (btn) btn.setAttribute('aria-label', b[1]);
    });
    var img = box.querySelector('img');
    var count = box.querySelector('.smc-lb-count');

    function show(i) {
      index = (i + items.length) % items.length;
      img.src = zoomSrc(items[index]);
      if (count) count.textContent = (index + 1) + ' / ' + items.length;
    }
    function close() {
      document.removeEventListener('keydown', onKey);
      box.remove();
    }
    function onKey(e) {
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowLeft') show(index - 1);
      if (e.key === 'ArrowRight') show(index + 1);
    }
    box.addEventListener('click', function (e) {
      if (e.target.classList.contains('smc-lb-prev')) show(index - 1);
      else if (e.target.classList.contains('smc-lb-next')) show(index + 1);
      else if (e.target !== img) close();
    });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(box);
    show(index);
  }

  function videoHtml(url) {
    var m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{6,})/);
    if (m) return '<iframe src="https://www.youtube-nocookie.com/embed/' + m[1] + '?autoplay=1&rel=0" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen title="Video"></iframe>';
    m = url.match(/vimeo\.com\/(\d+)/);
    if (m) return '<iframe src="https://player.vimeo.com/video/' + m[1] + '?autoplay=1" allow="autoplay; fullscreen" allowfullscreen title="Video"></iframe>';
    var v = document.createElement('video');
    v.src = url;
    v.controls = true;
    v.autoplay = true;
    v.playsInline = true;
    return v;
  }

  function init(root) {
    if (root.classList.contains('smc-js')) return;
    root.classList.add('smc-js');
    each(root, '[data-smc-slider]', slider);
    each(root, '[data-smc-tabs]', tabs);

    root.addEventListener('click', function (e) {
      var z = e.target.closest('[data-smc-zoom]');
      if (z && root.contains(z)) {
        e.preventDefault();
        var group = z.closest('[data-smc-gallery]') || z;
        var items = z.matches('[data-smc-gallery] [data-smc-zoom]')
          ? Array.prototype.slice.call(group.querySelectorAll('[data-smc-zoom]'))
          : [z];
        lightbox(items, Math.max(0, items.indexOf(z)));
        return;
      }
      var v = e.target.closest('[data-smc-video]');
      if (v && root.contains(v) && !v.classList.contains('is-playing')) {
        var player = videoHtml(v.getAttribute('data-smc-video') || '');
        v.classList.add('is-playing');
        if (typeof player === 'string') v.innerHTML = player;
        else { v.innerHTML = ''; v.appendChild(player); }
      }
    });

    var targets = root.querySelectorAll('[data-smc-reveal]');
    if (!('IntersectionObserver' in window)) {
      each(root, '[data-smc-reveal]', function (el) { el.classList.add('is-visible'); });
    } else if (targets.length) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.classList.add('is-visible');
            io.unobserve(en.target);
          }
        });
      }, { rootMargin: '0px 0px -8% 0px' });
      Array.prototype.forEach.call(targets, function (el) { io.observe(el); });
    }
  }

  function boot() {
    each(document, '.smc-root', init);
  }
  window.smcInit = boot; // khung xem trước của trang quản trị gọi lại sau khi thay nội dung
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
