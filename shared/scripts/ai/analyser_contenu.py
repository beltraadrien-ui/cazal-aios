"""Analyse IA des contenus (v3) — Whisper + GPT + visuels Claude CLI → PATCH Supabase.

Calqué sur le pipeline de Master-content (`analyze_from_apify.py` + `_analysis.py`) :
  Apify videoUrl → download (curl) → ffmpeg (audio WAV 16k) → Whisper → transcript
  → GPT (hook/structure/topic)
  → frames « hook-dense » (2 fps sur 0-4 s + 4 frames à 25/45/65/85 %, 512 px)
    lues par **Claude CLI headless** (abonnement, zéro coût API) → text_hook,
    visual_hook, visual_format, audio_hook (+ duration via ffprobe)
  → PATCH `contenu` (is_analyzed=true).

Gestion de l'EXPIRATION des videoUrl Apify : on **re-fetch les posts frais** au moment de
l'analyse (URLs valides), au lieu de stocker une URL qui aurait expiré. Pour chaque compte
ayant des contenus non analysés, un seul appel Apify ramène les videoUrl à jour.

Dégradé gracieux : si pas de videoUrl / ffmpeg absent → on analyse la **légende seule**
(transcript laissé vide) et on marque quand même is_analyzed=true (pas de boucle).
Si le step visuel échoue (CLI absent, timeout, JSON invalide) → champs visuels null,
JAMAIS de fallback (cohérence des données) ; compté dans `sans_visuel`.

Usage :
    python shared/scripts/ai/analyser_contenu.py [--limit 30]

Prérequis : OPENAI_API_KEY (Whisper + GPT) + APIFY_API_TOKEN (videoUrl frais).
ffmpeg + ffprobe + curl installés. Claude CLI loggé (pour les visuels).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import OPENAI_API_KEY, ROOT, status  # noqa: E402
from shared.database import get_client, update_contenu_fields  # noqa: E402
from shared.scripts.post.upsert_contenu_apify import fetch_posts_apify  # noqa: E402

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_PATH = PROMPTS_DIR / "gpt_hook_analysis.txt"
CLAUDE_VISUAL_PROMPT_PATH = PROMPTS_DIR / "claude_visual.txt"
ANALYSE_FIELDS = ("spoken_hook", "hook_structure", "hook_framework", "topic",
                  "topic_summary", "content_type", "call_to_action")
VISUAL_FIELDS = ("text_hook", "visual_hook", "visual_format", "audio_hook")
HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_FFPROBE = shutil.which("ffprobe") is not None
HAS_CURL = shutil.which("curl") is not None

# Échantillonnage des frames (mêmes réglages que Master-content, façon claude-video)
HOOK_WINDOW_S = 4.0                        # fenêtre hook échantillonnée en dense
HOOK_FPS = 2                               # frames/s dans la fenêtre hook (≤ 8 frames)
BODY_POSITIONS = (0.25, 0.45, 0.65, 0.85)  # fractions de la durée pour le reste
FRAME_WIDTH = 512                          # largeur max des frames (tokens maîtrisés)
VISUAL_FORMATS = {"Selfie", "Screen Recording", "Split Screen", "B-Roll", "Text Only", "Mixed"}


def _download(video_url: str, dest: Path) -> None:
    subprocess.run(["curl", "-sSL", "-o", str(dest), video_url],
                   check=True, capture_output=True, text=True)


def _extract_audio(mp4: Path, wav: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-vn", "-acodec", "pcm_s16le",
                    "-ar", "16000", "-ac", "1", str(wav)],
                   check=True, capture_output=True, text=True)


def _ffprobe_duration(mp4: Path) -> float | None:
    if not HAS_FFPROBE:
        return None
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", str(mp4)],
            check=True, capture_output=True, text=True)
        return float(json.loads(res.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def _extract_frames(mp4: Path, out_dir: Path, duration: float) -> list[tuple[Path, float]]:
    """Extraction hook-dense : HOOK_FPS f/s sur les HOOK_WINDOW_S premières secondes
    (le hook, là où tout se joue) + une frame à chaque BODY_POSITIONS de la durée.
    Retourne la liste chronologique de (Path, timestamp_seconds)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[tuple[Path, float]] = []

    hook_span = min(duration, HOOK_WINDOW_S)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp4), "-t", f"{hook_span:.2f}",
         "-vf", f"fps={HOOK_FPS},scale={FRAME_WIDTH}:-2",
         str(out_dir / "hook_%02d.jpg")],
        check=True, capture_output=True, text=True)
    for p in sorted(out_dir.glob("hook_*.jpg")):
        idx = int(p.stem.split("_")[1])  # 1-based
        frames.append((p, (idx - 1) / HOOK_FPS))

    for frac in BODY_POSITIONS:
        t = duration * frac
        if t <= hook_span:
            continue
        p = out_dir / f"body_{int(frac * 100):02d}.jpg"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(mp4),
                 "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", str(p)],
                check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            continue
        if p.exists():
            frames.append((p, t))
    return frames


def _claude_visuel(frames: list[tuple[Path, float]], transcript: str) -> dict:
    """Analyse visuelle via Claude CLI headless. Retourne {text_hook, visual_hook,
    visual_format, audio_hook}. Raise si le CLI échoue ou si la réponse n'est pas du JSON."""
    from shared.scripts.ai.call_claude import call_claude
    existing = [(p, t) for p, t in frames if p.exists()]
    if not existing:
        raise RuntimeError("aucune frame extraite")

    frame_list = "\n".join(f"- {p} (t={t:.1f}s)" for p, t in existing)
    prompt = CLAUDE_VISUAL_PROMPT_PATH.read_text(encoding="utf-8").format(
        frame_list=frame_list, transcript_excerpt=transcript[:1500])
    raw = call_claude(prompt, timeout=300)

    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(0)
    parsed = json.loads(cleaned)
    if isinstance(parsed, list):
        parsed = parsed[0]

    fmt = parsed.get("visual_format")
    if fmt is not None and fmt not in VISUAL_FORMATS:
        print(f"[note] visual_format hors taxonomie ({fmt!r}) -> null", file=sys.stderr)
        parsed["visual_format"] = None
    return parsed


def _whisper(wav: Path):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(wav, "rb") as f:
        tr = client.audio.transcriptions.create(model="whisper-1", file=f)
    return tr.text


def _gpt(text: str, prompt: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt},
                  {"role": "user", "content": text}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(resp.choices[0].message.content)


def run(limit: int) -> dict:
    if status("OPENAI_API_KEY") != "SET":
        raise EnvironmentError("OPENAI_API_KEY manquant dans .env")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    client = get_client()

    # Contenus non analysés (+ leur compte pour re-fetch les videoUrl frais)
    rows = client.table("contenu").select(
        "id, caption, compte_id").eq("is_analyzed", False).limit(limit).execute().data or []
    if not rows:
        return {"ok": 0, "fail": 0, "sans_transcript": 0, "sans_visuel": 0,
                "note": "rien à analyser", "errors": []}

    # Re-fetch Apify par compte → map media_id -> video_url frais
    handles = {}
    for cid in {r["compte_id"] for r in rows if r.get("compte_id")}:
        c = client.table("comptes").select("handle").eq("id", cid).limit(1).execute().data
        if c:
            handles[cid] = c[0]["handle"]
    url_map: dict[str, str] = {}
    if status("APIFY_API_TOKEN") == "SET":
        for cid, handle in handles.items():
            try:
                for p in fetch_posts_apify(handle, max(limit, 30)):
                    if p.get("media_id") and p.get("video_url"):
                        url_map[p["media_id"]] = p["video_url"]
            except Exception as e:  # noqa: BLE001
                print(f"[warn] fetch videoUrl {handle} : {e}", file=sys.stderr)

    ok, fail, no_tr, no_vis, errors = 0, 0, 0, 0, []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for r in rows:
            pid = r["id"]
            mp4 = tmp / f"{pid}.mp4"
            frames_dir = ROOT / "active" / f"_visual_{pid}"
            try:
                transcript, duration, visuals = None, None, {}
                if url_map.get(pid) and HAS_FFMPEG and HAS_CURL:
                    _download(url_map[pid], mp4)
                    duration = _ffprobe_duration(mp4)
                    wav = tmp / f"{pid}.wav"
                    try:
                        _extract_audio(mp4, wav)
                        transcript = _whisper(wav)
                    finally:
                        wav.unlink(missing_ok=True)
                    # Step visuel — frames sous la racine projet (Read du CLI headless)
                    if duration:
                        try:
                            frames = _extract_frames(mp4, frames_dir, duration)
                            visuals = _claude_visuel(frames, transcript or "")
                        except Exception as e:  # noqa: BLE001 — pas de fallback, champs null
                            print(f"[warn] visuels {pid} : {str(e)[:200]}", file=sys.stderr)
                        finally:
                            shutil.rmtree(frames_dir, ignore_errors=True)
                if transcript is None:
                    no_tr += 1
                if not any(visuals.get(k) is not None for k in VISUAL_FIELDS):
                    no_vis += 1

                text = " ".join(filter(None, [r.get("caption"), transcript])).strip()
                fields: dict = {"is_analyzed": True,
                                "analyzed_at": datetime.now(timezone.utc).isoformat()}
                if transcript:
                    fields["transcript"] = transcript
                if duration:
                    fields["duration"] = round(duration, 1)
                if text:
                    data = _gpt(text, prompt)
                    fields.update({k: data.get(k) for k in ANALYSE_FIELDS if data.get(k) is not None})
                fields.update({k: visuals.get(k) for k in VISUAL_FIELDS
                               if visuals.get(k) is not None})
                update_contenu_fields(pid, fields)
                ok += 1
                notes = "".join([" (légende seule)" if transcript is None else "",
                                 " (sans visuel)" if not visuals else ""])
                print(f"[{ok}] {pid} OK{notes}", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                fail += 1
                errors.append({"id": pid, "error": str(e)[:200]})
                print(f"[FAIL] {pid} : {e}", file=sys.stderr)
            finally:
                mp4.unlink(missing_ok=True)
                shutil.rmtree(frames_dir, ignore_errors=True)

    return {"ok": ok, "fail": fail, "sans_transcript": no_tr, "sans_visuel": no_vis,
            "ffmpeg": HAS_FFMPEG, "errors": errors}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    print(json.dumps(run(args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
