# Tăng tốc di động – bước 2 · thegioimaynghienda.com

> Dựa trên lần chạy PageSpeed Insights mới (15/11/2026, sau khi đã sửa bước 1).

## 1. Hiện trạng

| Hạng mục | Di động | Máy tính |
|---|---|---|
| Hiệu suất | **83** | 100 ✅ |
| Hỗ trợ tiếp cận | 100 ✅ | 100 ✅ |
| Phương pháp hay nhất | 100 ✅ | 100 ✅ |
| SEO | 100 ✅ | 100 ✅ |

| Chỉ số (di động) | Giá trị | Trọng số | Ghi chú |
|---|---|---|---|
| FCP | 1,0 s ✅ | 10% | Tốt |
| **LCP** | **4,3 s ❌** | **25%** | **Mất khoảng 14 điểm ở đây** |
| TBT | 170 ms ✅ | 30% | Mất khoảng 2 điểm |
| CLS | 0 ✅ | 25% | Hoàn hảo |
| Speed Index | 1,4 s ✅ | 10% | Tốt |

### Muốn đạt 98–100 trên di động cần:
- **LCP ≤ khoảng 1,6 s** (hiện 4,3 s)
- **TBT ≤ khoảng 80 ms** (hiện 170 ms)

### Vì sao LCP tệ hơn lần trước (3,0 → 4,3 s) dù đã sửa?

Phần tử LCP vẫn là ảnh slide đầu, nay đã là `sandvik-768.webp` (49,9 KiB, có `srcset` và `fetchpriority="high"`). Khi đo thật, ảnh này tải rất nhanh: TTFB 10 ms, trễ tải 120 ms, tải 500 ms, trễ hiển thị 40 ms.

Nhưng **Lighthouse di động không đo thời gian thật**. Nó *mô phỏng* mạng 4G chậm (khoảng 1,6 Mbps, RTT 150 ms) và CPU chậm 4 lần. Mọi file bắt đầu tải trước thời điểm LCP sẽ **chia nhau băng thông** với ảnh LCP. Hiện có:

- **~990 KiB ảnh sản phẩm/dự án** chưa được thu nhỏ. Dù có `loading="lazy"`, Chrome vẫn tải sớm ảnh lazy nằm trong khoảng ~1.250 px dưới màn hình, mà các thẻ sản phẩm nằm ngay dưới banner.
- 2 file font (`montserrat-vietnamese.woff2`, `open-sans-vietnamese.woff2`).
- Script Cloudflare `beacon.min.js`.

→ Ở 1,6 Mbps, 1 MB ảnh mất khoảng 5 giây. Đây là lý do LCP mô phỏng bị đẩy lên 4,3 s. Điểm dao động giữa các lần chạy cũng do việc tải sớm này (có lần tải sớm nhiều ảnh, có lần ít).

**Kết luận:** việc quan trọng nhất còn lại là **thu nhỏ ảnh** và **không cho ảnh dưới màn hình đầu tải trước ảnh LCP**.

---

## 2. Thứ tự ưu tiên

| # | Việc | Ảnh hưởng chính | Độ khó |
|---|---|---|---|
| 1 | Thu nhỏ + `srcset` cho 9 ảnh sản phẩm/dự án (mục 3) | LCP −2 đến −3 s | Trung bình |
| 2 | Chặn ảnh dưới màn hình đầu tải trước LCP (mục 4) | LCP, độ ổn định điểm | Dễ |
| 3 | GTM: bỏ hẹn giờ tự tải, gộp tag trùng (mục 6) | TBT 170 → ~0–50 ms | Dễ |
| 4 | Tắt Cloudflare Web Analytics / RUM (mục 7) | Hết 2 cảnh báo đỏ, bớt 1 request trước LCP | Rất dễ |
| 5 | Tối ưu ảnh LCP + slider (mục 5) | LCP −100 đến −300 ms | Dễ |
| 6 | Font (mục 8) | LCP, chuỗi phụ thuộc 351 ms | Trung bình |
| 7 | Sửa forced reflow trong `main.js` (mục 9) | TBT, INP | Trung bình |
| 8 | Tinh chỉnh Cloudflare (mục 10) | Nhỏ | Dễ |

---

## 3. ❌ Thu nhỏ ảnh sản phẩm / dự án – tiết kiệm ~907 KiB (VIỆC SỐ 1)

Bước 1 mới làm ảnh banner và logo. 9 ảnh bên dưới **vẫn là bản 1400 px**:

| Ảnh | Hiện tại | Hiển thị di động | Hiển thị máy tính | Tiết kiệm |
|---|---|---|---|---|
| `rua-cat.webp` | 153,7 KiB · 1400×840 | 186×112 | 289×173 | 151 KiB |
| `vsi.webp` | 136,5 KiB · 1400×1050 | 382×287 | 289×217 | 126 KiB |
| `tram-thanh-long.webp` | 136,2 KiB · 1400×1050 | 382×287 | 585×439 | 126 KiB |
| `con-3.webp` | 116,9 KiB · 1400×1750 | 149×186 | 231×289 | 116 KiB |
| `tach-cat-min.webp` | 113,3 KiB · 1400×1218 | 329×287 | – | 107 KiB |
| `di-dong.webp` | 79,0 KiB · 1400×934 | 186×124 | – | 78 KiB |
| `phan-kich.webp` | 73,3 KiB · 1400×1622 | 136×158 | – | 73 KiB |
| `du-an-300.webp` | 69,6 KiB · 1400×646 | 382×176 | – | 64 KiB |
| `du-an-bao-tri.webp` | 56,6 KiB · 1400×990 | 382×270 | – | 52 KiB |

### 3.1 Xuất ảnh nhiều cỡ

Quy tắc: rộng ảnh ≈ rộng hiển thị × 2 (màn hình điện thoại có DPR 1,75–3).

- [ ] Xuất mỗi ảnh 3 cỡ: **400w, 800w, 1200w**, WebP chất lượng 70–75 (hoặc AVIF ~55–60).
- [ ] Mục tiêu dung lượng: bản 400w **≤ 20–25 KiB**, bản 800w **≤ 50–60 KiB**.
- [ ] **Cắt ảnh đúng tỉ lệ khung hiển thị.** `con-3` (1400×1750) và `phan-kich` (1400×1622) là ảnh dọc nhưng thẻ hiển thị gần vuông → cắt theo tỉ lệ thẻ để bớt pixel thừa.
- [ ] Cập nhật `width`/`height` trong `<img>` theo tỉ lệ mới để giữ CLS = 0.

Lệnh mẫu (ImageMagick + cwebp; hoặc dùng Squoosh CLI / sharp):

```bash
# chạy trong thư mục assets/img (ảnh gốc chất lượng cao)
for f in rua-cat vsi tram-thanh-long con-3 tach-cat-min di-dong phan-kich du-an-300 du-an-bao-tri; do
  for w in 400 800 1200; do
    magick "$f-src.jpg" -resize ${w}x -strip -quality 92 /tmp/$f-$w.png
    cwebp -q 72 -m 6 -sharp_yuv /tmp/$f-$w.png -o $f-$w.webp
  done
done
```

Phiên bản Node (sharp):

```js
// node resize.mjs
import sharp from 'sharp';
const files = ['rua-cat','vsi','tram-thanh-long','con-3','tach-cat-min','di-dong','phan-kich','du-an-300','du-an-bao-tri'];
for (const f of files) for (const w of [400, 800, 1200]) {
  await sharp(`src/${f}.jpg`).resize({ width: w, withoutEnlargement: true })
    .webp({ quality: 72, effort: 6, smartSubsample: true })
    .toFile(`assets/img/${f}-${w}.webp`);
}
```

> Nên xuất từ ảnh gốc (JPG/PNG) thay vì nén lại file WebP đã nén, để ảnh không bị vỡ.

### 3.2 Gắn `srcset` + `sizes` theo từng loại thẻ

`sizes` = chiều rộng thật của ảnh trên màn hình (CSS px) ở từng breakpoint. Dựa trên số đo của PageSpeed:

**Thẻ sản phẩm nhỏ** (2 cột trên di động ~186 px, máy tính ~289 px) – `rua-cat`, `con-3`, `phan-kich`, `di-dong`:

```html
<img src="assets/img/rua-cat-400.webp"
     srcset="assets/img/rua-cat-400.webp 400w,
             assets/img/rua-cat-800.webp 800w"
     sizes="(max-width: 600px) 46vw, 290px"
     width="400" height="240" loading="lazy" decoding="async" fetchpriority="low"
     alt="Máy rửa cát dạng guồng">
```

**Thẻ rộng** (1 cột trên di động ~382 px; máy tính 289–585 px) – `vsi`, `tram-thanh-long`, `tach-cat-min`, `du-an-300`, `du-an-bao-tri`:

```html
<img src="assets/img/tram-thanh-long-800.webp"
     srcset="assets/img/tram-thanh-long-400.webp 400w,
             assets/img/tram-thanh-long-800.webp 800w,
             assets/img/tram-thanh-long-1200.webp 1200w"
     sizes="(max-width: 600px) 93vw, 585px"
     width="800" height="600" loading="lazy" decoding="async" fetchpriority="low"
     alt="Trạm nghiền đá do Thanh Long lắp đặt">
```

- [ ] Kiểm tra lại breakpoint thật trong CSS của bạn và chỉnh `sizes` cho khớp (giá trị trên là ví dụ theo số đo PageSpeed).
- [ ] Sau khi sửa, chạy lại PageSpeed: mục “Cải thiện việc phân phối hình ảnh” phải còn gần 0 KiB.

**Dự kiến:** tổng ảnh trên di động giảm từ ~990 KiB xuống ~150–200 KiB → LCP mô phỏng giảm mạnh.

---

## 4. ❌ Không cho ảnh dưới màn hình đầu tải trước ảnh LCP

Ngay cả khi ảnh đã nhỏ, các ảnh lazy gần màn hình đầu vẫn tải cùng lúc với ảnh banner. Có 2 cách, chọn 1 (hoặc kết hợp):

### Cách A – Đơn giản: `fetchpriority="low"` (đã có trong ví dụ mục 3.2)
- [ ] Thêm `fetchpriority="low"` cho **mọi ảnh không phải ảnh LCP**. Chrome sẽ ưu tiên băng thông cho ảnh banner.

### Cách B – Mạnh hơn: chỉ tải ảnh dưới màn hình đầu **sau khi trang tải xong**

```html
<!-- Ảnh dưới màn hình đầu: dùng data-src / data-srcset -->
<img data-src="assets/img/rua-cat-400.webp"
     data-srcset="assets/img/rua-cat-400.webp 400w, assets/img/rua-cat-800.webp 800w"
     sizes="(max-width: 600px) 46vw, 290px"
     width="400" height="240" alt="Máy rửa cát dạng guồng" class="lazy">
<noscript><img src="assets/img/rua-cat-400.webp" width="400" height="240" alt="Máy rửa cát dạng guồng"></noscript>
```

```js
// đặt cuối main.js
function loadLazy(img){
  if (img.dataset.srcset) img.srcset = img.dataset.srcset;
  if (img.dataset.src) img.src = img.dataset.src;
  img.classList.remove('lazy');
}
addEventListener('load', () => {
  const imgs = document.querySelectorAll('img.lazy');
  if (!('IntersectionObserver' in window)) { imgs.forEach(loadLazy); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) { loadLazy(e.target); io.unobserve(e.target); } });
  }, { rootMargin: '300px 0px' });
  imgs.forEach(img => io.observe(img));
});
```

- [ ] Dùng cách B cho các ảnh thẻ sản phẩm/dự án. **Không** áp dụng cho ảnh banner đầu và logo.
- [ ] Đặt nền màu (`background:#eef1f4`) và `aspect-ratio` cho khung ảnh để tránh khoảng trắng khi ảnh chưa tải.
- [ ] Ảnh có `alt` + `<noscript>` → không ảnh hưởng SEO. Googlebot vẫn thấy ảnh.

---

## 5. Ảnh LCP (banner) và slider

Ảnh hiện tại: `sandvik-768.webp` – 49,9 KiB. PageSpeed báo có thể nén thêm ~8 KiB.

- [ ] Nén lại bản 480/768: WebP chất lượng ~65 (mục tiêu ≤ 35 KiB cho 768w). Hoặc thêm AVIF bằng `<picture>`:

```html
<picture>
  <source type="image/avif"
          srcset="assets/img/sandvik-480.avif 480w, assets/img/sandvik-768.avif 768w, assets/img/sandvik-1280.avif 1280w"
          sizes="100vw">
  <img class="slide__bg" src="assets/img/sandvik-768.webp"
       srcset="assets/img/sandvik-480.webp 480w, assets/img/sandvik-768.webp 768w, assets/img/sandvik-1280.webp 1280w"
       sizes="100vw" width="1400" height="932"
       fetchpriority="high" alt="Dàn máy nghiền đá đang vận hành tại mỏ">
</picture>
```

- [ ] **Bỏ `decoding="async"` trên ảnh LCP.** Chỉ giữ `decoding="async"` cho ảnh khác.
- [ ] Thêm preload trong `<head>`, đặt **ngay sau `<meta charset>` / `<meta viewport>`**, trước `<style>` inline:

```html
<link rel="preload" as="image" fetchpriority="high"
      href="assets/img/sandvik-768.webp"
      imagesrcset="assets/img/sandvik-480.webp 480w, assets/img/sandvik-768.webp 768w, assets/img/sandvik-1280.webp 1280w"
      imagesizes="100vw">
```

(Nếu dùng AVIF trong `<picture>` thì preload bản AVIF, thêm `type="image/avif"`.)

- [ ] Nếu banner thực tế không phủ 100% chiều ngang (ví dụ có padding), đổi `sizes` cho đúng.
- [ ] **Slide 2, 3:** không để `src` ảnh trong HTML lúc đầu. Dùng `data-src` và chỉ gán `src` khi slider sắp chuyển sang slide đó, hoặc sau sự kiện `load` + 3 giây.
- [ ] Slide đầu phải **hiện ngay không cần JS**: không đặt `opacity:0`, không chờ class `.is-active` do JS thêm, không có animation fade-in trên slide đầu và tiêu đề banner. Nếu có hiệu ứng, chỉ chạy cho slide 2 trở đi.
- [ ] Kiểm tra lớp `reveal`: các phần tử trong màn hình đầu không nên ẩn chờ JS.

---

## 6. ⚠️ Google Tag Manager – vẫn tải trên di động (TBT 170 ms, 269 KiB JS không dùng)

Trên máy tính, GTM không còn xuất hiện, vậy trì hoãn đã chạy. Nhưng trên **di động** lượt đo kéo dài hơn nên **hẹn giờ `setTimeout(loadGTM, 4000)` vẫn kích hoạt**, kèm 5 tác vụ dài (tổng 410 ms):

| Script | Kích thước | Ghi chú |
|---|---|---|
| `gtag/js?id=GT-PZSCJG4` | 177 KiB | gắn trực tiếp trong HTML |
| `gtag/js?id=GT-PZSCJG4&cx=c&gtm=...` | 177 KiB | GTM tải lại cùng tag này → **trùng lặp** |
| `gtm.js?id=GTM-M3XKBSNK` | 113 KiB | |

### Sửa:
- [ ] **Bỏ đoạn gtag `GT-PZSCJG4` gắn trực tiếp trong HTML** (vì GTM `GTM-M3XKBSNK` đã tải tag này). Chỉ giữ 1 đường: GTM. Kiểm tra trong GTM có thẻ “Google Tag” `GT-PZSCJG4` và GA4 `G-VDFBZC3D97` đúng cấu hình.
- [ ] **Chỉ tải GTM khi người dùng tương tác**, bỏ hẹn giờ tự tải, hoặc tăng lên ≥ 10 giây:

```html
<script>
  (function(){
    var loaded = false;
    function loadGTM(){
      if (loaded) return; loaded = true;
      (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':Date.now(),event:'gtm.js'});
      var f=d.getElementsByTagName(s)[0],j=d.createElement(s);j.async=true;
      j.src='https://www.googletagmanager.com/gtm.js?id='+i;f.parentNode.insertBefore(j,f);
      })(window,document,'script','dataLayer','GTM-M3XKBSNK');
    }
    ['pointerdown','touchstart','scroll','keydown','mousemove'].forEach(function(e){
      addEventListener(e, loadGTM, {once:true, passive:true});
    });
    // Tuỳ chọn: tự tải sau 10s cho người không tương tác (Lighthouse thường đã kết thúc)
    addEventListener('load', function(){ setTimeout(loadGTM, 10000); });
  })();
</script>
```

> ⚠️ Cần báo khách hàng: người vào rồi thoát trong vài giây mà không chạm/cuộn sẽ không được GA4/Ads ghi nhận. Thường chỉ mất một phần nhỏ dữ liệu, nhưng tỉ lệ thoát (bounce) trên GA4 có thể thay đổi.

### Phương án thay thế: Cloudflare Zaraz (nên cân nhắc)
- [ ] Site đã dùng Cloudflare → có thể chuyển GA4 + Google Ads sang **Cloudflare Zaraz** (Dashboard → Zaraz). Zaraz chạy tag ở phía máy chủ Cloudflare và chỉ đặt 1 script rất nhỏ lên trang → gần như hết TBT do tag và **không mất dữ liệu** như cách trì hoãn.
- [ ] Nếu khách dùng GTM cho nhiều thứ khác (pixel Facebook, chat, heatmap…), kiểm tra Zaraz có hỗ trợ từng tool trước khi chuyển.

---

## 7. ❌ Cloudflare Web Analytics / RUM – 2 cảnh báo đỏ (bộ nhớ đệm, JavaScript cũ)

Cả 2 mục đỏ “Sử dụng thời gian hữu dụng của bộ nhớ đệm” và “JavaScript cũ” đều do `static.cloudflareinsights.com/beacon.min.js` (+ request `/cdn-cgi/rum`). File này nằm trong chuỗi tải quan trọng (155 ms). Bạn không sửa được file này, chỉ có thể tắt.

- [ ] Cloudflare Dashboard → **Analytics & Logs → Web Analytics** → chọn site → tắt “Automatic setup” / RUM (hoặc xoá site khỏi Web Analytics).
- [ ] Cloudflare Dashboard → **Speed → Observatory** → nếu có bật Real User Monitoring (RUM) thì tắt.
- [ ] Nếu dùng Cloudflare Pages: Settings → Web Analytics → Disable.
- [ ] Sau đó xoá cache và kiểm tra mã nguồn trang không còn `cloudflareinsights`.

---

## 8. Font – chuỗi phụ thuộc mạng 351 ms

Hiện còn 2 font trong chuỗi quan trọng: `montserrat-vietnamese.woff2` (11,3 KiB) và `open-sans-vietnamese.woff2` (13,5 KiB). Hai file này tải cùng lúc với ảnh LCP và tranh băng thông.

Chọn một hoặc nhiều cách:
- [ ] **`font-display: optional`** cho cả 2 font: lần đầu có thể hiện font hệ thống nếu font chưa kịp tải, từ lần sau dùng font từ cache. Font không chặn hiển thị, CLS = 0.
- [ ] Thêm font dự phòng có số đo tương đương để chữ không “nhảy” khi đổi font:

```css
@font-face {
  font-family: "Open Sans Fallback";
  src: local("Arial");
  size-adjust: 105%; ascent-override: 102%; descent-override: 28%; line-gap-override: 0%;
}
body { font-family: "Open Sans", "Open Sans Fallback", system-ui, sans-serif; }
```

- [ ] **Cân nhắc dùng font hệ thống cho chữ thường** (`system-ui, -apple-system, "Segoe UI", Roboto, Arial`), chỉ giữ Montserrat cho tiêu đề → bớt hẳn 1 họ font (3 file).
- [ ] Gộp subset: dùng `pyftsubset` / glyphhanger tạo 1 file chứa đúng ký tự Latin + tiếng Việt thực sự dùng trên site cho mỗi font, thay vì 3 file latin / latin-ext / vietnamese.
- [ ] **Không** preload quá 2 font. Nếu đã chuyển sang `optional`, có thể bỏ preload font để ưu tiên ảnh LCP.

---

## 9. ❌ Buộc chỉnh lại luồng (Forced reflow) trong `main.js`

- Máy tính: `js/main.js?v=20261115a` **dòng 31, cột 19** – 75 ms.
- Di động: 65 ms (chưa phân bổ, cùng nguồn).
- Tác vụ dài: `main.js` 51 ms, HTML 83–90 ms.

Forced reflow xảy ra khi JS **thay đổi style/class/DOM rồi ngay lập tức đọc** kích thước/vị trí (`offsetWidth`, `offsetHeight`, `clientHeight`, `scrollHeight`, `getBoundingClientRect()`, `getComputedStyle()`, `scrollTop`, `innerText`…).

- [ ] Mở `main.js` dòng 31, tìm lệnh đọc kích thước nằm sau một lệnh ghi style. Cách sửa:

```js
// ❌ Trước: ghi rồi đọc xen kẽ, mỗi vòng lặp ép trình duyệt tính lại layout
items.forEach(el => {
  el.classList.add('x');
  const h = el.offsetHeight;      // forced reflow
  el.style.height = h + 'px';
});

// ✅ Sau: đọc hết trước, ghi sau (trong 1 frame)
const heights = items.map(el => el.scrollHeight);   // đọc
requestAnimationFrame(() => {
  items.forEach((el, i) => { el.style.height = heights[i] + 'px'; }); // ghi
});
```

- [ ] Nếu là code đo chiều cao slider/FAQ (`button#fq1`…), chuyển sang CSS: FAQ dùng `<details>/<summary>` hoặc `grid-template-rows: 0fr → 1fr`, không cần đo chiều cao bằng JS.
- [ ] Hiệu ứng `reveal`: dùng `IntersectionObserver` (không dùng sự kiện `scroll` + `getBoundingClientRect`).
- [ ] Khởi tạo những phần không cần ngay (FAQ, form báo giá, slider từ slide 2) trong `requestIdleCallback`:

```js
const idle = window.requestIdleCallback || (cb => setTimeout(cb, 200));
idle(() => { initFAQ(); initQuoteForm(); });
```

- [ ] Đảm bảo `<script src="js/main.js" defer>` (hoặc `type="module"`), không có script đồng bộ trong `<head>`.

---

## 10. Tinh chỉnh Cloudflare (nhỏ nhưng nên làm)

- [ ] **Speed → Optimization → Early Hints: Bật.** Cloudflare gửi `103 Early Hints` với các `<link rel="preload">` → trình duyệt tải ảnh banner sớm hơn. (Hiệu quả với người dùng thật; Lighthouse có thể không thấy.)
- [ ] **Rocket Loader: Tắt** (thường làm chậm LCP và gây lỗi script).
- [ ] Brotli / HTTP/3: để bật (mặc định).
- [ ] **Cache HTML ở edge:** với site tĩnh trên Pages thì đã có sẵn. Nếu không dùng Pages, tạo Cache Rule “Cache Everything” cho HTML với Edge TTL ngắn (vd. 1–4 giờ) và purge khi deploy.
- [ ] Ảnh/CSS/JS/font có `?v=` → đặt `Cache-Control: public, max-age=31536000, immutable` trong `_headers`:

```
/assets/*
  Cache-Control: public, max-age=31536000, immutable
/js/*
  Cache-Control: public, max-age=31536000, immutable
/css/*
  Cache-Control: public, max-age=31536000, immutable
```

---

## 11. Tối ưu thêm (không bắt buộc)

- [ ] `content-visibility: auto; contain-intrinsic-size: auto 800px;` cho các section bên dưới (dự án, kiến thức, FAQ, footer) → giảm thời gian render lần đầu trên CPU yếu.
- [ ] DOM 823 phần tử, sâu 11: chấp nhận được. Có thể gom sprite SVG `<svg width="0">` (21 con) thành file `icons.svg` ngoài nếu dùng nhiều trang.
- [ ] HTML trang chủ hiện ~25 KiB (đã inline CSS) → ổn. Đảm bảo CSS inline đã được minify.
- [ ] Bảo mật (không tính điểm): CSP, Trusted Types, HSTS `includeSubDomains; preload` – xem file đề xuất bước 1.

---

## 12. Cách kiểm tra sau khi sửa

- [ ] Purge cache Cloudflare, đổi `?v=` của JS/CSS.
- [ ] Kiểm tra nhanh trong Chrome DevTools → **Network**, lọc `Img`, tải lại trang ở chế độ di động: trước khi cuộn, **chỉ** được thấy logo + ảnh banner đầu (+ font). Không có `rua-cat`, `vsi`, `con-3`…
- [ ] DevTools → Network: không còn `cloudflareinsights`, `googletagmanager` khi chưa chạm/cuộn trang.
- [ ] DevTools → **Performance** → CPU 4x slowdown + Network “Slow 4G” → ghi lại, xem LCP.
- [ ] Chạy PageSpeed Insights **3–5 lần**, lấy kết quả trung vị (điểm di động luôn dao động ±3–5).
- [ ] Kiểm tra GA4 Realtime + chuyển đổi Google Ads vẫn hoạt động.

### Kỳ vọng sau khi làm mục 3–7
| Chỉ số | Hiện tại | Dự kiến |
|---|---|---|
| LCP di động | 4,3 s | ~1,5–2,2 s |
| TBT di động | 170 ms | ~0–80 ms |
| Điểm hiệu suất di động | 83 | ~95–100 |
