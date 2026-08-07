# OakBMUN V — website

Static site for the fifth edition of the Oakridge Bachupally Model United Nations
(27, 28 & 29 August 2026 · Oakridge International School, Bachupally, Hyderabad).

## Contents

- `index.html` — the entire site in one self-contained file (all pages, images and fonts inlined).
  Routes are hash-based: `#/committees`, `#/itinerary`, `#/secretariat`, `#/transport`,
  `#/faqs`, `#/contact`.
- `.nojekyll` — tells GitHub Pages to serve the files as-is.

## Publishing on GitHub Pages

1. Push this folder's contents to the repository root (or keep them in `/site`).
2. Repository → Settings → Pages → Source: *Deploy from a branch*.
3. Branch: `main`, folder: `/` (or `/site` if you kept the folder).

No build step, no dependencies — `index.html` opens correctly from a file system too.

## Editing

Do not edit `index.html` by hand; it is compiled. Edit the design source
(`OakBMUN V Site.dc.html` and the per-page `.dc.html` files) and re-export.

Registration link: https://oakbmun-registration-platform-2.onrender.com
