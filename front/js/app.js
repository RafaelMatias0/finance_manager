/**
 * Início: resumo de contas (saldo por conta, só leitura) + resumo de
 * pendências (só leitura) + formulário de nova movimentação. O Histórico
 * completo (filtros, paginação, edição) saiu daqui na Fase 2 — agora mora
 * em controle.html/js/controle.js. Criar/editar/pagar pendência mora em
 * pendencias.html/js/pendencias.js.
 */
const estado = {
  categorias: [],
  subcategorias: [],
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
  const destravar = travarBotaoEnvio(evento.target);
  try {
    const resposta = await Api.login(dados.get("email"), dados.get("senha"));
    Auth.setToken(resposta.access_token);
    evento.target.reset();
    await mostrarTelaApp();
  } catch (erro) {
    mostrarErro("erro-login", erro.status === 401 ? "Email ou senha incorretos." : erro.message);
  } finally {
    destravar();
  }
});

document.getElementById("form-cadastro").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-cadastro");
  const dados = new FormData(evento.target);
  const destravar = travarBotaoEnvio(evento.target);
  try {
    await Api.cadastrar(dados.get("nome"), dados.get("email"), dados.get("senha"));
    const resposta = await Api.login(dados.get("email"), dados.get("senha"));
    Auth.setToken(resposta.access_token);
    evento.target.reset();
    await mostrarTelaApp();
  } catch (erro) {
    mostrarErro("erro-cadastro", erro.status === 409 ? "Esse email já está cadastrado." : erro.message);
  } finally {
    destravar();
  }
});

// ---------- Dashboard: inicialização ----------

async function iniciarDashboard() {
  document.querySelector('#form-movimentacao input[name="data"]').value = hojeISO();
  // carregarCategorias()/carregarContas() vão primeiro e isolados:
  // renderizarLancamentosRecentes usa categoriaPorId (estado.categorias)
  // pra decidir cor/sinal de cada lançamento, e agora também
  // estado.contas.length pra escolher a mensagem de "vazio" certa — não
  // pode rodar em paralelo com nenhum dos dois (senão corre risco de
  // ainda estarem vazios quando os lançamentos chegarem). Subcategorias
  // entram na mesma leva por conveniência (só alimentam o select do modal
  // de nova movimentação, que só abre depois disso terminar).
  await Promise.all([carregarCategorias(), carregarSubcategorias(), carregarContas()]);
  await Promise.all([carregarPendencias(), carregarLancamentosRecentes(), carregarUsuarioAtual()]);
}

function categoriaPorId(id) {
  return estado.categorias.find((c) => c.id === id);
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

  // A lista de subcategorias depende de qual categoria ficou selecionada
  // acima — troca de tipo muda as opções de categoria, então precisa
  // recalcular subcategoria em seguida (sem isso, ficaria mostrando
  // subcategorias de uma categoria que não está mais selecionada).
  preencherSelectSubcategoria();
}

document.querySelectorAll('input[name="tipo"]').forEach((radio) => {
  radio.addEventListener("change", preencherSelectCategorias);
});

// ---------- Subcategoria (opcional, depende da categoria escolhida acima —
// criar categoria/subcategoria nova agora é só em Controle, ver
// "Gerenciar categorias e subcategorias →" no próprio modal) ----------

async function carregarSubcategorias() {
  estado.subcategorias = await Api.subcategorias();
}

function preencherSelectSubcategoria() {
  const categoriaId = document.getElementById("select-categoria").value;
  const select = document.getElementById("select-subcategoria");
  const valorAtual = select.value;
  select.innerHTML = '<option value="">Nenhuma</option>';
  estado.subcategorias
    .filter((s) => s.categoria_id === categoriaId)
    .forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.nome;
      select.appendChild(opt);
    });
  // Só reaplica o valor anterior se ele ainda existir entre as opções
  // novas — senão fica preso numa subcategoria de outra categoria.
  if ([...select.options].some((opt) => opt.value === valorAtual)) {
    select.value = valorAtual;
  }
}

document.getElementById("select-categoria").addEventListener("change", preencherSelectSubcategoria);

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
      p.ciclos.forEach((c) => itens.push({ descricao: p.descricao, valor: p.valor, categoria_id: p.categoria_id, ...c }));
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
    const categoria = categoriaPorId(item.categoria_id);
    const ehDespesa = categoria?.tipo === "despesa";
    const tipoClasse = ehDespesa ? "etiqueta-tipo-despesa" : "etiqueta-tipo-receita";
    const tipoRotulo = ehDespesa ? "Despesa" : "Receita";
    div.innerHTML = `
      <span class="resumo-pendencias-inicio__desc">${escaparHtml(item.descricao)}</span>
      <span class="${tipoClasse}">${tipoRotulo}</span>
      <span class="${etiquetaClasse}">${formatarDataBR(item.data_vencimento)}</span>
      <span class="resumo-pendencias-inicio__valor">${formatarMoeda(item.valor)}</span>
    `;
    lista.appendChild(div);
  });

  if (itens.length > 3) {
    // Antes era um <p> sem função nenhuma — parecia clicável (itálico,
    // "+ N outras") mas não levava a lugar nenhum. Agora é um link de
    // verdade pra pendencias.html, reforçando o mesmo destino do
    // "Gerenciar pendências →" logo abaixo.
    const mais = document.createElement("a");
    mais.href = "pendencias.html";
    mais.className = "resumo-pendencias-inicio__mais";
    mais.textContent = `+ ${itens.length - 3} outra${itens.length - 3 > 1 ? "s" : ""} pendência${itens.length - 3 > 1 ? "s" : ""}`;
    lista.appendChild(mais);
  }
}

// ---------- Lançamentos recentes (card compacto, só leitura — o
// histórico completo com filtros/edição mora em controle.html) ----------

async function carregarLancamentosRecentes() {
  const resposta = await Api.historico({ limit: 5 });
  renderizarLancamentosRecentes(resposta.itens);
}

function renderizarLancamentosRecentes(itens) {
  const lista = document.getElementById("lista-lancamentos-recentes");
  const vazio = document.getElementById("lancamentos-recentes-vazio");
  lista.innerHTML = "";

  if (itens.length === 0) {
    // Mensagem muda conforme o que falta: sem conta, o próximo passo é
    // criar uma (não adianta apontar pros botões Receita/Despesa, que
    // vão só mostrar um erro); com conta, aponta pros botões de verdade.
    vazio.textContent = estado.contas.length === 0
      ? 'Nenhuma conta cadastrada ainda — crie uma no card "Contas" ao lado antes de lançar algo.'
      : 'Nenhum lançamento ainda. Use os botões "Receita"/"Despesa" acima pra registrar o primeiro.';
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  itens.forEach((mov) => {
    const categoria = categoriaPorId(mov.categoria_id);
    const classeValor = categoria?.tipo === "despesa" ? "valor--despesa" : "valor--receita";
    const sinal = categoria?.tipo === "despesa" ? "−" : "+";
    const item = document.createElement("div");
    item.className = "lancamento-inicio__item";
    item.innerHTML = `
      <span class="lancamento-inicio__data">${formatarDataBR(mov.data)}</span>
      <span class="lancamento-inicio__desc">${escaparHtml(mov.descricao || categoria?.nome || "—")}</span>
      <span class="lancamento-inicio__valor ${classeValor}">${sinal} ${formatarMoeda(mov.valor)}</span>
    `;
    lista.appendChild(item);
  });
}

// ---------- Nova movimentação (card flutuante, aberto pelos botões
// rápidos "Receita"/"Despesa" do card de Lançamentos) ----------

function abrirModalMovimentacao(tipo) {
  if (estado.contas.length === 0) {
    toast("Cadastre uma conta em Contas antes de lançar uma movimentação.", "erro");
    return;
  }

  limparErro("erro-movimentacao");
  const form = document.getElementById("form-movimentacao");
  form.reset();
  document.querySelector(`#form-movimentacao input[name="tipo"][value="${tipo}"]`).checked = true;
  form.elements["data"].value = hojeISO();
  preencherSelectCategorias();
  preencherSelectsConta();

  document.getElementById("modal-nova-movimentacao").classList.remove("oculto");
}

function fecharModalMovimentacao() {
  document.getElementById("modal-nova-movimentacao").classList.add("oculto");
}

document.getElementById("btn-nova-receita").addEventListener("click", () => abrirModalMovimentacao("receita"));
document.getElementById("btn-nova-despesa").addEventListener("click", () => abrirModalMovimentacao("despesa"));
document.getElementById("btn-cancelar-movimentacao").addEventListener("click", fecharModalMovimentacao);
document.getElementById("modal-nova-movimentacao").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-nova-movimentacao") fecharModalMovimentacao();
});

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
    subcategoria_id: dados.get("subcategoria_id") || null,
    conta_id: dados.get("conta_id"),
    descricao: dados.get("descricao") || null,
    data: dados.get("data"),
  };

  const destravar = travarBotaoEnvio(evento.target);
  try {
    await Api.criarMovimentacao(corpo);
    fecharModalMovimentacao();
    await Promise.all([carregarContas(), carregarLancamentosRecentes()]);
    toast("Movimentação adicionada.");
  } catch (erro) {
    mostrarErro("erro-movimentacao", erro.message);
  } finally {
    destravar();
  }
});

// ---------- Ponto de entrada ----------

if (Auth.estaLogado()) {
  mostrarTelaApp().catch(() => mostrarTelaAuth());
} else {
  mostrarTelaAuth();
}