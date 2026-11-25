from pathlib import Path

import numpy as np

from src.acquisition import Frame
from src.pipeline import apply_orange_tolerance, decide, load_project_config, observation, run, stop_line_from_config, write_proofs
from src.vehicules import new_tracker


def test_stop_line_is_scaled():
    config = load_project_config()
    line = stop_line_from_config(config, width=100, height=100)
    assert line.y1 == 62
    assert line.y2 == 62


def test_orange_after_red_counts_within_tolerance():
    config = load_project_config()
    observations = [
        observation(0, "orange", [(1, (40, 30, 60, 50))]),
        observation(1, "rouge", [(1, (40, 40, 60, 55))]),
        observation(2, "orange", [(1, (40, 70, 60, 90))]),
    ]
    events = decide(observations, [0.0, 0.2, 0.5], config, width=100, height=100)
    assert len(events) == 1
    assert events[0]["color"] == "rouge"
    assert events[0]["track_id"] == 1


def test_orange_without_recent_red_is_not_an_infraction():
    config = load_project_config()
    strict = {"scene": {**config["scene"], "orange_tolerance_s": 0.0}, "feu": config["feu"]}
    observations = [
        observation(0, "vert", [(1, (40, 20, 60, 40))]),
        observation(1, "orange", [(1, (40, 70, 60, 90))]),
    ]
    assert decide(observations, [0.0, 0.4], strict, width=100, height=100) == []


def test_tolerance_rewrites_only_the_following_orange():
    first = observation(0, "rouge", [])
    second = observation(1, "orange", [(3, (0, 0, 1, 1))])
    later = observation(2, "orange", [])
    adjusted = apply_orange_tolerance([first, second, later], [0.0, 0.4, 3.0], 1.0)
    assert [item.color for item in adjusted] == ["rouge", "rouge", "orange"]


def test_run_chains_light_tracking_and_plate():
    config = load_project_config()
    tracker = new_tracker(frame_rate=30)
    frames = []
    for index in range(8):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[5:25, 45:55] = (0, 0, 220)
        frames.append(Frame(index=index, time_s=index / 30, image=image))

    def detect(image):
        index = detect.n
        detect.n += 1
        y2 = 36 + index * 4
        return [
            {"xyxy": (40, y2 - 20, 60, y2), "conf": 0.9, "cls": 0, "kind": "vehicle"},
            {"xyxy": (10, 70, 40, 85), "conf": 0.8, "cls": 0, "kind": "plate"},
        ]

    detect.n = 0
    result = run(frames, detect, config, tracker=tracker)
    assert result["events"]
    assert result["events"][0]["color"] == "rouge"
    assert result["plate_index"] == 0


def test_run_uses_the_processed_cadence():
    config = load_project_config()
    scene = {**config["scene"], "vote_n_s": 1.0, "confirm_m_s": 0.6}
    tuned = {**config, "scene": scene}

    def frames_at(fps: float):
        frames = []
        for index in range(4):
            image = np.zeros((20, 20, 3), dtype=np.uint8)
            frames.append(Frame(index=index, time_s=index / fps, image=image))
        return frames

    slow = run(frames_at(5), lambda _image: [], tuned)
    fast = run(frames_at(30), lambda _image: [], tuned)
    assert (slow["lisseur_n"], slow["lisseur_m"]) == (5, 3)
    assert (fast["lisseur_n"], fast["lisseur_m"]) == (30, 18)


def test_proofs_are_written(tmp_path: Path):
    events = [{"track_id": 7, "index": 4, "color": "rouge"}]
    written = write_proofs(events, tmp_path / "preuves.sqlite", tmp_path)
    assert written[0].is_file()
    assert written[0].stat().st_size > 500
