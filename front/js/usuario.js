/**
 * Menu do usuário (canto superior direito de cada página): mostra o nome
 * de quem está logado, e abre um menu com "Perfil" (formulário flutuante
 * pra trocar o nome — email é fixo, é a identidade de login) e "Sair"
 * (antes vivia no rodapé da sidebar — ver js/sidebar.js).
 *
 * Mesmo padrão de sidebar.js: cada página logada inclui este script.
 */

let usuarioAtual = null;

function iniciaisDoNome(nome) {
  return (nome || "?").trim().charAt(0).toUpperCase();
}

async function carregarUsuarioAtual() {
  // Em index.html o DOMContentLoaded dispara ainda na tela pública, antes
  // do login — sem isso aqui, o GET /usuarios/me sem token dispararia um
  // 401 e um toast falso de "sessão expirada". Depois de logar, app.js
  // chama esta função de novo (dentro de iniciarDashboard()).
  if (!Auth.estaLogado()) return;
  try {
    usuarioAtual = await Api.meuUsuario();
  } catch (erro) {
    return; // sessao-expirada (ou rede) já é tratado em outro lugar
  }
  renderizarMenuUsuario();
}

function renderizarMenuUsuario() {
  if (!usuarioAtual) return;
  const avatar = document.getElementById("menu-usuario-avatar");
  const nome = document.getElementById("menu-usuario-nome");
  if (avatar) avatar.textContent = iniciaisDoNome(usuarioAtual.nome);
  if (nome) nome.textContent = usuarioAtual.nome;
}

// ---------- Abrir/fechar o dropdown ----------

function fecharMenuUsuario() {
  const menu = document.getElementById("menu-usuario");
  const botao = document.getElementById("btn-menu-usuario");
  const dropdown = document.getElementById("menu-usuario-dropdown");
  if (!menu) return;
  menu.classList.remove("is-aberto");
  dropdown.classList.add("oculto");
  botao.setAttribute("aria-expanded", "false");
}

function alternarMenuUsuario() {
  const menu = document.getElementById("menu-usuario");
  const dropdown = document.getElementById("menu-usuario-dropdown");
  const aberto = !dropdown.classList.contains("oculto");
  if (aberto) {
    fecharMenuUsuario();
  } else {
    menu.classList.add("is-aberto");
    dropdown.classList.remove("oculto");
    document.getElementById("btn-menu-usuario").setAttribute("aria-expanded", "true");
  }
}

function inicializarMenuUsuario() {
  const botao = document.getElementById("btn-menu-usuario");
  if (!botao) return; // página sem menu de usuário (não deveria acontecer, mas evita quebrar)

  botao.addEventListener("click", (evento) => {
    evento.stopPropagation();
    alternarMenuUsuario();
  });

  document.addEventListener("click", (evento) => {
    const menu = document.getElementById("menu-usuario");
    if (menu && !menu.contains(evento.target)) fecharMenuUsuario();
  });

  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") fecharMenuUsuario();
  });

  document.getElementById("btn-abrir-perfil").addEventListener("click", () => {
    fecharMenuUsuario();
    abrirModalPerfil();
  });

  document.getElementById("btn-sair").addEventListener("click", () => {
    Auth.limparToken();
    window.location.href = "index.html";
  });
}

// ---------- Modal de perfil ----------

function abrirModalPerfil() {
  if (!usuarioAtual) return;
  limparErro("erro-perfil");
  const form = document.getElementById("form-perfil");
  form.elements["nome"].value = usuarioAtual.nome;
  document.getElementById("texto-email-perfil").textContent = usuarioAtual.email;
  document.getElementById("modal-perfil").classList.remove("oculto");
}

function fecharModalPerfil() {
  document.getElementById("modal-perfil").classList.add("oculto");
}

document.addEventListener("DOMContentLoaded", () => {
  inicializarMenuUsuario();
  carregarUsuarioAtual();

  const btnCancelar = document.getElementById("btn-cancelar-perfil");
  if (btnCancelar) btnCancelar.addEventListener("click", fecharModalPerfil);

  const modal = document.getElementById("modal-perfil");
  if (modal) {
    modal.addEventListener("click", (evento) => {
      if (evento.target.id === "modal-perfil") fecharModalPerfil();
    });
  }

  const form = document.getElementById("form-perfil");
  if (form) {
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      limparErro("erro-perfil");
      const dados = new FormData(evento.target);
      const destravar = travarBotaoEnvio(evento.target);
      try {
        usuarioAtual = await Api.atualizarMeuUsuario({ nome: dados.get("nome") });
        renderizarMenuUsuario();
        fecharModalPerfil();
        toast("Perfil atualizado.");
      } catch (erro) {
        mostrarErro("erro-perfil", erro.message);
      } finally {
        destravar();
      }
    });
  }
});
