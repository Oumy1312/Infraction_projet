"""Interface locale. Le mode démo ne charge aucun poids entraîné.

La calibration est enregistrée dans un config.yaml de session,
jamais dans le config.yaml du projet.

    streamlit run app/main.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import streamlit as st

from app.session import PROJECT, demo_detect, demo_frames, session_config, write_session
from src.acquisition import Frame, frames as video_frames
from src.pipeline import load_project_config, run
from src.preuve import write_pdf

SESSIONS = PROJECT / "app" / "sessions"


def _draw(image: np.ndarray, stop_line: list[float], feu_zone: list[float]) -> np.ndarray:
    preview = image.copy()
    height, width = preview.shape[:2]
    x1, y1, x2, y2 = (int(feu_zone[0] * width), int(feu_zone[1] * height), int(feu_zone[2] * width), int(feu_zone[3] * height))
    cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 255), 2)
    ax, ay, bx, by = (int(stop_line[0] * width), int(stop_line[1] * height), int(stop_line[2] * width), int(stop_line[3] * height))
    cv2.line(preview, (ax, ay), (bx, by), (0, 0, 255), 2)
    return preview


def _bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _history() -> list[dict]:
    st.session_state.setdefault("analyses", [])
    return st.session_state["analyses"]


def _analyze(source_frames: list[Frame], config: dict, when: date, title: str) -> None:
    index = {"n": 0}

    def detect(image):
        current = index["n"]
        index["n"] += 1
        return demo_detect(image, current)

    result = run(source_frames, detect, config)
    folder = SESSIONS / datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    events = []
    for event in result["events"]:
        frame = source_frames[int(event["index"])]
        picture = folder / f"infraction_{event['track_id']}_{event['index']}.jpg"
        cv2.imwrite(str(picture), frame.image)
        events.append({**event, "image": str(picture), "confiance": 0.86, "temps_s": frame.time_s})
    doubts = []
    for state_index, state in enumerate(result["etats"]):
        if state in {"douteux", "inconnu"}:
            picture = folder / f"douteux_{state_index}.jpg"
            cv2.imwrite(str(picture), source_frames[state_index].image)
            doubts.append({"index": state_index, "image": str(picture), "temps_s": source_frames[state_index].time_s})
    _history().append(
        {
            "date": when.isoformat(),
            "titre": title,
            "events": events,
            "doutes": doubts,
            "decisions": {},
            "dossier": str(folder),
        }
    )


def main() -> None:
    st.set_page_config(page_title="Infractions", layout="wide")
    st.title("Infractions au feu")
    st.caption("Mode démo : détections simulées, aucun best.pt.")
    base = load_project_config()
    scene = base["scene"]
    uploaded = st.sidebar.file_uploader("Vidéo", type=["mp4", "avi", "mov"])
    use_demo = st.sidebar.checkbox("Scène de démonstration", value=uploaded is None)
    chosen_date = st.sidebar.date_input("Date de l'analyse", value=date.today())
    search = st.sidebar.date_input("Rechercher une date", value=date.today())

    if use_demo or uploaded is None:
        source = demo_frames()
        title = "démo"
    else:
        temporary = SESSIONS / "upload.mp4"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(uploaded.getbuffer())
        source = []
        for frame in video_frames(temporary):
            source.append(frame)
            if len(source) >= 80:
                break
        title = uploaded.name
    first = source[0].image
    st.subheader("Calibration")
    stop_y = st.slider("Ligne d'arrêt", 0.0, 1.0, float(scene["stop_line"][1]), 0.01)
    zone_x1 = st.slider("Zone du feu, gauche", 0.0, 1.0, float(scene["feu_zone"][0]), 0.01)
    zone_y1 = st.slider("Zone du feu, haut", 0.0, 1.0, float(scene["feu_zone"][1]), 0.01)
    zone_x2 = st.slider("Zone du feu, droite", 0.0, 1.0, float(scene["feu_zone"][2]), 0.01)
    zone_y2 = st.slider("Zone du feu, bas", 0.0, 1.0, float(scene["feu_zone"][3]), 0.01)
    stop_line = [0.0, stop_y, 1.0, stop_y]
    feu_zone = [zone_x1, zone_y1, zone_x2, zone_y2]
    st.image(_bgr_to_rgb(_draw(first, stop_line, feu_zone)), caption="Ligne rouge, zone du feu en jaune")
    payload = session_config(base, stop_line, feu_zone, backend="hsv")
    if st.button("Enregistrer la calibration"):
        path = SESSIONS / "courant" / "config.yaml"
        write_session(path, payload)
        st.session_state["config"] = payload
        st.success(f"Enregistré dans {path}. Le config.yaml du projet n'a pas été modifié.")
    config = st.session_state.get("config", payload)
    if st.button("Lancer l'analyse"):
        _analyze(source, config, chosen_date, title)

    st.subheader("Analyses")
    wanted = search.isoformat()
    for analysis_index, analysis in enumerate(_history()):
        if analysis["date"] != wanted:
            continue
        st.markdown(f"**{analysis['titre']}** — {analysis['date']}")
        if not analysis["events"]:
            st.info("Aucune infraction retenue.")
        for event_index, event in enumerate(analysis["events"]):
            key = f"{analysis_index}-{event_index}"
            decision = analysis["decisions"].get(key, "en attente")
            left, right = st.columns(2)
            with left:
                st.image(_bgr_to_rgb(cv2.imread(event["image"])), caption=f"piste {event['track_id']} à {event['temps_s']:.2f} s")
            with right:
                st.write(f"Couleur : {event['color']}")
                st.write(f"Confiance de la détection : {event['confiance']:.2f}")
                st.write(f"Décision : {decision}")
                if st.button("Valider", key=f"ok-{key}"):
                    analysis["decisions"][key] = "validé"
                    st.rerun()
                if st.button("Rejeter", key=f"no-{key}"):
                    analysis["decisions"][key] = "rejeté"
                    st.rerun()
        if analysis["doutes"]:
            st.markdown("Cas douteux, sans infraction")
            for doubt in analysis["doutes"]:
                st.image(_bgr_to_rgb(cv2.imread(doubt["image"])), caption=f"image {doubt['index']} à {doubt['temps_s']:.2f} s")
        if st.button("Exporter le PDF des cas validés", key=f"pdf-{analysis_index}"):
            lines = [f"{analysis['titre']} du {analysis['date']}"]
            image_path = None
            for event_index, event in enumerate(analysis["events"]):
                decision = analysis["decisions"].get(f"{analysis_index}-{event_index}", "en attente")
                if decision != "validé":
                    continue
                lines.append(f"Piste {event['track_id']} à {event['temps_s']:.2f} s, confiance {event['confiance']:.2f}")
                image_path = event["image"]
            if len(lines) == 1:
                st.warning("Aucun cas validé.")
            else:
                pdf = write_pdf(Path(analysis["dossier"]) / "preuves.pdf", "Infractions validées", lines, image_path)
                st.success(str(pdf))
                st.download_button("Télécharger le PDF", pdf.read_bytes(), file_name="preuves.pdf", mime="application/pdf")


if __name__ == "__main__":
    main()
