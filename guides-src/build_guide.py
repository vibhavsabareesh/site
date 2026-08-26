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
        words, lines, cur = text.split(), [], ""
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

    def heading(self, text):
        need = HEAD_LEAD * len(self._wrap(text, "montb", HEAD_SIZE)) + HEAD_GAP_AFTER + BODY_LEAD
        if self.y + need > BOTTOM:
            self.new_page()
        else:
            self.gap(HEAD_GAP_BEFORE)
        self.write(text, bold=True, size=HEAD_SIZE, lead=HEAD_LEAD, align_center=True)
        self.gap(HEAD_GAP_AFTER)

    def cover(self, committee, agenda):
        pg = self.new_page(cover=True)
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
        self.cover(content["committee"], content["agenda"])
        for sec in content["sections"]:
            self.new_page() if sec.get("page_break", True) else None
            if sec.get("heading"):
                self.heading(sec["heading"])
            for para in sec.get("body", []):
                self.write(para)
                self.gap(PARA_GAP)
            for b in sec.get("bullets", []):
                self.write("•  " + b, indent=10)
                self.gap(4)
        self.doc.save(out, garbage=4, deflate=True)
        return self.doc.page_count


if __name__ == "__main__":
    content = json.load(open(sys.argv[1], encoding="utf-8"))
    n = GuideWriter().build(content, sys.argv[2])
    print(f"wrote {sys.argv[2]} ({n} pages)")
