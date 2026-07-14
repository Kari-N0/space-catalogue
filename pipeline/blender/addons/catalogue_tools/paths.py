"""Windows <-> WSL path conversion — the ONE place that owns it (ADDON.md §2)."""


def win_to_wsl(path, distro):
    r"""\\wsl.localhost\<distro>\home\... -> /home/...; D:\x -> /mnt/d/x."""
    p = str(path).replace("/", "\\")
    prefix = f"\\\\wsl.localhost\\{distro}"
    if p.lower().startswith(prefix.lower()):
        return p[len(prefix):].replace("\\", "/") or "/"
    if len(p) > 2 and p[1] == ":" and p[2] == "\\":
        return f"/mnt/{p[0].lower()}/" + p[3:].replace("\\", "/")
    raise ValueError(f"cannot map to WSL: {path!r} (expected \\\\wsl.localhost\\{distro}\\... or a drive path)")


def wsl_to_win(path, distro):
    """/home/... -> \\\\wsl.localhost\\<distro>\\home\\...; /mnt/d/x -> D:\\x."""
    p = str(path)
    if p.startswith("/mnt/") and len(p) > 6 and p[6] == "/":
        return f"{p[5].upper()}:\\" + p[7:].replace("/", "\\")
    if p.startswith("/"):
        return f"\\\\wsl.localhost\\{distro}" + p.replace("/", "\\")
    raise ValueError(f"not an absolute WSL path: {path!r}")
