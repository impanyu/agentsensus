"""Language-uniform text length helpers, backed by tiktoken's o200k_base encoding.

Character counts are a poor cross-language length measure: Chinese text runs
close to 1 token/char, while English runs several chars/token, so a shared
char-based cap over-truncates Chinese and under-truncates English relative to
actual information content. Token counts (o200k_base, the encoding behind
GPT-4o-class models) are far more uniform across languages, so memory length
caps should be measured in tokens.
"""

import tiktoken

_ENC = None


def _enc():
    global _ENC
    if _ENC is None:
        _ENC = tiktoken.get_encoding("o200k_base")
    return _ENC


def count_tokens(text: str) -> int:
    """Return the o200k_base token count of `text`."""
    return len(_enc().encode(text))


def truncate_to_tokens(text: str, n: int) -> str:
    """Truncate `text` to at most `n` o200k_base tokens, then strip whitespace.

    Safe on multi-byte/multi-char token boundaries: o200k tokens always
    decode to whole strings, so slicing the encoded token ids and decoding
    back never splits a character.
    """
    enc = _enc()
    tokens = enc.encode(text)
    if len(tokens) <= n:
        return text.strip()
    return enc.decode(tokens[:n]).strip()
