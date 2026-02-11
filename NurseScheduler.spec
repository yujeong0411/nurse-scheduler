# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# ortools와 holidays의 모든 구성 요소를 수집
tmp_ret = collect_all('ortools')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('holidays')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# ── 핵심: PyQt6 등에서 가져온 중복된 런타임 DLL을 강제로 제거 ──
# 이 코드는 바이너리 목록에서 msvcp140과 vcruntime140이 포함된 모든 파일을 삭제합니다.
# 시스템(C:\Windows\System32)에 있는 DLL을 대신 사용하게 유도합니다.
excluded_binaries = ['MSVCP140.dll', 'VCRUNTIME140.dll', 'VCRUNTIME140_1.dll']
a.binaries = [x for x in a.binaries if x[0].lower() not in excluded_binaries]

project_root = os.getcwd()

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NurseScheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # False로 설정 (충돌 방지)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
    stack_size=67108864,    # 스택 사이즈 유지
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,              # 반드시 False로 설정
    upx_exclude=[],
    name='NurseScheduler_2',
)
