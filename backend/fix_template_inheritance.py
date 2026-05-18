from pathlib import Path

root = Path(__file__).resolve().parent.parent / 'frontend' / 'templates'
replacements = {
    "{% extends 'trading/base.html' %}": "{% extends 'base.html' %}",
    "{% extends 'trading/admin/admin_base.html' %}": "{% extends 'admin/admin_base.html' %}",
}
changed_files = []

for path in root.rglob('*.html'):
    text = path.read_text(encoding='utf-8')
    new_text = text
    for old, new in replacements.items():
        new_text = new_text.replace(old, new)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        changed_files.append(path.relative_to(root.parent))

print('updated', len(changed_files), 'files')
for path in changed_files:
    print(path)
