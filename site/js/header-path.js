/* GENERATED FILE. Never edit it by hand: it is the esaba.ca website's header script
   (src/lib/headerPath.ts, the rule; src/scripts/headerPath.ts, the measuring), bundled by
   tools/sync_header.py, whose --check fails when this copy has drifted. */
"use strict";
(() => {
  // src/lib/headerPath.ts
  var ELLIPSIS = "\u2026";
  var markText = (short) => short ? "@" : "@esaba";
  var maxFold = (names) => Math.max(0, names.length - 1);
  var foldLabel = (names, fold) => names.slice(0, fold).join("/");

  // src/scripts/headerPath.ts
  var mark = document.querySelector(".site-mark");
  var path = document.querySelector(".address-path");
  var header = document.querySelector(".site-header");
  var nav = header?.querySelector(".site-nav") ?? null;
  if (mark && path) {
    const home = path.firstElementChild;
    const folders = Array.from(path.querySelectorAll("[data-folder]"));
    const names = folders.map((folder) => folder.dataset.folder ?? "");
    let added = [];
    const show = (shortMark, fold) => {
      mark.textContent = markText(shortMark);
      folders.forEach((folder, i) => {
        const display = i < fold ? "none" : "";
        folder.style.display = display;
        if (folder.previousElementSibling instanceof HTMLElement) folder.previousElementSibling.style.display = display;
      });
      added.forEach((node) => node.remove());
      added = [];
      if (!fold || !home) return;
      const deepest = folders[fold - 1];
      const href = deepest.getAttribute("href");
      const crumb = document.createElement(href ? "a" : "span");
      crumb.className = "address-crumb";
      if (href) crumb.setAttribute("href", href);
      crumb.textContent = ELLIPSIS;
      crumb.setAttribute("aria-label", foldLabel(names, fold));
      crumb.title = foldLabel(names, fold);
      const separator = document.createElement("span");
      separator.className = "address-separator";
      separator.setAttribute("aria-hidden", "true");
      separator.textContent = "/";
      home.after(separator, crumb);
      added = [separator, crumb];
    };
    const fits = () => path.scrollWidth <= path.clientWidth;
    const fit = () => {
      show(false, 0);
      if (header && nav) {
        header.dataset.layout = "row";
        if (!fits() || header.scrollWidth > header.clientWidth) header.dataset.layout = "stacked";
      }
      if (fits()) return;
      for (let fold = 0; fold <= maxFold(names); fold++) {
        show(true, fold);
        if (fits()) return;
      }
    };
    fit();
    addEventListener("resize", fit);
    document.fonts?.ready.then(fit);
  }
})();
