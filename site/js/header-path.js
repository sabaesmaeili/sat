/* GENERATED FILE. Never edit it by hand: it is the esaba.ca website's header script
   (src/lib/headerPath.ts, the rule; src/scripts/headerPath.ts, the measuring), bundled by
   tools/sync_header.py, whose --check fails when this copy has drifted. */
"use strict";
(() => {
  // src/lib/headerPath.ts
  var ELLIPSIS = "\u2026";
  var FLOOR = 3;
  var markText = (short) => short ? "@" : "@esaba";
  var middle = (name, length) => {
    if (length >= name.length) return name;
    const kept = length - 1;
    return name.slice(0, Math.ceil(kept / 2)) + ELLIPSIS + name.slice(-Math.floor(kept / 2));
  };
  var canLoseOne = (name, length) => name.length > FLOOR && length > FLOOR;
  var shortenOnce = (names, lengths) => {
    let pick = -1;
    names.forEach((name, i) => {
      if (canLoseOne(name, lengths[i]) && (pick < 0 || lengths[i] > lengths[pick])) pick = i;
    });
    if (pick < 0) return null;
    return lengths.map((length, i) => i === pick ? length - 1 : length);
  };

  // src/scripts/headerPath.ts
  var mark = document.querySelector(".site-mark");
  var path = document.querySelector(".address-path");
  var header = document.querySelector(".site-header");
  var nav = header?.querySelector(".site-nav") ?? null;
  if (mark && path) {
    const folders = Array.from(path.querySelectorAll("[data-folder]"));
    const names = folders.map((folder) => folder.dataset.folder ?? "");
    const show = (shortMark, lengths) => {
      mark.textContent = markText(shortMark);
      folders.forEach((folder, i) => {
        const text = middle(names[i], lengths[i]);
        folder.textContent = text;
        if (text === names[i]) {
          folder.removeAttribute("aria-label");
          folder.removeAttribute("title");
        } else {
          folder.setAttribute("aria-label", names[i]);
          folder.setAttribute("title", names[i]);
        }
      });
    };
    const fits = () => path.scrollWidth <= path.clientWidth;
    const fit = () => {
      let lengths = names.map((name) => name.length);
      show(false, lengths);
      if (header && nav) {
        header.dataset.layout = "row";
        if (!fits() || header.scrollWidth > header.clientWidth) header.dataset.layout = "stacked";
      }
      if (fits()) return;
      while (lengths) {
        show(true, lengths);
        if (fits()) return;
        lengths = shortenOnce(names, lengths);
      }
    };
    fit();
    addEventListener("resize", fit);
    document.fonts?.ready.then(fit);
  }
})();
