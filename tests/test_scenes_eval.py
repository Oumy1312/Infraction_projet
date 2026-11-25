import csv
import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_config_is_not_the_project_file(tmp_path: Path):
    from app.session import PROJECT_CONFIG, assert_session_path, session_config

    with pytest.raises(ValueError):
        assert_session_path(PROJECT_CONFIG)
    payload = session_config({"feu": {"min_ratio": 0.08}, "scene": {}}, [0, 0.5, 1, 0.5], [0.4, 0.1, 0.6, 0.3])
    assert payload["feu"]["backend"] == "hsv"
    assert_session_path(tmp_path / "config.yaml")


def test_demo_scene_keeps_a_red_crossing():
    from app.session import demo_detect, demo_frames
    from src.pipeline import load_project_config, run

    cursor = {"index": 0}

    def detect(_image):
        current = cursor["index"]
        cursor["index"] += 1
        return demo_detect(_image, current)

    result = run(demo_frames(), detect, load_project_config())
    assert result["events"]
    assert result["events"][0]["color"] == "rouge"


def test_extract_keeps_a_regular_step(tmp_path: Path):
    video = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (32, 24))
    if not writer.isOpened():
        pytest.skip("encodeur vidéo indisponible")
    for index in range(10):
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        frame[:, :] = (0, 0, 20 * index)
        writer.write(frame)
    writer.release()
    module = _load("extract_frames", "08_extract_frames.py")
    written = module.extract(video, tmp_path / "images", every_s=0.5)
    assert len(written) == 2
    assert all(path.is_file() for path in written)


def test_fake_csv_precision_and_false_positives(tmp_path: Path):
    path = tmp_path / "verite.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["video", "temps_debut_s", "temps_fin_s", "vehicule", "feu_rouge_oui_non", "remarque"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"video": "a.mp4", "temps_debut_s": "1.0", "temps_fin_s": "2.0", "vehicule": "car", "feu_rouge_oui_non": "oui", "remarque": ""},
                {"video": "a.mp4", "temps_debut_s": "5.0", "temps_fin_s": "6.0", "vehicule": "car", "feu_rouge_oui_non": "non", "remarque": "feu vert"},
                {"video": "a.mp4", "temps_debut_s": "10.0", "temps_fin_s": "11.0", "vehicule": "bus", "feu_rouge_oui_non": "oui", "remarque": ""},
            ]
        )
    module = _load("eval_pipeline", "09_eval_pipeline.py")
    detections = [
        {"video": "a.mp4", "temps_s": 1.2},
        {"video": "a.mp4", "temps_s": 5.5},
        {"video": "a.mp4", "temps_s": 20.0},
    ]
    result = module.evaluer(detections, module.lire_verite(path), tolerance_s=0.5)
    assert result["vrais_positifs"] == 1
    assert result["precision"] == 1 / 3
    assert result["rappel"] == 0.5
    assert [item["temps_s"] for item in result["faux_positifs"]] == [5.5, 20.0]
