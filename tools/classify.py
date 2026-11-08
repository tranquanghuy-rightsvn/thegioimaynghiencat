#!/usr/bin/env python3
"""Xếp mỗi bài viết vào đúng 1 chuyên mục của menu mới -> tools/data/structure.tsv

Chạy:  python3 tools/classify.py            (chỉ thêm bài mới, giữ dòng đã sửa tay)
       python3 tools/classify.py --reset    (phân loại lại toàn bộ theo quy tắc)

File TSV có 3 cột: slug, chuyên mục, tiêu đề. Muốn chuyển bài sang chuyên mục
khác thì sửa cột 2 rồi chạy lại tools/build.py. Mã chuyên mục xem SECTIONS
trong tools/build.py.
"""
import html
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "html"
OUT = ROOT / "tools" / "data" / "structure.tsv"

# Công trình thật Thanh Long đã giao / lắp / chạy thử (đã đọc nội dung từng bài).
PROJECTS = {
    "ban-giao-tram-nghien-da-150-tan-gio",
    "ban-giao-tram-tuyen-quang-sat-tai-yen-bai",
    "thanh-long-ban-giao-tram-thu-8-nghien-da-0x4-va-rua-cat-tieu-chuan-tai-binh-phuoc",
    "thanh-long-jsc-ban-giao-may-nghien-da-voi",
    "chay-thu-day-chuyen-nghien-da-550-tan-gio-xay-da-1x2",
    "may-nghien-da-250",
    "may-nghien-da-350",
}


# Bài quy tắc từ khoá xếp sai (đã đọc tiêu đề/nội dung) -> chuyên mục đúng.
OVERRIDES = {
    "bao-gia-may-nghien-cat-nhan-tao-2": "gp-cat-nhan-tao",
    "day-chuyen-nghien-da-cap-phoi-o-quang-nam": "gp-nghien-da",
    "day-chuyen-nghien-da-va-cat-nguyen-lieu-dung-trong-be-tong-nhua": "gp-cat-nhan-tao",
    "dich-vu-cung-ung-day-chuyen-tuyen-quang-sat": "gp-tuyen-quang",
    "hat-cat-nho-thi-truong-lon-tai-binh-phuoc-dau-tu-tram-nghien-cat-dat-chuan": "gp-cat-nhan-tao",
    "may-nghien-bua-thiet-bi-dung-trong-day-chuyen-nghien-da": "tb-nghien-da",
    "may-nghien-bua-trong-day-chuyen-nghien-da-xay-dung": "tb-nghien-da",
    "may-nghien-cat-mini-giai-phap-hieu-qua-cho-nhu-cau-nghien-cat-nho": "tb-lam-cat",
    "may-nghien-cat-nhan-tao-la-gi-so-sanh-cat-nhan-tao-cat-tu-nhien": "tb-lam-cat",
    "may-nghien-cat-nhan-tao-tu-soi-song-tai-tinh-tuyen-quang": "gp-cat-nhan-tao",
    "may-nghien-cat-vsi-barmac": "tb-lam-cat",
    "may-nghien-cat-vsi-va-ung-dung-may-nghien-cat-vsi": "tb-lam-cat",
    "nhung-diem-khac-biet-may-nghien-cat-cong-nghe-my": "tb-lam-cat",
    "may-nghien-da-chia-khoa-trao-tay-cho-khoang-san-vung-tay-nguyen": "gp-nghien-da",
    "may-nghien-da-chia-khoa-trao-tay-giai-phap-toan-dien-cho-nha-dau-tu": "gp-nghien-da",
    "may-nghien-da-granite": "tb-nghien-da",
    "may-nghien-da-mini-giai-phap-toi-uu-cho-nhu-cau-nghien-da-nho-gon": "tb-nghien-da",
    "may-nghien-da-thanh-cat-hieu-qua": "tb-lam-cat",
    "may-nghien-da-thanh-cat-hieu-qua-nhat": "tb-lam-cat",
    "may-nghien-da-xay-dung-hieu-qua-cao-thanh-long": "tb-nghien-da",
}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def has(text, words):
    return any(w in text for w in words)


def classify(slug: str, title: str) -> str:
    if slug in OVERRIDES:
        return OVERRIDES[slug]
    if slug in PROJECTS:
        return "du-an"
    t = fold(slug.replace("-", " ") + " " + title)
    line = has(t, ["day chuyen", "tram nghien", "tram tuyen", "tram san xuat", "he thong", "chia khoa trao tay"])

    if has(t, ["may nghien da cu", "tram nghien da cu", "may cu", "thanh ly"]):
        return "dv-may-cu"
    if has(t, ["dich vu", "bao tri", "sua chua", "su co", "bao duong"]):
        return "dv-bao-tri"
    if has(t, ["bao gia da", "bao gia cat", "gia cat", "gia da ", "thi truong", "thuc trang", "tiem nang",
               "covid", "nha dau tu", "khai thac vlxd", "vat lieu xay dung tai", "vat lieu xay dung ba ria",
               "cao toc", "san bay", "cau phuoc an", "con khat", "siet chat", "nguon cat", "nha san xuat",
               "cat doi tai tinh", "khai thac cat nhan tao tai", "khai thac san xuat da voi"]):
        return "kt-thi-truong"
    if has(t, ["tai che", "phe lieu", "phe thai"]):
        return "gp-tai-che"
    if has(t, ["quang", "tuyen tu", "nghien bi", "hematit", "tach tu", "than da", "khoang san"]):
        return "gp-tuyen-quang" if line else "tb-tuyen-quang"
    if has(t, ["rua cat", "cat min", "ep bun", "nuoc thai", "sang rua", "xit rua", "mclanahan", "truc vit", "cao lanh"]):
        return "gp-rua-cat" if line else "tb-rua-cat"
    if has(t, ["di dong"]):
        return "tb-di-dong"
    if has(t, ["cat nhan tao", "cat nghien", "vsi", "lam cat", "nghien cat", "soi song", "soi thanh cat",
               "soi doi", "barmac", "cat ket", "mi sang", "cat tu nhien", "cat xay dung", "cat xay"]):
        if has(t, ["la gi", "phan biet", "tieu chuan", "khac biet", "ung dung", "phan loai", "co the",
                   "cap phoi cat", "gach khong nung", "danh gia chat luong", "lieu co the", "cong trinh cau duong",
                   "thay the cat", "vat lieu thay the", "giai phap thay the", "lam tu gi", "giai phap cho nganh"]):
            return "kt-cat-vlxd"
        if line or has(t, ["cong nghe", "cung cap"]):
            return "gp-cat-nhan-tao"
        return "tb-lam-cat"
    if has(t, ["sang rung", "vong bi", "bac dan", "cap lieu", "bang tai"]):
        return "tb-sang-phu-tung"
    if has(t, ["van hanh", "an toan", "quy trinh", "cuong do", "da 1 2", "da voi", "vat lieu dau vao",
               "sai lam", "loi ich", "toi uu"]):
        return "kt-ky-thuat"
    if line:
        return "gp-nghien-da"
    if has(t, ["nghien ham", "kep ham", "nghien con", "phan kich", "nghien bua", "roller", "may nghien",
               "may xay da", "nghien da"]):
        return "tb-nghien-da"
    return "kt-ky-thuat"


def articles():
    """Bài viết chính đang có trên site (bỏ trang trùng đã noindex)."""
    for f in sorted(SITE.glob("*/index.html")):
        h = f.read_text(encoding="utf-8")
        if "article__meta" not in h or 'name="robots" content="noindex' in h:
            continue
        title = html.unescape(re.search(r"<h1>(.*?)</h1>", h, re.S).group(1)).strip()
        yield f.parent.name, title


def main():
    reset = "--reset" in sys.argv
    old = {}
    if OUT.exists() and not reset:
        for line in OUT.read_text(encoding="utf-8").splitlines()[1:]:
            slug, section, *_ = line.split("\t")
            old[slug] = section
    rows = [(slug, old.get(slug) or classify(slug, title), title) for slug, title in articles()]
    OUT.write_text("slug\tchuyen_muc\ttieu_de\n" + "".join(f"{a}\t{b}\t{c}\n" for a, b, c in rows), encoding="utf-8")
    counts = {}
    for _, s, _ in rows:
        counts[s] = counts.get(s, 0) + 1
    for s, n in sorted(counts.items()):
        print(f"{n:4}  {s}")
    print(f"{len(rows):4}  tổng -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
