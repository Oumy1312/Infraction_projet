from pathlib import Path

import pytest

from src.vehicules import new_tracker, require_trained_weights, update_tracks

ROOT = Path(__file__).resolve().parents[1]


def _box(x: float, y: float, cls: int = 0, conf: float = 0.9):
    return {"xyxy": (x, y, x + 80, y + 140), "conf": conf, "cls": cls}


def test_stock_weight_name_is_refused(tmp_path: Path):
    decoy = tmp_path / "yolo11n.pt"
    decoy.write_bytes(b"not a weight")
    with pytest.raises(FileNotFoundError):
        require_trained_weights(decoy)
    with pytest.raises(FileNotFoundError):
        require_trained_weights(tmp_path / "best.pt")


def test_simulated_track_keeps_its_id():
    tracker = new_tracker(ROOT / "configs" / "bytetrack.yaml", frame_rate=30)
    seen = []
    x = 100.0
    for _ in range(5):
        seen.append(update_tracks(tracker, [_box(x, 80)]))
        x += 8
    active = [frame for frame in seen if frame]
    assert active
    ids = {track["track_id"] for frame in active for track in frame}
    assert len(ids) == 1


def test_two_simulated_objects_get_two_ids():
    tracker = new_tracker(frame_rate=30)
    last = []
    for step in range(4):
        last = update_tracks(
            tracker,
            [_box(40 + step * 5, 60, cls=0), _box(400 + step * 5, 70, cls=2)],
        )
    assert len(last) == 2
    assert len({track["track_id"] for track in last}) == 2
