import io
import json
import os
import re
import subprocess
import sys

import pymupdf

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
TARGET = os.path.join(BASE, 'report_final.pdf')
PM = os.path.join(BASE, 'pagemap.json')


def build_html():
    r = subprocess.run([sys.executable, os.path.join(BASE, 'md2html3.py')],
                       capture_output=True, cwd=BASE)
    if r.returncode != 0:
        print(r.stderr.decode('utf-8', 'replace'))
    print(r.stdout.decode('utf-8', 'replace').strip())


def render(out_pdf):
    url = 'file:///' + os.path.join(ROOT, 'report.html').replace('\\', '/')
    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                    '--print-to-pdf=%s' % out_pdf, url], capture_output=True)


def headings_from_html():
    html = io.open(os.path.join(ROOT, 'report.html'), encoding='utf-8').read()
    res = []
    for m in re.finditer(r'<h([23]) id="(sec-\d+(?:-\d+)?)">(.*?)</h[23]>', html, re.S):
        text = re.sub(r'<[^>]+>', '', m.group(3))
        res.append((int(m.group(1)), m.group(2), text))
    return res


def measure(pdf_path, heads):
    doc = pymupdf.open(pdf_path)
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    links = sorted(doc[0].get_links(), key=lambda l: (l['from'].y0, l['from'].x0))
    doc.close()
    if len(links) == len(heads):
        return {hid: links[i]['page'] for i, (lvl, hid, text) in enumerate(heads)}, len(pages), len(links)
    mapping = {}
    for lvl, hid, text in heads:
        probe = text.replace(' ', '')
        found = None
        for p in range(1, len(pages)):
            body = pages[p].replace(' ', '').replace('\n', '')
            if probe in body:
                found = p
                break
        mapping[hid] = found
    return mapping, len(pages), len(links)


build_html()
if os.path.exists(PM):
    os.remove(PM)

p1 = os.path.join(ROOT, 'pass1.pdf')
render(p1)
heads = headings_from_html()
mapping, n1, toc1 = measure(p1, heads)
missing = [h for h, v in mapping.items() if v is None]
print('pass1 pages', n1, 'toc pages', toc1, 'missing', missing)

json.dump(mapping, io.open(PM, 'w', encoding='utf-8'), ensure_ascii=False)

build_html()
p2 = os.path.join(ROOT, 'pass2.pdf')
render(p2)
mapping2, n2, toc2 = measure(p2, heads)
print('pass2 pages', n2, 'toc pages', toc2,
      'changed', {h: (mapping[h], mapping2[h]) for h in mapping if mapping[h] != mapping2[h]})

doc = pymupdf.open(p2)
doc.set_toc([[1 if lvl == 2 else 2, text, (mapping2[hid] or 0) + 1] for lvl, hid, text in heads])
for p in range(1, doc.page_count):
    page = doc[p]
    txt = str(p)
    w = page.rect.width
    page.insert_text((w / 2 - 4, page.rect.height - 26), txt,
                     fontname='helv', fontsize=9, color=(0.25, 0.25, 0.25))
doc.save(TARGET, garbage=3, deflate=True)
doc.close()
print('saved', TARGET, round(os.path.getsize(TARGET) / 1024 / 1024, 2), 'MB')
