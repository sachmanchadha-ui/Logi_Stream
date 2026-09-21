#!/usr/bin/env bash
# Portable toolchain bootstrap for LogiStream on Windows + Git Bash.
#
# winget has no Apache Maven package, and its Temurin MSI is machine-scope
# (needs UAC elevation). Both are installed here as portable archives under
# tools/ instead: no admin rights, and JAVA_HOME stays pinned to this repo
# so the machine default (JDK 26) is untouched.
#
# Rust uses the normal per-user rustup install (~/.cargo), no admin needed.
#
# Idempotent: re-running skips anything already present.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/tools"
MAVEN_VERSION="3.9.16"
mkdir -p "$TOOLS/dl"

PY_BIN=python
command -v python >/dev/null 2>&1 || PY_BIN=python3

unzip_to() {  # unzip_to <zipfile> <destdir>
  local zip="$1" dest="$2"
  mkdir -p "$dest"
  if [ -x /c/Windows/System32/tar.exe ]; then
    /c/Windows/System32/tar.exe -xf "$(cygpath -w "$zip")" -C "$(cygpath -w "$dest")"
  else
    powershell.exe -NoProfile -Command \
      "Expand-Archive -LiteralPath '$(cygpath -w "$zip")' -DestinationPath '$(cygpath -w "$dest")' -Force"
  fi
}

# ---------- Temurin 21 JDK ----------
if [ -x "$TOOLS/jdk21/bin/java.exe" ]; then
  echo "[jdk]   already installed"
else
  JDK_URL="https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"
  echo "[jdk]   downloading Temurin 21 (~200 MB) from adoptium.net ..."
  curl -sSL --max-time 1800 -o "$TOOLS/dl/jdk21.zip" "$JDK_URL"
  # a truncated or error-page download is the classic silent failure here
  sz=$(stat -c%s "$TOOLS/dl/jdk21.zip")
  [ "$sz" -gt 100000000 ] || { echo "[jdk]   ERROR: download is only $sz bytes"; exit 1; }
  rm -rf "$TOOLS/jdk21.tmp" && mkdir -p "$TOOLS/jdk21.tmp"
  unzip_to "$TOOLS/dl/jdk21.zip" "$TOOLS/jdk21.tmp"
  inner=$(find "$TOOLS/jdk21.tmp" -maxdepth 1 -mindepth 1 -type d | head -1)
  rm -rf "$TOOLS/jdk21" && mv "$inner" "$TOOLS/jdk21" && rm -rf "$TOOLS/jdk21.tmp"
  echo "[jdk]   installed -> tools/jdk21"
fi

# ---------- Apache Maven ----------
if [ -x "$TOOLS/maven/bin/mvn" ]; then
  echo "[maven] already installed"
else
  MVN_URL="https://dlcdn.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.zip"
  echo "[maven] $MVN_URL"
  curl -sSL --max-time 600 -o "$TOOLS/dl/maven.zip" "$MVN_URL"
  rm -rf "$TOOLS/maven.tmp" && mkdir -p "$TOOLS/maven.tmp"
  unzip_to "$TOOLS/dl/maven.zip" "$TOOLS/maven.tmp"
  rm -rf "$TOOLS/maven" && mv "$TOOLS/maven.tmp/apache-maven-${MAVEN_VERSION}" "$TOOLS/maven"
  rm -rf "$TOOLS/maven.tmp"
  chmod +x "$TOOLS/maven/bin/mvn"
  echo "[maven] installed -> tools/maven"
fi

# ---------- MinGW-w64 binutils (for the rust gnu toolchain) ----------
# This machine has no Visual Studio C++ toolset, so rust cannot use the msvc
# target: it shells out to link.exe, which on Git Bash resolves to coreutils'
# link.exe and fails. The gnu toolchain works instead, but rustup only ships
# dlltool/ld/gcc -- not the assembler dlltool itself invokes -- so linking dies
# with "dlltool.exe: CreateProcess". A portable binutils fixes it with no admin
# rights and no multi-GB Visual Studio install.
if [ -x "$TOOLS/mingw64/bin/as.exe" ]; then
  echo "[mingw] already installed"
else
  echo "[mingw] resolving the latest winlibs ucrt build..."
  MINGW_URL=$(curl -sS --max-time 120     "https://api.github.com/repos/brechtsanders/winlibs_mingw/releases/latest"     | "$PY_BIN" -c "
import json,sys
r=json.load(sys.stdin)
a=[x for x in r.get('assets',[]) if x['name'].endswith('.zip')
   and 'x86_64' in x['name'] and 'ucrt' in x['name'].lower() and 'posix' in x['name']]
print(sorted(a, key=lambda x: x['size'])[0]['browser_download_url'] if a else '')
")
  [ -n "$MINGW_URL" ] || { echo "[mingw] ERROR: could not resolve a download url"; exit 1; }
  echo "[mingw] downloading (~270 MB) $MINGW_URL"
  curl -sSL --max-time 2400 -o "$TOOLS/dl/mingw.zip" "$MINGW_URL"
  sz=$(stat -c%s "$TOOLS/dl/mingw.zip")
  [ "$sz" -gt 100000000 ] || { echo "[mingw] ERROR: download is only $sz bytes"; exit 1; }
  rm -rf "$TOOLS/mingw.tmp" && mkdir -p "$TOOLS/mingw.tmp"
  unzip_to "$TOOLS/dl/mingw.zip" "$TOOLS/mingw.tmp"
  inner=$(find "$TOOLS/mingw.tmp" -maxdepth 2 -mindepth 1 -type d -name "mingw64" | head -1)
  [ -n "$inner" ] || inner=$(find "$TOOLS/mingw.tmp" -maxdepth 1 -mindepth 1 -type d | head -1)
  rm -rf "$TOOLS/mingw64" && mv "$inner" "$TOOLS/mingw64" && rm -rf "$TOOLS/mingw.tmp"
  echo "[mingw] installed -> tools/mingw64"
fi

# ---------- Rust (per-user rustup) ----------
if command -v cargo >/dev/null 2>&1 || [ -x "$USERPROFILE/.cargo/bin/cargo.exe" ]; then
  echo "[rust]  already installed"
else
  echo "[rust]  downloading rustup-init..."
  curl -sSL --max-time 600 -o "$TOOLS/dl/rustup-init.exe" https://win.rustup.rs/x86_64
  "$TOOLS/dl/rustup-init.exe" -y --default-toolchain stable --profile minimal --no-modify-path
  echo "[rust]  installed -> $USERPROFILE/.cargo"
fi

echo
echo "Done. Source scripts/env.sh to put this toolchain on PATH."
