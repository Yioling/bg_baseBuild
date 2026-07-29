# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\TS\\Desktop\\TSForce_MentorAI\\run.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\TS\\Desktop\\TSForce_MentorAI\\frontend\\index.html', 'frontend'), ('C:\\Users\\TS\\Desktop\\TSForce_MentorAI\\backend\\data\\sample_kb', 'backend/data/sample_kb'), ('C:\\Users\\TS\\Desktop\\TSForce_MentorAI\\.env.example', '.')],
    hiddenimports=['fastembed', 'fastembed.text.text_embedding', 'pypdf', 'docx', 'trafilatura', 'reportlab', 'fpdf', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='xinhuo_mentor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
