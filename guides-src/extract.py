#!/usr/bin/env python3
"""Turn a supplied background guide (PDF or DOCX) into content.json.

Headings are detected by font size (anything meaningfully larger than the
document's body size) or by a short, fully bold line. Inline bold inside a
paragraph is preserved as [text, bold] runs so lead-ins survive.

Usage:  python extract.py in.pdf|in.docx out.json --committee UNSC --agenda "..." [--emblem emblems/unsc.png] [--skip 1,2]
"""
import argparse, collections, json, os, re, sys

# Word and Google Docs export bullets as private-use glyphs from symbol fonts
# (\uf0b7 and friends); those have no Montserrat glyph and would render as tofu.
BULLET_CHARS = "•●▪‣◦○➢➤·∙"
PUA_BULLETS = "\uf0a7\uf0b7\uf0d8\uf06c\uf0fc\uf0a8\uf076"
BULLET = re.compile(r"^\s*(?:[" + BULLET_CHARS + PUA_BULLETS + r"\-\u2013]|\d+[.)])\s*")


def strip_marker(runs, n):
    """Drop the first n characters of a paragraph, spanning runs if needed."""
    out, left = [], n
    for text, bold in runs:
        if left <= 0:
            out.append([text, bold])
        elif len(text) <= left:
            left -= len(text)
        else:
            out.append([text[left:], bold])
            left = 0
    return out or [["", False]]


def merge(runs):
    out = []
    for text, bold in runs:
        if out and out[-1][1] == bold:
            out[-1][0] += text
        else:
            out.append([text, bold])
    return [[t, b] for t, b in out if t.strip() or len(out) == 1]


def from_pdf(path, skip):
    import pymupdf
    doc = pymupdf.open(path)
    sizes = collections.Counter()
    for pg in doc:
        for b in pg.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["text"].strip():
                        sizes[round(s["size"], 1)] += len(s["text"])
    body_size = sizes.most_common(1)[0][0]

    # collect every line with its geometry first; many guides put each line in
    # its own block, so paragraphs have to be reassembled from the text edges
    lines = []
    for pno, pg in enumerate(doc, start=1):
        if pno in skip:
            continue
        for b in pg.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = [s for s in l["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                maxsize = max(round(s["size"], 1) for s in spans)
                runs = [[s["text"], "Bold" in s["font"]] for s in spans]
                major = maxsize >= body_size + 1.4
                kind = (True, 1) if major else (False, 1)
                lines.append({"text": text, "runs": runs, "kind": kind,
                              "x0": l["bbox"][0], "x1": l["bbox"][2], "page": pno})
    if not lines:
        return []
    right_edge = max(l["x1"] for l in lines if not l["kind"][0]) if any(not l["kind"][0] for l in lines) \
        else max(l["x1"] for l in lines)
    full_line = right_edge - 0.06 * (right_edge - min(l["x0"] for l in lines))

    paras, cur, cur_kind, cur_page = [], [], None, [lines[0]["page"]]

    def flush():
        if not cur:
            return
        runs = merge(cur)
        text = "".join(r[0] for r in runs).strip()
        if text:
            major = cur_kind[0]
            all_bold = all(b for s, b in runs if s.strip())
            # a whole short paragraph in bold is a subheading; bold inside a
            # longer paragraph is just emphasis
            sub = (not major and all_bold and len(text) < 70
                   and text.rstrip().endswith((":", ".", "-", "?", "!")))
            paras.append({"text": text, "runs": runs,
                          "heading": major or sub, "level": 1 if major else 2,
                          "page": cur_page[0]})
        cur.clear()

    span = right_edge - min(l["x0"] for l in lines)
    for i, l in enumerate(lines):
        if cur and (l["kind"] != cur_kind or cur_kind[0]):
            flush()
        if not cur:
            cur_page[0] = l["page"]
        cur_kind = l["kind"]
        cur.extend(l["runs"])
        cur.append([" ", l["runs"][-1][1]])
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        short = right_edge - l["x1"]
        # ragged-right text: a break needs terminal punctuation and a gap, or a
        # very short line. Ending mid-sentence means the paragraph continues.
        ends_para = (
            l["kind"][0]
            or nxt is None
            or nxt["kind"] != l["kind"]
            or bool(BULLET.match(nxt["text"]))
            or (l["text"].rstrip().endswith((".", "!", "?", ":", ";", '"', "”")) and short > 0.10 * span)
            or short > 0.34 * span
        )
        if ends_para:
            flush()
    flush()
    return paras


def from_docx(path, skip):
    import docx
    d = docx.Document(path)
    sizes = collections.Counter()
    for p in d.paragraphs:
        for r in p.runs:
            if r.text.strip() and r.font.size:
                sizes[r.font.size.pt] += len(r.text)
    body_size = sizes.most_common(1)[0][0] if sizes else 11.0
    paras = []
    for p in d.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        runs = merge([[r.text, bool(r.bold)] for r in p.runs if r.text]) or [[text, False]]
        joined = "".join(r[0] for r in runs)
        if len(joined.split()) < len(text.split()):
            # hyperlink runs live outside paragraph.runs; keep the full text
            runs = [[text, all(b for _, b in runs)]]
        maxsize = max([r.font.size.pt for r in p.runs if r.font.size] or [body_size])
        all_bold = all(b for _, b in runs if _.strip())
        major = maxsize >= body_size + 1.5 and all_bold
        heading = major or (maxsize >= body_size + 1.0 and all_bold)
        paras.append({"text": text, "runs": runs, "heading": heading,
                      "level": 1 if major else 2})
    return paras


def build_pages(paras, committee, agenda, emblem):
    """One entry per source page, so the output can be a 1:1 replica."""
    pages, cur_no, cur = [], None, None
    for p in paras:
        if p.get("page") != cur_no:
            cur_no = p.get("page")
            cur = {"page": cur_no, "blocks": []}
            pages.append(cur)
        if p["heading"]:
            cur["blocks"].append({"t": "h", "text": p["text"],
                                  "level": p.get("level", 1), "runs": p["runs"]})
            continue
        runs = p["runs"]
        m = BULLET.match(p["text"])
        if m:
            marker = m.group(0).strip()
            runs = strip_marker(runs, len(m.group(0)))
            blk = {"t": "b", "runs": runs}
            if marker and marker[0].isdigit():
                blk["marker"] = marker
            cur["blocks"].append(blk)
        else:
            cur["blocks"].append({"t": "p", "runs": runs})
    pages = [pg for pg in pages if any(
        any(r[0].strip() for r in b["runs"]) for b in pg["blocks"])]
    out = {"committee": committee, "agenda": agenda, "pages": pages}
    if emblem:
        out["emblem"] = emblem
    return out


def build(paras, committee, agenda, emblem):
    sections, cur = [], None
    for p in paras:
        if p["heading"]:
            cur = {"heading": p["text"], "level": p.get("level", 1),
                   "page_break": p.get("level", 1) == 1, "blocks": []}
            sections.append(cur)
            continue
        if cur is None:
            cur = {"heading": "", "level": 1, "page_break": False, "blocks": []}
            sections.append(cur)
        runs = p["runs"]
        m = BULLET.match(p["text"])
        if m:
            marker = m.group(0).strip()
            runs = [[BULLET.sub("", runs[0][0], count=1), runs[0][1]]] + runs[1:]
            blk = {"t": "b", "runs": runs}
            if marker[0].isdigit():
                blk["marker"] = marker      # numbered lists keep their numbers
            cur["blocks"].append(blk)
        else:
            cur["blocks"].append({"t": "p", "runs": runs})
    out = {"committee": committee, "agenda": agenda, "sections": sections}
    if emblem:
        out["emblem"] = emblem
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--committee", required=True)
    ap.add_argument("--agenda", required=True)
    ap.add_argument("--emblem")
    ap.add_argument("--skip", default="", help="1-based source pages to drop, e.g. cover/TOC")
    ap.add_argument("--start", default="", help="drop everything before the paragraph starting with this")
    ap.add_argument("--flow", action="store_true",
                    help="flow continuously instead of mirroring the source pagination")
    a = ap.parse_args()
    skip = {int(x) for x in a.skip.split(",") if x.strip()}
    paras = (from_docx if a.src.lower().endswith(".docx") else from_pdf)(a.src, skip)
    if a.start:
        for i, p in enumerate(paras):
            if p["text"].lower().startswith(a.start.lower()):
                paras = paras[i:]
                break
    paged = any("page" in p for p in paras) and not a.flow
    content = (build_pages if paged else build)(paras, a.committee, a.agenda, a.emblem)
    json.dump(content, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if "pages" in content:
        blocks = [b for pg in content["pages"] for b in pg["blocks"]]
        print(f"{a.out}: {len(content['pages'])} source pages, "
              f"{sum(1 for b in blocks if b['t'] == 'h')} headings, "
              f"{sum(1 for b in blocks if b['t'] == 'p')} paragraphs, "
              f"{sum(1 for b in blocks if b['t'] == 'b')} bullets")
    else:
        blocks = [b for s in content["sections"] for b in s["blocks"]]
        print(f"{a.out}: {len(content['sections'])} sections, "
              f"{sum(1 for b in blocks if b['t'] == 'p')} paragraphs, "
              f"{sum(1 for b in blocks if b['t'] == 'b')} bullets")
