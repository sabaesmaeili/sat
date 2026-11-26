#!/usr/bin/env node
/* Guard the students' saved progress. The drills keep it in the browser's localStorage under frozen keys, in the
   original pages' record format (commit 120473f): { "<question id>": {tries, ok, first, last, solved, revealed,
   wrong}, … }. A change to the pages must never lose or reset it. This test builds the site into a temporary folder,
   then runs the real site/js/drill.js on each built drill page (its DATA and CONF) in a sandbox with stand-in page
   elements and a recording localStorage, and checks:

     a. the storage keys are exactly sat-drill80-writing and sat-drill80-math, and the label switch's is the key + "-labels";
     b. progress saved in the original format, every field set, comes back unchanged after the page loads it and saves;
     c. a record for an id that is not in the bank survives load and save;
     d. opening the page writes nothing to storage; only a student's action saves.

     node tools/test_progress.js        exit 1 on any failure (tools/check.py runs it when node is installed)
*/
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const vm = require("vm");
const { spawnSync } = require("child_process");
const assert = require("assert");

const ROOT = path.join(__dirname, "..");
const FROZEN = { writing: "sat-drill80-writing", math: "sat-drill80-math" };  // never change: students' progress lives here
const failures = [];
function check(ok, msg) { if (!ok) failures.push(msg); }
const plain = (x) => (x === undefined ? x : JSON.parse(JSON.stringify(x)));  // values from the sandbox are another realm's objects
function same(a, b) { try { assert.deepStrictEqual(plain(a), plain(b)); return true; } catch (e) { return false; } }

// Build the site from the current sources (python from $PYTHON, as tools/check.py passes it).
const out = fs.mkdtempSync(path.join(os.tmpdir(), "sat-progress-"));
const built = spawnSync(process.env.PYTHON || "python3", [path.join(ROOT, "tools", "build.py"), "--out", path.join(out, "_site")], { encoding: "utf8" });
if (built.status !== 0) { console.error("test_progress: build failed\n" + built.stderr); process.exit(1); }

/* Stand-in page elements: every element (by id, or a query inside one) is a proxy named by its path. Properties set
   on it read back; anything else is a callable no-op; addEventListener records the handler under the element's name,
   so the test can play a student's click. */
function fakePage() {
  const listeners = {};
  const cache = {};
  function element(name) {
    if (cache[name]) return cache[name];
    const props = {};
    const self = new Proxy(() => {}, {
      get(_, key) {
        if (key in props) return props[key];
        if (key === Symbol.toPrimitive) return (hint) => (hint === "number" ? 0 : "");
        if (key === Symbol.iterator) return function* () {};
        if (key === "then") return undefined;
        if (key === "length") return 0;
        if (key === "addEventListener") return (type, fn) => { (listeners[name + " " + type] = listeners[name + " " + type] || []).push(fn); };
        if (key === "getElementById") return (id) => element("#" + id);
        if (key === "querySelector" || key === "querySelectorAll") return (sel) => element(name + " " + sel);
        return element(name + "." + String(key));
      },
      set(_, key, value) { props[key] = value; return true; },
      apply() { return element(name + "()"); },
    });
    return (cache[name] = self);
  }
  return { document: element("document"), listeners, fire(name, type) { (listeners[name + " " + type] || []).forEach((fn) => fn({ preventDefault() {} })); } };
}

function fakeStorage(initial) {
  const data = Object.assign({}, initial), reads = [], writes = [];
  return {
    data, reads, writes,
    api: {
      getItem(k) { reads.push(k); return Object.prototype.hasOwnProperty.call(data, k) ? data[k] : null; },
      setItem(k, v) { writes.push(k); data[k] = String(v); },
      removeItem(k) { writes.push(k); delete data[k]; },
    },
  };
}

const gradeSrc = fs.readFileSync(path.join(ROOT, "site", "js", "grade.js"), "utf8");
const drillSrc = fs.readFileSync(path.join(ROOT, "site", "js", "drill.js"), "utf8");

// Open one built drill page with the given storage: run its DATA/CONF script, js/grade.js and js/drill.js.
function openPage(section, storage) {
  const html = fs.readFileSync(path.join(out, "_site", section, "drill", "index.html"), "utf8");
  const m = html.match(/<script>\s*(var DATA = [\s\S]*?var CONF = [\s\S]*?;)\s*<\/script>/);
  if (!m) throw new Error(`${section}: no DATA/CONF script in the built page`);
  const page = fakePage();
  const sandbox = { document: page.document, localStorage: storage.api, setTimeout, clearTimeout, Promise, console };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(m[1] + "\nthis.DATA = DATA; this.CONF = CONF;", sandbox);
  vm.runInContext(gradeSrc, sandbox);
  vm.runInContext(drillSrc, sandbox);
  return { page, DATA: sandbox.DATA, CONF: sandbox.CONF };
}

for (const section of ["writing", "math"]) {
  const key = FROZEN[section];
  const ids = JSON.parse(fs.readFileSync(path.join(ROOT, "bank", "original", section + ".json"), "utf8")).items.map((it) => it.id);
  const typed = JSON.parse(fs.readFileSync(path.join(ROOT, "bank", "original", section + ".json"), "utf8")).items.find((it) => it.format === "spr");

  // Progress as the original pages saved it: every field, wrong as a list, solved and revealed together.
  const saved = {
    [ids[0]]: { tries: 3, ok: false, first: "A", last: "C", solved: true, wrong: ["A", "B"] },
    [ids[1]]: { tries: 2, ok: false, first: "D", last: "B", solved: true, revealed: true, wrong: ["D"] },
    [ids[2]]: { tries: 1, ok: true, first: "B", last: "B", solved: true },
    [ids[3]]: { tries: 0, ok: false, first: "(shown)", revealed: true },
    [ids[4]]: { tries: 1, ok: false, first: "C", last: "C", wrong: ["C"] },
    "0ld1d000": { tries: 2, ok: true, first: "A", last: "A", solved: true, revealed: true, wrong: [] },  // an id no longer in the bank
  };
  if (typed) saved[typed.id] = { tries: 2, ok: false, first: "5", last: "24", solved: true, wrong: ["5"] };
  const labels = { [key + "-labels"]: "1" };

  // a. keys
  const store = fakeStorage(Object.assign({ [key]: JSON.stringify(saved) }, labels));
  const { page, DATA, CONF } = openPage(section, store);
  check(CONF.key === key, `${section}: storage key is ${JSON.stringify(CONF.key)}, must stay ${JSON.stringify(key)}`);
  check(store.reads.includes(key), `${section}: the page doesn't read its progress from ${key}`);
  check(store.reads.includes(key + "-labels"), `${section}: the label switch isn't read from ${key}-labels`);
  check(same(DATA.map((q) => q.id).sort(), ids.slice().sort()), `${section}: the page's question ids differ from the bank's`);

  // d. opening the page writes nothing
  check(store.writes.length === 0, `${section}: opening the page wrote to storage (${store.writes.join(", ")}) before any action`);
  check(store.data[key] === JSON.stringify(saved), `${section}: opening the page changed the saved progress`);

  // b, c. a student's action saves; every saved record comes back unchanged
  const fresh = ids.find((id) => !(id in saved));
  page.fire(`#q-${fresh} .revbtn`, "click");  // Show answer on an untouched question
  check(store.writes.includes(key), `${section}: Show answer didn't save progress`);
  let after = {};
  try { after = JSON.parse(store.data[key]); } catch (e) { failures.push(`${section}: saved progress isn't JSON`); }
  for (const id of Object.keys(saved)) {
    check(same(after[id], saved[id]), `${section}: record ${id} changed on load and save: ${JSON.stringify(saved[id])} -> ${JSON.stringify(after[id])}`);
  }
  check(after[fresh] && after[fresh].revealed === true, `${section}: the student's action wasn't saved`);
  check(Object.keys(after).length === Object.keys(saved).length + 1, `${section}: saving added or dropped records`);
  check(store.data[key + "-labels"] === "1", `${section}: the label switch setting changed`);

  // a damaged record is dropped on its own; the others stay
  const damaged = Object.assign({}, saved, { [ids[5]]: "not a record" });
  const store2 = fakeStorage({ [key]: JSON.stringify(damaged) });
  const p2 = openPage(section, store2).page;
  check(store2.writes.length === 0, `${section}: opening the page with a damaged record wrote to storage`);
  p2.fire(`#q-${fresh} .revbtn`, "click");
  const after2 = JSON.parse(store2.data[key] || "{}");
  for (const id of Object.keys(saved)) check(same(after2[id], saved[id]), `${section}: a damaged record cost record ${id}`);
}

fs.rmSync(out, { recursive: true, force: true });
if (failures.length) {
  console.error(failures.map((f) => "test_progress: " + f).join("\n"));
  process.exit(1);
}
console.log("test_progress: keys frozen; saved progress (original format, unknown ids) survives opening the page and saving, on both drills.");
