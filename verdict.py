"""The shape of every answer this server gives.

The point of this project: a spoken assistant cannot show you a citation. A
listener has no way to tell a grounded answer from a confident guess, because
both arrive in the same voice at the same volume. So every reply here carries
what it is: whether it was answered, what it rested on, and what was looked in.

A refusal is a result, not an error. `REFUSED` means the server did its work
and found nothing it could stand behind. That is a successful call.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Verdict = Literal["ANSWERED", "REFUSED"]


@dataclass
class Assay:
    """One thing that was actually looked in, and what came back.

    Named after the discipline it enforces: a check that cannot come back
    negative is not a check. `hits` of 0 is a real and useful answer.
    """

    name: str
    looked_in: str
    hits: int

    def spoken(self) -> str:
        if self.hits == 0:
            return f"I looked in {self.looked_in} and found nothing"
        if self.hits == 1:
            return f"I found one match in {self.looked_in}"
        return f"I found {self.hits} matches in {self.looked_in}"


@dataclass
class Answer:
    """What the server hands back, every time, for every question."""

    verdict: Verdict
    question: str
    answer: str | None = None
    because: str = ""
    source: str | None = None
    quote: str | None = None
    checked: list[Assay] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checked"] = [asdict(a) for a in self.checked]
        return d

    def spoken(self) -> str:
        """What Alexa+ should actually say out loud.

        An answer names its source in the same breath, because a source
        mentioned later is a source the listener has already stopped hearing.
        A refusal says what was searched, so the person can tell the difference
        between "no" and "I have not got that".
        """
        if self.verdict == "ANSWERED":
            where = f", from {self.source}" if self.source else ""
            return f"{self.answer}{where}."
        looked = "; ".join(a.spoken() for a in self.checked) or "I had nothing to search"
        return f"I cannot answer that. {looked}. {self.because}".strip()


def answered(question: str, answer: str, source: str, quote: str,
             checked: list[Assay]) -> Answer:
    return Answer(
        verdict="ANSWERED",
        question=question,
        answer=answer,
        because=f"found in {source}",
        source=source,
        quote=quote,
        checked=checked,
    )


def refused(question: str, because: str, checked: list[Assay]) -> Answer:
    """Build a refusal.

    `because` must say what is missing, not that something went wrong. "I have
    no document covering the boiler" is useful. "An error occurred" is not.
    """
    return Answer(verdict="REFUSED", question=question, because=because, checked=checked)
