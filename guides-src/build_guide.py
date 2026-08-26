#!/usr/bin/env python3
"""Build an OakBMUN background guide PDF in the house design.

Usage:  python build_guide.py content.json out.pdf

The design (navy texture, header banner, teal footer, cover furniture) is
lifted straight from template.pdf, which is last year's guide with its text
redacted away -- so the look matches exactly rather than being re-drawn.

content.json:
{
  "committee": "DISEC",
  "agenda": "Agenda: ...",
  "sections": [
    {"heading": "Letter from the Executive Board", "body": ["para", "para"]},
    {"heading": "History", "body": ["..."], "bullets": ["..."]}
  ]
}
"""
import json, sys, os
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "template.pdf")
FONT_DIR = os.path.join(HERE, "fonts")

WHITE = (1, 1, 1)
TEAL = (0.702, 0.925, 0.961)          # #b3ecf5, the cover committee name
BODY_SIZE, BODY_LEAD = 12.0, 18.6
HEAD_SIZE, HEAD_LEAD = 18.3, 26.0
LEFT, RIGHT = 89.0, 506.0             # text frame from the reference guide
TOP, BOTTOM = 74.0, 757.0
PARA_GAP, HEAD_GAP_BEFORE, HEAD_GAP_AFTER = 10.0, 14.0, 8.0
COVER_NAME_SIZE, COVER_NAME_BASELINE = 69.2, 590.5
COVER_AGENDA_SIZE, COVER_AGENDA_BASELINE, COVER_AGENDA_LEAD = 18.3, 633.1, 25.3
EMBLEM_BOX = (147.0, 238.0, 456.0, 530.0)  # reference box, pulled up off the
                                           # committee name: the original art
                                           # had padding, trimmed emblems don't
NAVY = (0.055, 0.157, 0.278)


REG_TTF = os.path.join(FONT_DIR, "Montserrat-Regular.ttf")
BOLD_TTF = os.path.join(FONT_DIR, "Montserrat-Bold.ttf")


class GuideWriter:
    def __init__(self):
        self.tpl = pymupdf.open(TEMPLATE)
        self.doc = pymupdf.open()
        self.page = None
        self.y = TOP
        self.metrics = {"mont": pymupdf.Font(fontfile=REG_TTF),
                        "montb": pymupdf.Font(fontfile=BOLD_TTF)}

    def _fonts(self, page):
        page.insert_font(fontname="mont", fontfile=REG_TTF)
        page.insert_font(fontname="montb", fontfile=BOLD_TTF)

    def measure(self, text, font, size):
        return self.metrics[font].text_length(text, size)

    def new_page(self, cover=False):
        self.doc.insert_pdf(self.tpl, from_page=0 if cover else 1, to_page=0 if cover else 1)
        self.page = self.doc[-1]
        self._fonts(self.page)
        self.y = TOP
        return self.page

    def _wrap(self, text, font, size):
        """Greedy wrap to the text frame width."""
        width = RIGHT - LEFT
        words, lines, cur = [], [], ""
        for w in text.split():
            words.extend(self._split_long(w, font, size, width))
        for w in words:
            trial = (cur + " " + w).strip()
            if self.measure(trial, font, size) <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def _split_long(self, word, font, size, width):
        """Break a word too long for the line (URLs) into chunks that fit."""
        if self.measure(word, font, size) <= width:
            return [word]
        out, cur, last_break = [], "", -1
        for ch in word:
            if cur and self.measure(cur + ch, font, size) > width:
                # prefer to break a URL after a separator rather than mid-word
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
            for w in text.split():
                font = "montb" if bold else "mont"
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

    def write_runs(self, runs, size=BODY_SIZE, lead=BODY_LEAD, color=WHITE, indent=0.0):
        """Write a paragraph that mixes regular and bold text."""
        width = RIGHT - LEFT - indent
        space = self.measure(" ", "mont", size)
        for line in self._wrap_runs(runs, size, width):
            if self.y + lead > BOTTOM:
                self.new_page()
            x = LEFT + indent
            for i, (word, bold) in enumerate(line):
                if i:
                    x += space
                self.page.insert_text((x, self.y + size), word, fontname="montb" if bold else "mont",
                                      fontfile=BOLD_TTF if bold else REG_TTF,
                                      fontsize=size, color=color)
                x += self.measure(word, "montb" if bold else "mont", size)
            self.y += lead

    def write(self, text, bold=False, size=BODY_SIZE, lead=BODY_LEAD,
              color=WHITE, align_center=False, indent=0.0):
        font = "montb" if bold else "mont"
        for line in self._wrap(text, font, size):
            if self.y + lead > BOTTOM:
                self.new_page()
            w = self.measure(line, font, size)
            x = (LEFT + RIGHT - w) / 2 if align_center else LEFT + indent
            self.page.insert_text((x, self.y + size), line, fontname=font,
                                  fontfile=BOLD_TTF if bold else REG_TTF,
                                  fontsize=size, color=color)
            self.y += lead

    def gap(self, amount):
        self.y += amount

    def heading(self, text, level=1):
        if level > 1:
            need = BODY_LEAD * 2
            if self.y + need > BOTTOM:
                self.new_page()
            else:
                self.gap(8)
            self.write(text, bold=True, size=13.5, lead=20.0)
            self.gap(4)
            return
        return self._heading1(text)

    def _heading1(self, text):
        need = HEAD_LEAD * len(self._wrap(text, "montb", HEAD_SIZE)) + HEAD_GAP_AFTER + BODY_LEAD
        if self.y + need > BOTTOM:
            self.new_page()
        else:
            self.gap(HEAD_GAP_BEFORE)
        self.write(text, bold=True, size=HEAD_SIZE, lead=HEAD_LEAD, align_center=True)
        self.gap(HEAD_GAP_AFTER)

    def cover(self, committee, agenda, emblem=None):
        pg = self.new_page(cover=True)
        if emblem:
            # the template carries last year's committee emblem; cover it with
            # this committee's, fitted inside the reference emblem's box
            box = pymupdf.Rect(*EMBLEM_BOX)
            iw, ih = pymupdf.Pixmap(emblem).width, pymupdf.Pixmap(emblem).height
            scale = min(box.width / iw, box.height / ih)
            w, h = iw * scale, ih * scale
            cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
            pg.insert_image(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                            filename=emblem, keep_proportion=True, overlay=True)
        # metrics lifted from the reference cover: committee 69.2pt teal on a
        # 590.5 baseline, agenda 18.3pt white, centred, 25.3pt leading
        size = COVER_NAME_SIZE
        while self.measure(committee, "montb", size) > RIGHT - LEFT:
            size -= 2                       # keep long names such as LOK SABHA on one line
        w = self.measure(committee, "montb", size)
        pg.insert_text(((595.5 - w) / 2, COVER_NAME_BASELINE), committee, fontname="montb",
                       fontfile=BOLD_TTF, fontsize=size, color=TEAL)
        y = COVER_AGENDA_BASELINE
        for line in self._wrap(agenda, "montb", COVER_AGENDA_SIZE):
            tw = self.measure(line, "montb", COVER_AGENDA_SIZE)
            pg.insert_text(((595.5 - tw) / 2, y), line, fontname="montb",
                           fontfile=BOLD_TTF, fontsize=COVER_AGENDA_SIZE, color=WHITE)
            y += COVER_AGENDA_LEAD

    def build(self, content, out):
        emblem = content.get("emblem")
        if emblem and not os.path.isabs(emblem):
            emblem = os.path.join(HERE, emblem)
        self.cover(content["committee"], content["agenda"], emblem)
        for si, sec in enumerate(content["sections"]):
            if si == 0 or sec.get("page_break", False):
                self.new_page()
            if sec.get("heading"):
                self.heading(sec["heading"], sec.get("level", 1))
            blocks = sec.get("blocks")
            if blocks is None:   # older content files
                blocks = ([{"t": "p", "runs": x} for x in sec.get("body", [])]
                          + [{"t": "b", "runs": x} for x in sec.get("bullets", [])])
            for blk in blocks:
                runs = blk["runs"]
                if isinstance(runs, str):
                    runs = [[runs, False]]
                runs = [(r[0], bool(r[1])) for r in runs]
                if blk["t"] == "b":
                    marker = blk.get("marker", "\u2022")
                    self.write_runs([(marker + " ", False)] + runs, indent=12)
                    self.gap(5)
                else:
                    self.write_runs(runs)
                    self.gap(PARA_GAP)
        self.doc.save(out, garbage=4, deflate=True)
        return self.doc.page_count


if __name__ == "__main__":
    content = json.load(open(sys.argv[1], encoding="utf-8"))
    n = GuideWriter().build(content, sys.argv[2])
    print(f"wrote {sys.argv[2]} ({n} pages)")
