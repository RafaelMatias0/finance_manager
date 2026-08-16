/**
 * Página de Pendências: contas recorrentes (aluguel, assinaturas) e
 * avulsas (lançamentos futuros com vencimento). Pago/pendente nunca é
 * guardado — o backend calcula a partir de existir ou não uma
 * Movimentação vinculada a cada vencimento (ver GET /pendencias). Marcar
 * como paga cria essa Movimentação de verdade (POST /pendencias/{id}/pagar).
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
let pendencias = [];

function categoriaPorId(id) {
  return categorias.find((c) => c.id === id);
}

function contaPorId(id) {
  return contas.find((c) => c.id === id);
}

// ---------- Categorias / Contas (pra popular selects) ----------

async function carregarCategorias() {
  categorias = await Api.categorias();
  preencherSelectCategoriaPendencia();
}

function preencherSelectCategoriaPendencia() {
  const tipoSelecionado = document.querySelector('#form-pendencia input[name="tipo"]:checked').value;
  const select = document.getElementById("select-categoria-pendencia");
  const valorAtual = select.value;
  select.innerHTML = "";
  categorias
    .filter((c) => c.tipo === tipoSelecionado)
    .forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.nome;
      select.appendChild(opt);
    });
  if (valorAtual) select.value = valorAtual;
}

document.querySelectorAll('#form-pendencia input[name="tipo"]').forEach((radio) => {
  radio.addEventListener("change", preencherSelectCategoriaPendencia);
});

async function carregarContas() {
  contas = await Api.contas();
  preencherSelectsContaPendencia();
}

function preencherSelectsContaPendencia() {
  const selectPadrao = document.getElementById("select-conta-pendencia");
  const valorPadraoAtual = selectPadrao.value;
  selectPadrao.innerHTML = '<option value="">Nenhuma</option>';
  contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    selectPadrao.appendChild(opt);
  });
  if (valorPadraoAtual) selectPadrao.value = valorPadraoAtual;

  const selectPagamento = document.getElementById("select-conta-pagamento");
  const valorPagamentoAtual = selectPagamento.value;
  selectPagamento.innerHTML = "";
  contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.apelido ? `${c.nome_banco} — ${c.apelido}` : c.nome_banco;
    selectPagamento.appendChild(opt);
  });
  if (valorPagamentoAtual) selectPagamento.value = valorPagamentoAtual;
}

// ---------- Listar pendências ----------

async function carregarPendencias() {
  pendencias = await Api.pendencias();
  renderizarListaPendencias();
}

function formatarVencimento(pendencia, ciclo) {
  const rotulo = ciclo.status === "atrasada" ? "Venceu" : "Vence";
  return `${rotulo} ${formatarDataBR(ciclo.data_vencimento)}`;
}

function renderizarListaPendencias() {
  const lista = document.getElementById("lista-pendencias");
  const vazio = document.getElementById("pendencias-vazio");
  lista.innerHTML = "";

  if (pendencias.length === 0) {
    vazio.classList.remove("oculto");
    return;
  }
  vazio.classList.add("oculto");

  pendencias.forEach((pendencia) => {
    const categoria = categoriaPorId(pendencia.categoria_id);
    const conta = pendencia.conta_id ? contaPorId(pendencia.conta_id) : null;
    const classeValor = categoria?.tipo === "despesa" ? "valor--despesa" : "valor--receita";

    const div = document.createElement("div");
    div.className = "cartao-pendencia" + (pendencia.ativa ? "" : " cartao-pendencia--pausada");

    const metaPartes = [
      pendencia.recorrente ? `Recorrente · dia ${pendencia.dia_vencimento}` : "Avulsa",
      categoria?.nome ?? "—",
    ];
    if (conta) metaPartes.push(conta.nome_banco);
    if (!pendencia.ativa) metaPartes.push("pausada");

    div.innerHTML = `
      <div class="cartao-pendencia__cabecalho">
        <div class="cartao-pendencia__info">
          <span class="cartao-pendencia__descricao">${escaparHtml(pendencia.descricao)}</span>
          <span class="cartao-pendencia__meta">${escaparHtml(metaPartes.join(" · "))}</span>
        </div>
        <span class="cartao-pendencia__valor ${classeValor}">${formatarMoeda(pendencia.valor)}</span>
        <div class="cartao-pendencia__acoes">
          <button type="button" class="btn-editar-pendencia">Editar</button>
          ${pendencia.recorrente ? `<button type="button" class="btn-pausar-pendencia">${pendencia.ativa ? "Pausar" : "Reativar"}</button>` : ""}
          <button type="button" class="btn-apagar-pendencia">Apagar</button>
        </div>
      </div>
      <div class="lista-ciclos"></div>
    `;

    const listaCiclos = div.querySelector(".lista-ciclos");
    if (pendencia.ciclos.length === 0) {
      listaCiclos.innerHTML = '<p class="estado-vazio" style="padding:0.5rem 0;">Nada pendente por aqui.</p>';
    } else {
      pendencia.ciclos.forEach((ciclo) => {
        const linha = document.createElement("div");
        linha.className = "ciclo-pendencia";
        const etiquetaClasse = ciclo.status === "atrasada" ? "etiqueta-atrasada" : "etiqueta-a-vencer";
        linha.innerHTML = `
          <span class="${etiquetaClasse}">${formatarVencimento(pendencia, ciclo)}</span>
          <button type="button" class="link-acao btn-pagar-ciclo">Marcar como paga</button>
        `;
        linha.querySelector(".btn-pagar-ciclo").addEventListener("click", () => abrirModalPagar(pendencia, ciclo));
        listaCiclos.appendChild(linha);
      });
    }

    div.querySelector(".btn-editar-pendencia").addEventListener("click", () => abrirFormPendencia(pendencia));
    div.querySelector(".btn-apagar-pendencia").addEventListener("click", () => apagarPendencia(pendencia));
    const btnPausar = div.querySelector(".btn-pausar-pendencia");
    if (btnPausar) btnPausar.addEventListener("click", () => pausarPendencia(pendencia));

    lista.appendChild(div);
  });
}

// ---------- Criar / editar pendência ----------

function alternarCamposRecorrencia() {
  const recorrente = document.querySelector('#form-pendencia input[name="recorrente"]:checked').value === "sim";
  document.getElementById("campo-data-vencimento").classList.toggle("oculto", recorrente);
  document.getElementById("campo-dia-vencimento").classList.toggle("oculto", !recorrente);
  document.querySelector('#form-pendencia input[name="data_vencimento"]').required = !recorrente;
  document.querySelector('#form-pendencia input[name="dia_vencimento"]').required = recorrente;
}

document.querySelectorAll('#form-pendencia input[name="recorrente"]').forEach((radio) => {
  radio.addEventListener("change", alternarCamposRecorrencia);
});

let pendenciaEmEdicao = null;

function abrirFormPendencia(pendencia = null) {
  pendenciaEmEdicao = pendencia;
  limparErro("erro-pendencia");
  const form = document.getElementById("form-pendencia");
  form.reset();

  const radiosRecorrencia = document.querySelectorAll('#form-pendencia input[name="recorrente"]');

  document.getElementById("titulo-modal-pendencia").textContent = pendencia ? "Editar pendência" : "Nova pendência";

  if (pendencia) {
    const categoria = categoriaPorId(pendencia.categoria_id);
    form.elements["id"].value = pendencia.id;
    form.querySelector(`input[name="tipo"][value="${categoria?.tipo ?? "despesa"}"]`).checked = true;
    preencherSelectCategoriaPendencia();
    form.elements["descricao"].value = pendencia.descricao;
    form.elements["valor"].value = pendencia.valor;
    form.elements["categoria_id"].value = pendencia.categoria_id;
    form.elements["conta_id"].value = pendencia.conta_id ?? "";

    form.querySelector(`input[name="recorrente"][value="${pendencia.recorrente ? "sim" : "nao"}"]`).checked = true;
    radiosRecorrencia.forEach((r) => (r.disabled = true));
    if (pendencia.recorrente) {
      form.elements["dia_vencimento"].value = pendencia.dia_vencimento;
    } else {
      form.elements["data_vencimento"].value = pendencia.data_vencimento;
    }
  } else {
    form.elements["id"].value = "";
    radiosRecorrencia.forEach((r) => (r.disabled = false));
    preencherSelectCategoriaPendencia();
  }

  alternarCamposRecorrencia();
  document.getElementById("modal-form-pendencia").classList.remove("oculto");
}

function fecharFormPendencia() {
  document.getElementById("modal-form-pendencia").classList.add("oculto");
  pendenciaEmEdicao = null;
}

document.getElementById("btn-nova-pendencia").addEventListener("click", () => abrirFormPendencia());
document.getElementById("btn-cancelar-pendencia").addEventListener("click", fecharFormPendencia);
document.getElementById("modal-form-pendencia").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-form-pendencia") fecharFormPendencia();
});

document.getElementById("form-pendencia").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-pendencia");
  const dados = new FormData(evento.target);
  const id = dados.get("id");
  const recorrente = dados.get("recorrente") === "sim";

  const corpo = {
    descricao: dados.get("descricao"),
    valor: dados.get("valor"),
    categoria_id: dados.get("categoria_id"),
    conta_id: dados.get("conta_id") || null,
  };
  if (!id) {
    // recorrente/dia_vencimento/data_vencimento só podem ser definidos na
    // criação — editar preserva o tipo original (ver abrirFormPendencia).
    corpo.recorrente = recorrente;
  }
  if (recorrente) {
    corpo.dia_vencimento = dados.get("dia_vencimento");
  } else {
    corpo.data_vencimento = dados.get("data_vencimento");
  }

  try {
    if (id) {
      await Api.editarPendencia(id, corpo);
      toast("Pendência atualizada.");
    } else {
      await Api.criarPendencia(corpo);
      toast("Pendência criada.");
    }
    fecharFormPendencia();
    await carregarPendencias();
  } catch (erro) {
    mostrarErro("erro-pendencia", erro.message);
  }
});

async function pausarPendencia(pendencia) {
  try {
    await Api.editarPendencia(pendencia.id, { ativa: !pendencia.ativa });
    await carregarPendencias();
    toast(pendencia.ativa ? "Pendência pausada." : "Pendência reativada.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function apagarPendencia(pendencia) {
  const confirmado = confirm(`Apagar a pendência "${pendencia.descricao}"? Isso só é possível se ela não tiver pagamentos vinculados.`);
  if (!confirmado) return;
  try {
    await Api.apagarPendencia(pendencia.id);
    await carregarPendencias();
    toast("Pendência apagada.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

// ---------- Marcar como paga ----------

let cicloEmPagamento = null;

function abrirModalPagar(pendencia, ciclo) {
  cicloEmPagamento = { pendencia, ciclo };
  limparErro("erro-pagar-pendencia");
  const form = document.getElementById("form-pagar-pendencia");
  form.reset();

  document.getElementById("titulo-modal-pagar").textContent = `Marcar como paga — ${pendencia.descricao}`;
  form.elements["data_vencimento"].value = ciclo.data_vencimento;
  form.elements["valor"].value = pendencia.valor;
  form.elements["data"].value = hojeISO();
  if (pendencia.conta_id) form.elements["conta_id"].value = pendencia.conta_id;

  document.getElementById("modal-pagar-pendencia").classList.remove("oculto");
}

function fecharModalPagar() {
  document.getElementById("modal-pagar-pendencia").classList.add("oculto");
  cicloEmPagamento = null;
}

document.getElementById("btn-cancelar-pagar-pendencia").addEventListener("click", fecharModalPagar);
document.getElementById("modal-pagar-pendencia").addEventListener("click", (evento) => {
  if (evento.target.id === "modal-pagar-pendencia") fecharModalPagar();
});

document.getElementById("form-pagar-pendencia").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro("erro-pagar-pendencia");
  const dados = new FormData(evento.target);

  try {
    await Api.pagarPendencia(cicloEmPagamento.pendencia.id, {
      data_vencimento: dados.get("data_vencimento"),
      conta_id: dados.get("conta_id"),
      valor: dados.get("valor"),
      data: dados.get("data"),
      descricao: dados.get("descricao") || null,
    });
    fecharModalPagar();
    await carregarPendencias();
    toast("Pendência marcada como paga.");
  } catch (erro) {
    mostrarErro("erro-pagar-pendencia", erro.message);
  }
});

// ---------- Inicialização ----------

(async function iniciar() {
  await Promise.all([carregarCategorias(), carregarContas()]);
  await carregarPendencias();
})();
