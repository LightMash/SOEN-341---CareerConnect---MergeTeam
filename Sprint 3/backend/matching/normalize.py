"""
The one text-normalization function used everywhere in the matching feature
(catalog aliases, search queries, custom qualification names, resume lines).
Two strings that should be "the same qualification" must normalize to the
same text, so never compare raw user input anywhere else.
"""

import re
import unicodedata

# Characters that separate words (turned into a space), so "Python/Java" or
# "Skills: SQL, Git" still splits into separate words.
_SEPARATORS = re.compile(r"[/\\,;:|()\[\]{}<>•·▪●◦\-–—_*\"!?=~]")

# Every other punctuation mark is simply dropped, so "Ph.D." == "PhD" and
# "Bachelor's" == "Bachelors". + and # are kept on purpose: "C++" and "C#".
_DROPPED = re.compile(r"[^\w\s+#]")


def normalize(text: str | None, keep_case: bool = False) -> str:
    """
    Lowercase (unless keep_case), strip accents, turn separators into spaces,
    drop other punctuation except + and #, and collapse whitespace.

        normalize("Ph.D.")          -> "phd"
        normalize("Baccalauréat")   -> "baccalaureat"
        normalize("C++ / C#")       -> "c++ c#"
    """
    if not text:
        return ""
    # NFKD splits "é" into "e" + a combining accent, which is then removed.
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    if not keep_case:
        stripped = stripped.lower()
    stripped = _SEPARATORS.sub(" ", stripped)
    stripped = _DROPPED.sub("", stripped)
    return " ".join(stripped.split())
