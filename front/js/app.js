/**
 * Início: resumo de contas (saldo por conta, só leitura) + resumo de
 * pendências (só leitura) + formulário de nova movimentação. O Histórico
 * completo (filtros, paginação, edição) saiu daqui na Fase 2 — agora mora
 * em controle.html/js/controle.js. Criar/editar/pagar pendência mora em
 * pendencias.html/js/pendencias.js.
 */
const estado = {
  categorias: [],
  contas: [],
  pendencias: [],
};

// Utilidades (formatarMoeda, formatarDataBR, hojeISO, escaparHtml, toast,
// mostrarErro, limparErro) vêm de js/utils.js, carregado antes deste arquivo.

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
}

document.addEventListener("sessao-expirada", () => {
  toast("Sessão expirada. Faça login de novo.", "erro");
  mostrarTelaAuth();
});

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
  await Promise.all([carregarCategorias(), carregarContas(), carregarPendencias()]);
}

async function carregarCategorias() {
  estado.categorias = await Api.categorias();
  preencherSelectCategorias();
}

function preencherSelectCategorias() {
  const tipoSelecionado = document.querySelector('input[name="tipo"]:checked').value;

  const select = document.getElementById("select-categoria");
  const valorAtual = select.value;
  select.innerHTML = "";
  estado.categorias
    .filter((c) => c.tipo === tipoSelecionado)
    .forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.nome;
      select.appendChild(opt);
    });
  if (valorAtual) select.value = valorAtual;
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

// ---------- Contas bancárias (card compacto, só leitura — criar/editar/
// apagar conta e transferências agora vivem em contas.html) ----------

async function carregarContas() {
  estado.contas = await Api.contas();
  renderizarResumoContasInicio();
  preencherSelectsConta();
}

function renderizarResumoContasInicio() {
  const lista = document.getElementById("resumo-contas");
  const vazio = document.getElementById("resumo-contas-vazio");
  lista.innerHTML = "";

  if (estado.contas.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  estado.contas.forEach((conta) => {
    const item = document.createElement("div");
    item.className = "resumo-contas-inicio__item";
    const classeSaldo = Number(conta.saldo_atual) < 0 ? "valor--despesa" : "valor--receita";
    item.innerHTML = `
      <span class="resumo-contas-inicio__nome">${escaparHtml(conta.apelido || conta.nome_banco)}</span>
      <span class="resumo-contas-inicio__saldo ${classeSaldo}">${formatarMoeda(conta.saldo_atual)}</span>
    `;
    lista.appendChild(item);
  });
}

function preencherSelectsConta() {
  const select = document.getElementById("select-conta");
  const valorAtual = select.value;
  select.innerHTML = "";
  estado.contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    select.appendChild(opt);
  });
  if (valorAtual) select.value = valorAtual;
}

// ---------- Pendências (card compacto, só leitura — criar/editar/pagar
// pendência agora vive em pendencias.html) ----------

async function carregarPendencias() {
  estado.pendencias = await Api.pendencias();
  renderizarResumoPendenciasInicio();
}

function renderizarResumoPendenciasInicio() {
  const lista = document.getElementById("resumo-pendencias");
  const vazio = document.getElementById("resumo-pendencias-vazio");
  lista.innerHTML = "";

  // Achata os ciclos pendentes de todas as pendências (só as ativas fazem
  // sentido aqui — uma pausada não deveria cobrar atenção no Início),
  // atrasadas primeiro, depois a_vencer por data.
  const itens = [];
  estado.pendencias
    .filter((p) => p.ativa)
    .forEach((p) => {
      p.ciclos.forEach((c) => itens.push({ descricao: p.descricao, valor: p.valor, ...c }));
    });
  itens.sort((a, b) => {
    if (a.status !== b.status) return a.status === "atrasada" ? -1 : 1;
    return a.data_vencimento.localeCompare(b.data_vencimento);
  });

  if (itens.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  itens.slice(0, 3).forEach((item) => {
    const div = document.createElement("div");
    div.className = "resumo-pendencias-inicio__item";
    const etiquetaClasse = item.status === "atrasada" ? "etiqueta-atrasada" : "etiqueta-a-vencer";
    div.innerHTML = `
      <span class="resumo-pendencias-inicio__desc">${escaparHtml(item.descricao)}</span>
      <span class="${etiquetaClasse}">${formatarDataBR(item.data_vencimento)}</span>
      <span class="resumo-pendencias-inicio__valor">${formatarMoeda(item.valor)}</span>
    `;
    lista.appendChild(div);
  });

  if (itens.length > 3) {
    const mais = document.createElement("p");
    mais.className = "resumo-pendencias-inicio__mais";
    mais.textContent = `+ ${itens.length - 3} outra${itens.length - 3 > 1 ? "s" : ""} pendência${itens.length - 3 > 1 ? "s" : ""}`;
    lista.appendChild(mais);
  }
}

// ---------- Nova movimentação ----------

document.getElementById("form-movimentacao").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-movimentacao");

  if (estado.contas.length === 0) {
    mostrarErro("erro-movimentacao", "Cadastre uma conta em Contas antes de lançar uma movimentação.");
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
    await carregarContas();
    toast("Movimentação adicionada.");
  } catch (erro) {
    mostrarErro("erro-movimentacao", erro.message);
  }
});

// ---------- Ponto de entrada ----------

if (Auth.estaLogado()) {
  mostrarTelaApp().catch(() => mostrarTelaAuth());
} else {
  mostrarTelaAuth();
}
