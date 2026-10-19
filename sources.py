"""The only things this server is allowed to answer from.

A household's own documents. Nothing else. The server has no model, no web
access and no general knowledge, which is the point: it can only ever tell you
something that is written down somewhere you can go and read yourself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mcp_refusal import Answer, Assay, answered, refused

DOCS_DIR = Path(__file__).parent / "documents"

# Words that carry no signal in a lookup. Kept small and visible rather than
# pulled from a stopword package, so anyone reading this can see exactly what
# the matcher ignores.
NOISE = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "what",
    "when", "where", "who", "how", "my", "our", "i", "we", "to", "of", "on",
    "in", "for", "it", "that", "this", "and", "or", "me", "tell", "about",
    # Quantifiers and modals carry no lookup signal, and leaving them in
    # inflated the term count: "how much is the rent" counted as two terms
    # and so demanded two matches, which made it unanswerable.
    "much", "many", "long", "should", "can", "could", "will", "would", "need",
    "am", "be", "get", "got", "have", "has", "there", "any",
}

# Crude prefix stem. "responsibility" and "responsible" have to match each
# other or the lookup misses the line that answers the question, which is
# exactly what happened before this existed. Six characters is short enough to
# join a word to its relatives and long enough not to collide across topics.
STEM_LEN = 6


def stem(word: str) -> str:
    return word[:STEM_LEN]


@dataclass
class Document:
    name: str
    text: str

    @property
    def lines(self) -> list[str]:
        return [ln.strip() for ln in self.text.splitlines() if ln.strip()]


def load() -> list[Document]:
    """Read every document the household has put in the folder."""
    if not DOCS_DIR.is_dir():
        return []
    return [
        Document(name=p.name, text=p.read_text(encoding="utf-8", errors="replace"))
        for p in sorted(DOCS_DIR.glob("*.md"))
    ]


def terms(question: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", question.lower())
    kept = [w for w in words if w not in NOISE and len(w) > 2]
    # Deduplicate on the stem so "rent" and "rental" do not count twice and
    # quietly raise the bar the answer has to clear.
    seen, out = set(), []
    for w in kept:
        s = stem(w)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def ask(question: str) -> Answer:
    """Answer only from the documents, or refuse and say what was searched."""
    docs = load()

    if not docs:
        return refused(
            question,
            because="There are no documents loaded, so there is nothing I could "
                    "have answered from.",
            checked=[Assay(name="documents", looked_in="the household folder", hits=0)],
        )

    wanted = terms(question)
    if not wanted:
        return refused(
            question,
            because="I could not find anything specific enough in that question "
                    "to look up.",
            checked=[Assay(name="question", looked_in="the question itself", hits=0)],
        )

    checked: list[Assay] = []
    best: tuple[int, Document, str] | None = None

    for doc in docs:
        hits = 0
        best_line, best_score = "", 0
        for line in doc.lines:
            low = line.lower()
            score = sum(1 for w in wanted if w in low)
            if score:
                hits += 1
                if score > best_score:
                    best_line, best_score = line, score
        checked.append(Assay(name=doc.name, looked_in=doc.name, hits=hits))
        if best_score and (best is None or best_score > best[0]):
            best = (best_score, doc, best_line)

    # One matching word out of several is a coincidence, not an answer.
    # Refusing is the whole product: a wrong spoken answer costs more than a no.
    #
    # But the threshold has to scale with the question. "How much is the rent"
    # reduces to the single term "rent", and a flat requirement of two matches
    # made every one-term question unanswerable, including ones the documents
    # answer outright. Found by running it, not by reading it.
    # Half the question's terms, rounded up. A fixed number cannot work for
    # both "how much is the rent" and a seven word question, and a flat two
    # made every short question unanswerable.
    need = max(1, (len(wanted) + 1) // 2)
    if best is None or best[0] < need:
        near = sum(a.hits for a in checked)
        because = (
            "Nothing in your documents covers that."
            if near == 0 else
            "I found passages that share a word with your question, but nothing "
            "that actually answers it, so I am not going to guess."
        )
        return refused(question, because=because, checked=checked)

    _score, doc, line = best
    return answered(question, answer=line, source=doc.name, quote=line, checked=checked)
