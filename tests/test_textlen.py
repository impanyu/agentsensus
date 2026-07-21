from society.textlen import count_tokens, truncate_to_tokens

ZH_SHORT = "黛玉葬花"
ZH_LONG = "宝玉挨打了" * 30  # long compound, repeated clause
EN_SHORT = "the king died"
EN_LONG = "the quick brown fox jumps over the lazy dog " * 20


def test_count_tokens_deterministic():
    assert count_tokens(ZH_SHORT) == count_tokens(ZH_SHORT)
    assert count_tokens(EN_SHORT) == count_tokens(EN_SHORT)


def test_count_tokens_zh_roughly_tracks_char_count():
    # Chinese is close to 1 token/char (allow generous slack either way).
    n_chars = len(ZH_LONG)
    n_tokens = count_tokens(ZH_LONG)
    assert n_tokens > 0
    assert 0.5 * n_chars <= n_tokens <= 2.0 * n_chars


def test_count_tokens_en_much_smaller_than_char_count():
    n_chars = len(EN_LONG)
    n_tokens = count_tokens(EN_LONG)
    assert n_tokens > 0
    # English tokens are several chars each, so token count << char count.
    assert n_tokens < n_chars / 2


def test_truncate_to_tokens_respects_limit():
    truncated = truncate_to_tokens(EN_LONG, 5)
    assert count_tokens(truncated) <= 5


def test_truncate_to_tokens_is_prefix_like():
    truncated = truncate_to_tokens(EN_LONG, 5)
    assert EN_LONG.startswith(truncated) or truncated in EN_LONG[: len(truncated) + 5]


def test_truncate_to_tokens_noop_when_under_limit():
    assert truncate_to_tokens(EN_SHORT, 50) == EN_SHORT.strip()


def test_truncate_to_tokens_zh_respects_limit():
    truncated = truncate_to_tokens(ZH_LONG, 10)
    assert count_tokens(truncated) <= 10
