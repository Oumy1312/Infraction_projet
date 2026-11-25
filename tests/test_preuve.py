from pathlib import Path

from PIL import Image

from src.preuve import blur_regions, connect, record, write_pdf


def test_record_and_pdf_with_blur(tmp_path: Path):
    source = tmp_path / "frame.jpg"
    Image.new("RGB", (80, 60), (255, 0, 0)).save(source)
    blurred = blur_regions(source, [(10, 10, 40, 40)], tmp_path / "blur.jpg")
    assert blurred.is_file()
    connection = connect(tmp_path / "preuves.sqlite")
    row_id = record(connection, frame_index=3, track_id=7, color="rouge", note="test", image_path=str(blurred))
    assert row_id == 1
    pdf = write_pdf(
        tmp_path / "preuve.pdf",
        "Preuve d'infraction",
        ["Piste 7", "Feu rouge"],
        blurred,
    )
    assert pdf.is_file()
    assert pdf.stat().st_size > 500
