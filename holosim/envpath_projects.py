"""Local SQLite storage for editable EnvPath project work."""

from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4


MAX_DOCUMENT_BYTES = 24 * 1024
MAX_DOCUMENTS = 16


class ProjectError(ValueError):
    pass


class ProjectConflict(ProjectError):
    pass


def _string(value, limit):
    if type(value) is not str or len(value) > limit:
        raise ProjectError("Invalid project text or length.")
    return value


def _document(value):
    if type(value) is not dict or value.keys() != {"name", "draft", "next_step", "evidence", "videos"}:
        raise ProjectError("Invalid project fields.")
    name = _string(value["name"], 100).strip()
    if not name:
        raise ProjectError("Enter a project name.")
    evidence, videos = value["evidence"], value["videos"]
    if type(evidence) is not list or type(videos) is not list or max(len(evidence), len(videos)) > 24:
        raise ProjectError("A project can hold up to 24 evidence links and 24 videos.")
    for record in evidence:
        if (type(record) is not dict or record.keys() != {"idx", "hash"}
                or type(record["idx"]) is not int or not 0 <= record["idx"] < 2**53
                or type(record["hash"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", record["hash"])):
            raise ProjectError("Invalid evidence link.")
    for video in videos:
        if (type(video) is not dict or video.keys() != {"id", "title"}
                or type(video["id"]) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video["id"])):
            raise ProjectError("Invalid video link.")
        _string(video["title"], 200)
    return {"name": name, "draft": _string(value["draft"], 4000),
            "next_step": _string(value["next_step"], 1000),
            "evidence": evidence, "videos": videos}


class ProjectStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def _database(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS projects ("
                    "id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS project_files ("
                    "id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), "
                    "name TEXT NOT NULL, content TEXT NOT NULL)"
                )
                yield connection
        finally:
            connection.close()

    def list(self):
        with self._database() as db:
            rows = db.execute("SELECT id, name FROM projects ORDER BY name COLLATE NOCASE, id")
            return [{"id": project_id, "name": name} for project_id, name in rows]

    @staticmethod
    def _files(db, project_id):
        rows = db.execute(
            "SELECT id, name FROM project_files WHERE project_id = ? ORDER BY rowid", (project_id,)
        )
        return [{"id": file_id, "name": name} for file_id, name in rows]

    def read(self, project_id):
        if type(project_id) is not str or not re.fullmatch(r"[a-f0-9]{32}", project_id):
            raise ProjectError("Invalid project ID.")
        with self._database() as db:
            row = db.execute("SELECT revision, document FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                raise ProjectError("Project not found.")
            files = self._files(db, project_id)
        return {"id": project_id, "revision": row[0], **json.loads(row[1]), "files": files}

    def save(self, project_id, revision, document):
        clean = _document(document)
        if type(revision) is not int or not 0 <= revision < 2**53 - 1:
            raise ProjectError("Invalid project revision.")
        serialized = json.dumps(clean, ensure_ascii=True)
        with self._database() as db:
            if project_id is None and revision == 0:
                project_id = uuid4().hex
                db.execute("INSERT INTO projects VALUES (?, ?, ?, ?)",
                           (project_id, clean["name"], 1, serialized))
            elif (type(project_id) is str and re.fullmatch(r"[a-f0-9]{32}", project_id)
                  and revision > 0):
                result = db.execute(
                    "UPDATE projects SET name = ?, revision = revision + 1, document = ? "
                    "WHERE id = ? AND revision = ?", (clean["name"], serialized, project_id, revision)
                )
                if result.rowcount != 1:
                    raise ProjectConflict("This project changed. Reopen it before saving again.")
            else:
                raise ProjectError("Invalid project ID or revision.")
            files = self._files(db, project_id)
        return {"id": project_id, "revision": revision + 1, **clean, "files": files}

    def attach(self, project_id, name, content):
        if type(project_id) is not str or not re.fullmatch(r"[a-f0-9]{32}", project_id):
            raise ProjectError("Save the project before attaching files.")
        name = _string(name, 180)
        if not re.fullmatch(r"[^/\\\x00-\x1f]+\.(?:txt|md)", name, re.IGNORECASE):
            raise ProjectError("Choose a .txt or .md file.")
        content = _string(content, MAX_DOCUMENT_BYTES)
        if len(content.encode("utf-8")) > MAX_DOCUMENT_BYTES or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", content):
            raise ProjectError("Choose a UTF-8 text file up to 24 KiB.")
        file_id = uuid4().hex
        with self._database() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
                raise ProjectError("Project not found.")
            count = db.execute("SELECT COUNT(*) FROM project_files WHERE project_id = ?", (project_id,)).fetchone()[0]
            if count >= MAX_DOCUMENTS:
                raise ProjectError("A project can hold up to 16 files.")
            db.execute("INSERT INTO project_files VALUES (?, ?, ?, ?)", (file_id, project_id, name, content))
        return {"id": file_id, "name": name}

    def read_file(self, project_id, file_id):
        if any(type(value) is not str or not re.fullmatch(r"[a-f0-9]{32}", value)
               for value in (project_id, file_id)):
            raise ProjectError("Invalid project or file ID.")
        with self._database() as db:
            row = db.execute(
                "SELECT name, content FROM project_files WHERE project_id = ? AND id = ?",
                (project_id, file_id),
            ).fetchone()
        if row is None:
            raise ProjectError("Attachment not found.")
        return {"name": row[0], "content": row[1]}
