# -*- coding: utf-8 -*-
"""装配提交目录并打包 zip。

提交格式（题目要求）：
  实验3_241880548_王睿阳/
  ├── 实验报告.pdf      （由 build/doc.py 生成，需先运行）
  ├── UML/              （8 张 .puml + .png，沿用实验二产物）
  └── code/             （campus_eats + tests + scripts + 配置文件）

运行：python build/package.py
"""

import os
import shutil
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
REPO = os.path.dirname(ROOT)
FOLDER = '实验3_241880548_王睿阳'
SUB = os.path.join(ROOT, FOLDER)

CODE_FILES = ['requirements.txt', 'pytest.ini', 'README.md', '.pylintrc']
CODE_DIRS = ['campus_eats', 'tests', 'scripts']
SKIP_NAMES = {'__pycache__', '.pytest_cache', 'campus_eats.db'}


def refresh_subdir():
    """重建提交目录：报告 PDF 从 build/ 拷入，UML 从实验二复制，code 从实验三复制。"""
    if os.path.exists(SUB):
        shutil.rmtree(SUB)
    os.makedirs(os.path.join(SUB, 'UML'))
    pdf = os.path.join(BASE, 'report_final.pdf')
    if not os.path.exists(pdf):
        raise SystemExit('缺少 build/report_final.pdf——请先写 report.md 并运行 build/doc.py')
    shutil.copy2(pdf, os.path.join(SUB, '实验报告.pdf'))
    src_uml = os.path.join(REPO, 'lab2', '实验2_241880548_王睿阳', 'UML')
    for name in sorted(os.listdir(src_uml)):
        if name.endswith(('.puml', '.png')):
            shutil.copy2(os.path.join(src_uml, name),
                         os.path.join(SUB, 'UML', name))
    code_root = os.path.join(SUB, 'code')
    for target in CODE_DIRS:
        shutil.copytree(os.path.join(ROOT, target), os.path.join(code_root, target),
                        ignore=shutil.ignore_patterns('__pycache__',
                                                      '.pytest_cache', '*.pyc'))
    for name in CODE_FILES:
        shutil.copy2(os.path.join(ROOT, name), os.path.join(code_root, name))
    print('UML:', len(os.listdir(os.path.join(SUB, 'UML'))), '个文件；'
          'code:', sum(len(files) for _, _, files in os.walk(code_root)), '个文件')


def make_zip():
    """打 zip：zip 内只含一层 实验3_学号_姓名 目录。"""
    out = os.path.join(ROOT, FOLDER + '.zip')
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(SUB):
            dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, ROOT)
                zf.write(full, rel)
    size = os.path.getsize(out)
    print('zip:', out, '%.2f MB' % (size / 1024 / 1024))


if __name__ == '__main__':
    refresh_subdir()
    make_zip()
