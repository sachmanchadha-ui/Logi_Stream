#!/usr/bin/env bash
# Source this (do not execute) to put the repo-pinned toolchain on PATH.
#   set -a; source .env; set +a; source scripts/env.sh
#
# Pins JAVA_HOME to tools/jdk21 (Temurin 21 LTS) for this repo only.
# The machine default JDK is left alone.

_ls_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "$_ls_root/tools/jdk21" ]; then
  export JAVA_HOME="$_ls_root/tools/jdk21"
  PATH="$JAVA_HOME/bin:$PATH"
fi

if [ -d "$_ls_root/tools/maven" ]; then
  export MAVEN_HOME="$_ls_root/tools/maven"
  PATH="$MAVEN_HOME/bin:$PATH"
fi

# rustup installs per-user; $USERPROFILE is a Windows path, so normalise it
_ls_cargo="${CARGO_HOME:-$HOME/.cargo}"
if [ ! -d "$_ls_cargo/bin" ] && command -v cygpath >/dev/null 2>&1; then
  _ls_cargo="$(cygpath "$USERPROFILE")/.cargo"
fi
if [ -d "$_ls_cargo/bin" ]; then
  PATH="$PATH:$_ls_cargo/bin"
fi
unset _ls_cargo

# A very old MinGW (aclocal-1.4 era) sits on the system PATH at G:\MINGWin.
# Its dlltool.exe shadows the one rustup ships and fails every windows-sys crate
# with "Invalid bfd target", so the gateway cannot link while it is visible.
# Dropped for this repo's shells only; the system PATH is untouched.
PATH="$(printf '%s' "$PATH" | tr ':' '
' | grep -v -i '^/g/MINGW/bin$' | paste -sd ':' -)"

# rustc looks up dlltool.exe on PATH and does NOT fall back to the copy rustup
# ships, so the gnu toolchain's self-contained bin directory has to be visible
# or every windows-sys crate fails with "error calling dlltool".
_ls_selfcontained="${CARGO_HOME:-$HOME/.cargo}"
_ls_selfcontained="$(dirname "$_ls_selfcontained")/.rustup/toolchains/stable-x86_64-pc-windows-gnu/lib/rustlib/x86_64-pc-windows-gnu/bin/self-contained"
if [ -d "$_ls_selfcontained" ]; then
  PATH="$_ls_selfcontained:$PATH"
fi
unset _ls_selfcontained

export PATH
unset _ls_root
