#!/usr/bin/env python3
"""A loopback-only HTTP dashboard for short-drama project text files."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import ipaddress
import json
import os
import stat
import sys
import tempfile
import threading
import uuid
import webbrowser
from collections.abc import Iterator
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, BinaryIO
from urllib.parse import parse_qs, unquote, urlencode, urlsplit


# Creators run these scripts on whatever interpreter their machine provides, so
# an unsupported version must say so instead of failing inside an import.
MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )

TEXT_EXTENSIONS = frozenset({".md", ".json", ".jsonl", ".txt", ".srt", ".ass"})
MEDIA_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".mov"}
)
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}
DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_NODES = 2_000
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_MEDIA_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_REQUEST_BYTES = DEFAULT_MAX_FILE_BYTES + 64 * 1024
SKILL_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = SKILL_ROOT / "assets/dashboard"
SECURE_DIR_FD = (
    os.name != "nt"
    and bool(getattr(os, "O_DIRECTORY", 0))
    and bool(getattr(os, "O_NOFOLLOW", 0))
)


class DashboardError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _is_loopback(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_project_tool(root: Path) -> ModuleType:
    """Dynamically load the suite's canonical project status implementation."""
    root = root.resolve()
    installed_script = root / "scripts/project_tool.py"
    repository_script = root / "skills/short-drama/scripts/project_tool.py"
    script = installed_script if installed_script.is_file() else repository_script
    spec = importlib.util.spec_from_file_location("dashboard_project_tool", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load project tool: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _version(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_structured_text(path: PurePosixPath, content: str) -> None:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            raise DashboardError(
                HTTPStatus.BAD_REQUEST,
                f"JSON is invalid at line {exc.lineno}, column {exc.colno}",
            ) from exc
        return
    if suffix != ".jsonl":
        return
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            raise DashboardError(
                HTTPStatus.BAD_REQUEST,
                f"JSONL line {line_number} is invalid at column {exc.colno}",
            ) from exc


@contextlib.contextmanager
def _open_parent_directory(
    root: Path, relative: PurePosixPath
) -> Iterator[tuple[int, str]]:
    """Pin every parent directory without following a replaced symlink."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, relative.name
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _interprocess_lock(target: Path) -> Iterator[None]:
    """Serialize writes to one resolved path across dashboard processes."""
    lock_root = Path(tempfile.gettempdir()) / "short-drama-dashboard-locks"
    lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root_details = os.lstat(lock_root)
    if (
        not stat.S_ISDIR(root_details.st_mode)
        or root_details.st_uid != os.geteuid()
        or stat.S_IMODE(root_details.st_mode) & 0o077
    ):
        raise DashboardError(
            HTTPStatus.FORBIDDEN, "dashboard lock directory is not private"
        )
    digest = hashlib.sha256(str(target).encode("utf-8")).hexdigest()
    root_fd = os.open(lock_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptor = -1
    try:
        lock_name = f"{digest}.lock"
        try:
            descriptor = os.open(
                lock_name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=root_fd,
            )
        except FileExistsError:
            descriptor = os.open(
                lock_name,
                os.O_RDWR | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid():
            raise DashboardError(
                HTTPStatus.FORBIDDEN, "dashboard lock file is not trusted"
            )
        os.fchmod(descriptor, 0o600)
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(root_fd)


class ProjectStore:
    def __init__(
        self,
        workspace: Path,
        project_tool: ModuleType,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_nodes: int = DEFAULT_MAX_NODES,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_media_bytes: int = DEFAULT_MAX_MEDIA_BYTES,
    ) -> None:
        workspace = workspace.expanduser().resolve(strict=True)
        if not workspace.is_dir():
            raise NotADirectoryError(workspace)
        self.workspace = workspace
        self.project_tool = project_tool
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_file_bytes = max_file_bytes
        self.max_media_bytes = max_media_bytes
        self._write_lock = threading.Lock()

    @staticmethod
    def _project_id(relative: str) -> str:
        return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:20]

    def discover(self) -> tuple[list[dict[str, Any]], list[str]]:
        projects: list[dict[str, Any]] = []
        warnings: list[str] = []
        nodes = 0
        depth_truncated = False
        node_truncated = False

        def walk(directory: Path, depth: int) -> None:
            nonlocal depth_truncated, node_truncated, nodes
            if nodes >= self.max_nodes:
                return
            try:
                with os.scandir(directory) as iterator:
                    entries = sorted(iterator, key=lambda item: item.name.casefold())
            except OSError as exc:
                warnings.append(
                    f"无法读取 {directory.relative_to(self.workspace)}: {exc}"
                )
                return
            for entry in entries:
                if nodes >= self.max_nodes:
                    node_truncated = True
                    return
                nodes += 1
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                if (
                    entry.is_file(follow_symlinks=False)
                    and entry.name == "short-drama.json"
                ):
                    root = path.parent
                    relative = root.relative_to(self.workspace).as_posix() or "."
                    projects.append(
                        {"id": self._project_id(relative), "path": relative}
                    )
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if depth >= self.max_depth:
                        depth_truncated = True
                        continue
                    walk(path, depth + 1)

        walk(self.workspace, 0)
        if node_truncated:
            warnings.append(f"项目发现达到节点上限 {self.max_nodes}，结果已截断")
        if depth_truncated:
            warnings.append(f"项目发现达到深度上限 {self.max_depth}，更深目录已截断")
        return projects, warnings

    def project(self, project_id: str) -> Path:
        for item in self.discover()[0]:
            if item["id"] == project_id:
                candidate = (
                    self.workspace
                    if item["path"] == "."
                    else self.workspace / item["path"]
                )
                return candidate.resolve(strict=True)
        raise DashboardError(HTTPStatus.NOT_FOUND, "project not found")

    def status(self, project_id: str) -> dict[str, Any]:
        root = self.project(project_id)
        return self.project_tool.project_status(root)

    def _safe_path(
        self, project_id: str, relative: str, *, must_exist: bool = True
    ) -> tuple[Path, PurePosixPath]:
        root = self.project(project_id)
        raw = unquote(relative).replace("\\", "/")
        pure = PurePosixPath(raw)
        if (
            not raw
            or pure.is_absolute()
            or any(part in ("", ".", "..") for part in pure.parts)
        ):
            raise DashboardError(HTTPStatus.BAD_REQUEST, "unsafe project-relative path")
        current = root
        for part in pure.parts:
            current = current / part
            if current.is_symlink():
                raise DashboardError(
                    HTTPStatus.FORBIDDEN, "symbolic links are not allowed"
                )
        try:
            resolved = current.resolve(strict=must_exist)
        except FileNotFoundError as exc:
            raise DashboardError(HTTPStatus.NOT_FOUND, "file not found") from exc
        if resolved != root and root not in resolved.parents:
            raise DashboardError(HTTPStatus.FORBIDDEN, "path leaves project root")
        return resolved, pure

    @staticmethod
    def _is_protected(relative: PurePosixPath) -> bool:
        folded = tuple(part.casefold() for part in relative.parts)
        return (
            relative.name.casefold() == "short-drama.json"
            or bool(folded and folded[0] == ".short-drama")
            or bool(folded and folded[0] == "delivery")
        )

    def tree(self, project_id: str) -> dict[str, Any]:
        root = self.project(project_id)
        nodes = 0
        warnings: list[str] = []
        depth_truncated = False
        node_truncated = False
        oversized_text = 0
        oversized_media = 0

        def scan(directory: Path, depth: int) -> list[dict[str, Any]]:
            nonlocal depth_truncated, node_truncated, nodes
            nonlocal oversized_media, oversized_text
            children: list[dict[str, Any]] = []
            try:
                with os.scandir(directory) as iterator:
                    entries = sorted(
                        iterator,
                        key=lambda item: (
                            not item.is_dir(follow_symlinks=False),
                            item.name.casefold(),
                        ),
                    )
            except OSError as exc:
                warnings.append(f"无法读取 {directory.relative_to(root)}: {exc}")
                return children
            for entry in entries:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if PurePosixPath(relative).parts[0].casefold() == ".short-drama":
                    continue
                if nodes >= self.max_nodes:
                    node_truncated = True
                    break
                nodes += 1
                if entry.is_dir(follow_symlinks=False):
                    node: dict[str, Any] = {
                        "name": entry.name,
                        "path": relative,
                        "type": "directory",
                        "children": [],
                    }
                    if depth < self.max_depth:
                        node["children"] = scan(path, depth + 1)
                    else:
                        depth_truncated = True
                        node["truncated"] = True
                    children.append(node)
                    continue
                suffix = path.suffix.casefold()
                if suffix not in TEXT_EXTENSIONS and suffix not in MEDIA_EXTENSIONS:
                    continue
                try:
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                limit = (
                    self.max_file_bytes
                    if suffix in TEXT_EXTENSIONS
                    else self.max_media_bytes
                )
                if size > limit:
                    if suffix in TEXT_EXTENSIONS:
                        oversized_text += 1
                    else:
                        oversized_media += 1
                children.append(
                    {
                        "name": entry.name,
                        "path": relative,
                        "type": "text" if suffix in TEXT_EXTENSIONS else "media",
                        "size": size,
                        "oversize": size > limit,
                        "writable": suffix in TEXT_EXTENSIONS
                        and not self._is_protected(PurePosixPath(relative)),
                    }
                )
            return children

        tree = scan(root, 0)
        if node_truncated:
            warnings.append(f"文件树达到节点上限 {self.max_nodes}，结果已截断")
        if depth_truncated:
            warnings.append(f"文件树达到深度上限 {self.max_depth}，更深目录已截断")
        if oversized_text:
            warnings.append(
                f"{oversized_text} 个文本文件超过大小上限 {self.max_file_bytes} bytes，内容预览已禁用"
            )
        if oversized_media:
            warnings.append(
                f"{oversized_media} 个媒体文件超过大小上限 {self.max_media_bytes} bytes，媒体预览已禁用"
            )
        return {
            "tree": tree,
            "warnings": warnings,
            "limits": {
                "depth": self.max_depth,
                "nodes": self.max_nodes,
                "fileBytes": self.max_file_bytes,
                "mediaBytes": self.max_media_bytes,
            },
        }

    def read_text(self, project_id: str, relative: str) -> dict[str, Any]:
        root = self.project(project_id)
        path, pure = self._safe_path(project_id, relative)
        if path.suffix.casefold() not in TEXT_EXTENSIONS:
            raise DashboardError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "file type is not editable text"
            )
        if not path.is_file():
            raise DashboardError(HTTPStatus.BAD_REQUEST, "path is not a file")
        if not SECURE_DIR_FD:
            raise DashboardError(
                HTTPStatus.NOT_IMPLEMENTED,
                "safe text access is unavailable on this platform",
            )
        try:
            with _open_parent_directory(root, pure) as (parent_fd, name):
                data, _ = self._read_regular_at(parent_fd, name)
        except OSError as exc:
            raise DashboardError(
                HTTPStatus.FORBIDDEN, "text file cannot be opened safely"
            ) from exc
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DashboardError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "text file must be UTF-8"
            ) from exc
        return {
            "path": pure.as_posix(),
            "content": content,
            "version": _version(data),
            "writable": not self._is_protected(pure),
        }

    def _read_regular_at(self, parent_fd: int, name: str) -> tuple[bytes, int]:
        flags = os.O_RDONLY | os.O_NOFOLLOW
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise DashboardError(HTTPStatus.BAD_REQUEST, "path is not a file")
            if details.st_size > self.max_file_bytes:
                raise DashboardError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "file exceeds preview limit",
                )
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                data = handle.read(self.max_file_bytes + 1)
            if len(data) > self.max_file_bytes:
                raise DashboardError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "file exceeds preview limit",
                )
            return data, stat.S_IMODE(details.st_mode)
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _replace_text_at(
        self,
        parent_fd: int,
        name: str,
        encoded: bytes,
        mode: int,
        expected_version: str,
    ) -> None:
        temporary_name = f".{name}.{uuid.uuid4().hex}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        descriptor = os.open(temporary_name, flags, mode, dir_fd=parent_fd)
        replaced = False
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
                os.fchmod(handle.fileno(), mode)
            latest, _ = self._read_regular_at(parent_fd, name)
            if _version(latest) != expected_version:
                raise DashboardError(
                    HTTPStatus.CONFLICT, "file changed since it was opened"
                )
            os.replace(
                temporary_name,
                name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            replaced = True
            os.fsync(parent_fd)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if not replaced:
                try:
                    os.unlink(temporary_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass

    def write_text(
        self, project_id: str, relative: str, content: Any, expected_version: Any
    ) -> dict[str, Any]:
        root = self.project(project_id)
        path, pure = self._safe_path(project_id, relative)
        if path.suffix.casefold() not in TEXT_EXTENSIONS:
            raise DashboardError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "file type is not editable text"
            )
        if self._is_protected(pure):
            raise DashboardError(
                HTTPStatus.FORBIDDEN, "file is protected and read-only"
            )
        if not isinstance(content, str) or not isinstance(expected_version, str):
            raise DashboardError(
                HTTPStatus.BAD_REQUEST,
                "content and expectedVersion are required strings",
            )
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_file_bytes:
            raise DashboardError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "content exceeds file limit"
            )
        _validate_structured_text(pure, content)
        if not SECURE_DIR_FD:
            raise DashboardError(
                HTTPStatus.NOT_IMPLEMENTED,
                "safe text writes are unavailable on this platform",
            )
        with self._write_lock, _interprocess_lock(path):
            # Serialize the compare-and-replace sequence so concurrent dashboard
            # clients cannot both satisfy the same expectedVersion. On POSIX,
            # pin each parent directory so a concurrent symlink swap cannot
            # redirect the replace outside the project.
            try:
                with _open_parent_directory(root, pure) as (parent_fd, name):
                    current, mode = self._read_regular_at(parent_fd, name)
                    if _version(current) != expected_version:
                        raise DashboardError(
                            HTTPStatus.CONFLICT,
                            "file changed since it was opened",
                        )
                    self._replace_text_at(
                        parent_fd, name, encoded, mode, expected_version
                    )
            except OSError as exc:
                raise DashboardError(
                    HTTPStatus.FORBIDDEN, "text file cannot be replaced safely"
                ) from exc
        return {"path": pure.as_posix(), "version": _version(encoded), "saved": True}

    def media_info(self, project_id: str, relative: str) -> dict[str, Any]:
        handle, pure, content_type, size = self.open_media(project_id, relative)
        handle.close()
        return {
            "path": pure.as_posix(),
            "kind": "video" if content_type.startswith("video/") else "image",
            "contentType": content_type,
            "size": size,
            "readOnly": True,
            "contentUrl": f"/api/media/content?{urlencode({'project': project_id, 'path': pure.as_posix()})}",
            "status": "ready",
        }

    def open_media(
        self, project_id: str, relative: str
    ) -> tuple[BinaryIO, PurePosixPath, str, int]:
        root = self.project(project_id)
        path, pure = self._safe_path(project_id, relative)
        content_type = MEDIA_TYPES.get(path.suffix.casefold())
        if content_type is None:
            raise DashboardError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported preview media"
            )
        if not SECURE_DIR_FD:
            raise DashboardError(
                HTTPStatus.NOT_IMPLEMENTED,
                "safe media access is unavailable on this platform",
            )
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            with _open_parent_directory(root, pure) as (parent_fd, name):
                descriptor = os.open(name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise DashboardError(
                HTTPStatus.FORBIDDEN, "media file cannot be opened safely"
            ) from exc
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise DashboardError(HTTPStatus.BAD_REQUEST, "media path is not a file")
            if details.st_size > self.max_media_bytes:
                raise DashboardError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "media exceeds preview limit"
                )
            return os.fdopen(descriptor, "rb"), pure, content_type, details.st_size
        except Exception:
            os.close(descriptor)
            raise


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], store: ProjectStore) -> None:
        self.store = store
        super().__init__(server_address, DashboardHandler)

    def allowed_authority(self, authority: str) -> bool:
        parsed = urlsplit(f"//{authority}")
        if (
            not parsed.hostname
            or not _is_loopback(parsed.hostname)
            or parsed.username is not None
            or parsed.password is not None
            or bool(parsed.path or parsed.query or parsed.fragment)
        ):
            return False
        try:
            port = parsed.port
        except ValueError:
            return False
        return port == self.server_address[1]


class DashboardHandler(SimpleHTTPRequestHandler):
    server: DashboardHTTPServer

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        super().log_message(format, *args)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; media-src 'self'",
        )
        super().end_headers()

    def _security_ok(self) -> bool:
        host = self.headers.get("Host", "")
        if not host or not self.server.allowed_authority(host):
            self._json(HTTPStatus.FORBIDDEN, {"error": "invalid Host header"})
            return False
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "http"
                or not parsed.netloc
                or bool(parsed.path not in {"", "/"} or parsed.query or parsed.fragment)
                or not self.server.allowed_authority(parsed.netloc)
            ):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid Origin header"})
                return False
        return True

    def _json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _query(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urlsplit(self.path)
        return parsed.path, parse_qs(parsed.query, keep_blank_values=True)

    @staticmethod
    def _one(query: dict[str, list[str]], name: str) -> str:
        values = query.get(name)
        if not values or not values[0]:
            raise DashboardError(
                HTTPStatus.BAD_REQUEST, f"missing query parameter: {name}"
            )
        return values[0]

    @staticmethod
    def _byte_range(value: str | None, size: int) -> tuple[int, int] | None:
        if value is None:
            return None
        if not value.startswith("bytes=") or "," in value or size <= 0:
            raise DashboardError(
                HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "invalid byte range"
            )
        bounds = value[6:].strip()
        if "-" not in bounds:
            raise DashboardError(
                HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "invalid byte range"
            )
        first, last = bounds.split("-", 1)
        try:
            if first:
                start = int(first)
                end = int(last) if last else size - 1
                if start < 0 or start >= size or end < start:
                    raise ValueError
                end = min(end, size - 1)
            else:
                suffix = int(last)
                if suffix <= 0:
                    raise ValueError
                start = max(0, size - suffix)
                end = size - 1
        except ValueError as exc:
            raise DashboardError(
                HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "invalid byte range"
            ) from exc
        return start, end

    def _serve_media(self, query: dict[str, list[str]], *, send_body: bool) -> None:
        handle, _, content_type, size = self.server.store.open_media(
            self._one(query, "project"), self._one(query, "path")
        )
        try:
            try:
                selected = self._byte_range(self.headers.get("Range"), size)
            except DashboardError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return
            start, end = selected if selected is not None else (0, size - 1)
            length = 0 if size == 0 else end - start + 1
            self.send_response(
                HTTPStatus.PARTIAL_CONTENT if selected is not None else HTTPStatus.OK
            )
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if selected is not None:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if not send_body or length == 0:
                return
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            handle.close()

    def do_GET(self) -> None:
        if not self._security_ok():
            return
        path, query = self._query()
        try:
            if path == "/api/projects":
                projects, warnings = self.server.store.discover()
                self._json(HTTPStatus.OK, {"projects": projects, "warnings": warnings})
                return
            if path == "/api/status":
                self._json(
                    HTTPStatus.OK, self.server.store.status(self._one(query, "project"))
                )
                return
            if path == "/api/tree":
                self._json(
                    HTTPStatus.OK, self.server.store.tree(self._one(query, "project"))
                )
                return
            if path == "/api/file":
                self._json(
                    HTTPStatus.OK,
                    self.server.store.read_text(
                        self._one(query, "project"), self._one(query, "path")
                    ),
                )
                return
            if path == "/api/media":
                self._json(
                    HTTPStatus.OK,
                    self.server.store.media_info(
                        self._one(query, "project"), self._one(query, "path")
                    ),
                )
                return
            if path == "/api/media/content":
                self._serve_media(query, send_body=True)
                return
            if path.startswith("/api/"):
                self._json(HTTPStatus.NOT_FOUND, {"error": "API endpoint not found"})
                return
            if path == "/":
                self.path = "/index.html"
            super().do_GET()
        except DashboardError as exc:
            self._json(exc.status, {"error": exc.message})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_HEAD(self) -> None:
        if not self._security_ok():
            return
        path, query = self._query()
        if path == "/api/media/content":
            try:
                self._serve_media(query, send_body=False)
            except DashboardError as exc:
                self._json(exc.status, {"error": exc.message})
            except OSError as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if path.startswith("/api/"):
            self._json(
                HTTPStatus.METHOD_NOT_ALLOWED,
                {"error": "HEAD is not supported for API endpoints"},
            )
            return
        if path == "/":
            self.path = "/index.html"
        super().do_HEAD()

    def do_PUT(self) -> None:
        if not self._security_ok():
            return
        path, query = self._query()
        if path != "/api/file":
            self._json(HTTPStatus.NOT_FOUND, {"error": "API endpoint not found"})
            return
        try:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise DashboardError(
                    HTTPStatus.LENGTH_REQUIRED, "Content-Length is required"
                )
            length = int(raw_length)
            if length < 0 or length > DEFAULT_MAX_REQUEST_BYTES:
                raise DashboardError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body is too large"
                )
            if self.headers.get_content_type() != "application/json":
                raise DashboardError(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "Content-Type must be application/json",
                )
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise DashboardError(
                    HTTPStatus.BAD_REQUEST, "request body must be an object"
                )
            result = self.server.store.write_text(
                self._one(query, "project"),
                self._one(query, "path"),
                payload.get("content"),
                payload.get("expectedVersion"),
            )
            self._json(HTTPStatus.OK, result)
        except DashboardError as exc:
            self._json(exc.status, {"error": exc.message})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON request"})
        except OSError as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def create_server(
    workspace: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    suite_root: Path | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_media_bytes: int = DEFAULT_MAX_MEDIA_BYTES,
) -> DashboardHTTPServer:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if not _is_loopback(host) or (address is not None and address.version != 4):
        raise ValueError("dashboard may only bind to an IPv4 loopback address")
    suite = (suite_root or SKILL_ROOT).resolve()
    store = ProjectStore(
        workspace,
        load_project_tool(suite),
        max_depth=max_depth,
        max_nodes=max_nodes,
        max_file_bytes=max_file_bytes,
        max_media_bytes=max_media_bytes,
    )
    return DashboardHTTPServer((host, port), store)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve the local short-drama project dashboard"
    )
    parser.add_argument(
        "--workspace", required=True, type=Path, help="explicit workspace root to scan"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="loopback address (default: 127.0.0.1)"
    )
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument(
        "--open",
        action="store_true",
        help="open the dashboard in the default browser after binding",
    )
    args = parser.parse_args(argv)
    server = create_server(args.workspace, host=args.host, port=args.port)
    raw_host, port = server.server_address[:2]
    host = raw_host.decode("ascii") if isinstance(raw_host, bytes) else raw_host
    display_host = f"[{host}]" if ":" in host else host
    scheme = "http"
    url = f"{scheme}://{display_host}:{port}"
    print(f"Dashboard: {url}", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
