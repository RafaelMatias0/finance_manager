/**
 * Estado da tela de histórico (paginação + filtros ativos).
 */
const estado = {
  categorias: [],
  limite: 10,
  skip: 0,
  total: 0,
  filtros: {},
};

// ---------- Utilidades ----------

const formatadorMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function formatarMoeda(valor) {
  return formatadorMoeda.format(Number(valor));
}

function formatarDataBR(isoDate) {
  const [ano, mes, dia] = isoDate.split("-");
  return `${dia}/${mes}/${ano}`;
}

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function mostrarErro(elementoId, mensagem) {
  const el = document.getElementById(elementoId);
  el.textContent = mensagem;
  el.classList.add("is-visivel");
}

function limparErro(elementoId) {
  const el = document.getElementById(elementoId);
  el.textContent = "";
  el.classList.remove("is-visivel");
}

function toast(mensagem, tipo = "sucesso") {
  const regiao = document.getElementById("regiao-toast");
  const el = document.createElement("div");
  el.className = "toast" + (tipo === "erro" ? " toast--erro" : "");
  el.textContent = mensagem;
  regiao.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function categoriaPorId(id) {
  return estado.categorias.find((c) => c.id === id);
}

// ---------- Navegação entre telas ----------

function mostrarTelaAuth() {
  document.getElementById("tela-auth").classList.remove("oculto");
  document.getElementById("tela-app").classList.add("oculto");
  document.getElementById("btn-sair").classList.add("oculto");
}

async function mostrarTelaApp() {
  document.getElementById("tela-auth").classList.add("oculto");
  document.getElementById("tela-app").classList.remove("oculto");
  document.getElementById("btn-sair").classList.remove("oculto");
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

document.getElementById("btn-sair").addEventListener("click", () => {
  Auth.limparToken();
  mostrarTelaAuth();
});

// ---------- Dashboard: inicialização ----------

async function iniciarDashboard() {
  document.querySelector('#form-movimentacao input[name="data"]').value = hojeISO();
  await carregarCategorias();
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
  const dados = new FormData(evento.target);

  const corpo = {
    valor: dados.get("valor"),
    categoria_id: dados.get("categoria_id"),
    descricao: dados.get("descricao") || null,
    data: dados.get("data"),
  };

  try {
    await Api.criarMovimentacao(corpo);
    evento.target.reset();
    document.querySelector('#form-movimentacao input[name="data"]').value = hojeISO();
    preencherSelectCategorias();
    estado.skip = 0;
    await Promise.all([atualizarSaldo(), carregarHistorico()]);
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
    const tr = document.createElement("tr");

    const classeValor = categoria?.tipo === "despesa" ? "valor--despesa" : "valor--receita";
    const sinal = categoria?.tipo === "despesa" ? "−" : "+";

    tr.innerHTML = `
      <td>${formatarDataBR(mov.data)}</td>
      <td>${mov.descricao ? escaparHtml(mov.descricao) : '<span style="color:var(--tinta-suave)">—</span>'}</td>
      <td><span class="etiqueta-categoria">${escaparHtml(categoria?.nome ?? "—")}</span></td>
      <td class="alinhar-direita celula-valor ${classeValor}">${sinal} ${formatarMoeda(mov.valor)}</td>
      <td>
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

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
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
    await Promise.all([atualizarSaldo(), carregarHistorico()]);
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

  const select = document.getElementById("select-categoria-edicao");
  select.innerHTML = "";
  estado.categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    select.appendChild(opt);
  });
  select.value = mov.categoria_id;

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
      descricao: dados.get("descricao") || null,
      data: dados.get("data"),
    });
    fecharModalEdicao();
    await Promise.all([atualizarSaldo(), carregarHistorico()]);
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
