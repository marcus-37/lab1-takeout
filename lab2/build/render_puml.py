import io
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
UML = os.path.join(BASE, '..', '实验2_241880548_王睿阳', 'UML')
KROKI = 'https://kroki.io/plantuml/png'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

files = [f for f in sorted(os.listdir(UML)) if f.endswith('.puml')]
only = sys.argv[1:] 
for f in files:
    if only and f not in only:
        continue
    src = io.open(os.path.join(UML, f), encoding='utf-8').read().encode('utf-8')
    req = urllib.request.Request(KROKI, data=src, headers={'Content-Type': 'text/plain', 'User-Agent': UA})
    try:
        png = opener.open(req, timeout=120).read()
    except Exception as e:
        print('FAIL', f, e)
        continue
    out = os.path.join(UML, os.path.splitext(f)[0] + '.png')
    with open(out, 'wb') as fh:
        fh.write(png)
    print('OK', os.path.basename(out), len(png))
