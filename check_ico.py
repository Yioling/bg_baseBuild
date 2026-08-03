"""检查并修复 ICO 格式，确保 Windows EXE 图标可用"""
import struct
from pathlib import Path

ico_path = Path(__file__).parent / "thundersoft.ico"

with open(ico_path, 'rb') as f:
    data = f.read()

reserved, img_type, img_count = struct.unpack_from('<HHH', data, 0)
print(f'ICO header: reserved={reserved}, type={img_type}, count={img_count}')
print(f'Total size: {len(data)} bytes')

has_bmp = False
offset = 6
for i in range(img_count):
    w, h, colors, reserved2, planes, bpp, size, entry_offset = struct.unpack_from('<BBBBHHII', data, offset)
    if w == 0: w = 256
    if h == 0: h = 256
    entry_data = data[entry_offset:entry_offset+4]
    is_png = entry_data == b'\x89PNG'
    is_bmp = entry_data[:2] == b'\x28\x00' or entry_data[:4].startswith(b'BM')
    fmt = 'PNG' if is_png else ('BMP' if is_bmp else 'UNKNOWN')
    print(f'  Entry {i}: {w}x{h}, bpp={bpp}, size={size}, offset={entry_offset}, format={fmt}')
    if not is_png and not is_bmp:
        print(f'    First 8 bytes: {data[entry_offset:entry_offset+8].hex()}')
    if is_bmp:
        has_bmp = True
    offset += 16

if has_bmp:
    print('OK: Contains BMP entries (compatible with Windows EXE icons)')
else:
    print('WARNING: Only PNG entries - Windows EXE might not display icon properly!')
