from pathlib import Path
r = Path(__file__).resolve().parents[1]
html = (r / 'firmware/setup.html').read_text(encoding='utf-8')
assert ')FRANKYPAGE"' not in html
(r / 'firmware/Franky/SetupPage.h').write_text(
    '// SPDX-License-Identifier: MIT\n// Generated from firmware/setup.html by scripts/embed_setup.py\n'
    '#pragma once\nconst char setupPage[] PROGMEM = R"FRANKYPAGE(' + html + ')FRANKYPAGE";\n', encoding='utf-8')
