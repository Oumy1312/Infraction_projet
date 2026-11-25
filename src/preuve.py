"""Preuve : une ligne SQLite et un PDF ReportLab.

Si des rectangles sont fournis, ils sont floutés sur l'image avant le PDF.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as PdfImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


SCHEMA = """
CREATE TABLE IF NOT EXISTS infractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    frame_index INTEGER,
    track_id INTEGER,
    color TEXT,
    note TEXT,
    image_path TEXT
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    return connection


def record(
    connection: sqlite3.Connection,
    frame_index: int,
    track_id: int,
    color: str,
    note: str = "",
    image_path: str = "",
) -> int:
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = connection.execute(
        """
        INSERT INTO infractions (created_at, frame_index, track_id, color, note, image_path)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (created, frame_index, track_id, color, note, image_path),
    )
    connection.commit()
    return int(cursor.lastrowid)


def blur_regions(
    image_path: Path | str,
    boxes: list[tuple[int, int, int, int]],
    dest: Path | str,
) -> Path:
    source = Path(image_path)
    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        frame = image.convert("RGB")
        for x1, y1, x2, y2 in boxes:
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(frame.width, int(x2)), min(frame.height, int(y2))
            if x2 <= x1 or y2 <= y1:
                continue
            crop = frame.crop((x1, y1, x2, y2))
            frame.paste(crop.filter(ImageFilter.GaussianBlur(radius=12)), (x1, y1))
        frame.save(target)
    return target


def write_pdf(
    path: Path | str,
    title: str,
    lines: list[str],
    image_path: Path | str | None = None,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6 * mm)]
    for line in lines:
        story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 2 * mm))
    if image_path is not None and Path(image_path).is_file():
        story.append(Spacer(1, 4 * mm))
        story.append(PdfImage(str(image_path), width=160 * mm, height=90 * mm, kind="proportional"))
    document = SimpleDocTemplate(str(destination), pagesize=A4)
    document.build(story)
    return destination
