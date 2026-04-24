from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import ExtractedSegment, ExtractionResult

log = logging.getLogger("evg.extractor.audio")


def extract_audio(path: Path) -> ExtractionResult:
    """Transcribe audio (or video) via whisper.cpp / openai-whisper CLI.

    Tries `whisper.cpp` (`main` binary) first via JSON output, then OpenAI's
    whisper CLI as fallback. Both are invoked with shell=False and validated args.
    """
    segments = _transcribe_whispercpp(path)
    if segments is None:
        segments = _transcribe_openai_whisper(path)
    if not segments:
        return ExtractionResult(segments=[])
    return ExtractionResult(segments=segments)


def _which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _transcribe_whispercpp(path: Path) -> list[ExtractedSegment] | None:
    binary = _which("whisper-cpp", "whisper.cpp", "main")
    if not binary:
        return None
    with tempfile.TemporaryDirectory() as td:
        out_prefix = Path(td) / "out"
        cmd = [
            binary,
            "-f", str(path),
            "-oj",
            "-of", str(out_prefix),
        ]
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, timeout=60 * 30, shell=False
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            log.warning("whisper.cpp failed: %s", e)
            return None
        json_path = Path(f"{out_prefix}.json")
        if not json_path.exists():
            return None
        try:
            data = json.loads(json_path.read_text())
        except Exception as e:  # noqa: BLE001
            log.warning("whisper.cpp json parse failed: %s", e)
            return None
        out: list[ExtractedSegment] = []
        for s in data.get("transcription", []) or []:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            out.append(ExtractedSegment(
                text=text,
                ts_start_ms=int(s.get("offsets", {}).get("from", 0)),
                ts_end_ms=int(s.get("offsets", {}).get("to", 0)),
            ))
        return out


def _transcribe_openai_whisper(path: Path) -> list[ExtractedSegment]:
    binary = _which("whisper")
    if not binary:
        log.warning("no whisper binary found; audio %s left untranscribed", path)
        return []
    with tempfile.TemporaryDirectory() as td:
        cmd = [
            binary, str(path),
            "--output_format", "json",
            "--output_dir", td,
            "--model", "base.en",
            "--fp16", "False",
        ]
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, timeout=60 * 30, shell=False
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            log.warning("openai-whisper failed: %s", e)
            return []
        candidates = list(Path(td).glob("*.json"))
        if not candidates:
            return []
        try:
            data = json.loads(candidates[0].read_text())
        except Exception as e:  # noqa: BLE001
            log.warning("whisper json parse failed: %s", e)
            return []
        out: list[ExtractedSegment] = []
        for s in data.get("segments", []) or []:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            out.append(ExtractedSegment(
                text=text,
                ts_start_ms=int(float(s.get("start", 0)) * 1000),
                ts_end_ms=int(float(s.get("end", 0)) * 1000),
            ))
        if not out:
            full = (data.get("text") or "").strip()
            if full:
                out.append(ExtractedSegment(text=full))
        return out
