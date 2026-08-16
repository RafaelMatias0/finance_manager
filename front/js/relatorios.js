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
const graficos = {}; // registro de instâncias Chart.js, pra destruir antes de recriar

function categoriaPorId(id) {
  return categorias.find((c) => c.id === id);
}

function destruirGrafico(chave) {
  if (graficos[chave]) {
    graficos[chave].destroy();
    delete graficos[chave];
  }
}

// ---------- Abas ----------

document.querySelectorAll(".aba-relatorio").forEach((aba) => {
  aba.addEventListener("click", () => mostrarAba(aba.dataset.painel));
});

function mostrarAba(nome) {
  document.querySelectorAll(".aba-relatorio").forEach((a) => {
    const ativa = a.dataset.painel === nome;
    a.classList.toggle("is-ativa", ativa);
    a.setAttribute("aria-selected", String(ativa));
  });
  ["automaticos", "personalizado", "comparativo"].forEach((painel) => {
    document.getElementById(`painel-${painel}`).classList.toggle("oculto", painel !== nome);
  });
}

// ---------- Inicialização ----------

async function iniciar() {
  const hoje = hojeISO();
  const trintaDiasAtras = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);
  document.getElementById("p-data-inicio").value = trintaDiasAtras;
  document.getElementById("p-data-fim").value = hoje;
  document.getElementById("c-data-inicio").value = trintaDiasAtras;
  document.getElementById("c-data-fim").value = hoje;

  try {
    categorias = await Api.categorias();
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }
  preencherSelectsCategoria();
  await carregarRelatoriosAutomaticos();
}

function preencherSelectsCategoria() {
  const selectParticipacao = document.getElementById("p-categoria");
  categorias.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.nome} (${c.tipo})`;
    selectParticipacao.appendChild(opt);
  });

  ["c-categoria-1", "c-categoria-2"].forEach((id, indice) => {
    const select = document.getElementById(id);
    categorias.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.nome} (${c.tipo})`;
      select.appendChild(opt);
    });
    // Só pra já vir com duas categorias diferentes selecionadas por padrão
    if (categorias[indice]) select.value = categorias[indice].id;
  });
}

// ================= AUTOMÁTICOS =================

async function carregarRelatoriosAutomaticos() {
  let lista;
  try {
    lista = await Api.listarRelatoriosAutomaticos();
  } catch (erro) {
    toast(erro.message, "erro");
    return;
  }
  const corpo = document.getElementById("corpo-relatorios-automaticos");
  const vazio = document.getElementById("automaticos-vazio");
  corpo.innerHTML = "";

  if (lista.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  lista.forEach((r) => {
    const tr = document.createElement("tr");
    tr.className = "linha-clicavel";
    const rotuloTipo = r.tipo === "automatico_semanal" ? "Semanal" : "Mensal";
    tr.innerHTML = `
      <td>${rotuloTipo}</td>
      <td>${formatarDataBR(r.data_inicio)} – ${formatarDataBR(r.data_fim)}</td>
      <td>${new Date(r.criado_em).toLocaleString("pt-BR")}</td>
      <td><span class="link-acao">Ver</span></td>
    `;
    tr.addEventListener("click", () => visualizarRelatorioAutomatico(r));
    corpo.appendChild(tr);
  });
}

document.getElementById("btn-gerar-agora").addEventListener("click", async () => {
  const tipo = document.getElementById("select-tipo-gerar-agora").value;
  const botao = document.getElementById("btn-gerar-agora");
  botao.disabled = true;
  try {
    await Api.gerarRelatorioAgora(tipo);
    await carregarRelatoriosAutomaticos();
    toast("Relatório gerado.");
  } catch (erro) {
    toast(erro.message, "erro");
  } finally {
    botao.disabled = false;
  }
});

function visualizarRelatorioAutomatico(relatorio) {
  mostrarAba("personalizado");
  document.getElementById("form-personalizado").classList.add("oculto");
  const banner = document.getElementById("banner-visualizacao");
  const rotuloTipo = relatorio.tipo === "automatico_semanal" ? "semanal" : "mensal";
  document.getElementById("banner-visualizacao-texto").textContent =
    `Visualizando relatório ${rotuloTipo} de ${formatarDataBR(relatorio.data_inicio)} a ${formatarDataBR(relatorio.data_fim)}, ` +
    `gerado em ${new Date(relatorio.criado_em).toLocaleString("pt-BR")}.`;
  banner.classList.remove("oculto");
  renderizarResultadoPersonalizado(relatorio.dados);
}

document.getElementById("btn-fechar-banner").addEventListener("click", () => {
  document.getElementById("banner-visualizacao").classList.add("oculto");
  document.getElementById("form-personalizado").classList.remove("oculto");
  document.getElementById("resultado-personalizado").classList.add("oculto");
});

// ================= PERSONALIZADO =================

document.getElementById("form-personalizado").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-personalizado");

  const filtros = {
    data_inicio: document.getElementById("p-data-inicio").value,
    data_fim: document.getElementById("p-data-fim").value,
    tipo: document.getElementById("p-tipo").value || undefined,
    categoria_id: document.getElementById("p-categoria").value || undefined,
  };

  try {
    const dados = await Api.relatorioPersonalizado(filtros);
    renderizarResultadoPersonalizado(dados);
  } catch (erro) {
    mostrarErro("erro-personalizado", erro.message);
  }
});

function renderizarResultadoPersonalizado(dados) {
  document.getElementById("resultado-personalizado").classList.remove("oculto");

  document.getElementById("rp-receitas").textContent = formatarMoeda(dados.saldo.total_receitas);
  document.getElementById("rp-despesas").textContent = formatarMoeda(dados.saldo.total_despesas);
  document.getElementById("rp-saldo").textContent = formatarMoeda(dados.saldo.saldo);

  // Gráfico diário (barras agrupadas: receitas x despesas por dia)
  destruirGrafico("diario-p");
  const ctxDiario = document.getElementById("grafico-diario-p").getContext("2d");
  graficos["diario-p"] = new Chart(ctxDiario, {
    type: "bar",
    data: {
      labels: dados.grafico_diario.map((d) => formatarDataBR(d.data)),
      datasets: [
        { label: "Receitas", data: dados.grafico_diario.map((d) => d.total_receitas), backgroundColor: "#2F6F4E" },
        { label: "Despesas", data: dados.grafico_diario.map((d) => d.total_despesas), backgroundColor: "#B3462C" },
      ],
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } },
  });

  // Gráfico de participação da categoria (se selecionada)
  const cartaoCategoria = document.getElementById("cartao-grafico-categoria");
  if (dados.grafico_categoria) {
    cartaoCategoria.classList.remove("oculto");
    const gc = dados.grafico_categoria;
    document.getElementById("titulo-grafico-categoria").textContent =
      `Participação de "${gc.categoria_nome}" no total de ${gc.categoria_tipo === "receita" ? "receitas" : "despesas"}`;
    destruirGrafico("categoria-p");
    const ctxCategoria = document.getElementById("grafico-categoria-p").getContext("2d");
    graficos["categoria-p"] = new Chart(ctxCategoria, {
      type: "doughnut",
      data: {
        labels: [gc.categoria_nome, "Restante"],
        datasets: [{ data: [gc.percentual, Math.max(0, 100 - gc.percentual)], backgroundColor: ["#A9862E", "#D3D6C9"] }],
      },
      options: { responsive: true, plugins: { legend: { position: "bottom" } } },
    });
  } else {
    cartaoCategoria.classList.add("oculto");
  }

  // Histórico
  const corpo = document.getElementById("corpo-historico-p");
  const vazio = document.getElementById("historico-p-vazio");
  corpo.innerHTML = "";
  if (dados.historico.length === 0) {
    vazio.classList.remove("oculto");
  } else {
    vazio.classList.add("oculto");
    dados.historico.forEach((mov) => {
      const tr = document.createElement("tr");
      const classeValor = mov.categoria_tipo === "despesa" ? "valor--despesa" : "valor--receita";
      const sinal = mov.categoria_tipo === "despesa" ? "−" : "+";
      tr.innerHTML = `
        <td data-label="Data">${formatarDataBR(mov.data)}</td>
        <td data-label="Descrição">${mov.descricao ? escaparHtml(mov.descricao) : "—"}</td>
        <td data-label="Categoria"><span class="etiqueta-categoria">${escaparHtml(mov.categoria_nome)}</span></td>
        <td data-label="Valor" class="alinhar-direita celula-valor ${classeValor}">${sinal} ${formatarMoeda(mov.valor)}</td>
      `;
      corpo.appendChild(tr);
    });
  }
}

// ================= COMPARATIVO =================

document.getElementById("form-comparativo").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-comparativo");

  const cat1 = document.getElementById("c-categoria-1").value;
  const cat2 = document.getElementById("c-categoria-2").value;
  if (cat1 === cat2) {
    mostrarErro("erro-comparativo", "Escolha duas categorias diferentes.");
    return;
  }

  const filtros = {
    data_inicio: document.getElementById("c-data-inicio").value,
    data_fim: document.getElementById("c-data-fim").value,
    categoria_id_1: cat1,
    categoria_id_2: cat2,
  };

  try {
    const dados = await Api.relatorioComparativo(filtros);
    renderizarResultadoComparativo(dados);
  } catch (erro) {
    mostrarErro("erro-comparativo", erro.message);
  }
});

function renderizarResultadoComparativo(dados) {
  document.getElementById("resultado-comparativo").classList.remove("oculto");

  document.getElementById("rc-nome-1").textContent = dados.categoria_1.nome;
  document.getElementById("rc-total-1").textContent = formatarMoeda(dados.categoria_1.total);
  document.getElementById("rc-total-1").className = "resumo__valor " + (dados.categoria_1.tipo === "despesa" ? "valor--despesa" : "valor--receita");

  document.getElementById("rc-nome-2").textContent = dados.categoria_2.nome;
  document.getElementById("rc-total-2").textContent = formatarMoeda(dados.categoria_2.total);
  document.getElementById("rc-total-2").className = "resumo__valor " + (dados.categoria_2.tipo === "despesa" ? "valor--despesa" : "valor--receita");

  if (dados.modo === "tipos_diferentes") {
    document.getElementById("rc-rotulo-final").textContent = "Diferença (receita − despesa)";
    document.getElementById("rc-valor-final").textContent = formatarMoeda(dados.saldo_diferenca);
  } else {
    document.getElementById("rc-rotulo-final").textContent = "Soma das duas";
    document.getElementById("rc-valor-final").textContent = formatarMoeda(dados.saldo_soma);
  }

  // Gráfico de linhas comparativo
  destruirGrafico("linha-c");
  const ctxLinha = document.getElementById("grafico-linha-c").getContext("2d");
  graficos["linha-c"] = new Chart(ctxLinha, {
    type: "line",
    data: {
      labels: dados.grafico_diario_comparativo.map((d) => formatarDataBR(d.data)),
      datasets: [
        { label: dados.categoria_1.nome, data: dados.grafico_diario_comparativo.map((d) => d.categoria_1_total), borderColor: "#2F6F4E", backgroundColor: "#2F6F4E", tension: 0.15 },
        { label: dados.categoria_2.nome, data: dados.grafico_diario_comparativo.map((d) => d.categoria_2_total), borderColor: "#B3462C", backgroundColor: "#B3462C", tension: 0.15 },
      ],
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } },
  });

  // Gráficos de pizza (só quando as duas categorias são do mesmo tipo)
  const cartaoIndividual = document.getElementById("cartao-pizza-individual-c");
  const cartaoCombinada = document.getElementById("cartao-pizza-combinada-c");

  if (dados.modo === "mesmo_tipo") {
    cartaoIndividual.classList.remove("oculto");
    cartaoCombinada.classList.remove("oculto");

    destruirGrafico("pizza-individual-c");
    const ctxIndividual = document.getElementById("grafico-pizza-individual-c").getContext("2d");
    graficos["pizza-individual-c"] = new Chart(ctxIndividual, {
      type: "pie",
      data: {
        labels: dados.grafico_participacao_individual.map((p) => p.categoria),
        datasets: [{
          data: dados.grafico_participacao_individual.map((p) => p.percentual),
          backgroundColor: ["#2F6F4E", "#B3462C", "#D3D6C9"],
        }],
      },
      options: { responsive: true, plugins: { legend: { position: "bottom" } } },
    });

    destruirGrafico("pizza-combinada-c");
    const ctxCombinada = document.getElementById("grafico-pizza-combinada-c").getContext("2d");
    graficos["pizza-combinada-c"] = new Chart(ctxCombinada, {
      type: "pie",
      data: {
        labels: dados.grafico_participacao_combinada.map((p) => p.categoria),
        datasets: [{
          data: dados.grafico_participacao_combinada.map((p) => p.percentual),
          backgroundColor: ["#A9862E", "#D3D6C9"],
        }],
      },
      options: { responsive: true, plugins: { legend: { position: "bottom" } } },
    });
  } else {
    cartaoIndividual.classList.add("oculto");
    cartaoCombinada.classList.add("oculto");
  }

  // Histórico combinado
  const corpo = document.getElementById("corpo-historico-c");
  const vazio = document.getElementById("historico-c-vazio");
  corpo.innerHTML = "";
  if (dados.historico.length === 0) {
    vazio.classList.remove("oculto");
  } else {
    vazio.classList.add("oculto");
    dados.historico.forEach((mov) => {
      const tr = document.createElement("tr");
      const classeValor = mov.categoria_tipo === "despesa" ? "valor--despesa" : "valor--receita";
      const sinal = mov.categoria_tipo === "despesa" ? "−" : "+";
      tr.innerHTML = `
        <td data-label="Data">${formatarDataBR(mov.data)}</td>
        <td data-label="Descrição">${mov.descricao ? escaparHtml(mov.descricao) : "—"}</td>
        <td data-label="Categoria"><span class="etiqueta-categoria">${escaparHtml(mov.categoria_nome)}</span></td>
        <td data-label="Valor" class="alinhar-direita celula-valor ${classeValor}">${sinal} ${formatarMoeda(mov.valor)}</td>
      `;
      corpo.appendChild(tr);
    });
  }
}

iniciar();