from src.franchissement import Detection, Observation, StopLine, find_infractions, segments_cross


LINE = StopLine(0, 50, 100, 50)


def box_at(y2: float, track_id: int = 1) -> Detection:
    return Detection(track_id, (40, y2 - 20, 60, y2))


def test_crossing_segment_changes_side():
    assert segments_cross((50, 40), (50, 60), LINE)


def test_parallel_move_does_not_cross():
    assert not segments_cross((10, 40), (80, 40), LINE)


def test_red_crossing_is_an_infraction():
    observations = [
        Observation(0, "rouge", (box_at(40),)),
        Observation(1, "rouge", (box_at(70),)),
    ]
    events = find_infractions(observations, LINE)
    assert len(events) == 1
    assert events[0]["track_id"] == 1
    assert events[0]["index"] == 1


def test_green_crossing_is_not_an_infraction():
    observations = [
        Observation(0, "vert", (box_at(40),)),
        Observation(1, "vert", (box_at(70),)),
    ]
    assert find_infractions(observations, LINE) == []


def test_crossing_on_green_is_not_counted_again_when_the_light_turns_red():
    observations = [
        Observation(0, "vert", (box_at(40),)),
        Observation(1, "vert", (box_at(70),)),
        Observation(2, "rouge", (box_at(90),)),
    ]
    assert find_infractions(observations, LINE) == []


def test_two_tracks_are_independent():
    observations = [
        Observation(0, "rouge", (box_at(40, 1), box_at(40, 2))),
        Observation(1, "rouge", (box_at(70, 1), box_at(45, 2))),
    ]
    events = find_infractions(observations, LINE)
    assert [event["track_id"] for event in events] == [1]


def test_same_track_crosses_only_once():
    observations = [
        Observation(0, "rouge", (box_at(40),)),
        Observation(1, "rouge", (box_at(70),)),
        Observation(2, "rouge", (box_at(30),)),
        Observation(3, "rouge", (box_at(80),)),
    ]
    events = find_infractions(observations, LINE)
    assert len(events) == 1
