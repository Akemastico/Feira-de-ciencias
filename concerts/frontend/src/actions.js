// Dispatcher das ações que o modelo pede.
//
// Regra de ouro: o frontend NUNCA executa código que veio do modelo. A
// mensagem do servidor traz só um nome ("expressao", "animacao", "texto",
// "led", "som") e os argumentos. Aqui esse nome é procurado numa allowlist
// fechada e vira chamada de um método que já existe no BMO — nada de eval,
// new Function ou import dinâmico.
//
// A allowlist do cliente é a mesma do servidor: o que o backend já validou
// é conferido de novo aqui, porque a mensagem chega pela rede.

const EMOTIONS = new Set(['neutro', 'feliz', 'triste', 'surpreso', 'curioso', 'bravo']);
const ANIMATIONS = new Set(['pular', 'dancar', 'tremer', 'acenar', 'olhar_lado', 'dormir']);
const SOUNDS = new Set(['bip', 'erro', 'sucesso']);
const HEX = /^#[0-9a-fA-F]{6}$/;

const DURACAO_PADRAO = 1.5;
const DURACAO_MIN = 0.1;
const DURACAO_MAX = 10;
const TEXTO_MAX = 200;

function numero(valor, padrao, min, max) {
  if (typeof valor !== 'number' || !Number.isFinite(valor)) return padrao;
  return Math.min(max, Math.max(min, valor));
}

// Um método só é chamado se existir de verdade: enquanto o BMO ainda não tem
// playAnimation/setLed (eles chegam na task de animações e LED), a ação é
// ignorada com um aviso em vez de estourar um TypeError.
function temMetodo(alvo, nome) {
  return !!alvo && typeof alvo[nome] === 'function';
}

export class ActionDispatcher {
  constructor({ bmo, ui, audio, log = console } = {}) {
    this.bmo = bmo;
    this.ui = ui;
    this.audio = audio;
    this.log = log && typeof log.warn === 'function' ? log : console;

    // Nome da ação -> o que fazer com ela. O objeto é escrito aqui, no
    // código; o nome que chega da rede só escolhe uma destas entradas.
    this.handlers = {
      expressao: (args) => {
        this.bmo.setEmotion(args.emocao);
        this.ui.setEmocao(args.emocao);
      },
      animacao: (args) => this.bmo.playAnimation(args.nome, args.duracao),
      texto: (args) => this.ui.setFrase(args.texto),
      led: (args) => this.bmo.setLed(args.cor, args.piscar),
      som: (args) => this.audio.playBeep(args.tipo),
    };

    // O que precisa existir para a ação valer.
    this.disponivel = {
      expressao: () => temMetodo(this.bmo, 'setEmotion') && temMetodo(this.ui, 'setEmocao'),
      animacao: () => temMetodo(this.bmo, 'playAnimation'),
      texto: () => temMetodo(this.ui, 'setFrase'),
      led: () => temMetodo(this.bmo, 'setLed'),
      som: () => temMetodo(this.audio, 'playBeep'),
    };
  }

  // Devolve os argumentos conferidos da ação, ou null quando ela não vale
  // (nome fora da allowlist ou argumento inválido).
  validar(acao) {
    if (!acao || typeof acao.nome !== 'string') return null;
    const args = acao.args;
    if (!args || typeof args !== 'object' || Array.isArray(args)) return null;

    switch (acao.nome) {
      case 'expressao':
        return EMOTIONS.has(args.emocao) ? { emocao: args.emocao } : null;
      case 'animacao':
        return ANIMATIONS.has(args.nome)
          ? {
            nome: args.nome,
            duracao: numero(args.duracao, DURACAO_PADRAO, DURACAO_MIN, DURACAO_MAX),
          }
          : null;
      case 'texto': {
        if (typeof args.texto !== 'string') return null;
        const texto = args.texto.trim().slice(0, TEXTO_MAX);
        return texto ? { texto } : null;
      }
      case 'led':
        return typeof args.cor === 'string' && HEX.test(args.cor)
          ? { cor: args.cor, piscar: Boolean(args.piscar) }
          : null;
      case 'som':
        return SOUNDS.has(args.tipo) ? { tipo: args.tipo } : null;
      default:
        return null;
    }
  }

  // Executa uma ação. Devolve true quando ela rodou de verdade e false
  // quando foi ignorada (nome desconhecido, args inválidos, método que ainda
  // não existe ou erro no handler). Nunca levanta erro: a fala do BMO
  // precisa continuar mesmo com uma ação ruim no meio.
  execute(acao) {
    const args = this.validar(acao);
    if (!args) {
      this.log.warn('Ação ignorada:', acao);
      return false;
    }
    if (!this.disponivel[acao.nome]()) {
      this.log.warn('Ação ainda não suportada pelo BMO:', acao.nome);
      return false;
    }
    try {
      this.handlers[acao.nome](args);
      return true;
    } catch (err) {
      this.log.warn('Falha ao executar ação', acao.nome, err);
      return false;
    }
  }

  // Executa um lote de ações e devolve quantas rodaram. Uma ação ruim não
  // derruba as outras.
  executeAll(acoes) {
    if (!Array.isArray(acoes)) return 0;
    return acoes.reduce((total, acao) => total + (this.execute(acao) ? 1 : 0), 0);
  }
}
