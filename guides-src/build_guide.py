#!/usr/bin/env python3
"""Build an OakBMUN background guide PDF in the house design.

Usage:  python build_guide.py content.json out.pdf

The design (navy texture, header banner, teal footer, cover furniture) is
lifted straight from template.pdf, which is last year's guide with its text
redacted away -- so the look matches exactly rather than being re-drawn.

If content.json carries "pages", each source page is reproduced as exactly one
output page (a 1:1 replica of the supplied guide), shrinking the type a little
where a source page holds more than the house frame fits. Otherwise the text
flows continuously; either way no blank pages are emitted.
"""
import json, os, sys
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "template.pdf")
FONT_DIR = os.path.join(HERE, "fonts")
REG_TTF = os.path.join(FONT_DIR, "Montserrat-Regular.ttf")
BOLD_TTF = os.path.join(FONT_DIR, "Montserrat-Bold.ttf")

WHITE = (1, 1, 1)
TEAL = (0.702, 0.925, 0.961)           # #b3ecf5, the cover committee name
BODY_SIZE, BODY_LEAD = 12.0, 18.6
HEAD_SIZE, HEAD_LEAD = 18.3, 26.0
SUB_SIZE, SUB_LEAD = 13.5, 20.0
# The reference guide sets its frame at 89-506 x 74-757. The supplied guides
# run wider margins, so their dense pages would force the type very small at
# that width; widening a little keeps a readable size at 1:1 pagination.
LEFT, RIGHT = 78.0, 517.0
TOP, BOTTOM = 74.0, 768.0
PARA_GAP, HEAD_GAP_BEFORE, HEAD_GAP_AFTER = 8.0, 12.0, 7.0
BULLET_GAP, BULLET_INDENT = 2.5, 12.0
COVER_NAME_SIZE, COVER_NAME_BASELINE = 69.2, 590.5
COVER_AGENDA_SIZE, COVER_AGENDA_BASELINE, COVER_AGENDA_LEAD = 18.3, 633.1, 25.3
EMBLEM_BOX = (147.0, 238.0, 456.0, 530.0)
FIGURE_MIN_SHARE = 0.45    # a figure never shrinks below this much of its size
# Tried in order when a source page holds more than the house frame fits:
# (type scale, line-height ratio). Line spacing gives before glyph size does,
# because tighter leading reads far better than shrunken type.
FIT_STEPS = [(1.00, 1.55), (1.00, 1.46), (1.00, 1.38), (1.00, 1.30),
             (0.96, 1.30), (0.92, 1.28), (0.88, 1.28), (0.84, 1.26),
             (0.80, 1.26), (0.76, 1.24), (0.72, 1.24), (0.68, 1.22), (0.64, 1.20)]


class GuideWriter:
    def __init__(self):
        self.tpl = pymupdf.open(TEMPLATE)
        self.doc = pymupdf.open()
        self.page = None
        self.y = TOP
        self.dry = False
        self.metrics = {"mont": pymupdf.Font(fontfile=REG_TTF),
                        "montb": pymupdf.Font(fontfile=BOLD_TTF)}

    # ---------- page furniture ----------

    def new_page(self, cover=False):
        if self.dry:
            self.y = TOP
            return None
        self.doc.insert_pdf(self.tpl, from_page=0 if cover else 1, to_page=0 if cover else 1)
        self.page = self.doc[-1]
        self.page.insert_font(fontname="mont", fontfile=REG_TTF)
        self.page.insert_font(fontname="montb", fontfile=BOLD_TTF)
        self.y = TOP
        return self.page

    def measure(self, text, font, size):
        return self.metrics[font].text_length(text, size)

    def sanitize(self, text):
        """Replace characters Montserrat has no glyph for, so nothing renders
        as a tofu box (symbol-font bullets, odd dashes and spaces)."""
        subs = {"\u2013": "-", "\u2014": "\u2014", "\u00a0": " ", "\u2009": " ",
                "\u200b": "", "\ufeff": "", "\u2028": " "}
        font = self.metrics["mont"]
        out = []
        for ch in text:
            ch = subs.get(ch, ch)
            if not ch:
                continue
            if ch in " \n\t" or font.has_glyph(ord(ch)):
                out.append(ch)
            elif 0xF000 <= ord(ch) <= 0xF0FF:
                out.append("\u2022")      # symbol-font bullet
            else:
                out.append("")
        return "".join(out)

    # ---------- text ----------

    def _split_long(self, word, font, size, width):
        """Break a word too long for the line (URLs) into chunks that fit."""
        if self.measure(word, font, size) <= width:
            return [word]
        out, cur, last_break = [], "", -1
        for ch in word:
            if cur and self.measure(cur + ch, font, size) > width:
                if last_break > 0 and last_break >= len(cur) - 18:
                    out.append(cur[:last_break + 1])
                    cur = cur[last_break + 1:] + ch
                else:
                    out.append(cur)
                    cur = ch
                last_break = -1
            else:
                cur += ch
            if ch in "/-._?&=":
                last_break = len(cur) - 1
        if cur:
            out.append(cur)
        return out

    def _wrap_runs(self, runs, size, width):
        """Wrap [text, bold] runs into lines of [word, bold] pairs."""
        words = []
        for text, bold in runs:
            font = "montb" if bold else "mont"
            for w in self.sanitize(text).split():
                for piece in self._split_long(w, font, size, width):
                    words.append((piece, bold))
        lines, cur, cur_w = [], [], 0.0
        space = self.measure(" ", "mont", size)
        for w, bold in words:
            ww = self.measure(w, "montb" if bold else "mont", size)
            add = ww if not cur else ww + space
            if cur and cur_w + add > width:
                lines.append(cur)
                cur, cur_w = [(w, bold)], ww
            else:
                cur.append((w, bold))
                cur_w += add
        if cur:
            lines.append(cur)
        return lines

    def write_runs(self, runs, size=BODY_SIZE, lead=BODY_LEAD, color=WHITE,
                   indent=0.0, center=False, allow_break=True):
        width = RIGHT - LEFT - indent
        space = self.measure(" ", "mont", size)
        for line in self._wrap_runs(runs, size, width):
            if self.y + lead > BOTTOM and allow_break:
                self.new_page()
            if not self.dry:
                if center:
                    lw = sum(self.measure(w, "montb" if b else "mont", size) for w, b in line) \
                         + space * (len(line) - 1)
                    x = (LEFT + RIGHT - lw) / 2
                else:
                    x = LEFT + indent
                for i, (word, bold) in enumerate(line):
                    if i:
                        x += space
                    self.page.insert_text((x, self.y + size), word,
                                          fontname="montb" if bold else "mont",
                                          fontfile=BOLD_TTF if bold else REG_TTF,
                                          fontsize=size, color=color)
                    x += self.measure(word, "montb" if bold else "mont", size)
            self.y += lead

    def gap(self, amount):
        self.y += amount

    # ---------- blocks ----------

    def render_blocks(self, blocks, fit=(1.0, 1.55), allow_break=True, fig_scale=1.0):
        scale, ratio = fit
        # gaps ride the leading too, so tightening line spacing also tightens
        # the space between paragraphs and list items
        g = scale * (ratio / 1.55)
        body_lead = BODY_SIZE * scale * ratio
        head_lead = HEAD_SIZE * scale * (ratio * 0.92)
        sub_lead = SUB_SIZE * scale * (ratio * 0.96)
        for blk in blocks:
            runs = blk["runs"]
            if isinstance(runs, str):
                runs = [[runs, False]]
            runs = [(r[0], bool(r[1])) for r in runs]
            kind = blk.get("t", "p")
            if kind == "i":
                self.place_image(blk, scale * fig_scale, allow_break)
                continue
            if kind == "h":
                level = blk.get("level", 1)
                if level == 1:
                    self.gap(HEAD_GAP_BEFORE * g)
                    self.write_runs([(blk["text"], True)], HEAD_SIZE * scale,
                                    head_lead, center=True, allow_break=allow_break)
                    self.gap(HEAD_GAP_AFTER * g)
                else:
                    self.gap(8 * g)
                    self.write_runs([(blk["text"], True)], SUB_SIZE * scale,
                                    sub_lead, allow_break=allow_break)
                    self.gap(4 * g)
            elif kind == "b":
                marker = blk.get("marker", "•")
                self.write_runs([(marker + " ", False)] + runs, BODY_SIZE * scale,
                                body_lead, indent=BULLET_INDENT,
                                allow_break=allow_break)
                self.gap(BULLET_GAP * g)
            else:
                self.write_runs(runs, BODY_SIZE * scale, body_lead,
                                allow_break=allow_break)
                self.gap(PARA_GAP * g)

    def place_image(self, blk, scale, allow_break=True):
        """Draw one of the source's figures, scaled to the frame."""
        src = blk["src"]
        if not os.path.isabs(src):
            src = os.path.join(HERE, src)
        w, h = blk.get("w") or 0, blk.get("h") or 0
        if not (w and h) and os.path.exists(src):
            pix = pymupdf.Pixmap(src)
            w, h = pix.width, pix.height
        w, h = w * scale, h * scale
        avail = RIGHT - LEFT
        if w > avail:
            h *= avail / w
            w = avail
        room = BOTTOM - self.y
        if h > room and room > 0:
            # a figure that would run past the frame is scaled to what is left
            w *= room / h
            h = room
        self.gap(6 * scale)
        if not self.dry and os.path.exists(src):
            x = LEFT + (avail - w) / 2
            self.page.insert_image(pymupdf.Rect(x, self.y, x + w, self.y + h),
                                   filename=src, keep_proportion=True, overlay=True)
        self.y += h
        self.gap(8 * scale)

    def height_of(self, blocks, fit, fig_scale=1.0):
        """Dry-run the blocks to see how tall they are at this setting."""
        self.dry, saved_y = True, self.y
        self.y = TOP
        self.render_blocks(blocks, fit, allow_break=False, fig_scale=fig_scale)
        h = self.y - TOP
        self.dry, self.y = False, saved_y
        return h

    def figure_fit(self, blocks, fit, usable):
        """How much of their natural size the figures on this page can keep:
        whatever the text leaves, never more than full size."""
        if not any(b.get("t") == "i" for b in blocks):
            return 1.0
        text_only = [b for b in blocks if b.get("t") != "i"]
        text_h = self.height_of(text_only, fit)
        full_h = self.height_of(blocks, fit) - text_h
        if full_h <= 0:
            return 1.0
        room = usable - text_h
        return max(FIGURE_MIN_SHARE, min(1.0, room / full_h))

    # ---------- cover ----------

    def cover(self, committee, agenda, emblem=None):
        pg = self.new_page(cover=True)
        if emblem:
            box = pymupdf.Rect(*EMBLEM_BOX)
            pix = pymupdf.Pixmap(emblem)
            scale = min(box.width / pix.width, box.height / pix.height)
            w, h = pix.width * scale, pix.height * scale
            cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
            pg.insert_image(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                            filename=emblem, keep_proportion=True, overlay=True)
        size = COVER_NAME_SIZE
        while self.measure(committee, "montb", size) > RIGHT - LEFT:
            size -= 2
        w = self.measure(committee, "montb", size)
        pg.insert_text(((595.5 - w) / 2, COVER_NAME_BASELINE), committee, fontname="montb",
                       fontfile=BOLD_TTF, fontsize=size, color=TEAL)
        y = COVER_AGENDA_BASELINE
        width = RIGHT - LEFT
        for line in self._wrap_runs([(agenda, True)], COVER_AGENDA_SIZE, width):
            text = " ".join(w for w, _ in line)
            tw = self.measure(text, "montb", COVER_AGENDA_SIZE)
            pg.insert_text(((595.5 - tw) / 2, y), text, fontname="montb",
                           fontfile=BOLD_TTF, fontsize=COVER_AGENDA_SIZE, color=WHITE)
            y += COVER_AGENDA_LEAD

    def layout_page(self, items):
        """Reproduce a source page's geometry inside the house frame."""
        boxes = []
        for it in items:
            if it["k"] == "img":
                boxes.append(it["rect"])
            else:
                boxes.append([it["x"], it["y"] - it["size"], it["x"] + it["w"], it["y"]])
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
        fw, fh = RIGHT - LEFT, BOTTOM - TOP
        s = min(fw / max(x1 - x0, 1), fh / max(y1 - y0, 1))
        ox = LEFT + (fw - (x1 - x0) * s) / 2 - x0 * s
        oy = TOP + (fh - (y1 - y0) * s) / 2 - y0 * s
        pg = self.new_page()
        for it in items:
            if it["k"] == "img":
                r = it["rect"]
                src = it["src"] if os.path.isabs(it["src"]) else os.path.join(HERE, it["src"])
                if os.path.exists(src):
                    pg.insert_image(pymupdf.Rect(ox + r[0] * s, oy + r[1] * s,
                                                 ox + r[2] * s, oy + r[3] * s),
                                    filename=src, keep_proportion=True, overlay=True)
        for it in items:
            if it["k"] != "txt":
                continue
            text = self.sanitize(it["text"]).strip()
            if not text:
                continue
            font = "montb" if it.get("bold") else "mont"
            size = it["size"] * s
            room = it["w"] * s
            # Montserrat is wider than the serif faces these guides use, so a
            # span is eased down until it sits inside its original footprint
            if room > 0:
                while size > 4 and self.measure(text, font, size) > room * 1.06:
                    size -= 0.25
            pg.insert_text((ox + it["x"] * s, oy + it["y"] * s), text, fontname=font,
                           fontfile=BOLD_TTF if it.get("bold") else REG_TTF,
                           fontsize=size, color=WHITE)

    # ---------- build ----------

    def build(self, content, out):
        emblem = content.get("emblem")
        if emblem and not os.path.isabs(emblem):
            emblem = os.path.join(HERE, emblem)
        self.cover(content["committee"], content["agenda"], emblem)

        laid = content.get("layout_pages")
        if laid:
            for pg in laid:
                self.layout_page(pg["items"])
            print(f"  {len(laid)} pages reproduced by layout")
            self.doc.save(out, garbage=4, deflate=True)
            return self.doc.page_count

        pages = content.get("pages")
        if pages:
            live = []
            for src in pages:
                blocks = [b for b in src["blocks"]
                          if b.get("t") == "i" or any(r[0].strip() for r in b["runs"])]
                if blocks:
                    live.append(blocks)           # never emit a blank page
            usable = BOTTOM - TOP
            # one scale for the whole guide: per-page scaling would make the
            # type size jump around between pages
            def page_fits(blocks, f):
                return self.height_of(blocks, f, self.figure_fit(blocks, f, usable)) <= usable

            fit = next((f for f in FIT_STEPS if all(page_fits(b, f) for b in live)),
                       FIT_STEPS[-1])
            for blocks in live:
                self.new_page()
                self.render_blocks(blocks, fit, allow_break=False,
                                   fig_scale=self.figure_fit(blocks, fit, usable))
            print(f"  {len(live)} content pages at {BODY_SIZE * fit[0]:.1f}pt "
                  f"/ {BODY_SIZE * fit[0] * fit[1]:.1f}pt leading")
        else:
            blocks = [b for s in content["sections"] for b in
                      ([{"t": "h", "text": s["heading"], "level": s.get("level", 1),
                         "runs": [[s["heading"], True]]}] if s.get("heading") else [])
                      + s.get("blocks", [])]
            self.new_page()
            self.render_blocks(blocks)

        self.doc.save(out, garbage=4, deflate=True)
        return self.doc.page_count


if __name__ == "__main__":
    content = json.load(open(sys.argv[1], encoding="utf-8"))
    n = GuideWriter().build(content, sys.argv[2])
    print(f"wrote {sys.argv[2]} ({n} pages)")
