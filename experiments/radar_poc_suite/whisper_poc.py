from __future__ import annotations

import argparse
import json
from pathlib import Path


def transcribe(path: Path, model_name: str, language: str | None) -> dict:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)

    try:
        import whisper
    except ImportError as exc:
        raise SystemExit(
            "Whisper não instalado. Use o ambiente isolado e requirements-optional.txt."
        ) from exc

    model = whisper.load_model(model_name)
    kwargs = {"verbose": False}
    if language:
        kwargs["language"] = language
    result = model.transcribe(str(path), **kwargs)

    segments = []
    for segment in result.get("segments", []) or []:
        segments.append(
            {
                "start_seconds": float(segment.get("start", 0.0)),
                "end_seconds": float(segment.get("end", 0.0)),
                "text": str(segment.get("text", "")).strip(),
            }
        )

    return {
        "source_local_path": str(path.resolve()),
        "source_kind": "authorized_local_media",
        "model": model_name,
        "language": result.get("language", language),
        "text": str(result.get("text", "")).strip(),
        "segments": segments,
        "transcript_role": "extracted_representation_of_source",
        "production_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PoC Whisper — AgroLog MT")
    parser.add_argument("media", help="Arquivo local autorizado. URLs não são aceitas.")
    parser.add_argument("--model", default="turbo")
    parser.add_argument("--language", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if "://" in args.media:
        raise SystemExit("Este PoC aceita somente arquivo local, nunca URL remota.")

    payload = transcribe(Path(args.media), args.model, args.language)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"Transcrição salva em {args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
