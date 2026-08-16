/**
 * Sidebar compartilhada entre todas as páginas logadas. Cada página inclui
 * este script (mesmo padrão de config.js/utils.js/api.js: sem build step,
 * sem template compartilhado — o HTML da sidebar é duplicado em cada
 * página e este arquivo cuida do comportamento).
 *
 * Responsabilidades:
 * - Recolher/expandir a sidebar (estado persistido em localStorage).
 * - Marcar o item de navegação ativo (via data-pagina no <body>).
 * - Botão "Sair" da sidebar.
 */
const SIDEBAR_ESTADO_KEY = "gf_sidebar_recolhida";

function inicializarSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const recolhida = localStorage.getItem(SIDEBAR_ESTADO_KEY) === "1";
  sidebar.classList.toggle("sidebar--recolhida", recolhida);

  document.querySelectorAll("[data-acao='toggle-sidebar']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const agoraRecolhida = sidebar.classList.toggle("sidebar--recolhida");
      localStorage.setItem(SIDEBAR_ESTADO_KEY, agoraRecolhida ? "1" : "0");
    });
  });

  const paginaAtual = document.body.dataset.pagina;
  sidebar.querySelectorAll(".sidebar__link[data-pagina]").forEach((link) => {
    link.classList.toggle("is-ativo", link.dataset.pagina === paginaAtual);
  });

  const btnSairSidebar = document.getElementById("btn-sair-sidebar");
  if (btnSairSidebar) {
    btnSairSidebar.addEventListener("click", () => {
      Auth.limparToken();
      window.location.href = "index.html";
    });
  }
}

document.addEventListener("DOMContentLoaded", inicializarSidebar);