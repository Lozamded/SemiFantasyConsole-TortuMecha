# TortoiseMecha Documentation (React)

React + Vite rewrite of the docs site. Replaces `documentation OLD/` — a set
of 24 static HTML files that each carried a hand-copied sidebar and had to
be rewritten in bulk (with a script) every time the docs got reorganized.
This version has exactly one place that knows the site's structure.

## Running it

```bash
npm install
npm run dev       # http://localhost:5173, hot-reloading
npm run build     # production build -> dist/
npm run preview   # serve the production build locally
npm run verify    # server-render every page in nav.js, check for dead
                   # links / missing screenshots / render errors
```

## Exporting as PDF

```bash
pip install -r requirements-pdf.txt
playwright install chromium
python export_pdf.py             # -> tortoisemecha-docs.pdf
```

Builds the site, serves the production build, and prints every page in
`nav.js` through headless Chromium into one PDF. The sidebar becomes a
generated table-of-contents page plus a real PDF outline (bookmarks) that
mirrors the sidebar's groups — both driven by `nav.js`, so the PDF's
structure never drifts from the site's.

## The one file that matters: `src/nav.js`

Sidebar groups, page order, and page titles all live in one array here.
Nothing else hand-codes any of that:

- **`Sidebar`** renders directly from `nav.js` and highlights the active
  page from the current route — no per-page "active" class to maintain.
- **`PageNav`** (the prev/next links at the bottom of every page) walks
  `flatPages`, the flattened version of the same list — no page hardcodes
  its neighbors, so reordering never leaves a stale "Next: ..." link behind.
- **`App.jsx`**'s routes are generated from `nav.js` too (via
  `import.meta.glob`), matching each route to its component file by naming
  convention (`/studio/pixel-editors` → `pages/studio/PixelEditors.jsx`).
  There's no separate route table to keep in sync.

**To reorder, rename, or add a section: edit `nav.js`.** That's it — the
sidebar, the prev/next chain, and the routing all follow automatically.

## Adding a page

1. Add one entry to the right group in `src/nav.js`:
   `{ path: '/studio/new-thing', label: '8. New Thing' }`
2. Create the matching file: `src/pages/studio/NewThing.jsx` (kebab-case
   route segment → PascalCase filename is the only convention that matters).
3. `npm run verify` — it'll fail loudly if the path/filename don't match.

## Structure

```
src/
  nav.js                 # the single source of truth (see above)
  App.jsx                 # routes, generated from nav.js
  components/
    Layout.jsx             # sidebar + <Outlet/>, scroll-to-top on navigate
    Sidebar.jsx             # renders nav.js, highlights active route
    PageNav.jsx              # auto prev/next, computed from nav.js
  pages/
    Home.jsx, get-started/, studio/, walkthrough/, formats/, scripting/
  index.css               # global styles (ported ~as-is from the old site)
public/
  assets/screenshots/*.png  # real TortoiseStudio screenshots, referenced
                             # by absolute path (/assets/screenshots/...)
```

Every page component is plain content — an `<h1>`, some `<p>`/`<table>`/
`<div className="callout">`/etc., and a trailing `<PageNav />`. No page
needs to know what comes before or after it.
