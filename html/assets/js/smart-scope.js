/* Smart content (GAS.md mục XI): gắn phạm vi cho CSS do AI viết — DÙNG CHUNG cho trang quản trị
 * (khung xem trước, nạp https://thegioimaynghienda.com/assets/js/smart-scope.js) và build Python
 * (tools/smart.py chạy file này bằng `node`).
 * ".smc-card h3" -> ".smc-a.smc-a.smc-a .smc-card h3" (lặp class để thắng CSS của site và phần reset
 * trong smart.css). Bỏ @import/@charset, chú thích, "</style". Mỗi trang chỉ có 1 bài Smart content
 * nên dùng 1 class phạm vi cố định.
 * UMD: trình duyệt -> biến toàn cục smcScopeCss/smcColorStyle; Node -> require('.../smart-scope.js'). */
var SMC_SCOPE = '.smc-a.smc-a.smc-a';

function smcScopeCss(css) {
  var PASS = ['keyframes', '-webkit-keyframes', 'font-face', 'property', 'counter-style', 'page'];
  var RECURSE = ['media', 'supports', 'container', 'layer', 'starting-style'];

  function skipString(s, i) {
    var q = s[i];
    for (i++; i < s.length; i++) {
      if (s[i] === '\\') i++;
      else if (s[i] === q) return i;
    }
    return s.length;
  }
  /** Vị trí ký tự đầu tiên thuộc stops nằm ngoài chuỗi và ngoài ngoặc () []. */
  function scan(s, i, stops) {
    var depth = 0;
    for (; i < s.length; i++) {
      var c = s[i];
      if (c === '\\') i++;
      else if (c === '"' || c === "'") i = skipString(s, i);
      else if (c === '(' || c === '[') depth++;
      else if (c === ')' || c === ']') depth = Math.max(0, depth - 1);
      else if (depth === 0 && stops.indexOf(c) !== -1) return i;
    }
    return s.length;
  }
  function matchBrace(s, open) {
    var depth = 0;
    for (var i = open; i < s.length; i++) {
      var c = s[i];
      if (c === '\\') i++;
      else if (c === '"' || c === "'") i = skipString(s, i);
      else if (c === '{') depth++;
      else if (c === '}' && --depth === 0) return i;
    }
    return s.length;
  }
  function selectors(prelude) {
    var parts = [];
    var i = 0;
    while (i <= prelude.length) {
      var j = scan(prelude, i, ',');
      var sel = prelude.slice(i, j).trim();
      i = j + 1;
      if (!sel) continue;
      var m = /^(:root|html|body|\.smc-root)(?![\w-])/i.exec(sel);
      parts.push(m ? SMC_SCOPE + sel.slice(m[0].length) : SMC_SCOPE + ' ' + sel);
    }
    return parts.join(',');
  }
  function walk(s) {
    var out = '';
    var i = 0;
    while (i < s.length) {
      var j = scan(s, i, '{;');
      if (j >= s.length) break;
      var prelude = s.slice(i, j).trim();
      if (s[j] === ';') { i = j + 1; continue; } // @import, @charset...
      var end = matchBrace(s, j);
      var body = s.slice(j + 1, end);
      i = end + 1;
      if (!prelude) continue;
      if (prelude[0] === '@') {
        var name = prelude.slice(1).split(/[\s(]/)[0].toLowerCase();
        if (RECURSE.indexOf(name) !== -1) out += prelude + '{' + walk(body) + '}';
        else if (PASS.indexOf(name) !== -1) out += prelude + '{' + body + '}';
        continue;
      }
      out += selectors(prelude) + '{' + body.trim() + '}';
    }
    return out;
  }

  css = String(css || '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/<\/style|<!--|-->/gi, '');
  return walk(css).trim();
}

/** Màu riêng của bài (chỉ nhận mã hex) -> style="" gắn lên khung bài. */
function smcColorStyle(primary, accent) {
  var ok = function (v) { return /^#[0-9a-f]{3,8}$/i.test(String(v || '')); };
  return (ok(primary) ? '--smc-primary:' + primary + ';' : '') + (ok(accent) ? '--smc-accent:' + accent + ';' : '');
}

if (typeof module === 'object' && module && module.exports) {
  module.exports = { SMC_SCOPE: SMC_SCOPE, smcScopeCss: smcScopeCss, smcColorStyle: smcColorStyle };
}
