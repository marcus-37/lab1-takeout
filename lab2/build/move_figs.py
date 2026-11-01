import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, 'report.md')
s = io.open(p, encoding='utf-8').read()

pairs = [
    ('[[land]]\n![UML组件图](build/img/uml_component.png)\n\n', '### 2 领域模型：类图'),
    ('[[land]]\n![UML类图](build/img/uml_class.png)\n\n', '### 3 角色与用例：用例图'),
]

for block, anchor in pairs:
    if block not in s:
        print('skip (already moved):', anchor)
        continue
    s = s.replace(block, '', 1)
    s = s.replace(anchor, block + anchor, 1)
    print('moved before', anchor)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
