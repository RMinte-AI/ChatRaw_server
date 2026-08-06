(function () {
  "use strict";

  const icons = {
    chat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 17.5 3.5 21v-5.2A8 8 0 0 1 12 4a8 8 0 0 1 0 16 8.5 8.5 0 0 1-7-2.5Z"/><path d="M8 11h8M8 14h5"/></svg>',
    knowledge: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h9a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3V4.5Z"/><path d="M8 7.5h9a2 2 0 0 1 2 2V18h-2M8 12h6M8 15h4"/></svg>',
    document: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6Z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></svg>',
    data: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg>',
    task: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4h10a2 2 0 0 1 2 2v14H8a4 4 0 0 1-4-4V8a4 4 0 0 1 4-4Z"/><path d="M8 4v16M11 9h6M11 13h6"/></svg>',
    files: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 7V5a2 2 0 0 1 2-2h5l2 2h5a2 2 0 0 1 2 2v2"/></svg>',
    model: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 4 7v10l8 4 8-4V7Z"/><path d="m4 7 8 4 8-4M12 11v10"/></svg>',
    module: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><path d="M17.5 14v7M14 17.5h7"/></svg>',
    rule: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10v18l-5-3-5 3Z"/><path d="M10 8h4M10 12h4"/></svg>'
  };

  const cardSets = {
    work: [
      { icon: "chat", title: "对话工作台", desc: "保留当前多模型对话、文件输入与工具活动，作为进入内容空间的主入口。", meta: "最近使用 14:32", status: "可用" },
      { icon: "knowledge", title: "知识检索", desc: "从已批准的知识源中检索，并在同一工作区查看引用与上下文。", meta: "67 个知识条目", status: "已连接" },
      { icon: "document", title: "文档解析", desc: "上传文档，查看解析状态和结构化结果。", meta: "3 个任务运行中", status: "运行中" },
      { icon: "data", title: "数据查询", desc: "按明确查询契约读取业务数据，并保留执行记录。", meta: "上次运行 09:18", status: "可用" },
      { icon: "task", title: "任务中心", desc: "集中查看长任务、审批、产物与恢复状态。", meta: "2 项待处理", status: "待处理" },
      { icon: "files", title: "文件空间", desc: "管理对话、模块任务和个人工作流中使用的文件资源。", meta: "本周新增 18 个文件", status: "同步完成" }
    ],
    assets: [
      { icon: "knowledge", title: "知识库", desc: "维护可检索的资料集合、索引状态与来源信息。", meta: "最后更新 11:06", status: "已索引" },
      { icon: "files", title: "共享文件", desc: "查看平台内可用文件，并按权限进入对应内容。", meta: "126 个文件", status: "可用" },
      { icon: "document", title: "解析记录", desc: "回看文档解析任务及其结构化输出。", meta: "近 7 日 24 项", status: "正常" },
      { icon: "rule", title: "个人规则", desc: "管理只影响本人后续 Agent 任务的规则版本。", meta: "4 条已激活", status: "个人" },
      { icon: "model", title: "技能资源", desc: "选择任务中需要明确使用的个人技能材料。", meta: "已安装 12 项", status: "可用" },
      { icon: "data", title: "查询目录", desc: "浏览已发布的数据查询能力与字段说明。", meta: "9 项数据能力", status: "已发布" }
    ],
    system: [
      { icon: "model", title: "模型服务", desc: "查看逻辑模型、能力和当前可用状态。", meta: "3 个逻辑模型", status: "正常" },
      { icon: "module", title: "模块能力", desc: "浏览已启用模块和当前用户可以使用的操作。", meta: "6 个模块", status: "已启用" },
      { icon: "task", title: "运行状态", desc: "检查任务队列、审批等待和最近失败原因。", meta: "队列 3", status: "监测中" },
      { icon: "rule", title: "系统规则", desc: "查看管理员发布并影响新任务的系统默认规则。", meta: "2 条已激活", status: "只读" },
      { icon: "chat", title: "审计记录", desc: "按角色查看登录、配置和任务操作记录。", meta: "保留 90 天", status: "记录中" },
      { icon: "files", title: "平台信息", desc: "查看版本、协议与当前部署的基础信息。", meta: "Server 0.0.1", status: "当前版本" }
    ]
  };

  function revealEntries() {
    const entries = document.querySelectorAll(".reveal");
    if (!entries.length) return;
    if (!("IntersectionObserver" in window)) {
      entries.forEach((entry) => entry.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver((records) => {
      records.forEach((record) => {
        if (!record.isIntersecting) return;
        record.target.classList.add("is-visible");
        observer.unobserve(record.target);
      });
    }, { threshold: 0.08 });
    entries.forEach((entry) => observer.observe(entry));
  }

  function setupLogin() {
    const form = document.querySelector("[data-login-form]");
    if (!form) return;
    const error = form.querySelector("[data-login-error]");
    const cancel = form.querySelector("[data-login-cancel]");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const username = form.elements.username.value.trim();
      const password = form.elements.password.value;
      if (!username || !password) {
        error.textContent = "请输入用户名和密码。";
        return;
      }
      error.textContent = "";
      window.location.href = "home.html";
    });
    cancel.addEventListener("click", () => {
      form.reset();
      error.textContent = "";
      form.elements.username.focus();
    });
  }

  function renderCards(setName) {
    const grid = document.querySelector("[data-card-grid]");
    if (!grid) return;
    const cards = cardSets[setName] || cardSets.work;
    grid.innerHTML = cards.map((card, index) => `
      <article class="feature-card reveal stagger-${index}" tabindex="0">
        <div class="card-topline">
          <span class="card-icon">${icons[card.icon]}</span>
          <span class="card-status">${card.status}</span>
        </div>
        <h2>${card.title}</h2>
        <p>${card.desc}</p>
        <div class="card-footer">
          <span class="card-meta">${card.meta}</span>
          <a class="card-action" href="content.html?item=${encodeURIComponent(card.title)}">
            打开
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M14 7l5 5-5 5"/></svg>
          </a>
        </div>
      </article>
    `).join("");
    revealEntries();
  }

  function setupTabs() {
    const tabs = document.querySelectorAll("[data-card-tab]");
    if (!tabs.length) return;
    renderCards("work");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((item) => item.setAttribute("aria-selected", String(item === tab)));
        renderCards(tab.dataset.cardTab);
      });
    });
  }

  function setupCopilot() {
    const launcher = document.querySelector("[data-agent-launcher]");
    const panel = document.querySelector("[data-copilot-panel]");
    if (!launcher || !panel) return;
    const close = panel.querySelector("[data-copilot-close]");
    const form = panel.querySelector("[data-copilot-form]");
    const messages = panel.querySelector("[data-copilot-messages]");
    const setOpen = (open) => {
      panel.classList.toggle("is-open", open);
      launcher.setAttribute("aria-expanded", String(open));
      panel.setAttribute("aria-hidden", String(!open));
      if (open) panel.querySelector("input").focus();
    };
    launcher.addEventListener("click", () => setOpen(!panel.classList.contains("is-open")));
    close.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && panel.classList.contains("is-open")) setOpen(false);
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const input = form.elements.prompt;
      const value = input.value.trim();
      if (!value) return;
      const message = document.createElement("div");
      message.className = "copilot-message user";
      message.textContent = value;
      messages.appendChild(message);
      input.value = "";
      messages.scrollTop = messages.scrollHeight;
    });
  }

  function setupWorkspace() {
    const navItems = document.querySelectorAll("[data-workspace-item]");
    if (!navItems.length) return;
    const title = document.querySelector("[data-workspace-title]");
    const headline = document.querySelector("[data-workspace-headline]");
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("item");
    if (requested) {
      title.textContent = requested;
      headline.textContent = `从“${requested}”开始工作`;
      const matchedItem = Array.from(navItems).find((item) => item.dataset.title === requested);
      if (matchedItem) {
        navItems.forEach((item) => item.classList.toggle("active", item === matchedItem));
        navItems.forEach((item) => item.setAttribute("aria-current", item === matchedItem ? "page" : "false"));
      }
    }
    navItems.forEach((item) => {
      item.addEventListener("click", () => {
        navItems.forEach((nav) => nav.classList.toggle("active", nav === item));
        navItems.forEach((nav) => nav.setAttribute("aria-current", nav === item ? "page" : "false"));
        title.textContent = item.dataset.title;
        headline.textContent = item.dataset.headline;
      });
    });
    document.querySelectorAll("[data-prompt]").forEach((prompt) => {
      prompt.addEventListener("click", () => {
        const composer = document.querySelector("[data-composer]");
        composer.value = prompt.dataset.prompt;
        composer.focus();
      });
    });
    const composerForm = document.querySelector(".composer");
    if (composerForm) composerForm.addEventListener("submit", (event) => event.preventDefault());
  }

  function setupSettings() {
    const buttons = document.querySelectorAll("[data-settings-tab]");
    const panels = document.querySelectorAll("[data-settings-panel]");
    if (!buttons.length) return;
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((item) => item.classList.toggle("active", item === button));
        buttons.forEach((item) => item.setAttribute("aria-selected", String(item === button)));
        panels.forEach((panel) => { panel.hidden = panel.dataset.settingsPanel !== button.dataset.settingsTab; });
        const active = document.querySelector(`[data-settings-panel="${button.dataset.settingsTab}"]`);
        if (active) active.querySelector("h2").focus({ preventScroll: true });
      });
    });
    const hashTab = window.location.hash.replace("#", "");
    const requestedButton = Array.from(buttons).find((button) => button.dataset.settingsTab === hashTab);
    if (requestedButton) requestedButton.click();
    document.querySelectorAll(".toggle").forEach((toggle) => {
      toggle.addEventListener("click", () => {
        const checked = toggle.getAttribute("aria-checked") === "true";
        toggle.setAttribute("aria-checked", String(!checked));
      });
    });
    document.querySelectorAll("[data-save-settings]").forEach((button) => {
      button.addEventListener("click", () => {
        const previous = button.textContent;
        button.textContent = "已保存";
        button.disabled = true;
        window.setTimeout(() => {
          button.textContent = previous;
          button.disabled = false;
        }, 1200);
      });
    });
    document.querySelectorAll(".color-choice").forEach((choice) => {
      choice.addEventListener("click", () => {
        document.querySelectorAll(".color-choice").forEach((item) => item.setAttribute("aria-checked", String(item === choice)));
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupLogin();
    setupTabs();
    setupCopilot();
    setupWorkspace();
    setupSettings();
    revealEntries();
  });
}());
