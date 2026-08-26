# Background guide tooling

Generates OakBMUN background guides in the house design, then they get
committed to `guides/` and linked from the committee modal.

- `template.pdf` — last year's DISEC guide with all text redacted away, so
  page 1 is a blank cover and page 2 a blank content page. Copying these keeps
  the navy texture, header banner and teal footer byte-identical to the
  original rather than re-drawing them.
- `fonts/` — Montserrat Regular and Bold, instanced from the Google Fonts
  variable font (the guide's embedded copies are per-page subsets, unusable
  for new text).
- `build_guide.py` — `python build_guide.py content.json out.pdf`

## content.json

```json
{
  "committee": "DISEC",
  "agenda": "Agenda: ...",
  "sections": [
    { "heading": "Letter from the Executive Board", "body": ["para", "para"] },
    { "heading": "History", "body": ["..."], "bullets": ["..."] }
  ]
}
```

Each section starts a new page; set `"page_break": false` to continue on the
current one. Body text wraps and flows onto new pages automatically.

## Linking it on the site

Put the PDF at `guides/<img>.pdf` (matching the committee's `img` value) and
set that committee's `guide` field in the Committees page source to
`'./guides/<img>.pdf'`. The modal then shows a "Background guide (PDF)" link
under the agenda instead of the "coming soon" line.
