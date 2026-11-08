import io
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SUB = os.path.join(ROOT, '实验3_241880548_王睿阳')
IMG = os.path.join(BASE, 'img')

NUMS = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

def cn(n):
    return NUMS[n] if 0 <= n < len(NUMS) else str(n)

# ---------------- 图片 ----------------
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
ui_dir = os.path.join(SUB, 'UI界面')
if os.path.isdir(ui_dir):
    for f in sorted(os.listdir(ui_dir)):
        if f.endswith('.png'):
            shutil.copy2(os.path.join(ui_dir, f), os.path.join(IMG, f.split('_')[0].replace('UI-', 'ui') + '.png'))

# ---------------- 标题重编号 ----------------
raw = io.open(os.path.join(ROOT, 'report.md'), encoding='utf-8').read().split('\n')

out_lines = []
chap = 0
sub = 0
title = ''
meta = []
for line in raw:
    s = line.rstrip()
    if s.startswith('# ') and not title:
        title = s[2:].strip()
        out_lines.append(s)
        continue
    m2 = re.match(r'^##\s+(\d+)\s+(.*)$', s)
    if m2:
        chap += 1
        sub = 0
        out_lines.append('## %s、%s' % (cn(chap), m2.group(2)))
        continue
    m3 = re.match(r'^###\s+\d+\.(\d+)\s+(.*)$', s)
    if m3:
        sub += 1
        out_lines.append('### %s %s' % (sub, m3.group(2)))
        continue
    out_lines.append(s)

md = out_lines
io.open(os.path.join(ROOT, 'report.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

# ---------------- 解析结构 ----------------
body_md = []
headings = []   # (level, text, id)
i = 0
if md and md[0].strip().startswith('# '):
    i = 1
while i < len(md):
    s = md[i].strip()
    if s.startswith('## '):
        break
    if s:
        meta.append(s)
    i += 1

c2 = c3 = 0
rest = '\n'.join(md[i:])
for line in rest.split('\n'):
    m = re.match(r'^(##|###)\s+(.*)$', line.strip())
    if m:
        if m.group(1) == '##':
            c2 += 1; c3 = 0
            hid = 'sec-%d' % c2
        else:
            c3 += 1
            hid = 'sec-%d-%d' % (c2, c3)
        headings.append((len(m.group(1)), m.group(2).strip(), hid))

# ---------------- Markdown -> HTML ----------------
def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def inline(s):
    has_img = bool(IMG_RE.search(s))
    s = IMG_RE.sub(lambda m: '<img class="cimg" src="%s" alt="%s">' % (m.group(2), m.group(1)), s)
    if not has_img:
        s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    return s

src = rest.split('\n')
out = []
idx = 0
cur = None
c2 = c3 = 0

def close_list():
    global cur
    if cur:
        out.append('</%s>' % cur)
        cur = None

while idx < len(src):
    s = src[idx].strip()
    if not s:
        close_list(); idx += 1; continue

    m = re.match(r'^(##|###|####)\s+(.*)$', s)
    if m:
        close_list()
        lvl = len(m.group(1))
        if lvl == 2:
            c2 += 1; c3 = 0
            hid = 'sec-%d' % c2
        elif lvl == 3:
            c3 += 1
            hid = 'sec-%d-%d' % (c2, c3)
        else:
            hid = 'h-%d' % idx
        out.append('<h%d id="%s">%s</h%d>' % (lvl, hid, inline(m.group(2)), lvl))
        idx += 1; continue

    if s.startswith('|'):
        close_list()
        rows = []
        while idx < len(src) and src[idx].strip().startswith('|'):
            rows.append(src[idx].strip()); idx += 1
        cells = [[c.strip() for c in r.strip('|').split('|')] for r in rows]
        b = [c for c in cells if not all(x and set(x) <= set('-: ') for x in c)]
        if b:
            html = ['<table class="grid">', '<thead><tr>' + ''.join('<th>%s</th>' % inline(c) for c in b[0]) + '</tr></thead>', '<tbody>']
            for r in b[1:]:
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
        idx += 1; continue

    if s == '[[land]]':
        close_list(); out.append('<!--LAND-->'); idx += 1; continue

    if re.match(r'^\d+\.\s+', s):
        if cur != 'ol':
            close_list(); out.append('<ol>'); cur = 'ol'
        out.append('<li>%s</li>' % inline(re.sub(r'^\d+\.\s+', '', s)))
        idx += 1; continue

    if s.startswith('- '):
        if cur != 'ul':
            close_list(); out.append('<ul>'); cur = 'ul'
        out.append('<li>%s</li>' % inline(s[2:]))
        idx += 1; continue

    close_list()
    out.append('<p>%s</p>' % inline(s))
    idx += 1

body = '\n'.join(out)

# ---------------- 封面 / 目录 ----------------
project = ''
student = ''
report_date = ''
for line in meta:
    if line.startswith('项目名称'):
        project = line.split('：', 1)[-1].strip()
    if line.startswith('学号'):
        student = line
    if line.startswith('日期'):
        report_date = line.split('：', 1)[-1].strip()

name = ''
sid = ''
m = re.search(r'学号：\s*(\d+)', student)
if m:
    sid = m.group(1)
m = re.search(r'姓名：\s*(\S+)', student)
if m:
    name = m.group(1)

cover = '''<div class="cover">
  <div class="c-course">软件工程</div>
  <div class="c-sub">实验三：软件实现与构建</div>
  <div class="c-name">%s&nbsp;&nbsp;%s</div>
  <div class="c-date">%s</div>
  <div class="c-proj">项目：%s</div>
</div>''' % (name, sid, report_date or '2026 年 11 月', project)

PLACE = sys.argv[1] if len(sys.argv) > 1 else '00'
pagemap = {}
pm_path = os.path.join(BASE, 'pagemap.json')
if os.path.exists(pm_path) and len(sys.argv) == 1:
    import json
    pagemap = json.load(io.open(pm_path, encoding='utf-8'))
toc_rows = []
for lvl, text, hid in headings:
    num = str(pagemap.get(hid, PLACE))
    if lvl == 2:
        toc_rows.append('<div class="lv1"><a href="#%s"><span class="t">%s</span></a><span class="dots"></span><span class="pg">%s</span></div>'
                        % (hid, esc(text), num))
    else:
        toc_rows.append('<div class="lv2"><a href="#%s"><span class="t">%s</span></a><span class="dots"></span><span class="pg">%s</span></div>'
                        % (hid, esc(text), num))

toc = '<h2 class="toc-title" id="toc">目录</h2>\n<div class="toc">' + '\n'.join(toc_rows) + '</div>'

# ---------------- CSS ----------------
CSS = '''
@page { size: A4; margin: 18mm 16mm 16mm 16mm; }
@page land { size: A4 landscape; margin: 14mm 14mm 12mm 14mm; }
.land { page: land; break-before: page; break-after: page; }
.land figure { margin: 0; }
.land figure img { width: 100%; max-height: 168mm; object-fit: contain; }
html { -webkit-print-color-adjust: exact; }
body { font-family: "Microsoft YaHei", "SimSun", serif; font-size: 10.5pt; line-height: 1.75; color: #000; margin: 0; }
.cover { text-align: center; padding: 6mm 0 0; }
.c-course { font-size: 21pt; letter-spacing: 6pt; font-weight: 600; }
.c-sub { font-size: 12pt; margin-top: 8pt; letter-spacing: 1pt; }
.c-name { font-size: 12pt; margin-top: 14pt; letter-spacing: 1pt; }
.c-date { font-size: 11pt; margin-top: 6pt; }
.c-proj { font-size: 10pt; color: #444; margin-top: 4pt; }
h1 { font-size: 19pt; text-align: center; margin: 0 0 10pt; letter-spacing: 2pt; }
h2.toc-title { font-size: 15pt; font-weight: 700; letter-spacing: 2pt; margin: 7mm 0 5pt; border: 0; padding: 0; }
.toc { margin: 0 0 8pt; break-after: page; }
.toc .lv1 { display: flex; align-items: baseline; font-size: 11pt; font-weight: 700; margin-top: 5pt; }
.toc .lv2 { display: flex; align-items: baseline; font-size: 10pt; margin: 2pt 0 0 10pt; padding-left: 12pt; }
.toc a { color: #000; text-decoration: none; }
.toc .t { white-space: nowrap; }
.toc .dots { flex: 1; border-bottom: 1px dotted #666; margin: 0 5px; transform: translateY(-3pt); }
.toc .pg { min-width: 14pt; text-align: right; font-variant-numeric: tabular-nums; }
h2 { font-size: 15pt; font-weight: 700; margin: 16mm 0 8pt; border: 0; padding: 0; break-after: avoid; }
h3 { font-size: 12pt; font-weight: 700; margin: 12pt 0 6pt; break-after: avoid; }
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

html = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body>'
        % (esc(title), CSS)) + cover + toc + body + '</body></html>'

io.open(os.path.join(ROOT, 'report.html'), 'w', encoding='utf-8', newline='\n').write(html)
print('html ok, headings', len(headings))
