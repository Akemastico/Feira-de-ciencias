"""Contrato de ações do modelo: allowlist, validação e leitura no streaming.

O modelo pode pedir que o BMO mude a expressão, rode uma animação, mostre um
texto, acenda o LED ou toque um som. A lista é fechada: tudo que não estiver
nesta allowlist é descartado no backend. O frontend nunca recebe código do
modelo, só o nome da ação e os args já conferidos.
"""

from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from .config import settings

log = logging.getLogger(__name__)

# Allowlist fechada: o que o modelo pode pedir.
NOMES = ("expressao", "animacao", "texto", "led", "som")

ANIMACOES = {"pular", "dancar", "tremer", "acenar", "olhar_lado", "dormir"}
SONS = {"bip", "erro", "sucesso"}

MAX_ACOES = 8
TEXTO_MAX = 200

_COR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_ACOES_RE = re.compile(r'"acoes"\s*:\s*\[')
_NOME_RE = re.compile(r'"nome"\s*:\s*"([^"]*)"')
_ARGS_RE = re.compile(r'"args"\s*:\s*\{')


@dataclass(frozen=True)
class Acao:
    """Uma ação já validada, pronta para ir para o frontend."""

    nome: str
    args: dict[str, Any]


def _numero(valor: Any, minimo: float, maximo: float, padrao: float) -> float:
    """Devolve o número se estiver na faixa; senão devolve o padrão."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return padrao
    if minimo <= valor <= maximo:
        return float(valor)
    return padrao


def _args_expressao(args: dict) -> dict | None:
    emocao = args.get("emocao")
    if not isinstance(emocao, str) or emocao not in settings.EMOTIONS:
        return None
    return {"emocao": emocao}


def _args_animacao(args: dict) -> dict | None:
    nome = args.get("nome")
    if not isinstance(nome, str) or nome not in ANIMACOES:
        return None
    return {
        "nome": nome,
        "duracao": _numero(args.get("duracao"), 0.1, 10.0, 1.5),
    }


def _args_texto(args: dict) -> dict | None:
    texto = args.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        return None
    if len(texto) > TEXTO_MAX:
        log.warning("Texto de ação maior que %d caracteres; cortei", TEXTO_MAX)
        texto = texto[:TEXTO_MAX]
    return {
        "texto": texto,
        "duracao": _numero(args.get("duracao"), 0.5, 30.0, 4.0),
    }


def _args_led(args: dict) -> dict | None:
    cor = args.get("cor")
    if not isinstance(cor, str) or not _COR_RE.match(cor):
        return None
    piscar = args.get("piscar", False)
    if not isinstance(piscar, bool):
        piscar = False
    return {"cor": cor, "piscar": piscar}


def _args_som(args: dict) -> dict | None:
    tipo = args.get("tipo")
    if not isinstance(tipo, str) or tipo not in SONS:
        return None
    return {"tipo": tipo}


# Validador por ação: devolve os args normalizados ou None (ação descartada).
_VALIDADORES = {
    "expressao": _args_expressao,
    "animacao": _args_animacao,
    "texto": _args_texto,
    "led": _args_led,
    "som": _args_som,
}


def normalizar_acoes(raw: object) -> list[Acao]:
    """Filtra a lista crua do modelo e devolve só as ações válidas.

    Cada item precisa ter 'nome' (da allowlist) e 'args' (objeto). Args fora do
    contrato são descartados; ação desconhecida ou com args inválidos some
    sem derrubar o resto.
    """
    if not isinstance(raw, list):
        return []

    acoes: list[Acao] = []
    for item in raw[:MAX_ACOES]:
        if not isinstance(item, dict):
            continue

        nome = item.get("nome")
        args = item.get("args")
        if not isinstance(nome, str) or not isinstance(args, dict):
            continue

        validador = _VALIDADORES.get(nome)
        if validador is None:
            log.warning("Ação desconhecida do modelo: %r", nome)
            continue

        normalizados = validador(args)
        if normalizados is None:
            log.warning("Ação %r com args inválidos: %r", nome, args)
            continue

        acoes.append(Acao(nome=nome, args=normalizados))

    return acoes


def acoes_schema() -> dict:
    """Trecho de schema que o Ollama recebe quando as ações estão ligadas."""
    return {
        "type": "array",
        "maxItems": MAX_ACOES,
        "items": {
            "type": "object",
            "properties": {
                "nome": {"enum": list(NOMES)},
                "args": {"type": "object"},
            },
            "required": ["nome", "args"],
        },
    }


def _fim_do_bloco(texto: str, inicio: int, abre: str, fecha: str) -> int | None:
    """Índice do fechamento que fecha o bloco aberto em `inicio` (ou None).

    Strings e escapes são respeitados: um ']' dentro de um texto não fecha o
    array.
    """
    profundidade = 0
    dentro_de_string = False
    escapado = False
    for i in range(inicio, len(texto)):
        ch = texto[i]
        if dentro_de_string:
            if escapado:
                escapado = False
            elif ch == "\\":
                escapado = True
            elif ch == '"':
                dentro_de_string = False
            continue
        if ch == '"':
            dentro_de_string = True
        elif ch == abre:
            profundidade += 1
        elif ch == fecha:
            profundidade -= 1
            if profundidade == 0:
                return i
    return None


def _fim_do_array(texto: str, inicio: int) -> int | None:
    """Índice do ']' que fecha o array começado em `inicio` (ou None)."""
    return _fim_do_bloco(texto, inicio, "[", "]")


def _fim_do_objeto(texto: str, inicio: int) -> int | None:
    """Índice do '}' que fecha o objeto começado em `inicio` (ou None)."""
    return _fim_do_bloco(texto, inicio, "{", "}")


def _dividir_itens(texto: str) -> list[str]:
    """Separa os itens do array nas vírgulas do nível mais externo."""
    itens: list[str] = []
    atual: list[str] = []
    profundidade = 0
    dentro_de_string = False
    escapado = False

    for ch in texto:
        if dentro_de_string:
            atual.append(ch)
            if escapado:
                escapado = False
            elif ch == "\\":
                escapado = True
            elif ch == '"':
                dentro_de_string = False
            continue

        if ch == '"':
            dentro_de_string = True
            atual.append(ch)
            continue

        if ch in "[{":
            profundidade += 1
        elif ch in "]}":
            profundidade -= 1

        if ch == "," and profundidade == 0:
            itens.append("".join(atual))
            atual = []
            continue

        atual.append(ch)

    if atual:
        itens.append("".join(atual))

    return [item for item in itens if item.strip()]


def _campos_do_item(item: str) -> tuple[str | None, dict | None]:
    """Acha 'nome' e 'args' de um item do array.

    O 'nome' é procurado fora do bloco de args: dentro dele pode existir outro
    'nome' (o da animação, por exemplo) que não é o nome da ação.
    """
    args = None
    bloco_args = None

    match = _ARGS_RE.search(item)
    if match:
        inicio = match.end() - 1  # posição do '{' dos args
        fim = _fim_do_objeto(item, inicio)
        if fim is not None:
            bloco_args = (inicio, fim)
            try:
                args = json.loads(item[inicio:fim + 1])
            except json.JSONDecodeError:
                args = None

    nome = None
    for achado in _NOME_RE.finditer(item):
        if bloco_args and bloco_args[0] <= achado.start() <= bloco_args[1]:
            continue  # é o "nome" de dentro dos args
        nome = achado.group(1)
        break

    if not isinstance(args, dict):
        args = None

    return nome, args


class ActionStreamParser:
    """Acha o array 'acoes' no JSON que o modelo entrega em pedaços.

    O JSON chega por streaming (um pedaço por vez). O parser espera o array
    fechar, decodifica e valida as ações. Se o JSON vier quebrado, loga um
    aviso e devolve [] — a fala continua.
    """

    def __init__(self):
        self.buffer = ""
        self.concluido = False

    def feed(self, chunk: str) -> list[Acao]:
        """Acumula o pedaço e devolve as ações (se alguma apareceu agora)."""
        if self.concluido:
            return []

        self.buffer += chunk
        return self._extrair()

    def _extrair(self) -> list[Acao]:
        match = _ACOES_RE.search(self.buffer)
        if match is None:
            return []

        inicio = match.end() - 1  # posição do '['
        fim = _fim_do_array(self.buffer, inicio)
        if fim is None:
            return []  # o array ainda não fechou: espera mais pedaços

        # Depois do array não há mais ação: para de procurar e não repete.
        self.concluido = True
        texto = self.buffer[inicio:fim + 1]

        try:
            bruto = json.loads(texto)
        except json.JSONDecodeError:
            log.warning("JSON de ações quebrado; vou tentar recuperar as ações")
            acoes = self._resgatar(texto)
        else:
            acoes = normalizar_acoes(bruto)

        return acoes[:MAX_ACOES]

    def _resgatar(self, texto: str) -> list[Acao]:
        """Pega as ações de um JSON quebrado, item por item.

        O modelo às vezes erra a vírgula e sobra uma chave dentro do objeto da
        ação. Em vez de jogar tudo fora, lemos nome e args de cada item
        separado.
        """
        acoes: list[Acao] = []
        for item in _dividir_itens(texto[1:-1]):  # sem os colchetes
            nome, args = _campos_do_item(item)
            if nome is None or args is None:
                continue
            acoes.extend(normalizar_acoes([{"nome": nome, "args": args}]))
        return acoes
