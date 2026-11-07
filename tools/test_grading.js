#!/usr/bin/env node
/* Test the drills' grading of typed answers (site/js/grade.js) on every student-produced-response item in
   bank/original/math.json: each accepted value and its equivalent forms must pass; near misses must fail.

     node tools/test_grading.js        exit 1 on any failure (tools/check.py runs it when node is installed)
*/
"use strict";
const fs = require("fs");
const path = require("path");
const { check, value } = require(path.join(__dirname, "..", "site", "js", "grade.js"));

const bank = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "bank", "original", "math.json"), "utf8"));
const failures = [];
let cases = 0;
function expect(item, typed, want) {
  cases++;
  const got = check(item.accepted, typed);
  if (got !== want) failures.push(`${item.id} accepted ${JSON.stringify(item.accepted)}: ${JSON.stringify(typed)} gave ${got}, want ${want}`);
}
const isAccepted = (item, typed) => item.accepted.some((a) => { const x = value(a), y = value(typed); return x && y && x[0] * y[1] === y[0] * x[1]; });

// equivalent forms of one accepted value
function equivalents(a) {
  const out = [a, ` ${a} `];
  const neg = a.startsWith("-");
  const body = neg ? a.slice(1) : a;
  if (neg) out.push("−" + body);
  if (body.startsWith(".")) out.push((neg ? "-" : "") + "0" + body);
  if (/^\d*\.\d+$/.test(body)) out.push(a + "0");
  if (/^\d+$/.test(body)) out.push(a + ".0");
  const f = body.match(/^(\d+)\/(\d+)$/);
  if (f) out.push(`${neg ? "-" : ""}${2 * f[1]}/${2 * f[2]}`, `${neg ? "-" : ""}${3 * f[1]}/${3 * f[2]}`);
  return out;
}

// near misses of one accepted value: one unit off in its last place, a digit dropped, ten times bigger
function nearMisses(a) {
  const out = [];
  const neg = a.startsWith("-");
  const body = neg ? a.slice(1) : a;
  const sign = neg ? "-" : "";
  const dec = body.match(/^(\d*)\.(\d+)$/);
  if (/^\d+$/.test(body)) {
    const n = BigInt(a);
    out.push(String(n + 1n), String(n - 1n), String(n * 10n));
  } else if (dec) {
    const places = dec[2].length;
    const units = BigInt((dec[1] || "0") + dec[2]) * (neg ? -1n : 1n);
    for (const u of [units + 1n, units - 1n]) {
      const s = (u < 0n ? -u : u).toString().padStart(places + 1, "0");
      out.push(`${u < 0n ? "-" : ""}${s.slice(0, -places)}.${s.slice(-places)}`);
    }
    if (places > 1) out.push(`${sign}${dec[1]}.${dec[2].slice(0, -1)}`);
  } else {
    const f = body.match(/^(\d+)\/(\d+)$/);
    if (f) out.push(`${sign}${Number(f[1]) + 1}/${f[2]}`, `${sign}${f[1]}/${Number(f[2]) + 1}`);
  }
  return out;
}

const spr = bank.items.filter((it) => it.format === "spr");
for (const item of spr) {
  for (const a of item.accepted) {
    for (const e of equivalents(a)) expect(item, e, true);
    for (const m of nearMisses(a)) if (!isAccepted(item, m)) expect(item, m, false);
  }
  expect(item, "", null);
  expect(item, "abc", false);
}
// the cases the review found
const byId = Object.fromEntries(spr.map((it) => [it.id, it]));
const named = [
  ["137cc6fd", ["0.0177", ".0177", "0.0178", "4/225", "8/450"], ["0.017", "0.0185", "0.01777", ".0176", ".0179"]],
  ["2cb17792", ["17.5", "35/2", "17.50", "70/4"], ["17.51", "17.49", "17"]],
  ["3a84f885", ["1677", "1,677", "1677.0"], ["1676", "1678", "1677.5"]],
];
for (const [id, right, wrong] of named) {
  const item = byId[id];
  if (!item) { failures.push(`${id} is not a typed-answer item in the bank`); continue; }
  right.forEach((t) => expect(item, t, true));
  wrong.forEach((t) => expect(item, t, false));
}

if (failures.length) {
  console.error(`test_grading: ${failures.length} of ${cases} cases failed:`);
  failures.forEach((f) => console.error("  - " + f));
  process.exit(1);
}
console.log(`test_grading: ${cases} cases on ${spr.length} typed-answer items pass.`);
