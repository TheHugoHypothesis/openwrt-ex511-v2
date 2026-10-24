#!/usr/bin/env python3
"""Check local Markdown file links and privacy markers in the public EX511 guide."""
from pathlib import Path
import re
import sys
import subprocess
from urllib.parse import unquote

root = Path(__file__).resolve().parents[2]
files = [root/'README.md', root/'README.pt-BR.md', *sorted((root/'docs/ex511-v2').glob('*.md'))]
errors = []
for path in files:
    text = path.read_text()
    if text.count('```') % 2:
        errors.append(f'{path.relative_to(root)}: unbalanced code fence')
    for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^\s)]+)\)', text):
        target = unquote(target.strip('<>')).split('#', 1)[0]
        if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            continue
        if not (path.parent/target).exists():
            errors.append(f'{path.relative_to(root)}: missing target {target}')
# Machine-specific paths must not enter new maintained reader guides.
maintained = ['README.md','hardware.md','installation-ssh.md','installation-ssh.pt-BR.md',
              'build-current.md','results.md','recovery.md','network-operation.md','credits.md','publication.md']
for name in maintained:
    path = root/'docs/ex511-v2'/name
    if re.search(r'/home/(?!USER\b|user\b)[A-Za-z0-9_.-]+/', path.read_text()):
        errors.append(f'{path.relative_to(root)}: personal home path')
for name in ['installation-ssh.md', 'installation-ssh.pt-BR.md', 'build-current.md']:
    path = root/'docs/ex511-v2'/name
    for index, block in enumerate(re.findall(r'```sh\n(.*?)```', path.read_text(), re.S), 1):
        check = subprocess.run(['sh', '-n'], input=block, text=True, capture_output=True)
        if check.returncode:
            errors.append(f'{path.relative_to(root)}: shell block {index} fails sh -n')
if errors:
    print('\n'.join(errors), file=sys.stderr)
    raise SystemExit(1)
print(f'Checked {len(files)} Markdown files: local links, fences, maintained shell examples and path hygiene pass.')
