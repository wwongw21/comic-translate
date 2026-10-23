# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve()
app_name = "Comic Translate"
resources_dir = project_root / "resources"
icon_path = resources_dir / "icons" / "icon.icns"

version_namespace = {}
version_path = project_root / "app" / "version.py"
exec(compile(version_path.read_text(encoding="utf-8"), str(version_path), "exec"), version_namespace)
app_version = version_namespace["__version__"]

analysis = Analysis(
    [str(project_root / "comic.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(resources_dir), "resources")],
    # comic.py imports the main controller by string when the splash worker
    # finishes, so static import analysis cannot discover this entry point.
    hiddenimports=["controller"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=app_name,
)
application = BUNDLE(
    collected,
    name=f"{app_name}.app",
    icon=str(icon_path),
    bundle_identifier="com.comiclabs.comictranslate",
    version=app_version,
    info_plist={
        "CFBundleDisplayName": app_name,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    },
)
