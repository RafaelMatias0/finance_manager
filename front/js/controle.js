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

function contaPorId(id) {
  return contas.find((c) => c.id === id);
}

// ---------- Categorias / Contas (só pra popular selects — sem CRUD aqui) ----------

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
}

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

  try {
    await Api.editarMovimentacao(dados.get("id"), {
      valor: dados.get("valor"),
      categoria_id: dados.get("categoria_id"),
      conta_id: dados.get("conta_id"),
      descricao: dados.get("descricao") || null,
      data: dados.get("data"),
    });
    fecharModalEdicao();
    await carregarHistorico();
    toast("Movimentação atualizada.");
  } catch (erro) {
    mostrarErro("erro-edicao", erro.message);
  }
});

// ---------- Gráfico: gastos por categoria (mês atual) ----------

// Paleta categórica validada com a skill dataviz — 8 matizes de cor fixa,
// nunca cicladas (a partir da 9ª categoria, agrupa em "Outras" em vez de
// gerar mais cores). Validada contra --papel-cartao (#FBFBF8, a superfície
// onde o card do gráfico fica) com scripts/validate_palette.js: todos os
// checks passam (contraste abaixo de 3:1 em 3 matizes é aceitável porque a
// legenda — sempre visível — já funciona como rótulo direto de cada fatia).
const PALETA_CATEGORICA = [
  "#2a78d6", // azul
  "#eb6834", // laranja
  "#1baf7a", // água
  "#eda100", // amarelo
  "#e87ba4", // magenta
  "#008300", // verde
  "#4a3aa7", // violeta
  "#e34948", // vermelho
];
const COR_OUTRAS = "#A9AF9C"; // --linha-forte: neutro pro grupo "Outras"

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

  // Mais categorias do que cores na paleta: as menores (já vêm ordenadas
  // por total decrescente) viram uma fatia só "Outras" — nunca gera cor nova.
  let fatias = dados;
  let temOutras = false;
  if (dados.length > PALETA_CATEGORICA.length) {
    const principais = dados.slice(0, PALETA_CATEGORICA.length - 1);
    const resto = dados.slice(PALETA_CATEGORICA.length - 1);
    const totalResto = resto.reduce((soma, c) => soma + c.total, 0);
    fatias = [...principais, { categoria_nome: "Outras", total: totalResto }];
    temOutras = true;
  }
  const cores = fatias.map((_, i) => (temOutras && i === fatias.length - 1 ? COR_OUTRAS : PALETA_CATEGORICA[i]));

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

// ---------- Inicialização ----------

(async function iniciar() {
  await Promise.all([carregarCategorias(), carregarContas()]);
  await Promise.all([carregarHistorico(), carregarGraficoCategoria(), carregarResumoCategorias()]);
})();
