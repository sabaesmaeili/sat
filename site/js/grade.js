/* Grading a typed answer (a student-produced response) against the item's accepted values.

   Exact: the answer is right when it is one of the accepted values as written, or the same number. Decimals and
   fractions are compared as exact rationals (0.0177 = .0177, 8/450 = 4/225, 17.50 = 35/2), so nothing near an
   accepted value counts unless it equals one (0.017, 0.0185 and 17.51 are wrong). Commas between thousands and a
   typographic minus are read as plain digits and "-". Browsers without BigInt fall back to floats with only a
   rounding tolerance. Shared by the drill pages (js/drill.js) and the test (tools/test_grading.js). */
(function (root) {
  var NUMBER = /^(-?)(\d+(?:\.\d*)?|\.\d+)(?:\/(\d+(?:\.\d*)?|\.\d+))?$/;
  var HAS_BIGINT = typeof BigInt === "function";

  function clean(s) {
    s = String(s).trim().replace(/\s+/g, "").replace(/[−–]/g, "-");
    if (/^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, "");
    return s;
  }

  function ten(n) { var p = BigInt(1); for (var i = 0; i < n; i++) p = p * BigInt(10); return p; }

  /* "12.5" -> [125, 10] as BigInts */
  function decimal(t) {
    var i = t.indexOf(".");
    if (i < 0) return [BigInt(t), BigInt(1)];
    var frac = t.slice(i + 1);
    return [BigInt((t.slice(0, i) || "0") + frac || "0"), ten(frac.length)];
  }

  /* The exact value of a typed number as [numerator, denominator] (BigInt), or a float without BigInt; null if not a number. */
  function value(s) {
    var m = clean(s).match(NUMBER);
    if (!m) return null;
    if (!HAS_BIGINT) {
      var f = parseFloat(m[2]) / (m[3] !== undefined ? parseFloat(m[3]) : 1);
      return isFinite(f) ? (m[1] ? -f : f) : null;
    }
    var a = decimal(m[2]), n = a[0], d = a[1];
    if (m[3] !== undefined) {
      var b = decimal(m[3]);
      if (b[0] === BigInt(0)) return null;
      n = n * b[1]; d = d * b[0];
    }
    return [m[1] ? -n : n, d];
  }

  function same(x, y) {
    if (!HAS_BIGINT) return Math.abs(x - y) <= 1e-9 * Math.max(1, Math.abs(y));
    return x[0] * y[1] === y[0] * x[1];
  }

  /* true, false, or null for an empty answer */
  function check(accepted, typed) {
    var g = String(typed).trim();
    if (!g) return null;
    var cg = clean(g).toUpperCase(), i;
    for (i = 0; i < accepted.length; i++) if (cg === clean(accepted[i]).toUpperCase()) return true;
    var x = value(g);
    if (x === null) return false;
    for (i = 0; i < accepted.length; i++) {
      var y = value(accepted[i]);
      if (y !== null && same(x, y)) return true;
    }
    return false;
  }

  var api = { check: check, value: value };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SATGrade = api;
})(this);
