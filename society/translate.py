"""Memory translation tool (English-translation delivery, Deliverable 2).

Simulations run in the source language (e.g. Chinese for Three Kingdoms),
but the paper and any human-facing appendix must be in English. This module
translates a `SharedMemory.export()` dump (see `society/ltm.py`) into a
target language, adding a `text_<lang>` field to each entry while leaving
the original `text` untouched, and can build a compact bilingual table for
a paper appendix.
"""

import argparse
import json
import re
import warnings

_LANG_NAMES = {
    "en": "English",
    "zh": "Chinese",
}


def _lang_name(lang: str) -> str:
    return _LANG_NAMES.get(lang, lang)


def _batch_prompt(texts: list[str], target_language: str) -> str:
    lang_name = _lang_name(target_language)
    numbered = "\n".join(f"{i}: {t}" for i, t in enumerate(texts))
    return (
        f"Translate each of the following {len(texts)} memory statements "
        f"into {lang_name}. Reply with ONLY a JSON array of {len(texts)} "
        "strings, in the exact same order as the input, with no extra "
        "commentary, prefix, or Markdown.\n\n"
        f"Memory statements:\n{numbered}\n"
    )


def _single_prompt(text: str, target_language: str) -> str:
    lang_name = _lang_name(target_language)
    return (
        f"Translate the following memory statement into {lang_name}. "
        "Reply with ONLY the translated text, no explanation or quotes.\n\n"
        f"Memory statement: {text}"
    )


def _parse_json_array(reply: str, expected_len: int) -> list[str] | None:
    """Tolerant parse of a JSON array of strings from an LLM reply.

    Returns None (rather than raising) if the reply doesn't contain a
    parseable JSON array, or the array's length doesn't match
    `expected_len` -- callers fall back to a per-entry retry in that case.
    """
    match = re.search(r"\[.*\]", reply or "", re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, list) or len(parsed) != expected_len:
        return None
    return [str(x) for x in parsed]


async def translate_entries(
    entries: list[dict],
    llm,
    target_language: str = "en",
    batch_size: int = 25,
) -> list[dict]:
    """Translate LTM export entries' `text` into `target_language`.

    Args:
        entries: LTM export entries (each at least {"id", "text", "owners",
            "meta", ...}), e.g. from `SharedMemory.export()` /
            `SharedMemory.all_entries()`.
        llm: Async chat client duck-typing LLMClient/FakeLLM
            (`await llm.chat(prompt, system=..., bucket=...) -> str`).
        target_language: Language code to translate into (e.g. "en").
        batch_size: Number of entries translated per llm.chat call.

    Returns:
        A NEW list of entries (originals untouched), each the original
        entry's fields plus `text_<target_language>` holding the
        translation. Order is preserved. On unrecoverable translation
        failure for an entry, `text_<target_language>` is set to "" and a
        warning is emitted.
    """
    field = f"text_{target_language}"
    out_entries = [dict(e) for e in entries]

    for start in range(0, len(out_entries), batch_size):
        batch = out_entries[start : start + batch_size]
        texts = [e.get("text", "") for e in batch]

        reply = await llm.chat(
            _batch_prompt(texts, target_language),
            system=None,
            bucket="translate",
        )
        translations = _parse_json_array(reply, len(batch))

        if translations is not None:
            for entry, translation in zip(batch, translations):
                entry[field] = translation
            continue

        # Batch parse failed -- fall back to per-entry translation.
        warnings.warn(
            f"translate_entries: batch translation parse failed for "
            f"entries {start}..{start + len(batch) - 1}; falling back to "
            "per-entry translation",
            stacklevel=2,
        )
        for entry in batch:
            text = entry.get("text", "")
            try:
                single_reply = await llm.chat(
                    _single_prompt(text, target_language),
                    system=None,
                    bucket="translate",
                )
                entry[field] = (single_reply or "").strip()
            except Exception:
                entry[field] = ""
            if not entry[field]:
                warnings.warn(
                    f"translate_entries: could not translate entry "
                    f"id={entry.get('id')!r}; leaving {field}=''",
                    stacklevel=2,
                )

    return out_entries


def to_bilingual_table(entries: list[dict], lang: str = "en") -> list[dict]:
    """Build a compact bilingual table for a paper appendix.

    Args:
        entries: Entries as produced by `translate_entries` (or any entries
            already carrying a `text_<lang>` field).
        lang: Language code whose `text_<lang>` field is used as the
            translation column.

    Returns:
        [{"id", "source", "translation", "owners"}, ...], one row per
        entry, in the same order as `entries`.
    """
    field = f"text_{lang}"
    return [
        {
            "id": e.get("id"),
            "source": e.get("text", ""),
            "translation": e.get(field, ""),
            "owners": e.get("owners", []),
        }
        for e in entries
    ]


def _load_entries(ltm_path: str) -> list[dict]:
    with open(ltm_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        if isinstance(data.get("ltm"), list):
            return data["ltm"]
        if isinstance(data.get("entries"), list):
            return data["entries"]
        raise ValueError(
            f"{ltm_path}: expected a JSON array of entries, or a dict with "
            "an 'ltm'/'entries' array (e.g. ltm_final.json or a "
            "checkpoint.json), got a dict with neither"
        )
    if isinstance(data, list):
        return data
    raise ValueError(f"{ltm_path}: expected a JSON array or object, got {type(data)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate a SharedMemory export (LTM) into another language"
    )
    parser.add_argument(
        "--ltm",
        required=True,
        help="path to an LTM export json (e.g. ltm_final.json, *.ltm.json, or a "
        "checkpoint.json with an 'ltm' key)",
    )
    parser.add_argument("--out", required=True, help="path to write the augmented entries json")
    parser.add_argument("--lang", default="en", help="target language code (default: en)")
    parser.add_argument(
        "--config", default="config.json", help="path to config.json (api_key, base_url, ...)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=25, help="entries translated per llm.chat call"
    )
    return parser


def main(argv=None):
    import asyncio

    from society.run import _build_llm_and_embed

    parser = _build_parser()
    args = parser.parse_args(argv)

    entries = _load_entries(args.ltm)
    llm, _embed_fn = _build_llm_and_embed(args.config)

    translated = asyncio.run(
        translate_entries(entries, llm, target_language=args.lang, batch_size=args.batch_size)
    )

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)

    print(json.dumps({"count": len(translated), "lang": args.lang}, ensure_ascii=False))
    return translated


if __name__ == "__main__":
    main()
