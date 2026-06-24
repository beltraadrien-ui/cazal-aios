"""Analyse IA des contenus (v2) — transcript Whisper + extraction GPT → PATCH Supabase.

Calqué sur le pipeline de Master-content (`analyze_from_apify.py` + `_analysis.py`) :
  Apify videoUrl → download (curl) → ffmpeg (audio WAV 16k) → Whisper → transcript
  → GPT (hook/structure/topic) → PATCH `contenu` (is_analyzed=true).

Gestion de l'EXPIRATION des videoUrl Apify : on **re-fetch les posts frais** au moment de
l'analyse (URLs valides), au lieu de stocker une URL qui aurait expiré. Pour chaque compte
ayant des contenus non analysés, un seul appel Apify ramène les videoUrl à jour.

Dégradé gracieux : si pas de videoUrl / ffmpeg absent → on analyse la **légende seule**
(transcript laissé vide) et on marque quand même is_analyzed=true (pas de boucle).

Usage :
    python shared/scripts/ai/analyser_contenu.py [--limit 30]

Prérequis : OPENAI_API_KEY (Whisper + GPT) + APIFY_API_TOKEN (videoUrl frais). ffmpeg + curl installés.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import OPENAI_API_KEY, status  # noqa: E402
from shared.database import get_client, update_contenu_fields  # noqa: E402
from shared.scripts.post.upsert_contenu_apify import fetch_posts_apify  # noqa: E402

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "gpt_hook_analysis.txt"
ANALYSE_FIELDS = ("spoken_hook", "hook_structure", "hook_framework", "topic",
                  "topic_summary", "content_type", "call_to_action")
HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_CURL = shutil.which("curl") is not None


def _download(video_url: str, dest: Path) -> None:
    subprocess.run(["curl", "-sSL", "-o", str(dest), video_url],
                   check=True, capture_output=True, text=True)


def _extract_audio(mp4: Path, wav: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-vn", "-acodec", "pcm_s16le",
                    "-ar", "16000", "-ac", "1", str(wav)],
                   check=True, capture_output=True, text=True)


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


def _transcribe(video_url: str | None, tmp: Path, post_id: str) -> str | None:
    """Télécharge la vidéo + transcrit. None si impossible (pas d'URL / ffmpeg absent)."""
    if not video_url or not HAS_FFMPEG or not HAS_CURL:
        return None
    mp4, wav = tmp / f"{post_id}.mp4", tmp / f"{post_id}.wav"
    try:
        _download(video_url, mp4)
        _extract_audio(mp4, wav)
        return _whisper(wav)
    finally:
        for p in (mp4, wav):
            try:
                p.unlink()
            except FileNotFoundError:
                pass


def run(limit: int) -> dict:
    if status("OPENAI_API_KEY") != "SET":
        raise EnvironmentError("OPENAI_API_KEY manquant dans .env")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    client = get_client()

    # Contenus non analysés (+ leur compte pour re-fetch les videoUrl frais)
    rows = client.table("contenu").select(
        "id, caption, compte_id").eq("is_analyzed", False).limit(limit).execute().data or []
    if not rows:
        return {"ok": 0, "fail": 0, "sans_transcript": 0, "note": "rien à analyser", "errors": []}

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

    ok, fail, no_tr, errors = 0, 0, 0, []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for r in rows:
            pid = r["id"]
            try:
                transcript = _transcribe(url_map.get(pid), tmp, pid)
                if transcript is None:
                    no_tr += 1
                text = " ".join(filter(None, [r.get("caption"), transcript])).strip()
                fields: dict = {"is_analyzed": True,
                                "analyzed_at": datetime.now(timezone.utc).isoformat()}
                if transcript:
                    fields["transcript"] = transcript
                if text:
                    data = _gpt(text, prompt)
                    fields.update({k: data.get(k) for k in ANALYSE_FIELDS if data.get(k) is not None})
                update_contenu_fields(pid, fields)
                ok += 1
                print(f"[{ok}] {pid} OK{' (légende seule)' if transcript is None else ''}",
                      file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                fail += 1
                errors.append({"id": pid, "error": str(e)[:200]})
                print(f"[FAIL] {pid} : {e}", file=sys.stderr)

    return {"ok": ok, "fail": fail, "sans_transcript": no_tr,
            "ffmpeg": HAS_FFMPEG, "errors": errors}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    print(json.dumps(run(args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
