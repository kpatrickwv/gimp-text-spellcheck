"""Spellcheck logic for the GIMP text-spellcheck plugin.

Nothing in this module imports GIMP, so it can be tested on its own.
"""

import html
import os
import re

# ---------------------------------------------------------------------------
# Text and markup handling
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]*>")


def _escape(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("'", "&apos;")
                .replace('"', "&quot;"))


class LayerText:
    """A plain-text view of a text layer's contents, editable by position.

    GIMP text layers hold either plain text or Pango markup. For markup,
    styling tags can fall anywhere, including mid-word or around trailing
    spaces, so edits are made against the plain text and mapped back onto
    the text runs between tags. Tags are never touched, which keeps bold,
    italics, colors and fonts intact.
    """

    def __init__(self, source, is_markup):
        self.is_markup = is_markup
        # Each token: [kind, raw, decoded]. kind is "text" or "tag".
        self.tokens = []
        if not is_markup:
            self.tokens.append(["text", source, source])
            return
        pos = 0
        for m in _TAG_RE.finditer(source):
            if m.start() > pos:
                raw = source[pos:m.start()]
                self.tokens.append(["text", raw, html.unescape(raw)])
            self.tokens.append(["tag", m.group(), None])
            pos = m.end()
        if pos < len(source):
            raw = source[pos:]
            self.tokens.append(["text", raw, html.unescape(raw)])

    @property
    def plain(self):
        return "".join(t[2] for t in self.tokens if t[0] == "text")

    def replace(self, start, end, new):
        """Replace plain-text range [start, end) with new."""
        pos = 0
        inserted = False
        for tok in self.tokens:
            if tok[0] != "text":
                continue
            s, e = pos, pos + len(tok[2])
            pos = e
            ov_s, ov_e = max(s, start), min(e, end)
            if ov_s >= ov_e:
                continue
            text = tok[2]
            piece = "" if inserted else new
            tok[2] = text[:ov_s - s] + piece + text[ov_e - s:]
            tok[1] = _escape(tok[2]) if self.is_markup else tok[2]
            inserted = True
        if not inserted:
            raise ValueError("range not found in layer text")

    def serialize(self):
        return "".join(t[1] for t in self.tokens)


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[\w'\u2019]+")
_APOS = "'\u2019"


def find_words(text):
    """Yield (start, end, word) for each checkable word in text."""
    for m in _WORD_RE.finditer(text):
        raw = m.group()
        word = raw.strip(_APOS)
        if len(word) < 2:
            continue
        if any(c.isdigit() or c == "_" for c in word):
            continue
        start = m.start() + (len(raw) - len(raw.lstrip(_APOS)))
        yield start, start + len(word), word


def normalize(word):
    return word.replace("\u2019", "'").lower()


def match_case(template, word):
    """Give word the capitalization pattern of template."""
    if not word:
        return word
    if len(template) > 1 and template.isupper():
        return word.upper()
    if template[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def auto_layer_name(text):
    """Approximate the name GIMP gives an auto-named text layer."""
    line = text.strip().split("\n", 1)[0]
    return line if len(line) <= 30 else line[:30] + "..."


# ---------------------------------------------------------------------------
# Dictionary
# ---------------------------------------------------------------------------

class Checker:
    def __init__(self, user_dict_path):
        from spellchecker import SpellChecker
        self._sp = SpellChecker(language="en", distance=2)
        self.user_dict_path = user_dict_path
        self.user_words = set()
        self._suggest_cache = {}
        if user_dict_path and os.path.exists(user_dict_path):
            with open(user_dict_path, encoding="utf-8") as f:
                self.user_words = {normalize(w.strip()) for w in f if w.strip()}

    def is_known(self, word, ignores=()):
        n = normalize(word)
        if n in self.user_words or n in ignores:
            return True
        if self._sp.known([n]):
            return True
        # Possessives: "Alice's" is fine if "Alice" is.
        if n.endswith("'s") and (n[:-2] in self.user_words or self._sp.known([n[:-2]])):
            return True
        return False

    def suggestions(self, word, limit=8):
        n = normalize(word)
        if n not in self._suggest_cache:
            cands = self._sp.candidates(n) or set()
            cands.discard(n)
            ranked = sorted(cands, key=lambda w: (-self._sp.word_usage_frequency(w), w))
            self._suggest_cache[n] = ranked[:limit]
        return [match_case(word, s) for s in self._suggest_cache[n]]

    def add_word(self, word):
        n = normalize(word)
        if n in self.user_words:
            return
        self.user_words.add(n)
        if self.user_dict_path:
            os.makedirs(os.path.dirname(self.user_dict_path), exist_ok=True)
            with open(self.user_dict_path, "a", encoding="utf-8") as f:
                f.write(word + "\n")

    def misspellings(self, text, ignores=()):
        return [(s, e, w) for s, e, w in find_words(text)
                if not self.is_known(w, ignores)]
