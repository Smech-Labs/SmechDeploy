# SmechOS independent userland bootstrap -- design plan (not yet executed)

## Why

`restore_utils.py`, `restore_lib64.py`, and `restore_etc.py` currently copy
`/usr/bin`, `/usr/lib64`, and `/etc` files straight out of
`/mnt/kaymium_sovereign` -- a private reference host filesystem (itself just
the build machine's ordinary Ubuntu/glibc/GNU userland). That means SmechOS's
base userland isn't actually built by SmechOS at all; it's borrowed wholesale
from whatever Linux distro happens to be running on the build machine. This
plan replaces that with a real from-source bootstrap, consistent with
SmechOS's own "independent, own build system" identity.

## Confirmed stack

- **Compiler**: LLVM/Clang -- no GCC anywhere in the target.
- **libc**: musl -- no glibc anywhere in the target.
- **Shell**: GNU Bash -- unchanged, already compiled by
  `01_compile_core_system.sh`.
- **Coreutils/grep/sed/tar/etc.**: real GNU coreutils, GNU grep, GNU sed, GNU
  tar, etc. -- kept for familiar behavior, but compiled against musl+Clang
  instead of glibc+GCC.

The **build host's** existing Clang/LLVM (installed via `apt`, used the same
way the host's existing GCC/make is already used by
`01_compile_core_system.sh` to compile bash/openrc/grub) is the compiler
*tool*. Only musl and the userland packages below are compiled from source
*into the target* -- compiling LLVM/Clang itself from source is out of scope
(realistically a multi-hour build on its own, and the toolchain used to build
the target doesn't need to itself live in the target).

## Open question to resolve before execution

`01_compile_core_system.sh` already compiled GNU Bash once, linked against
whatever libc was on the build host's `$PATH` at the time (effectively
glibc, since that's what host clang/gcc links against by default). Keeping
"GNU Bash, unchanged" could mean either:
  (a) leave that existing glibc-linked bash binary as-is, or
  (b) recompile bash against musl too, for full consistency (no glibc
      anywhere in the target, including transitively via bash's own linking).
Recommend (b) for actual independence, but flagging this explicitly rather
than silently deciding it.

## Build order

### Stage 0 -- host tooling (not written into the target)
1. Verify/install host Clang/LLVM via `apt` (`clang`, `lld`, `llvm`).
   No source compile -- this is build-host tooling only, same role the
   host's existing `gcc`/`make` already play in `01_compile_core_system.sh`.

### Stage 1 -- musl libc
2. **musl** (latest stable, e.g. 1.2.5) -- `./configure --prefix=/usr
   CC=clang && make && make DESTDIR=$SMECH_TARGET install`. Provides
   `/usr/lib/libc.so`, musl's own minimal headers (musl bundles what it
   needs; no separate "Linux API headers" package required, unlike glibc),
   and the `musl-gcc`-style wrapper (`musl-clang` here) used to compile
   everything below against it instead of the host's glibc.

### Stage 2 -- userland, compiled with `musl-clang` from Stage 1
Each entry: package, why it's needed, what it currently replaces from
`restore_utils.py`'s copy-from-host behavior.

3. **GNU coreutils** -- `ls`, `cat`, `cp`, `mv`, `rm`, `mkdir`, `chmod`,
   `chown`, `ln`, `df`, `du`, etc. (the bulk of `/usr/bin`).
4. **GNU grep**
5. **GNU sed**
6. **GNU tar**
7. **gzip** and **xz** -- compression tools several other build steps
   already assume exist (`tar -xf foo.tar.xz` is used throughout the
   existing `bin/*.sh` scripts).
8. **GNU findutils** -- `find`, `xargs`.
9. **GNU diffutils** -- `diff`, `cmp`.
10. **GNU gawk**
11. **GNU make** -- needed on the *target* too (distinct from the host's
    `make` already used to drive these builds), since SmechOS itself ships
    a package manager (`spk`) that may need to build things post-install.
12. **file** -- magic-number file-type detection, a common implicit
    dependency of build/packaging tooling.
13. **(decision pending above)** GNU Bash, either left as the existing
    glibc-linked binary or recompiled against musl.

### Stage 3 -- `/etc` skeleton
14. Replace `restore_etc.py`'s host-copy with a small set of **hand-authored**
    base `/etc` files (`passwd`, `group`, `shadow` skeleton, `hostname`,
    `fstab` template, `nsswitch.conf` if needed by musl's NSS-equivalent,
    shell profile files) committed directly into `SmechDeploy` rather than
    sourced from any external machine. This is the one piece that was never
    really a "compile from source" problem -- it's small, static
    configuration content that should just be written by hand once and
    version-controlled.

### Stage 4 -- integration
15. Update `restore_utils.py`/`restore_lib64.py`/`restore_etc.py` (or
    replace them with new scripts, e.g. `bootstrap_musl.sh`,
    `bootstrap_userland.sh`) to write the Stage 1-3 outputs into
    `images/part2.img` via the same `debugfs -w` mechanism already used --
    only the *source* of the files changes, not the image-writing
    mechanism itself.
16. Update `build_order.txt` to point at the new scripts in place of the
    old `restore_*.py` entries.
17. Remove the `/mnt/kaymium_sovereign` dependency entirely once the above
    is verified working -- including deleting `reference_root.py` (drafted
    earlier this session, now obsolete under this plan) and the
    `smechdeploy-build-reference` GitHub repo's role in the build (it can
    stay published for historical/transparency reasons, just unused by the
    actual build going forward).

## Realistic time/compute expectations

musl compiles in minutes, not hours -- this is the main reason this plan is
far more tractable than a glibc/GCC LFS bootstrap. GNU coreutils/grep/sed/
tar/findutils/diffutils/gawk/make are all individually fast builds (each
well under 10 minutes on typical hardware). The realistic total for Stage
1+2 is on the order of 30-60 minutes of actual compile time, not the
multi-hour range a full glibc+GCC LFS bootstrap would require. This is a
same-session-feasible piece of work once the plan is approved.

## Not yet done

Nothing has been executed. No source has been downloaded, no scripts beyond
this plan have been written. Awaiting review/approval before Stage 0 begins.
