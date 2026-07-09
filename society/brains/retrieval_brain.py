import re

from society.actions import Action
from society.brains.base import Brain

_BLANK_LINE_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


class RetrievalBrain(Brain):
    """A brain for `info_carrier` agents (books, sites, notes): no LLM calls,
    it never takes its own turn (always `wait`), and instead answers `read`
    queries via simple keyword-overlap retrieval over a fixed corpus.
    """

    def __init__(self, corpus_text: str = "", chunk_size: int = 300):
        """
        Args:
            corpus_text: Full text of the carried document/site.
            chunk_size: Max characters per chunk. Paragraphs (split on blank
                lines) longer than this are further split by size.
        """
        self.corpus_text = corpus_text
        self.chunk_size = chunk_size
        self.chunks = self._build_chunks(corpus_text, chunk_size)

    @staticmethod
    def _build_chunks(text: str, chunk_size: int) -> list[str]:
        paragraphs = [p.strip() for p in _BLANK_LINE_RE.split(text) if p.strip()]
        chunks: list[str] = []
        for para in paragraphs:
            if len(para) <= chunk_size:
                chunks.append(para)
            else:
                for i in range(0, len(para), chunk_size):
                    piece = para[i:i + chunk_size].strip()
                    if piece:
                        chunks.append(piece)
        return chunks

    async def decide(self, view: dict) -> Action:
        """info_carrier agents never act on their own; always wait."""
        return Action("wait")

    def retrieve(self, query: str, top_k: int = 2) -> str:
        """Score every chunk by keyword overlap with `query` and return the
        top_k chunks joined together (no embeddings/LLM involved).

        Overlap is computed at two granularities: whole whitespace-delimited
        words of the query (weighted higher) and individual characters of
        the query (weighted lower, important for CJK text with no spaces).
        """
        if not self.chunks:
            return ""

        words = [w for w in _WHITESPACE_RE.split(query.strip()) if w]
        chars = [c for c in dict.fromkeys(query) if not c.isspace()]

        scored = []
        for idx, chunk in enumerate(self.chunks):
            score = 0
            for word in words:
                if word and word in chunk:
                    score += 2
            for ch in chars:
                if ch in chunk:
                    score += 1
            scored.append((score, idx, chunk))

        scored.sort(key=lambda t: (-t[0], t[1]))
        top = scored[:top_k]
        if all(score == 0 for score, _, _ in top):
            return ""
        return "\n\n".join(chunk for _, _, chunk in top)
