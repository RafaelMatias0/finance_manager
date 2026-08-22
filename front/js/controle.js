/**
 * Página Controle: Histórico completo (filtros, paginação, edição — o
 * mesmo painel que morava no Início antes da Fase 2), mais duas peças de
 * análise por categoria que consomem GET /relatorios/por-categoria: um
 * gráfico de gastos do mês (pizza) e uma tabela-resumo por categoria
 * (total/%/mín/média/máx/últimos 3 meses).
 */

// Se não estiver logado, nem tenta — manda de volta pro login.
if (!Auth.estaLogado()) {
  window.location.href = "index.html";
}

document.addEventListener("sessao-expirada", () => {
  toast("Sessão expirada. Faça login de novo.", "erro");
  window.location.href = "index.html";
});

// O botão "Sair" agora vive na sidebar (js/sidebar.js cuida dele, já que
// ela é compartilhada entre todas as páginas logadas).

let categorias = [];
let subcategorias = [];
let contas = [];

const estado = {
  limite: 10,
  skip: 0,
  total: 0,
  filtros: {},
};

function categoriaPorId(id) {
  return categorias.find((c) => c.id === id);
}

function subcategoriaPorId(id) {
  return subcategorias.find((s) => s.id === id);
}

function contaPorId(id) {
  return contas.find((c) => c.id === id);
}

// ---------- Categorias / Subcategorias / Contas (popular selects + o
// card de gerenciar categorias — CRUD de categoria/subcategoria mora
// só aqui, na Fase 6) ----------

async function carregarCategorias() {
  categorias = await Api.categorias();
  preencherSelectsCategoria();
}

function preencherSelectsCategoria() {
  const selectEdicao = document.getElementById("select-categoria-edicao");
  const valorAtual = selectEdicao.value;
  selectEdicao.innerHTML = "";
  categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    selectEdicao.appendChild(opt);
  });
  if (valorAtual) selectEdicao.value = valorAtual;

  const filtroCategoria = document.getElementById("filtro-categoria");
  const valorFiltroAtual = filtroCategoria.value;
  filtroCategoria.innerHTML = '<option value="">Todas</option>';
  categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    filtroCategoria.appendChild(opt);
  });
  filtroCategoria.value = valorFiltroAtual;

  const selectRelacionada = document.getElementById("select-categoria-relacionada");
  const valorRelacionadaAtual = selectRelacionada.value;
  selectRelacionada.innerHTML = "";
  categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    selectRelacionada.appendChild(opt);
  });
  if (valorRelacionadaAtual) selectRelacionada.value = valorRelacionadaAtual;
}

async function carregarSubcategorias() {
  subcategorias = await Api.subcategorias();
  preencherSelectSubcategoriaEdicao();
}

// Select de subcategoria do modal de edição — depende de qual categoria
// está selecionada ali (mesmo princípio do modal de nova movimentação
// no Início: só mostra subcategorias da categoria escolhida).
function preencherSelectSubcategoriaEdicao() {
  const categoriaId = document.getElementById("select-categoria-edicao").value;
  const select = document.getElementById("select-subcategoria-edicao");
  const valorAtual = select.value;
  select.innerHTML = '<option value="">Nenhuma</option>';
  subcategorias
    .filter((s) => s.categoria_id === categoriaId)
    .forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.nome;
      select.appendChild(opt);
    });
  if ([...select.options].some((opt) => opt.value === valorAtual)) {
    select.value = valorAtual;
  }
}

document.getElementById("select-categoria-edicao").addEventListener("change", preencherSelectSubcategoriaEdicao);

async function carregarContas() {
  contas = await Api.contas();
  preencherSelectsConta();
}

function preencherSelectsConta() {
  const selectEdicao = document.getElementById("select-conta-edicao");
  const valorAtual = selectEdicao.value;
  selectEdicao.innerHTML = "";
  contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    selectEdicao.appendChild(opt);
  });
  if (valorAtual) selectEdicao.value = valorAtual;

  const filtroConta = document.getElementById("filtro-conta");
  const valorFiltroAtual = filtroConta.value;
  filtroConta.innerHTML = '<option value="">Todas</option>';
  contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    filtroConta.appendChild(opt);
  });
  filtroConta.value = valorFiltroAtual;
}

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
    const subcategoria = mov.subcategoria_id ? subcategoriaPorId(mov.subcategoria_id) : null;
    const conta = contaPorId(mov.conta_id);
    const tr = document.createElement("tr");

    const classeValor = categoria?.tipo === "despesa" ? "valor--despesa" : "valor--receita";
    const sinal = categoria?.tipo === "despesa" ? "−" : "+";

    tr.innerHTML = `
      <td data-label="Data">${formatarDataBR(mov.data)}</td>
      <td data-label="Descrição">${mov.descricao ? escaparHtml(mov.descricao) : '<span style="color:var(--tinta-suave)">—</span>'}</td>
      <td data-label="Categoria">
        <span class="etiqueta-categoria">${escaparHtml(categoria?.nome ?? "—")}</span>
        ${subcategoria ? `<span class="etiqueta-subcategoria">${escaparHtml(subcategoria.nome)}</span>` : ""}
      </td>
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
  const confirmado = await confirmarAcao(`Apagar a movimentação de ${formatarMoeda(mov.valor)} em ${formatarDataBR(mov.data)}?`);
  if (!confirmado) return;
  try {
    await Api.apagarMovimentacao(mov.id);
    await carregarHistorico();
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
  selectCategoria.value = mov.categoria_id;
  // Categoria já vem certa acima — só falta recalcular as opções de
  // subcategoria pra ela antes de aplicar o valor salvo da movimentação.
  preencherSelectSubcategoriaEdicao();
  document.getElementById("select-subcategoria-edicao").value = mov.subcategoria_id ?? "";

  const selectConta = document.getElementById("select-conta-edicao");
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

  const destravar = travarBotaoEnvio(evento.target);
  try {
    await Api.editarMovimentacao(dados.get("id"), {
      valor: dados.get("valor"),
      categoria_id: dados.get("categoria_id"),
      subcategoria_id: dados.get("subcategoria_id") || null,
      conta_id: dados.get("conta_id"),
      descricao: dados.get("descricao") || null,
      data: dados.get("data"),
    });
    fecharModalEdicao();
    await carregarHistorico();
    toast("Movimentação atualizada.");
  } catch (erro) {
    mostrarErro("erro-edicao", erro.message);
  } finally {
    destravar();
  }
});

// ---------- Gerenciar categorias e subcategorias (card dedicado, entre
// Histórico e Resumo por categoria — antes, criar categoria vivia
// embutido no form de nova movimentação do Início; agora mora só aqui,
// e subcategoria nasce junto nesta mesma Fase) ----------

// Categoria com a lista de subcategorias aberta no momento (só uma por
// vez) — null quando nenhuma está expandida.
let categoriaExpandidaId = null;

function renderizarListaCategoriasGerenciar() {
  const lista = document.getElementById("lista-categorias-gerenciar");
  const vazio = document.getElementById("categorias-gerenciar-vazio");
  lista.innerHTML = "";

  if (categorias.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  categorias.forEach((cat) => {
    const subcategoriasDaCategoria = subcategorias.filter((s) => s.categoria_id === cat.id);
    const expandida = categoriaExpandidaId === cat.id;

    const tipoClasse = cat.tipo === "despesa" ? "etiqueta-tipo-despesa" : "etiqueta-tipo-receita";
    const tipoRotulo = cat.tipo === "despesa" ? "Despesa" : "Receita";
    const conteudoSubcategorias = subcategoriasDaCategoria.length > 0
      ? subcategoriasDaCategoria.map((s) => `<span class="etiqueta-categoria">${escaparHtml(s.nome)}</span>`).join("")
      : '<p class="cartao-categoria__vazio">Nenhuma subcategoria ainda.</p>';

    const div = document.createElement("div");
    div.className = "cartao-categoria";
    div.innerHTML = `
      <button type="button" class="cartao-categoria__cabecalho" aria-expanded="${expandida}">
        <span class="${tipoClasse}">${tipoRotulo}</span>
        <span class="cartao-categoria__nome">${escaparHtml(cat.nome)}</span>
        <svg class="cartao-categoria__seta" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
      </button>
      <div class="cartao-categoria__subcategorias ${expandida ? "" : "oculto"}">${conteudoSubcategorias}</div>
    `;
    div.querySelector(".cartao-categoria__cabecalho").addEventListener("click", () => {
      categoriaExpandidaId = expandida ? null : cat.id;
      renderizarListaCategoriasGerenciar();
    });
    lista.appendChild(div);
  });
}

// Um único modal cobre os dois formulários ("Nova categoria" e "Nova
// subcategoria") — o botão clicado já diz qual dos dois é, então não
// precisa de um passo extra só pra escolher o modo.
let modoCriacaoCategoria = "categoria";

function abrirModalCategoria(modo) {
  modoCriacaoCategoria = modo;
  limparErro("erro-categoria");
  const form = document.getElementById("form-categoria");
  form.reset();

  const ehSubcategoria = modo === "subcategoria";
  document.getElementById("titulo-modal-categoria").textContent = ehSubcategoria ? "Nova subcategoria" : "Nova categoria";
  document.getElementById("rotulo-nome-categoria").textContent = ehSubcategoria ? "Nome da subcategoria" : "Nome da categoria";
  document.getElementById("campo-categoria-relacionada").classList.toggle("oculto", !ehSubcategoria);
  document.getElementById("campo-tipo-categoria").classList.toggle("oculto", ehSubcategoria);
  document.getElementById("select-categoria-relacionada").required = ehSubcategoria;

  // Se uma categoria já estava expandida no card, pré-seleciona ela como
  // "categoria relacionada" — poupa um clique no caso mais comum (abrir
  // uma categoria e, na sequência, criar uma subcategoria pra ela).
  if (ehSubcategoria && categoriaExpandidaId) {
    document.getElementById("select-categoria-relacionada").value = categoriaExpandidaId;
  }

  document.getElementById("modal-categoria").classList.remove("oculto");
}

function fecharModalCategoria() {
  document.getElementById("modal-categoria").classList.add("oculto");
}

document.getElementById("btn-nova-categoria").addEventListener("click", () => abrirModalCategoria("categoria"));
document.getElementById("btn-nova-subcategoria").addEventListener("click", () => abrirModalCategoria("subcategoria"));
document.getElementById("btn-cancelar-categoria").addEventListener("click", fecharModalCategoria);
document.getElementById("modal-categoria").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-categoria") fecharModalCategoria();
});

document.getElementById("form-categoria").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-categoria");
  const dados = new FormData(evento.target);
  const nome = dados.get("nome").trim();

  const destravar = travarBotaoEnvio(evento.target);
  try {
    if (modoCriacaoCategoria === "subcategoria") {
      const categoriaRelacionadaId = dados.get("categoria_relacionada_id");
      const nova = await Api.criarSubcategoria({ nome, categoria_id: categoriaRelacionadaId });
      await carregarSubcategorias();
      categoriaExpandidaId = categoriaRelacionadaId;
      toast(`Subcategoria "${nova.nome}" criada.`);
    } else {
      const tipo = dados.get("tipo");
      const nova = await Api.criarCategoria(nome, tipo);
      await carregarCategorias();
      toast(`Categoria "${nova.nome}" criada.`);
    }
    fecharModalCategoria();
    renderizarListaCategoriasGerenciar();
  } catch (erro) {
    mostrarErro("erro-categoria", erro.message);
  } finally {
    destravar();
  }
});

// ---------- Gráfico: gastos por categoria (mês atual) ----------

// Canvas (Chart.js) não entende var(--...) — só cores resolvidas. Por isso
// toda cor de gráfico é lida assim, na hora de renderizar, em vez de
// hardcoded — o mesmo hex nunca sobrevive uma troca de tema. Chamado de
// novo a cada render (barato) pra sempre pegar o tema atual.
function corToken(nome) {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
}

// Paleta categórica validada com a skill dataviz — 8 matizes de cor fixa,
// nunca cicladas (a partir da 9ª categoria, agrupa em "Outras" em vez de
// gerar mais cores). Claro e escuro validados cada um contra a superfície
// de verdade do próprio tema (scripts/validate_palette.js, --superficie):
// todos os checks passam (contraste abaixo de 3:1 em algumas matizes no
// claro é aceitável porque a legenda — sempre visível — já funciona como
// rótulo direto de cada fatia). Valores em --grafico-1..8 (style.css).
function paletaCategorica() {
  return [1, 2, 3, 4, 5, 6, 7, 8].map((i) => corToken(`--grafico-${i}`));
}

// Preenchimento de área do gráfico de linhas (mesma cor da linha, bem
// transparente, tipo sombra).
function corComTransparencia(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

let graficoCategoriaMes = null;

async function carregarGraficoCategoria() {
  const hoje = new Date();
  const primeiroDiaMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1).toISOString().slice(0, 10);

  let dados;
  try {
    dados = await Api.porCategoria({ data_inicio: primeiroDiaMes, data_fim: hojeISO(), tipo: "despesa" });
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }

  const vazio = document.getElementById("grafico-categoria-mes-vazio");
  const canvas = document.getElementById("grafico-categoria-mes");

  if (dados.length === 0) {
    vazio.classList.remove("oculto");
    canvas.classList.add("oculto");
    return;
  }
  vazio.classList.add("oculto");
  canvas.classList.remove("oculto");

  const paleta = paletaCategorica();
  const corOutras = corToken("--linha-forte");

  // Mais categorias do que cores na paleta: as menores (já vêm ordenadas
  // por total decrescente) viram uma fatia só "Outras" — nunca gera cor nova.
  let fatias = dados;
  let temOutras = false;
  if (dados.length > paleta.length) {
    const principais = dados.slice(0, paleta.length - 1);
    const resto = dados.slice(paleta.length - 1);
    const totalResto = resto.reduce((soma, c) => soma + c.total, 0);
    fatias = [...principais, { categoria_nome: "Outras", total: totalResto }];
    temOutras = true;
  }
  const cores = fatias.map((_, i) => (temOutras && i === fatias.length - 1 ? corOutras : paleta[i]));

  if (graficoCategoriaMes) graficoCategoriaMes.destroy();
  graficoCategoriaMes = new Chart(canvas.getContext("2d"), {
    type: "pie",
    data: {
      labels: fatias.map((c) => c.categoria_nome),
      datasets: [{ data: fatias.map((c) => c.total), backgroundColor: cores }],
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } },
  });
}

// ---------- Gráfico: balanço diário por conta, últimos 30 dias (destaque da página) ----------

let graficoSaldoDiario = null;

async function carregarGraficoSaldoDiario() {
  let dados;
  try {
    dados = await Api.saldoDiarioPorConta();
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }

  const vazio = document.getElementById("grafico-saldo-diario-vazio");
  const canvas = document.getElementById("grafico-saldo-diario");

  if (dados.length === 0) {
    vazio.classList.remove("oculto");
    canvas.classList.add("oculto");
    return;
  }
  vazio.classList.add("oculto");
  canvas.classList.remove("oculto");

  // Mesma janela (fixa em até 30 dias, ou menor se a atividade do usuário
  // for mais recente que isso — ver calcular_serie_saldo_diaria) pra todas
  // as contas, então todo mundo tem ponto em todo dia (sem buraco) e dá
  // pra usar os dias da primeira conta como eixo X direto.
  const dias = dados[0].serie.map((p) => p.dia);

  const corSuperficie = corToken("--superficie");
  const paleta = paletaCategorica();

  const datasets = dados.map((conta, i) => {
    const cor = paleta[i % paleta.length];
    return {
      label: conta.conta_nome,
      data: conta.serie.map((p) => p.saldo),
      borderColor: cor,
      backgroundColor: corComTransparencia(cor, 0.15),
      // Ponto só aparece no hover, e só o exato onde o mouse está (não os
      // outros pontos daquele dia) — ver interaction.intersect abaixo.
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHitRadius: 10,
      pointBackgroundColor: cor,
      pointBorderColor: corSuperficie,
      fill: true,
      tension: 0.4,
    };
  });

  if (graficoSaldoDiario) graficoSaldoDiario.destroy();
  graficoSaldoDiario = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { labels: dias.map(formatarDataBR), datasets },
    options: {
      responsive: true,
      interaction: { mode: "nearest", intersect: true },
      plugins: { legend: { position: "bottom" } },
      scales: { y: { ticks: { callback: (valor) => formatarMoeda(valor) } } },
    },
  });
}

// ---------- Gráfico: balanço geral (receita vs. despesa, desde o início) ----------

let graficoBalancoGeral = null;

async function carregarGraficoBalancoGeral() {
  let dados;
  try {
    dados = await Api.saldo();
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }

  const vazio = document.getElementById("grafico-balanco-geral-vazio");
  const canvas = document.getElementById("grafico-balanco-geral");
  const totalReceitas = Number(dados.total_receitas);
  const totalDespesas = Number(dados.total_despesas);

  if (totalReceitas === 0 && totalDespesas === 0) {
    vazio.classList.remove("oculto");
    canvas.classList.add("oculto");
    return;
  }
  vazio.classList.add("oculto");
  canvas.classList.remove("oculto");

  if (graficoBalancoGeral) graficoBalancoGeral.destroy();
  graficoBalancoGeral = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: ["Receitas", "Despesas"],
      datasets: [{ data: [totalReceitas, totalDespesas], backgroundColor: [corToken("--receita"), corToken("--despesa")] }],
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } },
  });
}

// ---------- Tabela: resumo por categoria (histórico completo) ----------

async function carregarResumoCategorias() {
  let dados;
  try {
    dados = await Api.porCategoria({ meses_recentes: 3 });
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }
  renderizarResumoCategorias(dados);
}

function renderizarResumoCategorias(dados) {
  const corpo = document.getElementById("corpo-resumo-categorias");
  const vazio = document.getElementById("resumo-categorias-vazio");
  corpo.innerHTML = "";

  if (dados.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  // Cabeçalho das 3 colunas de mês: todas as categorias trazem os mesmos
  // meses (só o total muda), então basta olhar a primeira.
  (dados[0].mensal || []).forEach((m, i) => {
    const th = document.getElementById(`cabecalho-mes-${i + 1}`);
    if (th) th.textContent = formatarMesAno(m.mes);
  });

  dados.forEach((cat) => {
    const classeValor = cat.categoria_tipo === "despesa" ? "valor--despesa" : "valor--receita";
    const colunasMensais = (cat.mensal || [])
      .map((m) => `<td data-label="${formatarMesAno(m.mes)}" class="alinhar-direita celula-valor">${formatarMoeda(m.total)}</td>`)
      .join("");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="Categoria">${escaparHtml(cat.categoria_nome)}</td>
      <td data-label="Total" class="alinhar-direita celula-valor ${classeValor}">${formatarMoeda(cat.total)}</td>
      <td data-label="% do tipo" class="alinhar-direita celula-valor">${cat.percentual.toFixed(2)}%</td>
      <td data-label="Mínimo" class="alinhar-direita celula-valor">${formatarMoeda(cat.minimo)}</td>
      <td data-label="Média" class="alinhar-direita celula-valor">${formatarMoeda(cat.media)}</td>
      <td data-label="Máximo" class="alinhar-direita celula-valor">${formatarMoeda(cat.maximo)}</td>
      ${colunasMensais}
    `;
    corpo.appendChild(tr);
  });
}

// Chart.js não escuta variável CSS sozinho — troca de tema em runtime
// (clique no sol/lua) precisa recriar os 3 gráficos pra pegar as cores
// novas (ver corToken/paletaCategorica acima e o dispatch em js/tema.js).
document.addEventListener("tema-alterado", () => {
  carregarGraficoSaldoDiario();
  carregarGraficoCategoria();
  carregarGraficoBalancoGeral();
});

// ---------- Inicialização ----------

(async function iniciar() {
  await Promise.all([carregarCategorias(), carregarSubcategorias(), carregarContas()]);
  renderizarListaCategoriasGerenciar();
  await Promise.all([
    carregarHistorico(),
    carregarGraficoSaldoDiario(),
    carregarGraficoCategoria(),
    carregarGraficoBalancoGeral(),
    carregarResumoCategorias(),
  ]);
})();