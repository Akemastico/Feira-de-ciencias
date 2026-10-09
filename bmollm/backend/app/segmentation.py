import re

_ABBREVIATIONS = {
    "sr", "sra", "srta", "dr", "dra", "prof", "profa", "etc", "ex", "av",
    "eng", "pag", "fig", "num", "obs", "jan", "fev", "mar", "abr", "mai",
    "jun", "jul", "ago", "set", "out", "nov", "dez",
}

_SENTENCE_END = re.compile(r"([.!?…]+)(\s+|$)")


class SentenceSplitter:
    """Divide um fluxo de texto em frases completas para TTS incremental."""

    def __init__(self):
        self._buf = ""

    def feed(self, text: str):
        self._buf += text
        sentences = []
        pos = 0
        while True:
            match = _SENTENCE_END.search(self._buf, pos)
            if match is None:
                break
            preceding = self._buf[: match.start(1)]
            word_match = re.search(r"([A-Za-zÀ-ÿ]+)\s*$", preceding)
            if word_match and word_match.group(1).lower() in _ABBREVIATIONS:
                pos = match.end(1)
                continue
            sentence = self._buf[: match.end(1)].strip()
            self._buf = self._buf[match.end(1):]
            if sentence:
                sentences.append(sentence)
            pos = 0
        return sentences

    def flush(self):
        text = self._buf.strip()
        self._buf = ""
        return [text] if text else []
