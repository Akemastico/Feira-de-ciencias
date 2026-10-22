import re

_EMOTION_RE = re.compile(r'"emocao"\s*:\s*"([^"\\]*)"')
_RESPOSTA_KEY_RE = re.compile(r'"resposta"\s*:\s*"')

_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
    '"': '"', "\\": "\\", "/": "/",
}


class ResponseParser:
    """Extrai 'emocao' e decodifica o texto de 'resposta' incrementalmente."""

    def __init__(self):
        self.buffer = ""
        self.emotion = None
        self._resp_started = False
        self._resp_done = False
        self._decoded_len = 0

    def feed(self, chunk: str):
        self.buffer += chunk
        if self.emotion is None:
            match = _EMOTION_RE.search(self.buffer)
            if match:
                self.emotion = match.group(1)
        if not self._resp_started and not self._resp_done:
            match = _RESPOSTA_KEY_RE.search(self.buffer)
            if match:
                self._resp_started = True
                self._decoded_len = match.end()
        return self

    def drain_text(self) -> str:
        if not self._resp_started or self._resp_done:
            return ""
        out = []
        i = self._decoded_len
        n = len(self.buffer)
        while i < n:
            ch = self.buffer[i]
            if ch == "\\":
                if i + 1 >= n:
                    break
                nxt = self.buffer[i + 1]
                if nxt == "u":
                    if i + 6 > n:
                        break
                    hexs = self.buffer[i + 2:i + 6]
                    if all(h in "0123456789abcdefABCDEF" for h in hexs):
                        out.append(chr(int(hexs, 16)))
                        i += 6
                        continue
                    out.append(ch)
                    i += 1
                    continue
                out.append(_ESCAPES.get(nxt, ch))
                i += 2
            elif ch == '"':
                self._resp_done = True
                break
            else:
                out.append(ch)
                i += 1
        self._decoded_len = i
        return "".join(out)
