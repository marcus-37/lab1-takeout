# -*- coding: utf-8 -*-
"""代码量统计：总行数 / 非空行 / 代码行（去空行与注释），供实验报告引用。

口径说明：
- 总行数：文件全部行；
- 代码行：去除空行、纯注释行（# 或 docstring 独立行按启发式处理）后的行数。
运行：python build/count_lines.py
"""

import io
import os
import re
import tokenize

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
TARGETS = ['campus_eats', 'tests', 'scripts']

COMMENT_OR_BLANK = re.compile(r'^\s*(#|$)')


def stats_of(path):
    """统计单个 py 文件，返回（总行, 代码行）。

    代码行 = 含有非注释 token 的物理行去重数（docstring 算代码，
    与 pylint 的 loc 口径一致；纯注释行与空行不计）。
    """
    with io.open(path, encoding='utf-8') as handle:
        src = handle.read()
    total = src.count('\n') + (0 if src.endswith('\n') or not src else 1)
    code_lines = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok in tokens:
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                            tokenize.INDENT, tokenize.DEDENT,
                            tokenize.ENCODING, tokenize.ENDMARKER):
                continue
            code_lines.add(tok.start[0])
    except tokenize.TokenError:
        code_lines = {i + 1 for i, line in enumerate(src.splitlines())
                      if not COMMENT_OR_BLANK.match(line)}
    return total, len(code_lines)


def main():
    """按目录汇总输出。"""
    grand_total = grand_code = 0
    for target in TARGETS:
        t_dir = os.path.join(ROOT, target)
        if not os.path.isdir(t_dir):
            continue
        total = code = files = 0
        for dirpath, _, filenames in os.walk(t_dir):
            if '__pycache__' in dirpath:
                continue
            for name in filenames:
                if name.endswith('.py'):
                    files += 1
                    f_total, f_code = stats_of(os.path.join(dirpath, name))
                    total += f_total
                    code += f_code
        print('%-12s 文件 %3d  总行数 %5d  代码行(token) %5d'
              % (target, files, total, code))
        grand_total += total
        grand_code += code
    print('%-12s 文件 %3d  总行数 %5d  代码行(token) %5d'
          % ('合计', 0, grand_total, grand_code))


if __name__ == '__main__':
    main()
