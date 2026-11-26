"""Generate real, synthetic PDF files and their local page/text-layer assets.

Uses existing project dependencies only. No downloaded papers or model calls.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import textwrap

import pypdfium2 as pdfium
from pypdf import PdfWriter, PdfReader
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples/mvp-workbench"
WIDTH, HEIGHT = 480, 660


def create():
    js = "const fs=require('fs'),vm=require('vm');let c={window:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),c);process.stdout.write(JSON.stringify(c.window.DOC_DEMO));"
    docs = json.loads(subprocess.check_output(["node", "-e", js, str(OUT / "demo-data.js")], encoding="utf-8"))
    titles = ["Visual Representation with Limited Labels", "Lightweight Visual Encoding and Transfer", "Controlled Studies of Self-supervised Features", "A Practical Guide to Reading Experiments"]
    sections = ["Abstract and motivation", "Experimental setting", "Results and interpretation", "Limitations and future work"]
    context = [
        "This synthetic paper is provided for interface testing. It is not a published study and its authors, experimental settings and results are fictional. The document is a complete local PDF, with searchable text and stable page coordinates.",
        "Our research question concerns the relationship between representation learning and the available training budget. To interpret an experiment, the reader should examine the dataset, the model architecture and the evaluation protocol together. A shared term can have different roles in different papers.",
        "A controlled comparison records both the reported result and the conditions under which it was obtained. Results on different datasets or with different training schedules do not establish a direct ranking of methods. Missing details should remain missing until supported by source evidence.",
        "Reading a retrieved passage is the beginning of verification. The surrounding paragraphs may clarify whether a method belongs to the current experiment, a baseline or a cited study. Notes should retain the source location and distinguish direct statements from interpretation.",
        "The reader may annotate any selectable text in this document. A search query does not restrict where a note can be attached. When documents change, saved quotations should continue to refer to the source version from which they were collected.",
    ]
    result = {}
    for di, d in enumerate(docs):
        writer = PdfWriter()
        fonts = DictionaryObject()
        for name, base in [("F1", "Times-Roman"), ("F2", "Helvetica-Bold"), ("F3", "Helvetica")]:
            fonts[NameObject("/" + name)] = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/" + base)}))
        page_blocks = []
        all_search_blocks = []
        for pi in range(3):
            page = writer.add_blank_page(WIDTH, HEIGHT)
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
            commands = ["0.16 0.22 0.33 rg"]
            layouts = []

            def draw(text, x, y, size=11.5, font="F1", block=None):
                text = text.encode("ascii", "replace").decode("ascii")
                encoded = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                commands.append(f"BT /{font} {size} Tf 1 0 0 1 {x} {y} Tm ({encoded}) Tj ET")
                layouts.append({"text": text, "block": block, "size": size, "font": font})

            def paragraph(text, y, block=None):
                text = text.replace("×", "x")
                # Narrow single-column papers remain readable in three panes.
                for line in textwrap.wrap(text, width=77):
                    draw(line, 34, y, block=block)
                    y -= 17
                return y - 12

            draw("DOCLENS / RESEARCH READING SAMPLES", 34, 630, 8, "F3")
            commands.append("0.82 0.85 0.90 RG 0.7 w 34 619 m 446 619 l S")
            draw(f"Synthetic material - {d['id'].upper()} / page {pi + 1}", 34, 20, 8, "F3")
            if pi == 0:
                y = 582
                for line in textwrap.wrap(titles[di], 38):
                    draw(line, 34, y, 20, "F2"); y -= 27
                draw("Research interface demo | 2026 | not a published paper", 34, y - 4, 9, "F3")
                y -= 47
                draw("1  Abstract", 34, y, 14, "F2"); y -= 25
                # English body is deliberately explicit about the synthetic dataset.
                intro = "This study examines visual representation learning under a limited training budget. The objective is to make experimental choices and their supporting evidence easy to inspect."
                if d["id"] == "d": intro = "This reading guide explains how to inspect and compare experimental reports without confusing cited settings with the current study."
                y = paragraph(intro, y, 0)
                draw("2  Reading the evidence", 34, y, 14, "F2"); y -= 25
                for text in context[:3]: y = paragraph(text, y)
            elif pi == 1:
                draw("3  Methods and experimental setting", 34, 581, 16, "F2")
                y = 548
                source = d["sections"][1]["text"]
                if d["id"] == "d": source = "Inspect the model, dataset, training epochs and evaluation protocol before comparing numerical results. A result from prior work is not automatically a result from the current experiment."
                y = paragraph(source, y, 1)
                y = paragraph(context[1], y)
                draw("4  Results and interpretation", 34, y, 14, "F2"); y -= 27
                source = d["sections"][2]["text"] if len(d["sections"]) > 2 else context[2]
                y = paragraph(source, y, 2)
                y = paragraph(context[2], y)
                draw("Checklist for a fair comparison", 34, y, 12, "F2"); y -= 25
                for line in ["Dataset and split    | record the exact name", "Architecture         | separate use from mention", "Training schedule    | keep the value and unit", "Evidence             | verify the original passage"]:
                    draw(line, 40, y, 10, "F3"); y -= 20
            else:
                draw("5  Limitations and future work", 34, 581, 16, "F2")
                y = 548
                source = d["sections"][3]["text"] if len(d["sections"]) > 3 else context[3]
                y = paragraph(source, y, 3)
                for text in [context[3], context[4]]: y = paragraph(text, y)
                draw("Appendix: verification notes", 34, y, 14, "F2"); y -= 27
                y = paragraph("A document viewer should provide access to every page, preserve the reading position of each open paper, and make the selected passage easy to revisit. Saving a note must not modify the original PDF.", y, 4)
                paragraph(context[0], y)
            stream = DecodedStreamObject(); stream.set_data("\n".join(commands).encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
            page_blocks.append(layouts)
        pdf_path = OUT / "sample-documents" / f"{d['id']}.pdf"
        writer.write(pdf_path)
        assert len(PdfReader(pdf_path).pages) == 3
        pages = []
        document = pdfium.PdfDocument(pdf_path)
        for pi in range(3):
            pdf_page = document[pi]
            textpage = pdf_page.get_textpage()
            text = textpage.get_text_range()
            # Map each actual PDFium text line to its authored block, in draw order.
            word_data = []
            layout_index = 0
            for line in text.splitlines():
                found = next((j for j in range(layout_index, len(page_blocks[pi])) if page_blocks[pi][j]["text"] == line), None)
                meta = page_blocks[pi][found] if found is not None else {"block":None,"size":11.5,"font":"F1"}
                if found is not None: layout_index = found + 1
                # Index via PDFium's own extraction, then get exact glyph boxes.
                pos = text.find(line, word_data[-1].get("end", 0) if word_data else 0)
                if pos < 0: continue
                for match in re.finditer(r"\S+", line):
                    begin, end = pos + match.start(), pos + match.end()
                    boxes = [textpage.get_charbox(i) for i in range(begin, end)]
                    left = min(b[0] for b in boxes); right = max(b[2] for b in boxes)
                    bottom = min(b[1] for b in boxes); top = max(b[3] for b in boxes)
                    word_data.append({"text": match.group(), "x":round(left,3),"y":round(HEIGHT-top,3),"w":round(right-left,3),"h":round(top-bottom,3),"size":meta["size"],"font":meta["font"],"block":meta["block"],"start":begin,"end":end})
            image_path = OUT / "pdf-pages" / f"{d['id']}-{pi+1}.png"
            bitmap = pdf_page.render(scale=1.65)
            bitmap.to_pil().save(image_path, optimize=True)
            bitmap.close()
            # All declared coordinates come from the saved PDF, not a fake HTML layout.
            assert word_data and all(0<=w['x']<WIDTH and 0<=w['y']<HEIGHT for w in word_data)
            for block_id in sorted({w['block'] for w in word_data if w['block'] is not None}):
                block_words=[w for w in word_data if w['block']==block_id]
                all_search_blocks.append({'id':block_id,'page':pi+1,'text':' '.join(w['text'] for w in block_words)})
            pages.append({"number":pi+1,"image":f"pdf-pages/{image_path.name}","width":WIDTH,"height":HEIGHT,"words":word_data})
            textpage.close(); pdf_page.close()
        document.close()
        result[d['id']]={"title":d['title'],"englishTitle":titles[di],"file":f"sample-documents/{d['id']}.pdf","sha256":hashlib.sha256(pdf_path.read_bytes()).hexdigest(),"pages":pages,"blocks":all_search_blocks}
    (OUT / "pdf-data.js").write_text("/* Source: saved local synthetic PDFs, rendered by PDFium. */\nwindow.PDF_DEMO = "+json.dumps(result,ensure_ascii=False,separators=(',',':'))+";\n",encoding="utf-8")
    print(json.dumps({"documents":len(result),"pages":sum(len(x['pages']) for x in result.values()),"word_boxes":sum(len(p['words']) for d in result.values() for p in d['pages']),"source_pdf_sha256":{k:v['sha256'] for k,v in result.items()}},indent=2))


if __name__ == "__main__":
    create()
