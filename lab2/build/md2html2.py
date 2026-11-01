import io
import os
import re
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SUB = os.path.join(ROOT, '实验2_241880548_王睿阳')
IMG = os.path.join(BASE, 'img')
os.makedirs(IMG, exist_ok=True)

uml = {
    'UML类图.png': 'uml_class.png',
    'UML组件图.png': 'uml_component.png',
    'UML用例图-顾客与商家.png': 'uml_usecase_c.png',
    'UML用例图-配送与管理.png': 'uml_usecase_d.png',
    'UML状态图.png': 'uml_state.png',
    'UML活动图.png': 'uml_activity.png',
    'UML时序图-下单支付.png': 'uml_seq_order.png',
    'UML时序图-派单配送.png': 'uml_seq_delivery.png',
}
for src, dst in uml.items():
    p = os.path.join(SUB, 'UML', src)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(IMG, dst))
        print('img', dst)

ui_dir = os.path.join(SUB, 'UI界面')
for f in sorted(os.listdir(ui_dir)):
    if f.endswith('.png'):
        n = f.split('_')[0].replace('UI-', 'ui')
        shutil.copy2(os.path.join(ui_dir, f), os.path.join(IMG, n + '.png'))
        print('img', n + '.png')

# ---------------- 转 HTML ----------------
md = io.open(os.path.join(ROOT, 'report.md'), encoding='utf-8').read().split('\n')

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def inline(s):
    s = IMG_RE.sub(lambda m: '<img class="cimg" src="%s" alt="%s">' % (m.group(2), m.group(1)), s)
    s = esc(s) if '<img' not in s else s
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    return s

out = []
i = 0
cur = None

def close_list():
    global cur
    if cur:
        out.append('</%s>' % cur)
        cur = None

while i < len(md):
    s = md[i].strip()
    if not s:
        close_list(); i += 1; continue

    m = re.match(r'^(#{1,4})\s+(.*)$', s)
    if m:
        close_list()
        n = len(m.group(1))
        out.append('<h%d>%s</h%d>' % (n, inline(m.group(2)), n))
        i += 1; continue

    if s.startswith('|'):
        close_list()
        rows = []
        while i < len(md) and md[i].strip().startswith('|'):
            rows.append(md[i].strip()); i += 1
        cells = [[c.strip() for c in r.strip('|').split('|')] for r in rows]
        body = [c for c in cells if not all(x and set(x) <= set('-: ') for x in c)]
        if body:
            html = ['<table class="grid">', '<thead><tr>' + ''.join('<th>%s</th>' % inline(c) for c in body[0]) + '</tr></thead>', '<tbody>']
            for r in body[1:]:
                html.append('<tr>' + ''.join('<td>%s</td>' % inline(c) for c in r) + '</tr>')
            html.append('</tbody></table>')
            out.extend(html)
        continue

    if s.startswith('!['):
        close_list()
        mm = re.match(r'!\[([^\]]*)\]\(([^)]+)\)(?:\{w=([\d.]+)%\})?', s)
        if mm:
            w = mm.group(3) or '100'
            fig = ('<figure><img src="%s" style="width:%s%%" alt="%s"><figcaption>%s</figcaption></figure>'
                   % (mm.group(2), w, mm.group(1), mm.group(1)))
            if out and out[-1] == '<!--LAND-->':
                out.pop()
                fig = '<div class="land">' + fig + '</div>'
            out.append(fig)
        i += 1; continue

    if s == '[[land]]':
        close_list()
        out.append('<!--LAND-->')
        i += 1; continue

    if re.match(r'^\d+\.\s+', s):
        if cur != 'ol':
            close_list(); out.append('<ol>'); cur = 'ol'
        out.append('<li>%s</li>' % inline(re.sub(r'^\d+\.\s+', '', s)))
        i += 1; continue

    if s.startswith('- '):
        if cur != 'ul':
            close_list(); out.append('<ul>'); cur = 'ul'
        out.append('<li>%s</li>' % inline(s[2:]))
        i += 1; continue

    close_list()
    out.append('<p>%s</p>' % inline(s))
    i += 1

body = '\n'.join(out)

CSS = '''
@page { size: A4; margin: 18mm 16mm 16mm 16mm; }
@page land { size: A4 landscape; margin: 14mm 14mm 12mm 14mm; }
.land { page: land; break-before: page; break-after: page; }
.land figure { margin: 0; }
.land figure img { width: 100%; max-height: 168mm; object-fit: contain; }
body { font-family: "Microsoft YaHei", "SimSun", serif; font-size: 10.5pt; line-height: 1.75; color: #000; margin: 0; }
h1 { font-size: 19pt; text-align: center; margin: 4pt 0 16pt; letter-spacing: 2pt; }
h2 { font-size: 14pt; margin: 16pt 0 8pt; border-bottom: 1.5px solid #FF6B2C; padding-bottom: 4pt; }
h3 { font-size: 11.5pt; margin: 12pt 0 6pt; color: #1F2329; }
p { margin: 0 0 7pt; text-align: justify; }
ul, ol { margin: 0 0 8pt; padding-left: 20pt; }
li { margin-bottom: 3pt; }
table.grid { width: 100%; border-collapse: collapse; margin: 8pt 0 10pt; font-size: 9.5pt; break-inside: auto; }
table.grid tr { break-inside: avoid; }
table.grid th, table.grid td { border: 1px solid #C9CDD4; padding: 5pt 7pt; text-align: left; vertical-align: middle; }
table.grid th { background: #F2F3F5; font-weight: 700; }
figure { margin: 8pt 0 12pt; text-align: center; }
figure img { max-width: 100%; }
figcaption { font-size: 9pt; color: #4E5969; margin-top: 4pt; }
img.cimg { width: 100%; display: block; }
td img.cimg { width: 88%; margin: 0 auto; }
td:has(img) { padding: 4pt; }
'''

html = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>' + CSS +
        '</style></head><body>' + body + '</body></html>')
io.open(os.path.join(ROOT, 'report.html'), 'w', encoding='utf-8', newline='\n').write(html)
print('html ok')
