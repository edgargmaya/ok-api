#!/usr/bin/env python3
"""
Analiza repositorios on-prem (solo rama master) antes de migrarlos a GitHub.

Para cada ruta en repos_to_check.txt:
  - clona vía SSH únicamente la rama master
  - estima el peso de master (clon empaquetado, historial unpacked, árbol HEAD)
  - detecta blobs > 100 MB con el mismo algoritmo que ghe_migrator
  - si es Java, clasifica jar/war/ear de HEAD como Maven (eliminable) o in-house
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_MAX_BLOB_MB = 100
DEFAULT_SSH_PREFIX = "ssh://git@scm.mx.att.com/"
DEFAULT_BRANCH = "master"
MAVEN_SEARCH = "https://search.maven.org/solrsearch/select"
REPO1_BASE = "https://repo1.maven.org/maven2"
USER_AGENT = "att-repo-analizer/1.0"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# groupIds corporativos: no se consideran bibliotecas públicas de Maven
DEFAULT_INHOUSE_PREFIXES = (
    "com.att",
    "att.",
    "mx.att",
    "com.mx.att",
    "mx.com.att",
    "com.attmexico",
    "attmexico",
    "telmex",
    "telemex",
    "com.telmex",
    "com.telemex",
    "mx.com.telmex",
)

JAVA_ARCHIVE_EXTS = (".jar", ".war", ".ear")
JAVA_MARKERS = (
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "web.xml",
    ".java",
    ".jar",
    ".war",
    ".ear",
)


def _human_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _xml_local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _is_ssh_url(url: str) -> bool:
    return url.startswith(("ssh://", "git@"))


def run_cmd(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    capture: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=full_env,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Comando falló: {' '.join(cmd)}\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
    return result


def setup_ssh(private_key: str, logger: logging.Logger) -> None:
    """Escribe la llave SSH igual que el entrypoint del migrator."""
    key = private_key.replace("\r\n", "\n").strip()
    if not key:
        raise RuntimeError("SSH_PRIVATE_KEY está vacía")
    if "\\n" in key and "BEGIN" in key:
        key = key.replace("\\n", "\n")
    if not key.endswith("\n"):
        key += "\n"

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    key_path = ssh_dir / "id_rsa"
    key_path.write_text(key, encoding="utf-8")
    key_path.chmod(0o600)

    config_path = ssh_dir / "config"
    config_path.write_text(
        "Host *\n"
        "    IdentityFile ~/.ssh/id_rsa\n"
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking no\n"
        "    UserKnownHostsFile /dev/null\n",
        encoding="utf-8",
    )
    config_path.chmod(0o644)
    os.environ["GIT_SSH_COMMAND"] = (
        f"ssh -i {key_path} -o IdentitiesOnly=yes "
        "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    )
    logger.info("Llave SSH configurada en %s", key_path)


def read_repo_list(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo de repos: {path}")
    repos: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            line = line.split("|", 1)[0].strip()
        elif "\t" in line:
            line = line.split("\t", 1)[0].strip()
        if line:
            repos.append(line)
    return repos


def resolve_source_url(entry: str, ssh_prefix: str) -> str:
    item = entry.strip()
    if _is_ssh_url(item) or item.startswith(("http://", "https://")):
        return item
    return ssh_prefix.rstrip("/") + "/" + item.lstrip("/")


def git_env() -> dict:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def list_remote_heads(source_url: str) -> list[str]:
    result = run_cmd(
        ["git", "ls-remote", "--heads", source_url],
        env=git_env(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"No se pudieron listar ramas remotas de {source_url}:\n{result.stderr}"
        )
    heads: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/heads/"):
            heads.append(ref[len("refs/heads/") :])
    return heads


def dir_size_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


@dataclass
class BlobInfo:
    blob_id: str
    path: str
    size_bytes: int
    paths: list[str]
    intro_commit: Optional[str] = None
    intro_author_name: Optional[str] = None
    intro_author_email: Optional[str] = None
    intro_date: Optional[str] = None

    def to_report_line(self) -> str:
        ext = Path(self.path).suffix or "(sin extensión)"
        author = f"{self.intro_author_name or '?'} <{self.intro_author_email or '?'}>"
        paths_str = ", ".join(sorted(set(self.paths))) if len(self.paths) > 1 else self.path
        return (
            f"  Path: {paths_str}\n"
            f"  Size: {self.size_bytes} bytes ({_human_size(self.size_bytes)})\n"
            f"  Type: {ext}\n"
            f"  Blob ID: {self.blob_id}\n"
            f"  Introduced in commit: {self.intro_commit or '?'}\n"
            f"  Author: {author}\n"
            f"  Date: {self.intro_date or '?'}\n"
        )


def find_large_blobs(
    repo_path: Path,
    max_bytes: int,
    logger: logging.Logger,
    revision: str = "HEAD",
) -> dict[str, BlobInfo]:
    """
    Encuentra blobs mayores a max_bytes en el historial alcanzable desde revision.

    Misma técnica que ghe_migrator/python-migrator/migrate_ssh.py (rev-list | cat-file),
    acotada a la rama a migrar en lugar de --all.
    """
    logger.info("Escaneando historial de %s en busca de blobs grandes...", revision)

    proc1 = subprocess.Popen(
        ["git", "rev-list", revision, "--objects"],
        cwd=repo_path,
        stdout=subprocess.PIPE,
        text=True,
    )
    proc2 = subprocess.Popen(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)"],
        cwd=repo_path,
        stdin=proc1.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )
    if proc1.stdout:
        proc1.stdout.close()
    stdout, _ = proc2.communicate()
    proc1.wait()

    lines = (stdout or "").strip().split("\n") if stdout else []
    if not lines:
        return {}

    blob_to_paths: dict[str, list[str]] = {}
    blob_to_size: dict[str, int] = {}
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        obj_type, obj_id, size_str = parts[0], parts[1], parts[2]
        rest = parts[3] if len(parts) > 3 else ""
        if obj_type != "blob":
            continue
        try:
            size = int(size_str)
        except ValueError:
            continue
        if size <= max_bytes:
            continue
        path = rest.strip() if rest else "(sin path)"
        blob_to_paths.setdefault(obj_id, []).append(path)
        blob_to_size[obj_id] = size

    blobs: dict[str, BlobInfo] = {}
    for blob_id, paths in blob_to_paths.items():
        size = blob_to_size.get(blob_id, 0)
        primary_path = paths[0] if paths else "(desconocido)"
        intro_commit = intro_author = intro_email = intro_date = None
        try:
            result = run_cmd(
                [
                    "git",
                    "log",
                    revision,
                    "--reverse",
                    f"--find-object={blob_id}",
                    "--format=%H%x09%an%x09%ae%x09%ai",
                ],
                cwd=repo_path,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                first_line = result.stdout.strip().split("\n")[0]
                cols = first_line.split("\t")
                if len(cols) >= 4:
                    intro_commit, intro_author, intro_email, intro_date = cols[:4]
        except Exception as exc:
            logger.warning("No se pudo obtener commit intro para blob %s: %s", blob_id, exc)

        blobs[blob_id] = BlobInfo(
            blob_id=blob_id,
            path=primary_path,
            size_bytes=size,
            paths=paths,
            intro_commit=intro_commit,
            intro_author_name=intro_author,
            intro_author_email=intro_email,
            intro_date=intro_date,
        )
    return blobs


def sum_reachable_blob_sizes(repo_path: Path, revision: str) -> tuple[int, int]:
    """Retorna (bytes unpacked de blobs únicos, cantidad de blobs) en revision."""
    proc1 = subprocess.Popen(
        ["git", "rev-list", revision, "--objects"],
        cwd=repo_path,
        stdout=subprocess.PIPE,
        text=True,
    )
    proc2 = subprocess.Popen(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize)"],
        cwd=repo_path,
        stdin=proc1.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )
    if proc1.stdout:
        proc1.stdout.close()
    stdout, _ = proc2.communicate()
    proc1.wait()

    total = 0
    count = 0
    seen: set[str] = set()
    for line in (stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] != "blob":
            continue
        blob_id = parts[1]
        if blob_id in seen:
            continue
        seen.add(blob_id)
        try:
            total += int(parts[2])
            count += 1
        except ValueError:
            continue
    return total, count


def head_tree_entries(repo_path: Path, revision: str) -> list[tuple[str, str, int, str]]:
    """Lista (mode, blob_id, size, path) del árbol HEAD de revision."""
    result = run_cmd(
        ["git", "ls-tree", "-r", "-l", revision],
        cwd=repo_path,
        check=False,
    )
    if result.returncode != 0:
        return []
    entries: list[tuple[str, str, int, str]] = []
    for line in result.stdout.splitlines():
        # 100644 blob <sha> <size>\t<path>
        try:
            meta, path = line.split("\t", 1)
        except ValueError:
            continue
        parts = meta.split()
        if len(parts) < 4 or parts[1] != "blob":
            continue
        try:
            size = int(parts[3])
        except ValueError:
            continue
        entries.append((parts[0], parts[2], size, path))
    return entries


def git_blob_bytes(repo_path: Path, blob_id: str) -> bytes:
    result = subprocess.run(
        ["git", "cat-file", "blob", blob_id],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    return result.stdout


def parse_pom_properties(data: bytes) -> dict[str, str]:
    props: dict[str, str] = {}
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return props
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def read_zip_entry(zf: zipfile.ZipFile, name: str) -> Optional[bytes]:
    try:
        return zf.read(name)
    except KeyError:
        return None


def extract_maven_coords_from_jar(content: bytes) -> dict[str, str]:
    """Lee META-INF/maven/**/pom.properties y MANIFEST.MF."""
    coords: dict[str, str] = {}
    if not content.startswith(b"PK"):
        return coords
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            pom_props_names = [
                n for n in zf.namelist()
                if n.startswith("META-INF/maven/") and n.endswith("pom.properties")
            ]
            if pom_props_names:
                props = parse_pom_properties(zf.read(pom_props_names[0]))
                if props.get("groupId"):
                    coords["groupId"] = props["groupId"]
                if props.get("artifactId"):
                    coords["artifactId"] = props["artifactId"]
                if props.get("version"):
                    coords["version"] = props["version"]
            manifest = read_zip_entry(zf, "META-INF/MANIFEST.MF")
            if manifest:
                for raw in manifest.decode("utf-8", errors="replace").splitlines():
                    if ":" not in raw:
                        continue
                    key, value = raw.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if key == "Implementation-Title" and "artifactId" not in coords:
                        coords["manifestTitle"] = value
                    if key == "Implementation-Version" and "version" not in coords:
                        coords["manifestVersion"] = value
                    if key == "Bundle-SymbolicName" and "groupId" not in coords:
                        coords["bundleName"] = value
    except zipfile.BadZipFile:
        coords["not_zip"] = "true"
    return coords


def list_nested_war_libs(content: bytes) -> list[dict]:
    nested: list[dict] = []
    if not content.startswith(b"PK"):
        return nested
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                lower = name.lower()
                if not lower.endswith(JAVA_ARCHIVE_EXTS):
                    continue
                in_lib_dir = (
                    "web-inf/lib/" in lower
                    or lower.startswith("lib/")
                    or "/lib/" in lower
                )
                if not in_lib_dir:
                    continue
                info = zf.getinfo(name)
                nested.append(
                    {
                        "path": name,
                        "size_bytes": info.file_size,
                        "size_human": _human_size(info.file_size),
                    }
                )
    except zipfile.BadZipFile:
        return nested
    return nested


def parse_pom_dependencies(xml_bytes: bytes) -> list[tuple[str, str, str]]:
    deps: list[tuple[str, str, str]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return deps

    def text_of(node: ET.Element, child: str) -> str:
        for el in list(node):
            if _xml_local(el.tag) == child:
                return (el.text or "").strip()
        return ""

    for el in root.iter():
        if _xml_local(el.tag) != "dependency":
            continue
        gid = text_of(el, "groupId")
        aid = text_of(el, "artifactId")
        ver = text_of(el, "version")
        if gid and aid:
            deps.append((gid, aid, ver))
    return deps


FILENAME_VERSION_RE = re.compile(
    r"^(?P<artifact>.+)-(?P<version>\d[\w.\-]*)\.(?P<ext>jar|war|ear)$",
    re.IGNORECASE,
)


def coords_from_filename(filename: str) -> dict[str, str]:
    name = Path(filename).name
    match = FILENAME_VERSION_RE.match(name)
    if not match:
        return {}
    return {
        "artifactId": match.group("artifact"),
        "version": match.group("version"),
    }


class MavenLookup:
    def __init__(self, enabled: bool, logger: logging.Logger):
        self.enabled = enabled
        self.logger = logger
        self._sha1_cache: dict[str, Optional[dict]] = {}
        self._gav_cache: dict[str, bool] = {}
        self.ok = True
        self.failures = 0

    def _http_json(self, url: str) -> Optional[dict]:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            self.failures += 1
            if self.failures >= 8:
                self.ok = False
            self.logger.warning("Consulta Maven falló (%s): %s", url, exc)
            return None

    def _http_exists(self, url: str) -> Optional[bool]:
        req = Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(req, timeout=15) as resp:
                return 200 <= getattr(resp, "status", 200) < 400
        except HTTPError as exc:
            if exc.code in (404, 410):
                return False
            if exc.code in (405, 501):
                return self._http_exists_get(url)
            self.failures += 1
            self.logger.warning("HEAD Maven falló (%s): %s", url, exc)
            return None
        except (URLError, TimeoutError) as exc:
            self.failures += 1
            if self.failures >= 8:
                self.ok = False
            self.logger.warning("HEAD Maven falló (%s): %s", url, exc)
            return None

    def _http_exists_get(self, url: str) -> Optional[bool]:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
        try:
            with urlopen(req, timeout=15) as resp:
                return 200 <= getattr(resp, "status", 200) < 400
        except HTTPError as exc:
            if exc.code in (404, 410):
                return False
            self.failures += 1
            return None
        except (URLError, TimeoutError):
            self.failures += 1
            return None

    def by_sha1(self, sha1: str) -> Optional[dict]:
        if not self.enabled or not self.ok:
            return None
        if sha1 in self._sha1_cache:
            return self._sha1_cache[sha1]
        query = quote(f"1:{sha1}", safe=":")
        url = f"{MAVEN_SEARCH}?q={query}&rows=1&wt=json"
        payload = self._http_json(url)
        time.sleep(0.15)
        doc = None
        if payload:
            docs = payload.get("response", {}).get("docs") or []
            if docs:
                doc = docs[0]
        self._sha1_cache[sha1] = doc
        return doc

    def gav_on_repo1(self, group_id: str, artifact_id: str, version: str, ext: str) -> Optional[bool]:
        if not self.enabled or not self.ok:
            return None
        if not (group_id and artifact_id and version):
            return None
        key = f"{group_id}:{artifact_id}:{version}:{ext}"
        if key in self._gav_cache:
            return self._gav_cache[key]
        path = f"{group_id.replace('.', '/')}/{artifact_id}/{version}/{artifact_id}-{version}.{ext}"
        exists = self._http_exists(f"{REPO1_BASE}/{path}")
        time.sleep(0.1)
        if exists is not None:
            self._gav_cache[key] = exists
        return exists


def is_inhouse_group(group_id: str, prefixes: tuple[str, ...]) -> bool:
    gid = (group_id or "").strip().lower()
    if not gid:
        return False
    for prefix in prefixes:
        p = prefix.lower().rstrip(".")
        if gid == p or gid.startswith(p + "."):
            return True
    return False


def classify_library(
    path: str,
    size_bytes: int,
    content: Optional[bytes],
    pom_deps: set[tuple[str, str]],
    lookup: MavenLookup,
    inhouse_prefixes: tuple[str, ...],
) -> dict:
    kind = Path(path).suffix.lower().lstrip(".") or "bin"
    sha1 = hashlib.sha1(content).hexdigest() if content else ""
    coords = extract_maven_coords_from_jar(content) if content else {}
    from_name = coords_from_filename(path)
    group_id = coords.get("groupId", "")
    artifact_id = coords.get("artifactId") or from_name.get("artifactId", "")
    version = coords.get("version") or from_name.get("version", "")
    nested = []
    if kind in ("war", "ear") and content:
        nested = list_nested_war_libs(content)

    maven_doc = lookup.by_sha1(sha1) if sha1 else None
    repo1_exists = lookup.gav_on_repo1(group_id, artifact_id, version, kind) if group_id else None
    in_pom = (group_id, artifact_id) in pom_deps if group_id and artifact_id else (
        any(aid == artifact_id for _gid, aid in pom_deps) if artifact_id else False
    )

    if maven_doc:
        group_id = group_id or maven_doc.get("g", "")
        artifact_id = artifact_id or maven_doc.get("a", "")
        version = version or maven_doc.get("v", "")
        classification = "maven_central"
        recommendation = "ELIMINABLE"
        reason = (
            f"SHA1 exacto encontrado en Maven Central "
            f"({maven_doc.get('g')}:{maven_doc.get('a')}:{maven_doc.get('v')})"
        )
    elif is_inhouse_group(group_id, inhouse_prefixes):
        classification = "inhouse"
        recommendation = "CONSERVAR"
        reason = f"groupId corporativo/in-house: {group_id}"
    elif repo1_exists:
        classification = "maven_modified"
        recommendation = "REVISAR"
        reason = (
            "Existe GAV en Maven Central pero el SHA1 no coincide; "
            "puede ser una copia parcheada o reempaquetada. No eliminar a ciegas."
        )
    elif in_pom and group_id and not is_inhouse_group(group_id, inhouse_prefixes):
        classification = "maven_from_pom"
        recommendation = "ELIMINABLE"
        reason = (
            f"Declarada en pom.xml como {group_id}:{artifact_id}:{version or '?'} "
            "y no es groupId in-house. Puede resolverse desde Maven."
        )
    elif not content:
        classification = "unread"
        recommendation = "REVISAR"
        reason = "No se pudo leer el blob para clasificarlo"
    elif coords.get("not_zip"):
        classification = "not_an_archive"
        recommendation = "REVISAR"
        reason = "La extensión es jar/war/ear pero el contenido no es un ZIP válido"
    elif not lookup.enabled or not lookup.ok:
        if group_id and not is_inhouse_group(group_id, inhouse_prefixes):
            classification = "lookup_failed_maybe_maven"
            recommendation = "REVISAR"
            reason = "Sin consulta a Maven Central; metadata Maven presente pero no verificada"
        else:
            classification = "lookup_failed"
            recommendation = "CONSERVAR"
            reason = "Sin consulta a Maven Central y sin evidencia de biblioteca pública"
    else:
        classification = "not_in_maven"
        recommendation = "CONSERVAR"
        reason = (
            "No existe en Maven Central (SHA1) y no es resoluble como GAV público. "
            "Tratar como biblioteca in-house o copiada de otro proyecto."
        )

    maven_coords = None
    if group_id and artifact_id:
        maven_coords = f"{group_id}:{artifact_id}:{version or '?'}"

    return {
        "path": path,
        "size_bytes": size_bytes,
        "size_human": _human_size(size_bytes),
        "kind": kind,
        "sha1": sha1,
        "group_id": group_id or None,
        "artifact_id": artifact_id or None,
        "version": version or None,
        "maven_coords": maven_coords,
        "classification": classification,
        "recommendation": recommendation,
        "reason": reason,
        "nested_libs": nested,
        "in_pom": bool(in_pom),
    }


@dataclass
class RepoReport:
    repo: str
    source_url: str
    status: str
    error: Optional[str] = None
    has_master: bool = False
    available_branches: list[str] = field(default_factory=list)
    commit_count: int = 0
    clone_size_bytes: int = 0
    unpacked_history_bytes: int = 0
    unpacked_blob_count: int = 0
    head_tree_bytes: int = 0
    head_file_count: int = 0
    large_blob_count: int = 0
    large_blob_bytes: int = 0
    large_blobs: list[dict] = field(default_factory=list)
    is_java: bool = False
    jar_count_head: int = 0
    war_count_head: int = 0
    ear_count_head: int = 0
    history_archive_count: int = 0
    history_archive_bytes: int = 0
    maven_deletable_count: int = 0
    maven_deletable_bytes: int = 0
    inhouse_count: int = 0
    inhouse_bytes: int = 0
    review_count: int = 0
    review_bytes: int = 0
    libraries: list[dict] = field(default_factory=list)
    migration_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["clone_size_human"] = _human_size(self.clone_size_bytes)
        data["unpacked_history_human"] = _human_size(self.unpacked_history_bytes)
        data["head_tree_human"] = _human_size(self.head_tree_bytes)
        data["large_blob_human"] = _human_size(self.large_blob_bytes)
        data["maven_deletable_human"] = _human_size(self.maven_deletable_bytes)
        data["inhouse_human"] = _human_size(self.inhouse_bytes)
        return data


def looks_like_java(paths: list[str]) -> bool:
    lowered = [p.lower() for p in paths]
    for marker in JAVA_MARKERS:
        if marker.startswith("."):
            if any(p.endswith(marker) for p in lowered):
                return True
        else:
            if any(p.endswith("/" + marker) or p == marker or p.endswith(marker) for p in lowered):
                return True
    return False


def analyze_repo(
    entry: str,
    source_url: str,
    work_root: Path,
    branch: str,
    max_blob_bytes: int,
    lookup: MavenLookup,
    inhouse_prefixes: tuple[str, ...],
    logger: logging.Logger,
    keep_clone: bool,
) -> RepoReport:
    report = RepoReport(repo=entry, source_url=source_url, status="ok")
    work_dir: Optional[Path] = None
    try:
        logger.info("Listando ramas remotas...")
        heads = list_remote_heads(source_url)
        report.available_branches = heads
        has_branch = branch in heads
        report.has_master = has_branch
        if not has_branch:
            report.status = "sin_rama_master"
            report.error = (
                f"No existe la rama '{branch}'. Ramas disponibles: "
                + (", ".join(heads) if heads else "(ninguna)")
            )
            report.migration_notes.append(
                f"No se puede estimar la migración de '{branch}' porque no existe en origen."
            )
            return report

        work_dir = Path(tempfile.mkdtemp(prefix="analizer-", dir=str(work_root)))
        logger.info("Clonando %s (bare, solo %s)...", source_url, branch)
        run_cmd(
            [
                "git",
                "clone",
                "--bare",
                "--single-branch",
                "--branch",
                branch,
                source_url,
                str(work_dir),
            ],
            env=git_env(),
        )

        report.clone_size_bytes = dir_size_bytes(work_dir)
        count_result = run_cmd(
            ["git", "rev-list", "--count", branch],
            cwd=work_dir,
            check=False,
        )
        if count_result.returncode == 0 and count_result.stdout.strip().isdigit():
            report.commit_count = int(count_result.stdout.strip())

        unpacked, blob_count = sum_reachable_blob_sizes(work_dir, branch)
        report.unpacked_history_bytes = unpacked
        report.unpacked_blob_count = blob_count

        entries = head_tree_entries(work_dir, branch)
        report.head_file_count = len(entries)
        report.head_tree_bytes = sum(size for _m, _b, size, _p in entries)
        head_paths = [path for _m, _b, _s, path in entries]
        report.is_java = looks_like_java(head_paths)

        large = find_large_blobs(work_dir, max_blob_bytes, logger, revision=branch)
        report.large_blob_count = len(large)
        report.large_blob_bytes = sum(b.size_bytes for b in large.values())
        report.large_blobs = []
        for blob in sorted(large.values(), key=lambda item: -item.size_bytes):
            report.large_blobs.append(
                {
                    "blob_id": blob.blob_id,
                    "path": blob.path,
                    "paths": blob.paths,
                    "size_bytes": blob.size_bytes,
                    "size_human": _human_size(blob.size_bytes),
                    "extension": Path(blob.path).suffix or "(sin extensión)",
                    "intro_commit": blob.intro_commit,
                    "intro_author_name": blob.intro_author_name,
                    "intro_author_email": blob.intro_author_email,
                    "intro_date": blob.intro_date,
                    "report_line": blob.to_report_line(),
                }
            )

        # Inventario de jar/war/ear en todo el historial de master (peso, no clasificación)
        hist_ids: set[str] = set()
        hist_bytes = 0
        proc1 = subprocess.Popen(
            ["git", "rev-list", branch, "--objects"],
            cwd=work_dir,
            stdout=subprocess.PIPE,
            text=True,
        )
        proc2 = subprocess.Popen(
            ["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)"],
            cwd=work_dir,
            stdin=proc1.stdout,
            stdout=subprocess.PIPE,
            text=True,
        )
        if proc1.stdout:
            proc1.stdout.close()
        stdout, _ = proc2.communicate()
        proc1.wait()
        for line in (stdout or "").splitlines():
            parts = line.split(None, 3)
            if len(parts) < 3 or parts[0] != "blob":
                continue
            path = parts[3].strip().lower() if len(parts) > 3 else ""
            if not path.endswith(JAVA_ARCHIVE_EXTS):
                continue
            blob_id = parts[1]
            if blob_id in hist_ids:
                continue
            hist_ids.add(blob_id)
            try:
                hist_bytes += int(parts[2])
            except ValueError:
                continue
        report.history_archive_count = len(hist_ids)
        report.history_archive_bytes = hist_bytes

        pom_deps: set[tuple[str, str]] = set()
        for _mode, blob_id, _size, path in entries:
            if path.endswith("pom.xml") or path == "pom.xml":
                try:
                    pom_bytes = git_blob_bytes(work_dir, blob_id)
                    for gid, aid, _ver in parse_pom_dependencies(pom_bytes):
                        pom_deps.add((gid, aid))
                except Exception as exc:
                    logger.warning("No se pudo parsear %s: %s", path, exc)

        libraries: list[dict] = []
        for _mode, blob_id, size, path in entries:
            lower = path.lower()
            if not lower.endswith(JAVA_ARCHIVE_EXTS):
                continue
            content: Optional[bytes] = None
            try:
                # Evitar cargar blobs enormes en memoria
                if size <= 180 * 1024 * 1024:
                    content = git_blob_bytes(work_dir, blob_id)
            except Exception as exc:
                logger.warning("No se pudo leer %s: %s", path, exc)
            info = classify_library(
                path=path,
                size_bytes=size,
                content=content,
                pom_deps=pom_deps,
                lookup=lookup,
                inhouse_prefixes=inhouse_prefixes,
            )
            info["blob_id"] = blob_id
            libraries.append(info)
            kind = info["kind"]
            if kind == "jar":
                report.jar_count_head += 1
            elif kind == "war":
                report.war_count_head += 1
            elif kind == "ear":
                report.ear_count_head += 1
            if info["recommendation"] == "ELIMINABLE":
                report.maven_deletable_count += 1
                report.maven_deletable_bytes += size
            elif info["recommendation"] == "CONSERVAR":
                report.inhouse_count += 1
                report.inhouse_bytes += size
            else:
                report.review_count += 1
                report.review_bytes += size

        report.libraries = libraries
        if report.jar_count_head or report.war_count_head or report.ear_count_head:
            report.is_java = True

        if report.large_blob_count:
            report.migration_notes.append(
                f"Hay {report.large_blob_count} blob(s) > {_human_size(max_blob_bytes)} "
                "en el historial de master; GitHub.com los rechazará salvo que se filtren "
                "(el migrator ya hace --strip-blobs-bigger-than 100M)."
            )
        else:
            report.migration_notes.append(
                "No hay blobs > 100 MB en master; el push a GitHub.com no debería fallar por tamaño de archivo."
            )
        report.migration_notes.append(
            f"Peso estimado de clonar solo master (empaquetado): {_human_size(report.clone_size_bytes)}."
        )
        if report.maven_deletable_count:
            report.migration_notes.append(
                f"{report.maven_deletable_count} biblioteca(s) Maven en HEAD "
                f"({_human_size(report.maven_deletable_bytes)}) pueden eliminarse y resolverse por Maven."
            )
        if report.inhouse_count:
            report.migration_notes.append(
                f"{report.inhouse_count} biblioteca(s) in-house o ausentes de Maven "
                f"({_human_size(report.inhouse_bytes)}) deben conservarse."
            )
        if report.review_count:
            report.migration_notes.append(
                f"{report.review_count} binario(s) requieren revisión manual."
            )
        if report.history_archive_count > (report.jar_count_head + report.war_count_head + report.ear_count_head):
            report.migration_notes.append(
                f"El historial de master contiene {report.history_archive_count} jar/war/ear únicos "
                f"({_human_size(report.history_archive_bytes)}); hay binarios viejos que ya no están en HEAD."
            )
        return report
    except Exception as exc:
        report.status = "error"
        report.error = str(exc)
        logger.exception("Fallo analizando %s", entry)
        return report
    finally:
        if work_dir and work_dir.exists() and not keep_clone:
            shutil.rmtree(work_dir, ignore_errors=True)


def write_outputs(reports: list[RepoReport], output_dir: Path, max_blob_mb: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = output_dir / "summary.csv"
    libs_csv = output_dir / "libraries.csv"
    blobs_csv = output_dir / "large_blobs.csv"
    summary_md = output_dir / "summary.md"
    summary_json = output_dir / "summary.json"

    with summary_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "repo",
                "status",
                "has_master",
                "commits",
                "clone_size",
                "clone_size_bytes",
                "unpacked_history",
                "head_tree",
                "large_blobs",
                "large_blobs_size",
                "is_java",
                "jars_head",
                "wars_head",
                "maven_eliminables",
                "maven_eliminables_size",
                "inhouse_conservar",
                "inhouse_size",
                "revisar",
                "error",
            ],
        )
        writer.writeheader()
        for report in reports:
            writer.writerow(
                {
                    "repo": report.repo,
                    "status": report.status,
                    "has_master": report.has_master,
                    "commits": report.commit_count,
                    "clone_size": _human_size(report.clone_size_bytes),
                    "clone_size_bytes": report.clone_size_bytes,
                    "unpacked_history": _human_size(report.unpacked_history_bytes),
                    "head_tree": _human_size(report.head_tree_bytes),
                    "large_blobs": report.large_blob_count,
                    "large_blobs_size": _human_size(report.large_blob_bytes),
                    "is_java": report.is_java,
                    "jars_head": report.jar_count_head,
                    "wars_head": report.war_count_head,
                    "maven_eliminables": report.maven_deletable_count,
                    "maven_eliminables_size": _human_size(report.maven_deletable_bytes),
                    "inhouse_conservar": report.inhouse_count,
                    "inhouse_size": _human_size(report.inhouse_bytes),
                    "revisar": report.review_count,
                    "error": report.error or "",
                }
            )

    with libs_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "repo",
                "path",
                "kind",
                "size",
                "size_bytes",
                "sha1",
                "group_id",
                "artifact_id",
                "version",
                "classification",
                "recommendation",
                "reason",
            ],
        )
        writer.writeheader()
        for report in reports:
            for lib in report.libraries:
                writer.writerow(
                    {
                        "repo": report.repo,
                        "path": lib.get("path"),
                        "kind": lib.get("kind"),
                        "size": lib.get("size_human"),
                        "size_bytes": lib.get("size_bytes"),
                        "sha1": lib.get("sha1"),
                        "group_id": lib.get("group_id") or "",
                        "artifact_id": lib.get("artifact_id") or "",
                        "version": lib.get("version") or "",
                        "classification": lib.get("classification"),
                        "recommendation": lib.get("recommendation"),
                        "reason": lib.get("reason"),
                    }
                )

    with blobs_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "repo",
                "path",
                "size",
                "size_bytes",
                "blob_id",
                "extension",
                "intro_commit",
                "intro_author",
                "intro_email",
                "intro_date",
            ],
        )
        writer.writeheader()
        for report in reports:
            for blob in report.large_blobs:
                writer.writerow(
                    {
                        "repo": report.repo,
                        "path": blob.get("path"),
                        "size": blob.get("size_human"),
                        "size_bytes": blob.get("size_bytes"),
                        "blob_id": blob.get("blob_id"),
                        "extension": blob.get("extension"),
                        "intro_commit": blob.get("intro_commit") or "",
                        "intro_author": blob.get("intro_author_name") or "",
                        "intro_email": blob.get("intro_author_email") or "",
                        "intro_date": blob.get("intro_date") or "",
                    }
                )

    lines = [
        "# Análisis pre-migración (rama master)",
        "",
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Umbral de blob grande: {max_blob_mb} MB",
        "",
        "| Repo | Estado | Peso master (pack) | Historial unpacked | HEAD | Blobs > "
        f"{max_blob_mb}MB | Java | Maven ELIMINABLE | In-house CONSERVAR |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    for report in reports:
        lines.append(
            "| {repo} | {status} | {pack} | {hist} | {head} | {blobs} | {java} | {mvn} | {ih} |".format(
                repo=report.repo.replace("|", "\\|"),
                status=report.status,
                pack=_human_size(report.clone_size_bytes),
                hist=_human_size(report.unpacked_history_bytes),
                head=_human_size(report.head_tree_bytes),
                blobs=f"{report.large_blob_count} ({_human_size(report.large_blob_bytes)})",
                java="sí" if report.is_java else "no",
                mvn=f"{report.maven_deletable_count} ({_human_size(report.maven_deletable_bytes)})",
                ih=f"{report.inhouse_count} ({_human_size(report.inhouse_bytes)})",
            )
        )
    lines.append("")

    for report in reports:
        lines.extend(
            [
                f"## {report.repo}",
                "",
                f"- URL: `{report.source_url}`",
                f"- Estado: **{report.status}**",
                f"- Rama master: {'sí' if report.has_master else 'no'}",
                f"- Commits en master: {report.commit_count}",
                f"- Peso estimado del clon (solo master, empaquetado): **{_human_size(report.clone_size_bytes)}**",
                f"- Suma unpacked de blobs del historial: {_human_size(report.unpacked_history_bytes)} "
                f"({report.unpacked_blob_count} blobs)",
                f"- Árbol actual (HEAD): {_human_size(report.head_tree_bytes)} / {report.head_file_count} archivos",
                f"- Blobs > {max_blob_mb} MB: **{report.large_blob_count}** ({_human_size(report.large_blob_bytes)})",
                f"- Java: {'sí' if report.is_java else 'no'} "
                f"(jar={report.jar_count_head}, war={report.war_count_head}, ear={report.ear_count_head})",
                f"- jar/war/ear únicos en historial: {report.history_archive_count} "
                f"({_human_size(report.history_archive_bytes)})",
            ]
        )
        if report.error:
            lines.append(f"- Error: {report.error}")
        if report.available_branches:
            preview = ", ".join(report.available_branches[:30])
            extra = "" if len(report.available_branches) <= 30 else " ..."
            lines.append(f"- Otras ramas (no se migrarían): {preview}{extra}")
        lines.append("")
        if report.migration_notes:
            lines.append("### Notas de migración")
            lines.append("")
            for note in report.migration_notes:
                lines.append(f"- {note}")
            lines.append("")
        if report.large_blobs:
            lines.append("### Blobs grandes")
            lines.append("")
            for blob in report.large_blobs:
                lines.append("```")
                lines.append(blob["report_line"].rstrip())
                lines.append("```")
                lines.append("")
        if report.libraries:
            lines.append("### Binarios Java en HEAD de master")
            lines.append("")
            lines.append("| Archivo | Tipo | Tamaño | Clasificación | Acción | Coordenadas |")
            lines.append("|---|---|---:|---|---|---|")
            for lib in report.libraries:
                lines.append(
                    "| {path} | {kind} | {size} | {cls} | {rec} | {coords} |".format(
                        path=str(lib.get("path", "")).replace("|", "\\|"),
                        kind=lib.get("kind"),
                        size=lib.get("size_human"),
                        cls=lib.get("classification"),
                        rec=lib.get("recommendation"),
                        coords=(lib.get("maven_coords") or "—").replace("|", "\\|"),
                    )
                )
            lines.append("")
            for lib in report.libraries:
                lines.append(f"- `{lib.get('path')}` — {lib.get('reason')}")
            lines.append("")

    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary_json.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for report in reports:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", report.repo).strip("_") or "repo"
        (output_dir / f"{slug}.json").write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analiza repos on-prem (rama master) antes de migrar")
    parser.add_argument("--repos-file", default="repos_to_check.txt")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--work-dir", default=".work")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--max-blob-size-mb", type=int, default=DEFAULT_MAX_BLOB_MB)
    parser.add_argument(
        "--ssh-source-prefix",
        default=os.environ.get("SSH_SOURCE_PREFIX", DEFAULT_SSH_PREFIX),
    )
    parser.add_argument(
        "--inhouse-prefix",
        action="append",
        default=[],
        help="Prefijo extra de groupId in-house (repetible)",
    )
    parser.add_argument("--skip-maven-lookup", action="store_true")
    parser.add_argument("--keep-clones", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=DATE_FORMAT)
    logger = logging.getLogger("analizer")

    repos_file = Path(args.repos_file)
    output_dir = Path(args.output_dir)
    work_root = Path(args.work_dir)
    work_root.mkdir(parents=True, exist_ok=True)

    ssh_key = os.environ.get("SSH_PRIVATE_KEY", "")
    if ssh_key.strip():
        setup_ssh(ssh_key, logger)
    else:
        logger.warning("SSH_PRIVATE_KEY no está definida; se usará la config SSH del entorno")

    try:
        repos = read_repo_list(repos_file)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2

    if not repos:
        logger.info("repos_to_check.txt no tiene entradas. Nada que analizar.")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "summary.md").write_text(
            "# Análisis pre-migración\n\nLista vacía: agregue una ruta por línea en `repos_to_check.txt`.\n",
            encoding="utf-8",
        )
        return 0

    prefixes = tuple(DEFAULT_INHOUSE_PREFIXES) + tuple(args.inhouse_prefix)
    lookup = MavenLookup(enabled=not args.skip_maven_lookup, logger=logger)
    max_bytes = args.max_blob_size_mb * 1024 * 1024
    reports: list[RepoReport] = []

    logger.info("Repos a analizar: %s", len(repos))
    for index, entry in enumerate(repos, start=1):
        source_url = resolve_source_url(entry, args.ssh_source_prefix)
        logger.info("------------------------------------------------------")
        logger.info("Analizando repo %s de %s", index, len(repos))
        logger.info("path=%s url=%s", entry, source_url)
        logger.info("------------------------------------------------------")
        report = analyze_repo(
            entry=entry,
            source_url=source_url,
            work_root=work_root,
            branch=args.branch,
            max_blob_bytes=max_bytes,
            lookup=lookup,
            inhouse_prefixes=prefixes,
            logger=logger,
            keep_clone=args.keep_clones,
        )
        reports.append(report)
        logger.info(
            "Resultado %s: status=%s pack=%s blobs>limite=%s jars=%s wars=%s",
            entry,
            report.status,
            _human_size(report.clone_size_bytes),
            report.large_blob_count,
            report.jar_count_head,
            report.war_count_head,
        )

    write_outputs(reports, output_dir, args.max_blob_size_mb)
    logger.info("Reportes escritos en %s", output_dir)

    failed = [r for r in reports if r.status == "error"]
    if failed and len(failed) == len(reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
