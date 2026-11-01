import io
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

s = io.open(os.path.join(ROOT, 'report.md'), encoding='utf-8').read()
new6 = io.open(os.path.join(BASE, 'sec6.txt'), encoding='utf-8').read()
i = s.index('## 6 版本信息')
s = s[:i] + new6
io.open(os.path.join(ROOT, 'report.md'), 'w', encoding='utf-8', newline='\n').write(s)
print('ok', len(s))
