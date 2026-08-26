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
PARA_GAP, HEAD_GAP_BEFORE, HEAD_GAP_AFTER = 10.0, 14.0, 8.0
BULLET_GAP, BULLET_INDENT = 5.0, 12.0
COVER_NAME_SIZE, COVER_NAME_BASELINE = 69.2, 590.5
COVER_AGENDA_SIZE, COVER_AGENDA_BASELINE, COVER_AGENDA_LEAD = 18.3, 633.1, 25.3
EMBLEM_BOX = (147.0, 238.0, 456.0, 530.0)
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

    def render_blocks(self, blocks, fit=(1.0, 1.55), allow_break=True):
        scale, ratio = fit
        body_lead = BODY_SIZE * scale * ratio
        head_lead = HEAD_SIZE * scale * (ratio * 0.92)
        sub_lead = SUB_SIZE * scale * (ratio * 0.96)
        for blk in blocks:
            runs = blk["runs"]
            if isinstance(runs, str):
                runs = [[runs, False]]
            runs = [(r[0], bool(r[1])) for r in runs]
            kind = blk.get("t", "p")
            if kind == "h":
                level = blk.get("level", 1)
                if level == 1:
                    self.gap(HEAD_GAP_BEFORE * scale)
                    self.write_runs([(blk["text"], True)], HEAD_SIZE * scale,
                                    head_lead, center=True, allow_break=allow_break)
                    self.gap(HEAD_GAP_AFTER * scale)
                else:
                    self.gap(8 * scale)
                    self.write_runs([(blk["text"], True)], SUB_SIZE * scale,
                                    sub_lead, allow_break=allow_break)
                    self.gap(4 * scale)
            elif kind == "b":
                marker = blk.get("marker", "•")
                self.write_runs([(marker + " ", False)] + runs, BODY_SIZE * scale,
                                body_lead, indent=BULLET_INDENT,
                                allow_break=allow_break)
                self.gap(BULLET_GAP * scale)
            else:
                self.write_runs(runs, BODY_SIZE * scale, body_lead,
                                allow_break=allow_break)
                self.gap(PARA_GAP * scale)

    def height_of(self, blocks, fit):
        """Dry-run the blocks to see how tall they are at this setting."""
        self.dry, saved_y = True, self.y
        self.y = TOP
        self.render_blocks(blocks, fit, allow_break=False)
        h = self.y - TOP
        self.dry, self.y = False, saved_y
        return h

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

    # ---------- build ----------

    def build(self, content, out):
        emblem = content.get("emblem")
        if emblem and not os.path.isabs(emblem):
            emblem = os.path.join(HERE, emblem)
        self.cover(content["committee"], content["agenda"], emblem)

        pages = content.get("pages")
        if pages:
            live = []
            for src in pages:
                blocks = [b for b in src["blocks"] if any(r[0].strip() for r in b["runs"])]
                if blocks:
                    live.append(blocks)           # never emit a blank page
            usable = BOTTOM - TOP
            # one scale for the whole guide: per-page scaling would make the
            # type size jump around between pages
            fit = next((f for f in FIT_STEPS
                        if all(self.height_of(b, f) <= usable for b in live)),
                       FIT_STEPS[-1])
            for blocks in live:
                self.new_page()
                self.render_blocks(blocks, fit, allow_break=False)
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
