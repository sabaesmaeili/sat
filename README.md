# SAT Prep pages

Plain static HTML. No build step; upload the whole folder.

- `index.html` – landing page
- `writing-playbook.html`, `math-playbook.html` – cheat sheets
- `writing-drill.html`, `math-drill.html` – 80-question drills (progress is saved in the visitor's browser via localStorage)
- `img/writing/`, `img/math/` – question and explanation images (`<id>-q.png`, `<id>-a.png`)

External files loaded from CDNs: Google Fonts (all pages) and MathJax 3.2.2 from cdnjs (math pages).
To put this under a sub-path (e.g. `/sat/`), copy the folder as is; all links are relative.

Questions and official explanations come from the College Board SAT Suite Question Bank. Check the College Board's terms before publishing the drills on a public site.
