import glob
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(BASE, 'html')
OUT = os.path.join(BASE, '..', '实验2_241880548_王睿阳', 'UI界面')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

os.makedirs(OUT, exist_ok=True)

for path in sorted(glob.glob(os.path.join(HTML, '*.html'))):
    name = os.path.splitext(os.path.basename(path))[0]
    is_desk = 'desk' in open(path, encoding='utf-8').read()[:4000] and 'class="desk"' in open(path, encoding='utf-8').read()
    w, h = (1440, 900) if is_desk else (390, 844)
    out_png = os.path.join(OUT, name + '.png')
    url = 'file:///' + path.replace('\\', '/')
    cmd = [
        EDGE,
        '--headless=new',
        '--disable-gpu',
        '--hide-scrollbars',
        '--force-device-scale-factor=2',
        '--window-size=%d,%d' % (w, h),
        '--screenshot=%s' % out_png,
        url,
    ]
    r = subprocess.run(cmd, capture_output=True)
    ok = os.path.exists(out_png)
    print(('OK ' if ok else 'FAIL ') + name, (os.path.getsize(out_png) if ok else r.stderr[-200:]))
