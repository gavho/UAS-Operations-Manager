import sys
import struct
from pathlib import Path

def pe_arch(path: Path):
    try:
        with open(path, "rb") as f:
            mz = f.read(2)
            if mz != b"MZ":
                return "not PE", None
            f.seek(0x3C)
            pe_off = struct.unpack("<I", f.read(4))[0]
            f.seek(pe_off)
            sig = f.read(4)
            if sig != b"PE\x00\x00":
                return "invalid PE sig", None
            mach = struct.unpack("<H", f.read(2))[0]
            if mach == 0x14C:
                return "x86", mach
            elif mach == 0x8664:
                return "x64", mach
            else:
                return f"machine=0x{mach:04x}", mach
    except Exception as e:
        return f"error: {e}", None

def main():
    project_root = Path(__file__).resolve().parent.parent
    lib_dir = project_root / "lib"

    print(f"Project root: {project_root}")
    print(f"Lib dir:      {lib_dir}")
    print(f"Python arch:  {struct.calcsize('P')*8}-bit")
    try:
        import sqlite3
        print(f"sqlite3 module version: {sqlite3.version}, SQLite runtime: {sqlite3.sqlite_version}")
    except Exception as e:
        print(f"sqlite3 version check error: {e}")

    if not lib_dir.is_dir():
        print("lib directory not found.")
        sys.exit(1)

    dlls = sorted(lib_dir.glob("*.dll"))
    if not dlls:
        print("No DLLs found in lib directory.")
        sys.exit(1)

    print("\nScanning DLL architectures in lib/:")
    mismatches = []
    python_is_64 = struct.calcsize('P')*8 == 64

    for dll in dlls:
        arch, mach = pe_arch(dll)
        print(f" - {dll.name:25s} -> {arch}")
        if arch in ("x86", "x64"):
            if python_is_64 and arch == "x86":
                mismatches.append((dll.name, arch))
            if not python_is_64 and arch == "x64":
                mismatches.append((dll.name, arch))

    if mismatches:
        print("\nMISMATCHES detected (DLL bitness differs from Python process):")
        for name, arch in mismatches:
            print(f" - {name}: {arch} vs Python {'x64' if python_is_64 else 'x86'}")
        print("\nAction: Replace the mismatched DLLs with the correct bitness for your Python.")
    else:
        print("\nNo obvious bitness mismatches detected. If load_extension still fails,")
        print("there may be dependency/version issues or missing VC runtimes.")

if __name__ == "__main__":
    main()
