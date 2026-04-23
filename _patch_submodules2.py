import re

# edit_company.html - remove the two attendance submodule label blocks that got orphaned
with open('templates/admin/edit_company.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove orphaned attendance submodule labels (QR Code Generation + QR Scanner)
content = re.sub(
    r'\s*<label class="checkbox-item">\s*<input type="checkbox" name="attendance_qr_generation_enabled"[^>]*>.*?</label>',
    '',
    content,
    flags=re.DOTALL
)
content = re.sub(
    r'\s*<label class="checkbox-item">\s*<input type="checkbox" name="attendance_qr_scanner_enabled"[^>]*>.*?</label>',
    '',
    content,
    flags=re.DOTALL
)
# Also remove from the submit validation JS querySelectorAll if present
content = content.replace(
    ', input[name="attendance_qr_generation_enabled"], input[name="attendance_qr_scanner_enabled"]',
    ''
)

with open('templates/admin/edit_company.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('edit_company.html patched')

# add_company.html - same
with open('templates/admin/add_company.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r'\s*<label class="checkbox-item">\s*<input type="checkbox" name="attendance_qr_generation_enabled"[^>]*>.*?</label>',
    '',
    content,
    flags=re.DOTALL
)
content = re.sub(
    r'\s*<label class="checkbox-item">\s*<input type="checkbox" name="attendance_qr_scanner_enabled"[^>]*>.*?</label>',
    '',
    content,
    flags=re.DOTALL
)
content = content.replace(
    ', input[name="attendance_qr_generation_enabled"], input[name="attendance_qr_scanner_enabled"]',
    ''
)

with open('templates/admin/add_company.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('add_company.html patched')

# Verify
for fname in ['templates/admin/edit_company.html', 'templates/admin/add_company.html']:
    with open(fname, 'r', encoding='utf-8') as f:
        c = f.read()
    remaining = [x for x in ['attendance_qr_generation_enabled', 'attendance_qr_scanner_enabled', 'attendanceSubmoduleGroup', 'QR Code Generation', 'QR Scanner (Canteen)'] if x in c]
    print(f'{fname}: remaining refs = {remaining}')
