"""Small Linux boundary: candidate files + Python libs, no host data/network.

Landlock protects files even from same-UID code. Seccomp blocks network and
cross-process access. Unavailable production isolation fails closed.
"""
import ctypes
import errno
import os
import platform
import sys
from pathlib import Path


def filesystem_fence(readable, writable):
    if sys.platform != "linux" or platform.machine() not in ("x86_64", "aarch64"):
        raise RuntimeError("production isolation requires Linux Landlock")
    libc = ctypes.CDLL(None, use_errno=True)
    syscall = libc.syscall
    abi = syscall(444, 0, 0, 1)
    if abi < 1:
        raise RuntimeError("Landlock unavailable; refusing unisolated candidate")

    all_rights = (1 << 13) - 1
    if abi >= 2:
        all_rights |= 1 << 13
    if abi >= 3:
        all_rights |= 1 << 14
    rights = ctypes.c_uint64(all_rights)
    ruleset = syscall(444, ctypes.byref(rights), ctypes.sizeof(rights), 0)
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")

    class Beneath(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]

    try:
        for paths, access in ((readable, 1 | 4 | 8), (writable, all_rights)):
            for name in paths:
                path = Path(name).resolve()
                if not path.exists():
                    continue
                bits = access
                if not path.is_dir():
                    bits &= 1 | 2 | 4 | ((1 << 14) if abi >= 3 else 0)
                fd = os.open(str(path), os.O_PATH | os.O_CLOEXEC)
                try:
                    rule = Beneath(bits, fd)
                    if syscall(445, ruleset, 1, ctypes.byref(rule), 0) != 0:
                        raise OSError(ctypes.get_errno(), "landlock_add_rule")
                finally:
                    os.close(fd)
        if libc.prctl(38, 1, 0, 0, 0) != 0 or syscall(446, ruleset, 0) != 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self")
    finally:
        os.close(ruleset)


def syscall_fence(network=False):
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x7FFF0000)
    if not ctx:
        raise RuntimeError("seccomp initialization failed")
    blocked = ["ptrace", "process_vm_readv", "process_vm_writev", "pidfd_getfd", "mount", "umount2", "setns", "unshare", "bpf", "open_by_handle_at", "io_uring_setup"]
    if not network:
        blocked += ["socket", "connect", "bind", "listen", "accept", "accept4", "sendto", "sendmsg"]
    try:
        for name in blocked:
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, number, 0) != 0:
                raise RuntimeError("seccomp rule failed: " + name)
        if lib.seccomp_load(ctx) != 0:
            raise RuntimeError("seccomp load failed")
    finally:
        lib.seccomp_release(ctx)


def python_paths():
    return [sys.executable, Path(sys.base_prefix) / "lib", Path(sys.prefix) / "lib", Path(sys.prefix) / "pyvenv.cfg", "/usr/lib", "/lib", "/lib64", "/etc/ld.so.cache", "/dev/null", "/dev/urandom"]
