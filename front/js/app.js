/**
 * Estado da tela de histórico (paginação + filtros ativos).
 */
const estado = {
  categorias: [],
  contas: [],
  limite: 10,
  skip: 0,
  total: 0,
  filtros: {},
};

// Utilidades (formatarMoeda, formatarDataBR, hojeISO, escaparHtml, toast,
// mostrarErro, limparErro) vêm de js/utils.js, carregado antes deste arquivo.

function categoriaPorId(id) {
  return estado.categorias.find((c) => c.id === id);
}

function contaPorId(id) {
  return estado.contas.find((c) => c.id === id);
}

// ---------- Navegação entre telas ----------

function mostrarTelaAuth() {
  document.getElementById("topo-publico").classList.remove("oculto");
  document.getElementById("tela-auth").classList.remove("oculto");
  document.getElementById("app-shell").classList.add("oculto");
}

async function mostrarTelaApp() {
  document.getElementById("topo-publico").classList.add("oculto");
  document.getElementById("tela-auth").classList.add("oculto");
  document.getElementById("app-shell").classList.remove("oculto");
  await iniciarDashboard();

  // Se veio de outra página com #contas (link "Contas" da sidebar), rola
  // até o painel de contas assim que o dashboard estiver pronto.
  if (window.location.hash === "#contas") {
    abrirModalContas();
  }
}

document.addEventListener("sessao-expirada", () => {
  toast("Sessão expirada. Faça login de novo.", "erro");
  mostrarTelaAuth();
});

// Chamada pela sidebar (js/sidebar.js) quando o link "Contas" é clicado
// nesta própria página — aqui não existe um modal de listagem, o painel
// de contas já fica inline no dashboard, então só rolamos até ele.
function abrirModalContas() {
  const painel = document.getElementById("painel-contas");
  if (painel) painel.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- Abas de login/cadastro ----------

document.querySelectorAll(".aba").forEach((aba) => {
  aba.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach((a) => {
      a.classList.remove("is-ativa");
      a.setAttribute("aria-selected", "false");
    });
    aba.classList.add("is-ativa");
    aba.setAttribute("aria-selected", "true");

    document.querySelectorAll(".tela-auth .formulario").forEach((f) => f.classList.add("oculto"));
    document.querySelector(`.formulario[data-painel="${aba.dataset.aba}"]`).classList.remove("oculto");
  });
});

// ---------- Login / Cadastro ----------

document.getElementById("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-login");
  const dados = new FormData(evento.target);
  try {
    const resposta = await Api.login(dados.get("email"), dados.get("senha"));
    Auth.setToken(resposta.access_token);
    evento.target.reset();
    await mostrarTelaApp();
  } catch (erro) {
    mostrarErro("erro-login", erro.status === 401 ? "Email ou senha incorretos." : erro.message);
  }
});

document.getElementById("form-cadastro").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-cadastro");
  const dados = new FormData(evento.target);
  try {
    await Api.cadastrar(dados.get("nome"), dados.get("email"), dados.get("senha"));
    const resposta = await Api.login(dados.get("email"), dados.get("senha"));
    Auth.setToken(resposta.access_token);
    evento.target.reset();
    await mostrarTelaApp();
  } catch (erro) {
    mostrarErro("erro-cadastro", erro.status === 409 ? "Esse email já está cadastrado." : erro.message);
  }
});

// ---------- Dashboard: inicialização ----------

async function iniciarDashboard() {
  document.querySelector('#form-movimentacao input[name="data"]').value = hojeISO();
  await Promise.all([carregarCategorias(), carregarContas()]);
  await Promise.all([atualizarSaldo(), carregarHistorico()]);
}

async function carregarCategorias() {
  estado.categorias = await Api.categorias();
  preencherSelectCategorias();
}

function preencherSelectCategorias() {
  const tipoSelecionado = document.querySelector('input[name="tipo"]:checked').value;

  const selects = [
    { el: document.getElementById("select-categoria"), tipo: tipoSelecionado },
    { el: document.getElementById("select-categoria-edicao"), tipo: null },
  ];

  selects.forEach(({ el, tipo }) => {
    const valorAtual = el.value;
    el.innerHTML = "";
    estado.categorias
      .filter((c) => !tipo || c.tipo === tipo)
      .forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.nome;
        el.appendChild(opt);
      });
    if (valorAtual) el.value = valorAtual;
  });

  const filtroCategoria = document.getElementById("filtro-categoria");
  const valorFiltroAtual = filtroCategoria.value;
  filtroCategoria.innerHTML = '<option value="">Todas</option>';
  estado.categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    filtroCategoria.appendChild(opt);
  });
  filtroCategoria.value = valorFiltroAtual;
}

document.querySelectorAll('input[name="tipo"]').forEach((radio) => {
  radio.addEventListener("change", preencherSelectCategorias);
});

// ---------- Nova categoria (rápida) ----------

document.getElementById("btn-toggle-nova-categoria").addEventListener("click", () => {
  document.getElementById("bloco-nova-categoria").classList.toggle("oculto");
});

document.getElementById("btn-salvar-categoria").addEventListener("click", async () => {
  const nome = document.getElementById("input-nome-categoria").value.trim();
  if (!nome) return;
  const tipo = document.querySelector('input[name="tipo"]:checked').value;
  try {
    const nova = await Api.criarCategoria(nome, tipo);
    await carregarCategorias();
    document.getElementById("select-categoria").value = nova.id;
    document.getElementById("input-nome-categoria").value = "";
    document.getElementById("bloco-nova-categoria").classList.add("oculto");
    toast(`Categoria "${nova.nome}" criada.`);
  } catch (erro) {
    toast(erro.message, "erro");
  }
});

// ---------- Contas bancárias ----------

async function carregarContas() {
  estado.contas = await Api.contas();
  renderizarListaContas();
  preencherSelectsConta();
}

function renderizarListaContas() {
  const lista = document.getElementById("lista-contas");
  const vazio = document.getElementById("contas-vazio");
  lista.innerHTML = "";

  if (estado.contas.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  estado.contas.forEach((conta) => {
    const div = document.createElement("div");
    div.className = "cartao-conta";
    const classeSaldo = Number(conta.saldo_atual) < 0 ? "valor--despesa" : "valor--receita";
    div.innerHTML = `
      <div class="cartao-conta__info">
        <span class="cartao-conta__banco">${escaparHtml(conta.nome_banco)}</span>
        ${conta.apelido ? `<span class="cartao-conta__apelido">${escaparHtml(conta.apelido)}</span>` : ""}
      </div>
      <span class="cartao-conta__saldo ${classeSaldo}">${formatarMoeda(conta.saldo_atual)}</span>
      <div class="cartao-conta__acoes">
        <button type="button" class="btn-editar-conta">Editar</button>
        <button type="button" class="btn-apagar-conta">Apagar</button>
      </div>
    `;
    div.querySelector(".btn-editar-conta").addEventListener("click", () => abrirFormConta(conta));
    div.querySelector(".btn-apagar-conta").addEventListener("click", () => apagarConta(conta));
    lista.appendChild(div);
  });
}

function preencherSelectsConta() {
  const selects = [
    document.getElementById("select-conta"),
    document.getElementById("select-conta-edicao"),
    document.getElementById("select-conta-origem"),
    document.getElementById("select-conta-destino"),
  ];

  selects.forEach((el) => {
    if (!el) return;
    const valorAtual = el.value;
    el.innerHTML = "";
    estado.contas.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
      el.appendChild(opt);
    });
    if (valorAtual) el.value = valorAtual;
  });

  const filtroConta = document.getElementById("filtro-conta");
  const valorFiltroAtual = filtroConta.value;
  filtroConta.innerHTML = '<option value="">Todas</option>';
  estado.contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    filtroConta.appendChild(opt);
  });
  filtroConta.value = valorFiltroAtual;

  // Transferência precisa de duas contas diferentes selecionadas por padrão
  const origem = document.getElementById("select-conta-origem");
  const destino = document.getElementById("select-conta-destino");
  if (estado.contas.length > 1 && origem && destino) {
    origem.value = estado.contas[0].id;
    destino.value = estado.contas[1].id;
  }
}

let contaEmEdicao = null;

function abrirFormConta(conta = null) {
  contaEmEdicao = conta;
  limparErro("erro-conta");
  const form = document.getElementById("form-conta");
  form.reset();

  document.getElementById("titulo-modal-conta").textContent = conta ? "Editar conta" : "Nova conta";
  if (conta) {
    form.elements["id"].value = conta.id;
    form.elements["nome_banco"].value = conta.nome_banco;
    form.elements["apelido"].value = conta.apelido ?? "";
    form.elements["saldo_inicial"].value = conta.saldo_inicial;
  } else {
    form.elements["id"].value = "";
    form.elements["saldo_inicial"].value = "0";
  }

  document.getElementById("modal-form-conta").classList.remove("oculto");
}

function fecharFormConta() {
  document.getElementById("modal-form-conta").classList.add("oculto");
  contaEmEdicao = null;
}

document.getElementById("btn-nova-conta").addEventListener("click", () => abrirFormConta());
document.getElementById("btn-cancelar-conta").addEventListener("click", fecharFormConta);
document.getElementById("modal-form-conta").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-form-conta") fecharFormConta();
});

document.getElementById("form-conta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-conta");
  const dados = new FormData(evento.target);
  const id = dados.get("id");

  const corpo = {
    nome_banco: dados.get("nome_banco"),
    apelido: dados.get("apelido") || null,
    saldo_inicial: dados.get("saldo_inicial") || "0",
  };

  try {
    if (id) {
      await Api.editarConta(id, corpo);
      toast("Conta atualizada.");
    } else {
      await Api.criarConta(corpo);
      toast("Conta criada.");
    }
    fecharFormConta();
    await carregarContas();
    await atualizarSaldo();
  } catch (erro) {
    mostrarErro("erro-conta", erro.message);
  }
});

async function apagarConta(conta) {
  const rotulo = conta.apelido ? `${conta.nome_banco} (${conta.apelido})` : conta.nome_banco;
  const confirmado = confirm(`Apagar a conta "${rotulo}"? Isso só é possível se ela não tiver movimentações ou transferências.`);
  if (!confirmado) return;
  try {
    await Api.apagarConta(conta.id);
    await carregarContas();
    await atualizarSaldo();
    toast("Conta apagada.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

// ---------- Transferência entre contas ----------

document.getElementById("btn-abrir-transferencia").addEventListener("click", () => {
  if (estado.contas.length < 2) {
    toast("Cadastre pelo menos duas contas pra poder transferir.", "erro");
    return;
  }
  limparErro("erro-transferencia");
  const form = document.getElementById("form-transferencia");
  form.reset();
  form.elements["data"].value = hojeISO();
  preencherSelectsConta();
  document.getElementById("modal-transferencia").classList.remove("oculto");
});

document.getElementById("btn-cancelar-transferencia").addEventListener("click", () => {
  document.getElementById("modal-transferencia").classList.add("oculto");
});
document.getElementById("modal-transferencia").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-transferencia") {
    document.getElementById("modal-transferencia").classList.add("oculto");
  }
});

document.getElementById("form-transferencia").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-transferencia");
  const dados = new FormData(evento.target);

  const origem = dados.get("conta_origem_id");
  const destino = dados.get("conta_destino_id");
  if (origem === destino) {
    mostrarErro("erro-transferencia", "Escolha duas contas diferentes.");
    return;
  }

  try {
    await Api.criarTransferencia({
      conta_origem_id: origem,
      conta_destino_id: destino,
      valor: dados.get("valor"),
      descricao: dados.get("descricao") || null,
      data: dados.get("data"),
    });
    document.getElementById("modal-transferencia").classList.add("oculto");
    await carregarContas();
    await atualizarSaldo();
    toast("Transferência realizada.");
  } catch (erro) {
    mostrarErro("erro-transferencia", erro.message);
  }
});

// ---------- Saldo ----------

async function atualizarSaldo() {
  const saldo = await Api.saldo();
  document.getElementById("valor-receitas").textContent = formatarMoeda(saldo.total_receitas);
  document.getElementById("valor-despesas").textContent = formatarMoeda(saldo.total_despesas);
  document.getElementById("valor-saldo").textContent = formatarMoeda(saldo.saldo);
}

// ---------- Nova movimentação ----------

document.getElementById("form-movimentacao").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-movimentacao");

  if (estado.contas.length === 0) {
    mostrarErro("erro-movimentacao", "Cadastre uma conta bancária antes de lançar uma movimentação.");
    return;
  }

  const dados = new FormData(evento.target);

  const corpo = {
    valor: dados.get("valor"),
    categoria_id: dados.get("categoria_id"),
    conta_id: dados.get("conta_id"),
    descricao: dados.get("descricao") || null,
    data: dados.get("data"),
  };

  try {
    await Api.criarMovimentacao(corpo);
    evento.target.reset();
    document.querySelector('#form-movimentacao input[name="data"]').value = hojeISO();
    preencherSelectCategorias();
    preencherSelectsConta();
    estado.skip = 0;
    await Promise.all([atualizarSaldo(), carregarHistorico(), carregarContas()]);
    toast("Movimentação adicionada.");
  } catch (erro) {
    mostrarErro("erro-movimentacao", erro.message);
  }
});

// ---------- Filtros ----------

document.getElementById("btn-toggle-filtros").addEventListener("click", () => {
  document.getElementById("bloco-filtros").classList.toggle("oculto");
});

document.getElementById("btn-aplicar-filtros").addEventListener("click", () => {
  estado.filtros = {
    tipo: document.getElementById("filtro-tipo").value,
    categoria_id: document.getElementById("filtro-categoria").value,
    conta_id: document.getElementById("filtro-conta").value,
    data_inicio: document.getElementById("filtro-data-inicio").value,
    data_fim: document.getElementById("filtro-data-fim").value,
    ordenar_por: document.getElementById("filtro-ordenar-por").value,
    ordem: document.getElementById("filtro-ordem").value,
  };
  estado.skip = 0;
  carregarHistorico();
});

document.getElementById("btn-limpar-filtros").addEventListener("click", () => {
  document.getElementById("filtro-tipo").value = "";
  document.getElementById("filtro-categoria").value = "";
  document.getElementById("filtro-conta").value = "";
  document.getElementById("filtro-data-inicio").value = "";
  document.getElementById("filtro-data-fim").value = "";
  document.getElementById("filtro-ordenar-por").value = "data";
  document.getElementById("filtro-ordem").value = "desc";
  estado.filtros = {};
  estado.skip = 0;
  carregarHistorico();
});

// ---------- Histórico ----------

async function carregarHistorico() {
  const resposta = await Api.historico({
    ...estado.filtros,
    skip: estado.skip,
    limit: estado.limite,
  });
  estado.total = resposta.total;
  renderizarHistorico(resposta.itens);
  renderizarPaginacao();
}

function renderizarHistorico(itens) {
  const corpo = document.getElementById("corpo-historico");
  const vazio = document.getElementById("historico-vazio");
  corpo.innerHTML = "";

  if (itens.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  itens.forEach((mov) => {
    const categoria = categoriaPorId(mov.categoria_id);
    const conta = contaPorId(mov.conta_id);
    const tr = document.createElement("tr");

    const classeValor = categoria?.tipo === "despesa" ? "valor--despesa" : "valor--receita";
    const sinal = categoria?.tipo === "despesa" ? "−" : "+";

    tr.innerHTML = `
      <td data-label="Data">${formatarDataBR(mov.data)}</td>
      <td data-label="Descrição">${mov.descricao ? escaparHtml(mov.descricao) : '<span style="color:var(--tinta-suave)">—</span>'}</td>
      <td data-label="Categoria"><span class="etiqueta-categoria">${escaparHtml(categoria?.nome ?? "—")}</span></td>
      <td data-label="Conta"><span class="etiqueta-conta">${escaparHtml(conta?.nome_banco ?? "—")}</span></td>
      <td data-label="Valor" class="alinhar-direita celula-valor ${classeValor}">${sinal} ${formatarMoeda(mov.valor)}</td>
      <td data-label="Ações">
        <div class="acoes-linha">
          <button type="button" class="btn-editar">Editar</button>
          <button type="button" class="btn-apagar">Apagar</button>
        </div>
      </td>
    `;

    tr.querySelector(".btn-editar").addEventListener("click", () => abrirModalEdicao(mov));
    tr.querySelector(".btn-apagar").addEventListener("click", () => apagarMovimentacao(mov));

    corpo.appendChild(tr);
  });
}

function renderizarPaginacao() {
  const inicio = estado.total === 0 ? 0 : estado.skip + 1;
  const fim = Math.min(estado.skip + estado.limite, estado.total);
  document.getElementById("texto-paginacao").textContent = `${inicio}–${fim} de ${estado.total}`;
  document.getElementById("btn-pagina-anterior").disabled = estado.skip === 0;
  document.getElementById("btn-pagina-proxima").disabled = estado.skip + estado.limite >= estado.total;
}

document.getElementById("btn-pagina-anterior").addEventListener("click", () => {
  estado.skip = Math.max(0, estado.skip - estado.limite);
  carregarHistorico();
});

document.getElementById("btn-pagina-proxima").addEventListener("click", () => {
  estado.skip += estado.limite;
  carregarHistorico();
});

// ---------- Apagar ----------

async function apagarMovimentacao(mov) {
  const confirmado = confirm(`Apagar a movimentação de ${formatarMoeda(mov.valor)} em ${formatarDataBR(mov.data)}?`);
  if (!confirmado) return;
  try {
    await Api.apagarMovimentacao(mov.id);
    await Promise.all([atualizarSaldo(), carregarHistorico(), carregarContas()]);
    toast("Movimentação apagada.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

// ---------- Edição (modal) ----------

let movimentacaoEmEdicao = null;

function abrirModalEdicao(mov) {
  movimentacaoEmEdicao = mov;
  limparErro("erro-edicao");

  const form = document.getElementById("form-edicao");
  form.elements["id"].value = mov.id;
  form.elements["valor"].value = mov.valor;
  form.elements["descricao"].value = mov.descricao ?? "";
  form.elements["data"].value = mov.data;

  const selectCategoria = document.getElementById("select-categoria-edicao");
  selectCategoria.innerHTML = "";
  estado.categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    selectCategoria.appendChild(opt);
  });
  selectCategoria.value = mov.categoria_id;

  const selectConta = document.getElementById("select-conta-edicao");
  selectConta.innerHTML = "";
  estado.contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    selectConta.appendChild(opt);
  });
  selectConta.value = mov.conta_id;

  document.getElementById("modal-edicao").classList.remove("oculto");
}

function fecharModalEdicao() {
  document.getElementById("modal-edicao").classList.add("oculto");
  movimentacaoEmEdicao = null;
}

document.getElementById("btn-cancelar-edicao").addEventListener("click", fecharModalEdicao);

document.getElementById("modal-edicao").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-edicao") fecharModalEdicao();
});

document.getElementById("form-edicao").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-edicao");
  const dados = new FormData(evento.target);

  try {
    await Api.editarMovimentacao(dados.get("id"), {
      valor: dados.get("valor"),
      categoria_id: dados.get("categoria_id"),
      conta_id: dados.get("conta_id"),
      descricao: dados.get("descricao") || null,
      data: dados.get("data"),
    });
    fecharModalEdicao();
    await Promise.all([atualizarSaldo(), carregarHistorico(), carregarContas()]);
    toast("Movimentação atualizada.");
  } catch (erro) {
    mostrarErro("erro-edicao", erro.message);
  }
});

// ---------- Ponto de entrada ----------

if (Auth.estaLogado()) {
  mostrarTelaApp().catch(() => mostrarTelaAuth());
} else {
  mostrarTelaAuth();
}