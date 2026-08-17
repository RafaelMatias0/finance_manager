/**
 * Página de Planos e Metas: "guardar dinheiro" (meta simples de valor, ou
 * redução de gasto numa categoria) e "quitar dívida" (prazo livre, ou
 * parcelas — que reaproveita o mecanismo de Pendência por baixo).
 * Progresso nunca é editado diretamente — vem sempre calculado pela API
 * (GET /planos já traz `progresso` pronto).
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
let planos = [];

function contaPorId(id) {
  return contas.find((c) => c.id === id);
}

// ---------- Categorias / Contas (pra popular selects) ----------

async function carregarCategorias() {
  categorias = await Api.categorias();
  preencherSelectCategoriaPlano();
}

function preencherSelectCategoriaPlano() {
  const select = document.getElementById("select-categoria-plano");
  const valorAtual = select.value;
  select.innerHTML = "";
  // Guardar dinheiro (redução) e quitar dívida sempre trabalham com
  // categorias de despesa — reduzir um gasto, ou classificar o pagamento
  // de uma dívida.
  categorias
    .filter((c) => c.tipo === "despesa")
    .forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.nome;
      select.appendChild(opt);
    });
  if (valorAtual) select.value = valorAtual;
}

async function carregarContas() {
  contas = await Api.contas();
  preencherSelectContaPlano();
}

function preencherSelectContaPlano() {
  const select = document.getElementById("select-conta-plano");
  const valorAtual = select.value;
  select.innerHTML = "";
  contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    select.appendChild(opt);
  });
  if (valorAtual) select.value = valorAtual;
}

// ---------- Listar planos ----------

async function carregarPlanos() {
  planos = await Api.planos();
  renderizarListaPlanos();
}

function rotuloTipoPlano(plano) {
  if (plano.tipo === "guardar_dinheiro") {
    return plano.guardar_modo === "simples" ? "Guardar dinheiro" : "Reduzir gasto";
  }
  return plano.divida_modo === "prazo" ? "Quitar dívida (prazo)" : "Quitar dívida (parcelas)";
}

function renderizarListaPlanos() {
  const lista = document.getElementById("lista-planos");
  const vazio = document.getElementById("planos-vazio");
  lista.innerHTML = "";

  if (planos.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  planos.forEach((plano) => {
    const conta = contaPorId(plano.conta_id);
    const metaPartes = [rotuloTipoPlano(plano), conta ? conta.nome_banco : "—"];
    if (!plano.ativo) metaPartes.push("pausado");

    const div = document.createElement("div");
    div.className = "cartao-plano" + (plano.ativo ? "" : " cartao-plano--pausado");
    div.innerHTML = `
      <div class="cartao-plano__cabecalho">
        <div class="cartao-plano__info">
          <span class="cartao-plano__nome">${escaparHtml(plano.nome)}</span>
          <span class="cartao-plano__meta">${escaparHtml(metaPartes.join(" · "))}</span>
        </div>
        <div class="cartao-plano__acoes">
          <button type="button" class="btn-editar-plano">Editar</button>
          <button type="button" class="btn-pausar-plano">${plano.ativo ? "Pausar" : "Reativar"}</button>
          <button type="button" class="btn-apagar-plano">Apagar</button>
        </div>
      </div>
      <div class="cartao-plano__progresso"></div>
    `;

    div.querySelector(".btn-editar-plano").addEventListener("click", () => abrirFormPlano(plano));
    div.querySelector(".btn-pausar-plano").addEventListener("click", () => pausarPlano(plano));
    div.querySelector(".btn-apagar-plano").addEventListener("click", () => apagarPlano(plano));

    renderizarProgressoPlano(div.querySelector(".cartao-plano__progresso"), plano);
    lista.appendChild(div);
  });
}

function renderizarProgressoPlano(container, plano) {
  const p = plano.progresso;

  if (p.modo === "reducao_categoria") {
    const resumo = document.createElement("p");
    resumo.className = "barra-progresso__texto";
    resumo.innerHTML = `<span>Meses dentro da meta</span><strong>${p.meses_cumpridos} de ${p.meses_total}</strong>`;
    container.appendChild(resumo);

    const checklist = document.createElement("div");
    checklist.className = "checklist-mensal";
    p.meses.forEach((m) => {
      const item = document.createElement("div");
      item.className = "checklist-mensal__item";
      const marcaClasse = m.cumpriu ? "checklist-mensal__marca--ok" : "checklist-mensal__marca--falhou";
      item.innerHTML = `
        <span class="checklist-mensal__marca ${marcaClasse}">${m.cumpriu ? "✓" : "✗"}</span>
        <span class="checklist-mensal__mes">${formatarMesAno(m.mes)}</span>
        <span class="checklist-mensal__detalhe">${formatarMoeda(m.gasto)} (${escaparHtml(m.alvo)})</span>
      `;
      checklist.appendChild(item);
    });
    container.appendChild(checklist);
    return;
  }

  // simples / prazo / parcelas: barra de progresso comum
  const barra = document.createElement("div");
  barra.className = "barra-progresso";
  barra.innerHTML = `<div class="barra-progresso__preenchimento" style="width:${Math.min(100, p.percentual)}%"></div>`;
  container.appendChild(barra);

  const texto = document.createElement("p");
  texto.className = "barra-progresso__texto";
  texto.innerHTML = `<span>${formatarMoeda(p.progresso_valor)} de ${formatarMoeda(p.valor_alvo)}</span><strong>${p.percentual.toFixed(1)}%</strong>`;
  container.appendChild(texto);

  if (p.modo === "prazo") {
    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "link-acao";
    botao.textContent = "Registrar pagamento";
    botao.addEventListener("click", () => abrirModalPagamento(plano));
    container.appendChild(botao);
  }

  if (p.modo === "parcelas") {
    const listaCiclos = document.createElement("div");
    listaCiclos.className = "lista-ciclos";
    if (p.ciclos.length === 0) {
      listaCiclos.innerHTML = '<p class="estado-vazio" style="padding:0.5rem 0;">Nada pendente por aqui.</p>';
    } else {
      p.ciclos.forEach((ciclo) => {
        const linha = document.createElement("div");
        linha.className = "ciclo-pendencia";
        const etiquetaClasse = ciclo.status === "atrasada" ? "etiqueta-atrasada" : "etiqueta-a-vencer";
        const rotulo = ciclo.status === "atrasada" ? "Venceu" : "Vence";
        linha.innerHTML = `
          <span class="${etiquetaClasse}">${rotulo} ${formatarDataBR(ciclo.data_vencimento)}</span>
          <button type="button" class="link-acao btn-pagar-parcela">Marcar como paga</button>
        `;
        linha.querySelector(".btn-pagar-parcela").addEventListener("click", () => abrirModalPagamento(plano, ciclo));
        listaCiclos.appendChild(linha);
      });
    }
    container.appendChild(listaCiclos);
  }
}

// ---------- Criar / editar plano ----------

function alternarCamposPlano() {
  const tipo = document.querySelector('#form-plano input[name="tipo"]:checked').value;
  const guardarModoEl = document.querySelector('#form-plano input[name="guardar_modo"]:checked');
  const dividaModoEl = document.querySelector('#form-plano input[name="divida_modo"]:checked');
  const criterioReducaoEl = document.querySelector('#form-plano input[name="criterio_reducao"]:checked');
  const guardarModo = guardarModoEl ? guardarModoEl.value : null;
  const dividaModo = dividaModoEl ? dividaModoEl.value : null;
  const criterioReducao = criterioReducaoEl ? criterioReducaoEl.value : null;

  const ehGuardar = tipo === "guardar_dinheiro";
  const ehDivida = tipo === "quitar_divida";
  const ehSimples = ehGuardar && guardarModo === "simples";
  const ehReducao = ehGuardar && guardarModo === "reducao_categoria";
  const ehPrazo = ehDivida && dividaModo === "prazo";
  const ehParcelas = ehDivida && dividaModo === "parcelas";
  const editando = planoEmEdicao !== null;

  document.getElementById("grupo-guardar-modo").classList.toggle("oculto", !ehGuardar);
  document.getElementById("grupo-divida-modo").classList.toggle("oculto", !ehDivida);

  const mostrarCategoria = ehReducao || ehDivida;
  document.getElementById("campo-categoria-plano").classList.toggle("oculto", !mostrarCategoria);
  document.getElementById("select-categoria-plano").required = mostrarCategoria;
  document.getElementById("rotulo-categoria-plano").textContent = ehReducao ? "Categoria a reduzir" : "Categoria da dívida";

  document.getElementById("grupo-criterio-reducao").classList.toggle("oculto", !ehReducao);

  const mostrarAlvoPercentual = ehReducao && criterioReducao === "percentual_receita";
  const mostrarAlvoValorReducao = ehReducao && criterioReducao === "valor_fixo";
  document.getElementById("campo-alvo-percentual").classList.toggle("oculto", !mostrarAlvoPercentual);
  document.querySelector('#form-plano input[name="alvo_percentual"]').required = mostrarAlvoPercentual;
  document.getElementById("campo-alvo-valor-reducao").classList.toggle("oculto", !mostrarAlvoValorReducao);
  document.querySelector('#form-plano input[name="alvo_valor_reducao"]').required = mostrarAlvoValorReducao;

  // numero_parcelas/dia_vencimento pertencem à Pendencia criada por
  // trás do plano — só fazem sentido na criação, não são editáveis
  // depois (PATCH /planos nem aceita esses campos).
  const mostrarCamposParcela = ehParcelas && !editando;
  document.getElementById("campo-numero-parcelas").classList.toggle("oculto", !mostrarCamposParcela);
  document.querySelector('#form-plano input[name="numero_parcelas"]').required = mostrarCamposParcela;
  document.getElementById("campo-dia-vencimento-plano").classList.toggle("oculto", !mostrarCamposParcela);
  document.querySelector('#form-plano input[name="dia_vencimento"]').required = mostrarCamposParcela;

  const mostrarValorAlvo = ehSimples || ehPrazo || (ehParcelas && !editando);
  document.getElementById("campo-valor-alvo").classList.toggle("oculto", !mostrarValorAlvo);
  document.querySelector('#form-plano input[name="valor_alvo"]').required = mostrarValorAlvo;
  const rotuloValorAlvo = document.getElementById("rotulo-valor-alvo");
  if (ehParcelas) rotuloValorAlvo.textContent = "Valor de cada parcela";
  else if (ehPrazo) rotuloValorAlvo.textContent = "Valor total da dívida";
  else rotuloValorAlvo.textContent = "Valor alvo";

  const mostrarDataPrazo = ehGuardar || ehPrazo;
  document.getElementById("campo-data-prazo").classList.toggle("oculto", !mostrarDataPrazo);
  document.querySelector('#form-plano input[name="data_prazo"]').required = mostrarDataPrazo;
}

document.querySelectorAll(
  '#form-plano input[name="tipo"], #form-plano input[name="guardar_modo"], #form-plano input[name="divida_modo"], #form-plano input[name="criterio_reducao"]'
).forEach((el) => el.addEventListener("change", alternarCamposPlano));

let planoEmEdicao = null;

function abrirFormPlano(plano = null) {
  planoEmEdicao = plano;
  limparErro("erro-plano");
  const form = document.getElementById("form-plano");
  form.reset();

  preencherSelectCategoriaPlano();
  preencherSelectContaPlano();

  const radiosCascata = document.querySelectorAll(
    '#form-plano input[name="tipo"], #form-plano input[name="guardar_modo"], #form-plano input[name="divida_modo"], #form-plano input[name="criterio_reducao"]'
  );

  document.getElementById("titulo-modal-plano").textContent = plano ? "Editar plano" : "Novo plano";

  if (plano) {
    form.elements["id"].value = plano.id;
    form.elements["nome"].value = plano.nome;
    form.querySelector(`input[name="tipo"][value="${plano.tipo}"]`).checked = true;
    if (plano.guardar_modo) {
      form.querySelector(`input[name="guardar_modo"][value="${plano.guardar_modo}"]`).checked = true;
    }
    if (plano.divida_modo) {
      form.querySelector(`input[name="divida_modo"][value="${plano.divida_modo}"]`).checked = true;
    }
    if (plano.criterio_reducao) {
      form.querySelector(`input[name="criterio_reducao"][value="${plano.criterio_reducao}"]`).checked = true;
    }
    radiosCascata.forEach((r) => (r.disabled = true));

    form.elements["conta_id"].value = plano.conta_id;
    form.elements["mes_inicio"].value = plano.mes_inicio.slice(0, 7);
    if (plano.categoria_id) form.elements["categoria_id"].value = plano.categoria_id;
    const ehParcelas = plano.tipo === "quitar_divida" && plano.divida_modo === "parcelas";
    if (plano.valor_alvo !== null && !ehParcelas) {
      form.elements["valor_alvo"].value = plano.valor_alvo;
    }
    if (plano.data_prazo) form.elements["data_prazo"].value = plano.data_prazo;
    if (plano.alvo_percentual !== null) form.elements["alvo_percentual"].value = plano.alvo_percentual;
    if (plano.alvo_valor_reducao !== null) form.elements["alvo_valor_reducao"].value = plano.alvo_valor_reducao;
  } else {
    form.elements["id"].value = "";
    radiosCascata.forEach((r) => (r.disabled = false));
  }

  alternarCamposPlano();
  document.getElementById("modal-form-plano").classList.remove("oculto");
}

function fecharFormPlano() {
  document.getElementById("modal-form-plano").classList.add("oculto");
  planoEmEdicao = null;
}

document.getElementById("btn-novo-plano").addEventListener("click", () => abrirFormPlano());
document.getElementById("btn-cancelar-plano").addEventListener("click", fecharFormPlano);
document.getElementById("modal-form-plano").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-form-plano") fecharFormPlano();
});

document.getElementById("form-plano").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-plano");
  const dados = new FormData(evento.target);
  const id = dados.get("id");

  // Campos desabilitados (tipo/submodo, ao editar) não entram no
  // FormData — por isso lê do objeto planoEmEdicao quando editando.
  const tipo = id ? planoEmEdicao.tipo : dados.get("tipo");
  const guardarModo = id ? planoEmEdicao.guardar_modo : dados.get("guardar_modo");
  const dividaModo = id ? planoEmEdicao.divida_modo : dados.get("divida_modo");
  const criterioReducao = id ? planoEmEdicao.criterio_reducao : dados.get("criterio_reducao");

  const corpo = {
    nome: dados.get("nome"),
    conta_id: dados.get("conta_id"),
    mes_inicio: `${dados.get("mes_inicio")}-01`,
  };
  if (!id) corpo.tipo = tipo;

  if (tipo === "guardar_dinheiro") {
    if (!id) corpo.guardar_modo = guardarModo;
    corpo.data_prazo = dados.get("data_prazo");
    if (guardarModo === "simples") {
      corpo.valor_alvo = dados.get("valor_alvo");
    } else {
      corpo.categoria_id = dados.get("categoria_id");
      if (!id) corpo.criterio_reducao = criterioReducao;
      if (criterioReducao === "percentual_receita") {
        corpo.alvo_percentual = dados.get("alvo_percentual");
      } else {
        corpo.alvo_valor_reducao = dados.get("alvo_valor_reducao");
      }
    }
  } else {
    corpo.categoria_id = dados.get("categoria_id");
    if (!id) corpo.divida_modo = dividaModo;
    if (dividaModo === "prazo") {
      corpo.valor_alvo = dados.get("valor_alvo");
      corpo.data_prazo = dados.get("data_prazo");
    } else if (!id) {
      corpo.valor_alvo = dados.get("valor_alvo");
      corpo.numero_parcelas = dados.get("numero_parcelas");
      corpo.dia_vencimento = dados.get("dia_vencimento");
    }
  }

  try {
    if (id) {
      await Api.editarPlano(id, corpo);
      toast("Plano atualizado.");
    } else {
      await Api.criarPlano(corpo);
      toast("Plano criado.");
    }
    fecharFormPlano();
    await carregarPlanos();
  } catch (erro) {
    mostrarErro("erro-plano", erro.message);
  }
});

async function pausarPlano(plano) {
  try {
    await Api.editarPlano(plano.id, { ativo: !plano.ativo });
    await carregarPlanos();
    toast(plano.ativo ? "Plano pausado." : "Plano reativado.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function apagarPlano(plano) {
  const confirmado = confirm(`Apagar o plano "${plano.nome}"? Isso só é possível se ele não tiver pagamentos vinculados.`);
  if (!confirmado) return;
  try {
    await Api.apagarPlano(plano.id);
    await carregarPlanos();
    toast("Plano apagado.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

// ---------- Registrar pagamento (dívida por prazo, ou parcela) ----------

let pagamentoEmAndamento = null;

function abrirModalPagamento(plano, ciclo = null) {
  pagamentoEmAndamento = { plano, ciclo };
  limparErro("erro-pagamento-plano");
  const form = document.getElementById("form-pagamento-plano");
  form.reset();

  document.getElementById("titulo-modal-pagamento-plano").textContent = `Registrar pagamento — ${plano.nome}`;
  if (ciclo && plano.progresso.parcelas_total) {
    form.elements["valor"].value = (plano.progresso.valor_alvo / plano.progresso.parcelas_total).toFixed(2);
  }
  form.elements["data"].value = hojeISO();

  document.getElementById("modal-pagamento-plano").classList.remove("oculto");
}

function fecharModalPagamento() {
  document.getElementById("modal-pagamento-plano").classList.add("oculto");
  pagamentoEmAndamento = null;
}

document.getElementById("btn-cancelar-pagamento-plano").addEventListener("click", fecharModalPagamento);
document.getElementById("modal-pagamento-plano").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-pagamento-plano") fecharModalPagamento();
});

document.getElementById("form-pagamento-plano").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-pagamento-plano");
  const dados = new FormData(evento.target);
  const { plano, ciclo } = pagamentoEmAndamento;

  try {
    if (ciclo) {
      // Parcela: a mesma rota de pagar pendência, com a conta fixa do
      // plano (não é escolhida por lançamento, ao contrário de uma
      // pendência avulsa comum).
      await Api.pagarPendencia(plano.pendencia_id, {
        data_vencimento: ciclo.data_vencimento,
        conta_id: plano.conta_id,
        valor: dados.get("valor"),
        data: dados.get("data"),
        descricao: dados.get("descricao") || null,
      });
    } else {
      await Api.aportarPlano(plano.id, {
        valor: dados.get("valor"),
        data: dados.get("data"),
        descricao: dados.get("descricao") || null,
      });
    }
    fecharModalPagamento();
    await carregarPlanos();
    toast("Pagamento registrado.");
  } catch (erro) {
    mostrarErro("erro-pagamento-plano", erro.message);
  }
});

// ---------- Inicialização ----------

(async function iniciar() {
  await Promise.all([carregarCategorias(), carregarContas()]);
  await carregarPlanos();
})();
