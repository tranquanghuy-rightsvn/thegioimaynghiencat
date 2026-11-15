# Báo cáo PageSpeed Insights – thegioimaynghienda.com

> Nguồn: PageSpeed Insights (Lighthouse), lần chạy ngày 15/11/2026, cả hai chế độ **Di động** và **Máy tính**.
> Mục tiêu: đạt 100 điểm ở mọi hạng mục.

## 1. Điểm hiện tại

| Hạng mục | Di động | Máy tính | Mục tiêu |
|---|---|---|---|
| Hiệu suất (Performance) | **92** | **97** | 100 |
| Hỗ trợ tiếp cận (Accessibility) | **94** | **94** | 100 |
| Phương pháp hay nhất (Best Practices) | **77** | **77** | 100 |
| SEO | 100 ✅ | 100 ✅ | 100 |
| Duyệt web bằng tác nhân | 3/3 ✅ | 3/3 ✅ | – |

### Chỉ số hiệu suất

| Chỉ số | Di động | Máy tính |
|---|---|---|
| First Contentful Paint | 0,9 s ✅ | 0,7 s ✅ |
| Largest Contentful Paint | **3,0 s ⚠️** | 1,1 s ✅ |
| Total Blocking Time | 160 ms ✅ | 30 ms ✅ |
| Cumulative Layout Shift | 0,005 ✅ | 0,011 ✅ |
| Speed Index | 1,8 s ✅ | 0,8 s ✅ |

**Phần tử LCP:** ảnh slide đầu `assets/img/sandvik.webp` (`<img class="slide__bg" ... fetchpriority="high">`).

> **Lưu ý cho khách hàng:** Điểm Hiệu suất dao động vài điểm giữa các lần chạy (mạng, máy chủ test). Trên di động, LCP phải xuống khoảng ≤ 1,2–1,5 s mới chạm 98–100. Best Practices và Accessibility thì đạt 100 ổn định được nếu sửa hết các mục dưới đây.

---

## 2. Thứ tự ưu tiên (làm theo thứ tự này)

| # | Việc cần làm | Ảnh hưởng | Độ khó |
|---|---|---|---|
| 1 | Bỏ `action="mailto:..."` / yêu cầu không an toàn (mục 5.1) | Best Practices 77 → ~100 | Dễ |
| 2 | Sửa tương phản màu + kích thước nút chấm slider (mục 4) | Accessibility 94 → 100 | Dễ |
| 3 | Gộp và trì hoãn Google Tag Manager / gtag (mục 3.4) | TBT, JS không dùng, tác vụ dài | Trung bình |
| 4 | Ảnh responsive (`srcset`/`sizes`) + nén lại ảnh (mục 3.1) | LCP di động, −996 KiB | Trung bình |
| 5 | Inline CSS quan trọng, preload font (mục 3.2, 3.3) | LCP di động, −280 ms | Trung bình |
| 6 | Tắt Cloudflare Web Analytics nếu không dùng (mục 3.5) | Cache, JS cũ | Dễ |
| 7 | Thêm header bảo mật (mục 5.3) | Không tính điểm, nên làm | Dễ |

---

## 3. Hiệu suất (Performance)

### 3.1 ❌ Cải thiện việc phân phối hình ảnh – tiết kiệm ~996 KiB (di động) / ~903 KiB (máy tính)

Tất cả ảnh đều xuất 1400px nhưng hiển thị nhỏ hơn nhiều.

| Ảnh | Kích thước file | Gốc → Hiển thị (di động) | Tiết kiệm |
|---|---|---|---|
| `img/rua-cat.webp` | 153,7 KiB | 1400×840 → 186×112 | 151,0 KiB |
| `img/vsi.webp` | 136,5 KiB | 1400×1050 → 382×287 | 126,4 KiB |
| `img/tram-thanh-long.webp` | 136,2 KiB | 1400×1050 → 382×287 | 126,1 KiB |
| `img/con-3.webp` | 116,9 KiB | 1400×1750 → 149×186 | 115,6 KiB |
| `img/tach-cat-min.webp` | 113,3 KiB | 1400×1218 → 329×287 | 107,0 KiB |
| `img/sandvik.webp` (**ảnh LCP**) | 132,2 KiB | 916×932 → 631×420 | 91,2 KiB |
| `img/di-dong.webp` | 79,0 KiB | 1400×934 → 186×124 | 77,6 KiB |
| `img/phan-kich.webp` | 73,3 KiB | 1400×1622 → 136×158 | 72,6 KiB |
| `img/du-an-300.webp` | 69,6 KiB | 1400×646 → 382×176 | 64,4 KiB |
| `img/du-an-bao-tri.webp` | 56,6 KiB | 1400×990 → 382×270 | 52,3 KiB |
| `img/logo.webp` | 11,6 KiB | 160×157 → 42×41 (+ nên nén mạnh hơn) | 11,3 KiB |

Máy tính: `rua-cat` hiển thị 289×173, `vsi` 289×217, `con-3` 231×289.

**Cách sửa:**
- [ ] Xuất mỗi ảnh thành nhiều cỡ, ví dụ `-400w`, `-800w`, `-1400w` (WebP hoặc AVIF, chất lượng ~70–75).
- [ ] Dùng `srcset` + `sizes` để trình duyệt chọn cỡ phù hợp:

```html
<img src="assets/img/rua-cat-400.webp"
     srcset="assets/img/rua-cat-400.webp 400w,
             assets/img/rua-cat-800.webp 800w,
             assets/img/rua-cat-1400.webp 1400w"
     sizes="(max-width: 600px) 50vw, 300px"
     width="1400" height="840" loading="lazy" decoding="async"
     alt="Máy rửa cát dạng guồng">
```

- [ ] Ảnh LCP `sandvik.webp`: tạo bản 640w/960w/1280w, giữ `fetchpriority="high"`, **không** `loading="lazy"`, và preload trong `<head>`:

```html
<link rel="preload" as="image" href="assets/img/sandvik-960.webp"
      imagesrcset="assets/img/sandvik-640.webp 640w, assets/img/sandvik-960.webp 960w, assets/img/sandvik-1280.webp 1280w"
      imagesizes="100vw" fetchpriority="high">
```

- [ ] Logo: xuất bản 84×82 (2x của 42×41) và tăng mức nén.
- [ ] Các slide 2, 3 của banner: `loading="lazy"` để không tranh băng thông với slide 1.

### 3.2 ❌ Yêu cầu chặn hiển thị – tiết kiệm ~280 ms (di động) / ~100 ms (máy tính)

- File chặn: `css/style.css?v=20261108r` (14,3 KiB).

**Cách sửa (chọn 1):**
- [ ] **Cách đơn giản nhất:** CSS chỉ 14 KiB → inline toàn bộ vào `<style>` trong `<head>` khi build (site tĩnh nên làm được).
- [ ] Hoặc inline CSS “above the fold” (header, menu, slide đầu), phần còn lại tải không chặn:

```html
<link rel="preload" href="css/style.css?v=..." as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="css/style.css?v=..."></noscript>
```

### 3.3 ❌ Cây phần phụ thuộc mạng (chuỗi yêu cầu quan trọng) – độ trễ tối đa 252 ms

Chuỗi: HTML → `style.css` → 6 file font. Font chỉ được phát hiện sau khi CSS tải xong:

- `montserrat-vietnamese.woff2` (11,2 KiB), `montserrat-latin-ext.woff2` (67,5 KiB), `montserrat-latin.woff2` (35,5 KiB)
- `open-sans-vietnamese.woff2` (13,5 KiB), `open-sans-latin-ext.woff2` (30,7 KiB), `open-sans-latin.woff2` (42,8 KiB)

**Cách sửa:**
- [ ] Preload 2–3 font dùng ở màn hình đầu (thường là bản `latin` + `vietnamese` của font tiêu đề và font chữ thường):

```html
<link rel="preload" href="assets/fonts/montserrat-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/open-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
```

- [ ] Kiểm tra `unicode-range` trong `@font-face` đúng để trình duyệt không tải `latin-ext` khi không cần (latin-ext Montserrat 67 KiB là file lớn nhất).
- [ ] Cân nhắc gộp subset `latin` + `vietnamese` thành 1 file mỗi font (dùng `pyftsubset`/glyphhanger), bỏ `latin-ext` nếu không dùng.
- [ ] Dùng `font-display: swap` (hoặc `optional` để triệt tiêu CLS).

### 3.4 ⚠️ Giảm JavaScript không dùng đến – 344 KiB · Tác vụ dài · Bên thứ ba

Toàn bộ đến từ **Google Tag Manager / gtag** (648 KiB, 405 ms thời gian chạy trên di động). Trang đang tải **4 script** của Google:

| Script | Kích thước | Không dùng |
|---|---|---|
| `gtag/js?id=G-VDFBZC3D97&cx=c&gtm=...` | 177 KiB | 124 KiB |
| `gtag/js?id=G-VDFBZC3D97` | 177 KiB | 76 KiB |
| `gtm.js?id=GTM-M3XKBSNK` | 113 KiB | 72 KiB |
| `gtag/js?id=GT-PZSCJG4` | 177 KiB | 72 KiB |

→ GA4 `G-VDFBZC3D97` đang bị tải **2 lần** (1 lần trực tiếp, 1 lần qua GTM).
Ghi nhận 6 tác vụ dài (di động) / 4 (máy tính), đều từ gtag.

**Cách sửa:**
- [ ] **Chỉ giữ 1 cách gắn tag**: hoặc chỉ GTM (`GTM-M3XKBSNK`) và cấu hình GA4 + Google Ads (`GT-PZSCJG4`) bên trong GTM; hoặc chỉ gtag. Xoá các đoạn `gtag/js` gắn thẳng trong HTML nếu đã có trong GTM.
- [ ] Trì hoãn tải GTM đến sau khi trang tải xong / khi người dùng tương tác đầu tiên:

```html
<script>
  function loadGTM(){
    if (window.gtmLoaded) return; window.gtmLoaded = true;
    (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':Date.now(),event:'gtm.js'});
    var f=d.getElementsByTagName(s)[0],j=d.createElement(s);j.async=true;
    j.src='https://www.googletagmanager.com/gtm.js?id='+i;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-M3XKBSNK');
  }
  ['scroll','mousemove','touchstart','keydown','click'].forEach(function(e){
    addEventListener(e, loadGTM, {once:true, passive:true});
  });
  addEventListener('load', function(){ setTimeout(loadGTM, 4000); });
</script>
```

> ⚠️ Trì hoãn tag có thể làm mất một ít dữ liệu Analytics/Ads của người thoát trang rất nhanh — cần báo khách hàng và thống nhất trước.

### 3.5 ⚠️ Bộ nhớ đệm (4 KiB) · JavaScript cũ (10 KiB) · Tính năng Baseline

Cả 3 mục đến từ `static.cloudflareinsights.com/beacon.min.js` (Cloudflare Web Analytics / RUM) — không sửa được file này.

- [ ] Nếu không cần Cloudflare Web Analytics: tắt trong Cloudflare Dashboard → Analytics & Logs → Web Analytics (tắt tự động chèn / RUM). Đã có GA4 nên thường có thể bỏ.

### 3.6 ⚠️ Rút gọn CSS – 2,4 KiB

- [ ] Minify `style.css` khi build (cssnano, lightningcss, esbuild…). Nếu đã inline CSS (mục 3.2) thì minify luôn phần inline.

### 3.7 ❌ Buộc chỉnh lại luồng (Forced reflow) – chỉ trên máy tính

- Vị trí: `js/main.js?v=20261103b` dòng **24**, cột 19 (18 ms).
- [ ] Kiểm tra đoạn này: không đọc `offsetHeight/getBoundingClientRect/scrollTop…` ngay sau khi đổi style/class. Gom các lệnh đọc lên trước, ghi sau, hoặc bọc phần ghi trong `requestAnimationFrame`.

### 3.8 ℹ️ Thông tin thêm (không bắt buộc)

- **CLS di động 0,005:** đoạn `<p>` giới thiệu “Công ty Cổ phần Thiết bị và Dịch vụ Kỹ thuật Thanh Long…” xê dịch khi font web tải xong → dùng `font-display: optional` hoặc font dự phòng có `size-adjust`.
- **CLS máy tính 0,011:** menu chính `<nav class="nav">` xê dịch → cùng nguyên nhân font; đặt chiều cao cố định cho header/nav.
- **Kích thước DOM:** 827 phần tử, độ sâu 11 — chấp nhận được.
- **LCP breakdown (di động):** TTFB 0 ms · trễ tải 60 ms · thời gian tải 60 ms · trễ hiển thị 140 ms → phần trễ hiển thị chủ yếu do CSS/font chặn (mục 3.2, 3.3).

---

## 4. Hỗ trợ tiếp cận (Accessibility) – 94 → 100

### 4.1 ❌ Màu chữ và màu nền không đủ tương phản

Dòng mô tả nhỏ (`<p>`) trong các thẻ sản phẩm `<article class="product reveal">`:

- “NGHIỀN SƠ CẤP · ĐỘ MỞ 600×900 – 900×1200 MM” (Máy nghiền hàm)
- “NGHIỀN TRUNG, MỊN · MODEL SC350, SC650” (Máy nghiền côn)
- “HẠT DẠNG KHỐI · ĐÁ VÔI, VẬT LIỆU TÁI CHẾ” (Máy nghiền phản kích)
- “TÁCH CỠ 0–5, 5–10, 10–20, 20–40 MM” (Sàng rung phân loại)

**Cách sửa:**
- [ ] Đổi màu chữ của dòng này (ví dụ class mô tả trong `.product`) sao cho tỉ lệ tương phản ≥ **4.5:1** (chữ nhỏ). Không dùng `opacity` để làm nhạt chữ.
- [ ] Kiểm tra lại bằng DevTools (Inspect → biểu tượng màu → Contrast ratio) hoặc webaim.org/resources/contrastchecker.
- [ ] Lưu ý class `reveal` (hiệu ứng hiện dần): nếu lúc Lighthouse đo, phần tử còn `opacity` < 1 thì cũng bị tính là thiếu tương phản → đảm bảo hiệu ứng chỉ dùng `transform`, hoặc trạng thái ban đầu không làm mờ chữ.

### 4.2 ❌ Đích chạm quá nhỏ / quá sát nhau

Các nút chấm của slider banner: `<button role="tab" aria-label="Banner 2">`, `Banner 3`.

**Cách sửa:**
- [ ] Vùng bấm tối thiểu **24×24 px** (khuyến nghị 44×44 px trên di động) và có khoảng cách giữa các nút. Có thể giữ chấm nhỏ bằng cách mở rộng vùng bấm:

```css
.slider__dots button {            /* đổi đúng selector của bạn */
  position: relative;
  width: 10px; height: 10px;       /* chấm nhìn thấy */
  margin: 0 8px;
}
.slider__dots button::after {
  content: ""; position: absolute;
  inset: -12px;                    /* vùng bấm ~34×34 px */
}
```

### 4.3 ℹ️ Các liên kết giống hệt nhau phải có cùng mục đích (nên sửa)

- Di động: 2 link “Xem tất cả” trỏ tới `san-pham/may-nghien-da/` và `san-pham/may-lam-cat/`.
- Máy tính: nhiều link “BÁO GIÁ” (`bao-gia/` và `#bao-gia` với `data-cap="150|300|500"`).

**Cách sửa:**
- [ ] Thêm ngữ cảnh: `<a href="san-pham/may-nghien-da/" aria-label="Xem tất cả máy nghiền đá">Xem tất cả</a>`
- [ ] `<a href="#bao-gia" aria-label="Báo giá trạm nghiền 150 tấn/giờ">BÁO GIÁ</a>` (tương tự cho 300, 500).

---

## 5. Phương pháp hay nhất (Best Practices) – 77 → 100

### 5.1 ❌ Không sử dụng HTTPS – 1 yêu cầu không an toàn: `mailto:hieu@labcare.com.vn`

Trạng thái: “Được phép nhưng có cảnh báo” (Mixed content). Đây là lỗi làm mất nhiều điểm nhất.

Nhiều khả năng do một **form gửi tới `mailto:`** (ví dụ `<form action="mailto:hieu@labcare.com.vn">`), hoặc một yêu cầu/redirect tới địa chỉ `mailto:` từ JavaScript. Link `<a href="mailto:...">` bình thường thì không bị tính.

**Cách sửa:**
- [ ] Tìm trong mã nguồn: `grep -rn "mailto:hieu@labcare" .`
- [ ] Nếu là `action` của form báo giá: thay bằng endpoint HTTPS, ví dụ Cloudflare Pages Functions / Worker gửi mail, Formspree, Web3Forms, Google Apps Script… rồi gửi bằng `fetch()`.
- [ ] Nếu là JS kiểu `location.href = "mailto:..."` khi submit: thay bằng gửi qua endpoint HTTPS như trên.
- [ ] Giữ email hiển thị dạng `<a href="mailto:...">` là được.

### 5.2 ❌ Có vấn đề trong bảng Issues của Chrome DevTools: Mixed content

- Cùng nguyên nhân với mục 5.1 → sửa 5.1 là hết mục này.
- [ ] Mở DevTools → tab **Issues** trên trang chủ để xác nhận không còn cảnh báo.

### 5.3 ℹ️ Bảo mật (không tính điểm, nên làm)

| Mục | Hiện trạng | Mức |
|---|---|---|
| CSP chống XSS | Không có CSP ở chế độ thực thi | Cao |
| Trusted Types | Không có chỉ thị Trusted Types trong CSP | Cao |
| COOP (tách biệt nguồn gốc) | Không có header COOP | Cao |
| HSTS | Thiếu `includeSubDomains` và `preload` | Trung bình |

**Cách sửa (site tĩnh trên Cloudflare Pages → file `_headers` ở thư mục gốc):**

```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  Cross-Origin-Opener-Policy: same-origin
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://static.cloudflareinsights.com; connect-src 'self' https://*.google-analytics.com https://*.analytics.google.com https://www.googletagmanager.com https://cloudflareinsights.com; img-src 'self' data: https://*.google-analytics.com https://www.googletagmanager.com; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'
```

- [ ] Chạy CSP ở chế độ `Content-Security-Policy-Report-Only` trước, kiểm tra Console không có lỗi chặn, sau đó mới đổi thành `Content-Security-Policy`. Thêm domain của endpoint form (mục 5.1) vào `connect-src`/`form-action`.
- [ ] ⚠️ `includeSubDomains; preload` áp dụng cho **mọi subdomain** và rất khó gỡ khi đã nộp danh sách preload — chỉ bật khi chắc chắn mọi subdomain đều chạy HTTPS.
- [ ] Nếu không dùng Pages mà dùng Cloudflare Workers/Transform Rules thì thêm header ở Rules → Transform Rules → Modify Response Header.

---

## 6. SEO – 100 ✅ · Duyệt web bằng tác nhân – 3/3 ✅

Không có đề xuất. Giữ nguyên.

---

## 7. Checklist kiểm tra sau khi sửa

- [ ] Xoá cache Cloudflare (Caching → Purge Everything) và đổi `?v=` của CSS/JS.
- [ ] Chạy lại PageSpeed Insights 3 lần cho cả Di động và Máy tính, lấy kết quả trung vị.
- [ ] Kiểm tra GA4 Realtime / Google Ads vẫn ghi nhận sau khi gộp và trì hoãn tag.
- [ ] Kiểm tra form báo giá vẫn gửi được sau khi bỏ `mailto:`.
- [ ] Kiểm tra slider, menu trên di động sau khi sửa nút chấm và font.
