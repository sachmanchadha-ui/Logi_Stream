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

export PATH
unset _ls_root
