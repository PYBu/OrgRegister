(() => {
  const $ = (selector, root = document) => root.querySelector(selector);

  function addClearTasksButton() {
    const view = $('#view-tasks');
    const lead = view && $('.lead', view);
    const surface = view && $('.surface', view);
    if (!view || !lead || !surface || $('#clearTasks', view)) return;
    const heading = document.createElement('div');
    heading.className = 'section-heading';
    lead.parentNode.insertBefore(heading, lead);
    heading.appendChild(lead);
    const button = document.createElement('button');
    button.id = 'clearTasks';
    button.type = 'button';
    button.className = 'secondary danger-outline';
    button.textContent = '清除全部记录';
    heading.appendChild(button);
    button.addEventListener('click', async () => {
      if (!confirm('确定清除全部任务记录和步骤日志吗？此操作不可撤销。')) return;
      button.disabled = true;
      try {
        const response = await fetch('/api/tasks', { method: 'DELETE' });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        if (window.loadTasks) await window.loadTasks();
        if (window.stats) await window.stats();
        if (window.toast) window.toast(`已清除 ${result.removed || 0} 条任务记录`);
      } catch (error) {
        if (window.toast) window.toast(`清除失败：${error.message}`);
      } finally {
        button.disabled = false;
      }
    });
  }

  function addAccountDeleteButtons() {
    document.querySelectorAll('#accountRows .account-actions').forEach((actions) => {
      if ($('[data-account-delete]', actions)) return;
      const detail = actions.closest('.account-detail');
      const card = actions.closest('.account-card');
      const summary = card && $('.account-summary', card);
      const toggle = summary && summary.dataset.toggle;
      const id = toggle && toggle.replace(/^account-/, '');
      if (!id) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'danger-outline';
      button.dataset.accountDelete = id;
      button.textContent = '删除账号';
      actions.appendChild(button);
    });
  }

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-account-delete]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const card = button.closest('.account-card');
    const email = $('strong', card)?.textContent || '此账号';
    if (!confirm(`确定删除 ${email} 吗？账号凭证会从邮箱池中移除，任务历史会保留。`)) return;
    button.disabled = true;
    try {
      const response = await fetch(`/api/accounts/${encodeURIComponent(button.dataset.accountDelete)}`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      if (window.loadAccounts) await window.loadAccounts();
      if (window.loadEmails) await window.loadEmails();
      if (window.stats) await window.stats();
      if (window.toast) window.toast(`已删除 ${result.email || email}`);
    } catch (error) {
      button.disabled = false;
      if (window.toast) window.toast(`删除失败：${error.message}`);
    }
  }, true);

  function init() {
    addClearTasksButton();
    addAccountDeleteButtons();
    const rows = $('#accountRows');
    if (rows) new MutationObserver(addAccountDeleteButtons).observe(rows, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
