# GAS.md — CMS thegioimaynghienda.com (quyết định nghiệp vụ CHỐT)

Đọc file này TRƯỚC khi sửa bất kỳ file nào trong `gas/` (`Code.js`, `index.html`, `app.html`,
`css.html`, `js.html`). Theo playbook skill `free-cms-static-site-pipeline` (mẫu xevip).
Sửa code xong thì cập nhật lại file này trong cùng lượt sửa — file lệch code còn tệ hơn không có.

```
Trang quản trị (https://thegioimaynghienda.com/admin/, nhúng web app Apps Script)
   │ Lưu / Xoá  →  GitHub Contents API (repo tranquanghuy-rightsvn/thegioimaynghiencat, nhánh master)
   ▼
data/*.json  ──(push data/posts.json hoặc data/menu.json)──►  GitHub Actions: python3 tools/build.py
   ──► commit "CI: build html from data" (chỉ html/) ──► Cloudflare tự deploy html/
```

Phạm vi CMS (đúng yêu cầu: "quản lý đầy đủ các mục trên menu, bao gồm Danh mục và bài viết"):
1. **Menu** — các nhóm trên thanh menu chính (Thiết bị, Giải pháp, Dự án, Dịch vụ, Kiến thức…).
2. **Danh mục** — các mục con trong từng nhóm menu (trang danh mục /san-pham/may-nghien-da/…).
3. **Bài viết** — toàn bộ 242 bài cũ (đã chuyển sang data/) + bài mới.
4. **Người dùng** — ai được đăng nhập CMS.

Ngoài phạm vi (KHÔNG quản lý qua CMS, sửa tay trong `html/`): trang chủ, Giới thiệu, Sản
phẩm (/san-pham/ — danh sách máy), Dịch vụ (/dich-vu/), Báo giá, Liên hệ; 3 mục cố định trên
menu "Giới thiệu", "Liên hệ", "Báo giá" (nằm trong `tools/menu.py`).

## I. Đăng nhập & phân quyền

1. OTP qua email → token. Không mật khẩu, không dựa vào phiên Google.
2. Chỉ email có trong Sheet `Users` mới xin được OTP — trừ chủ script (người deploy) luôn
   được và luôn là `root` ngầm định, không nằm trong Sheet, không hiện ở tab Người dùng.
3. 3 cấp `root > admin > editor`:
   - `editor`: Bài viết (thêm/sửa/xoá, tải ảnh).
   - `admin`: mọi thứ của editor + Menu + Danh mục + Người dùng (vì menu/danh mục đổi cấu
     trúc toàn site, đổi URL).
   - `root`: chủ script. Không cấp được qua CMS.
   Qua CMS chỉ thêm/sửa/xoá được `admin`, `editor`; không tự sửa/xoá chính mình.
4. OTP sống 10 phút, cooldown 60 giây/email, sai 5 lần phải xin mã mới. Token sống 30 ngày,
   lưu localStorage; Đăng xuất thu hồi token trên server; token hết hạn được dọn lúc đăng nhập.
5. Server tự kiểm tra quyền ở MỌI hàm (`requireRole_`). Ẩn tab không phải bảo mật.

## II. Bài viết

1. Ô nhập trên giao diện:
   - **Tiêu đề**
   - **URL** (`/<slug>/` ở gốc site) — tự sinh từ tiêu đề (bỏ dấu, gạch ngang), bất biến sau
     lần Lưu đầu. Không được trùng bài khác, không trùng thư mục có sẵn của site (`RESERVED_SLUGS`
     trong Code.js + thư mục gốc của mọi nhóm/danh mục).
   - **Danh mục** — chọn 1 danh mục (nhóm theo menu). Quyết định URL breadcrumb, trang danh
     mục chứa bài, "bài viết liên quan".
   - **Mô tả** — dùng cho meta description + thẻ bài (dưới 50 ký tự thì build tự lấy câu khác).
   - **Chủ đề (tag)** — gõ tên, cách nhau bằng dấu phẩy, có gợi ý tag sẵn có. Tag mới tự tạo
     trang `/tag/<slug>/`.
   - **Ảnh đại diện** — bắt buộc với bài mới; bài cũ giữ ảnh cũ nếu không tải ảnh khác.
   - **Nội dung** — TinyMCE (tự host ở `html/vendor/tinymce/` 6.8.5): đoạn văn, H2/H3/H4,
     đậm/nghiêng/gạch chân, danh sách, link, bảng, video YouTube (media), mã HTML.
     **CÓ chèn ảnh trong nội dung**: nút "Chèn ảnh" mở thẳng hộp chọn file (chọn nhiều ảnh),
     ảnh bọc `<figure>` + `<figcaption>`; alt = caption, caption trống thì alt = tiêu đề bài.
2. Tự suy, không có ô nhập: ngày đăng (`date`, lần Lưu đầu, giữ nguyên về sau), ngày sửa
   (`modified`, mỗi lần Lưu), tiêu đề SEO (= tiêu đề + " | Thế Giới Máy Nghiền Đá", build lo),
   `legacy_categories` (chuyên mục WordPress cũ, chỉ còn "video") — giữ nguyên khi Lưu.
   Link nội bộ tự động (cụm từ khoá → trang danh mục/bài trụ cột) do build thêm, KHÔNG lưu
   trong nội dung.
3. Danh sách trong Admin: GAS đọc `data/posts.json` qua GitHub API trong `boot()` (luôn mới
   nhất), cache localStorage (stale-while-revalidate).
4. Ảnh: nén phía trình duyệt (cạnh dài ≤ 1600px, JPEG 0.85), tải thẳng lên GitHub ngay khi
   chọn. Ảnh RIÊNG 1-1 theo bài, mỗi bài 1 thư mục `html/assets/img/cms/<slug>/`:
   `cover-<mili-giây>.jpg` (tải lại ảnh đại diện = tên mới, tránh bộ nhớ đệm 30 ngày giữ ảnh
   cũ; ảnh đại diện cũ tự xoá lúc Lưu) và `content-<N>.jpg` (đánh số bất biến).
   Ảnh của 242 bài cũ (`html/assets/img/content/`, `posts/`) dùng chung → KHÔNG BAO GIỜ xoá.
   Trong `content_html`, link và ảnh lưu dạng tuyệt đối theo domain (`/assets/...`, `/slug/`);
   build đổi sang đường dẫn tương đối theo độ sâu trang + tự thêm width/height/lazy cho ảnh.

## III. Sửa bài

- URL khoá ở cả server (throw) lẫn client (disable). Tải ảnh xong cũng khoá URL.
- Ảnh trong editor hiển thị qua `raw.githubusercontent.com/<owner>/<repo>/<branch>/html/...`
  (editor chạy ở origin khác), đổi ngược về `/...` lúc Lưu.
- TinyMCE: `convert_urls:false` — không được để nó tự đổi link `/slug/` thành tương đối.
- Form dùng chung giữa tạo mới/sửa: mở form tạo mới phải bật lại ô URL.

## IV. Xoá bài

- Hỏi xác nhận trước. Xoá: `data/posts/<slug>.json` + thư mục ảnh `assets/img/cms/<slug>/` +
  gỡ khỏi `data/posts.json` (ghi SAU CÙNG).
- Giữ SEO: thêm 301 `/<slug>/` → trang danh mục của bài vào `data/redirects.json`. Tạo lại
  bài cùng URL thì redirect đó tự bị gỡ.

## V. Menu (nhóm trên thanh menu chính)

- 5 nhóm gốc (`builtin`): Thiết bị, Giải pháp, Dự án, Dịch vụ, Kiến thức. Sửa được: tên hiện
  trên menu, thứ tự, "liên kết thêm" (link cố định đứng trước danh mục trong dropdown, vd
  Dịch vụ → "Lắp đặt & chuyển giao"). KHÔNG xoá được (trang đích của chúng là trang làm tay
  hoặc trang đặc thù).
- Nhóm mới: tên + giới thiệu + liên kết thêm; URL `/<key>/` tự sinh từ tên, bất biến; build tự
  dựng trang đích liệt kê các danh mục. Xoá được khi không còn danh mục → 301 về trang chủ.
- Mục cố định Giới thiệu / Liên hệ / Báo giá không quản lý ở đây.

## VI. Danh mục

- Ô nhập: Tên, Nhóm menu (bất biến sau khi tạo), URL (`<gốc nhóm>/<slug>/`, bất biến), Giới
  thiệu (đoạn mở đầu + meta description), Thứ tự trong nhóm, Máy hiển thị (chọn từ danh sách
  máy của trang /san-pham/), Bảng cấu hình theo công suất (có/không), Quy trình công nghệ (mỗi
  dòng `Công đoạn | Thiết bị`), Từ khoá dự án (bài trong danh mục "Dự án" có tiêu đề chứa từ
  khoá này hiện ở khối "Dự án đã triển khai").
- Xoá chỉ khi danh mục không còn bài viết → 301 URL danh mục về trang đích của nhóm.
- Danh mục có URL trùng trang đích nhóm (Dự án `/du-an/`) không xoá được.

## VII. UX chung

- 2 modal riêng: XÁC NHẬN (Huỷ/Xoá) trước khi xoá; THÔNG BÁO kết quả (1 nút Đóng), không
  alert()/confirm(), không toast. Sau mỗi Lưu/Xoá: "Website sẽ được cập nhật sau 1-2 phút!".
- Mọi nút async: spinner + disable, tự phục hồi khi lỗi. Lưu xong quay về danh sách của mục đó.
- 1 lượt `boot()` lấy hết dữ liệu; lần sau hiện ngay từ cache rồi làm mới ngầm; mọi
  mutation tự cập nhật cache. Chuyển tab không tải lại.
- Mọi key localStorage (trừ token) mang `CLIENT_BUILD` — server tự băm từ `app.html` + `js.html`
  (`clientBuild_()`), không gõ tay; key bản cũ tự dọn.
- Khối `if (TOKEN) bootApp()` LUÔN là đoạn cuối `js.html`; kiểm bằng
  `node scripts/check_gas_client.mjs` (hook tự chạy khi sửa `gas/*.html`).
- Không lộ tên hạ tầng (Sheet/Drive/Apps Script/GitHub) trong chữ hiển thị, comment hay lỗi
  của các file `.html` gửi xuống trình duyệt.

## VIII. Lưu trữ (tên file/cột CỐ ĐỊNH — đổi phải sửa cả Code.js lẫn tools/build.py)

Google Sheet "Thegioimaynghienda CMS Data" (tự tạo lần đầu): sheet `Users` (`email`, `role`).

GitHub (repo site):

| Đường dẫn | Nội dung | Trigger CI |
|---|---|---|
| `data/menu.json` | `{groups:[{key,label,landing,nav,base,order,builtin,intro,links:[{name,path}]}], categories:[{key,parent,name,path,intro,order,products[],capacity,flow[[công đoạn,thiết bị]],project_kw[]}]}` | **có** |
| `data/posts.json` | index mọi bài `[{slug,title,description,section,date,modified,thumb,tags[],legacy_categories[]}]` | **có** |
| `data/posts/<slug>.json` | 1 bài = các field trên + `content_html` | không |
| `data/tags.json` | `{slug: tên hiển thị}` (mọi tag có trang) | không |
| `data/redirects.json` | `{"/url-cu/": "/url-moi/"}` — 301 do CMS tạo (xoá bài/danh mục/nhóm) | không |
| `html/assets/img/cms/` | ảnh CMS tải lên | không |

Thứ tự ghi trong 1 thao tác: ảnh → chi tiết bài → tags.json / redirects.json → file trigger
(`posts.json` hoặc `menu.json`) LUÔN SAU CÙNG.
Độ trễ thật: Lưu → CI build (~1 phút) → Cloudflare deploy (~1 phút).

`tools/export_cms_data.py` chỉ chạy 1 lần (đã chạy 18/11/2026) để chuyển dữ liệu từ bản scrape
WordPress sang `data/`; từ nay `data/` là nguồn chân lý, không chạy lại (có chặn `--force`).

## IX. Bug đã gặp ở dự án này

- Tên nhóm menu có ký tự `&`/`"` lọt thẳng vào HTML menu — do `tools/menu.py` không escape
  (trước đây tên menu viết cứng). Đã escape.
- Bài mới trong data/ không sinh trang — vì route bài lọc theo danh sách URL của audit cũ.
  Đã thêm mọi bài trong data/ vào danh sách hợp lệ.
- Xoá bài rồi xoá luôn danh mục/nhóm của nó tạo chuỗi redirect (bài → danh mục đã xoá → nhóm
  đã xoá) và redirect đầu chuỗi bị bỏ (đích không còn) → 404. `tools/build.py` giờ đi theo
  chuỗi trong `data/redirects.json` tới trang còn sống.

## X. Script Properties (tên CỐ ĐỊNH)

- `GITHUB_TOKEN` — fine-grained PAT, repo `thegioimaynghiencat`, quyền Contents: Read and write.
- `GITHUB_OWNER` = `tranquanghuy-rightsvn`
- `GITHUB_REPO` = `thegioimaynghiencat`
- `GITHUB_BRANCH` = `master`
- `SPREADSHEET_ID` — không cần điền, tự tạo lần đầu.
