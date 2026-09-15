(() => {
  // Edit this block to change the About content shown in Settings.
  const ABOUT_INFO = {
    zh: {
      title: '关于 OrgRegister | Ver.ORegGPT',
      content: '本版本为 Beta-ORegGPT  测试版。\n\n- 本服务用于 自动化注册 ChatGPT 账号并获取Session Token与Access Token，支持多段式的 Microsoft 邮箱。但是本服务仅作测试使用，作为逆向研究课题。\n- 代理ip默认走本地7890端口。\n- 由 Minier Buper 创作并开源！（Github/PYBu）\n- 本服务不提供更新，仅希望对你的课题研究有所帮助！',
    },
    en: {
      title: 'About OrgRegister | Ver.ORegGPT',
      content: 'This version is the Beta-ORegGPT beta release.\n\n- This service is used to automatically register ChatGPT accounts and obtain Session Tokens and Access Tokens, and supports multi-part Microsoft email addresses. However, this service is for testing purposes only, as part of a reverse-engineering research project.\n- The proxy IP uses the local port 7890 by default.\n- Created and open-sourced by Minier Buper! (Github/PYBu)\n- This service will not provide updates. I only hope it can be of some help to your research!',
    },
    ja: { title: 'OrgRegister について', content: 'Beta-ORegGPT テスト版です。\n\nこのサービスは研究目的のテスト用途です。' },
    sv: { title: 'Om OrgRegister', content: 'Detta är Beta-ORegGPT-testversionen.\n\nTjänsten är endast avsedd för test och forskning.' },
    zhTW: { title: '關於 OrgRegister', content: '這是 Beta-ORegGPT 測試版本。\n\n本服務僅供測試與研究用途。' },
  };

  const $ = (id) => document.getElementById(id);
  const nav = document.querySelector('.nav');
  if (!nav) return;

  const settingsButton = document.createElement('button');
  settingsButton.type = 'button';
  settingsButton.dataset.view = 'settings';
  settingsButton.textContent = '设置';
  settingsButton.className = 'settings-link';
  document.querySelector('.sidebar').appendChild(settingsButton);

  const section = document.createElement('section');
  section.id = 'view-settings';
  section.className = 'hidden';
  section.innerHTML = `<div class="eyebrow" data-zh="应用偏好" data-en="Preferences">应用偏好</div>
    <p class="lead" data-zh="设置" data-en="Settings">设置</p>
    <section class="surface settings-panel"><h2 data-zh="语言" data-en="Language">语言</h2>
      <p class="note" data-zh="选择面板显示语言。切换后立即生效。" data-en="Choose the dashboard language. Changes apply immediately.">选择面板显示语言。切换后立即生效。</p>
      <div class="language-options" role="group" aria-label="Language">
        <button type="button" data-locale="zh-CN">中文</button>
        <button type="button" data-locale="zh-TW">繁體中文</button>
        <button type="button" data-locale="en-US">English</button>
        <button type="button" data-locale="ja-JP">日本語</button>
        <button type="button" data-locale="sv-SE">Svenska</button>
      </div>
    </section>
    <section class="surface settings-panel about-panel">
      <h2 id="about-title"></h2>
      <p id="about-content" class="about-content"></p>
    </section>`;
  document.querySelector('.content').appendChild(section);

  const translations = {
    zh: {
      brand: 'OrgRegister', brandSmall: 'account operations', register: '注册机', emails: '邮箱池', tasks: '任务记录', accounts: '成功号池', settings: '设置',
      idle: '空闲', running: '运行中', total: '邮箱总数', ready: '可处理', success: '成功账号', failed: '失败任务', operations: 'Operations', lead: 'Keep the queue moving.', taskControl: '任务控制',
      proxy: '代理', proxyTest: '测试代理', concurrency: '并发', limit: '数量', hideChrome: '隐藏 Chrome', start: '开始任务', stop: '结束任务', autoHealth: '自动验活', interval: '间隔（分钟）', save: '保存设置', readyEmails: '可注册邮箱', terminal: '实时看板', waiting: '等待任务启动...',
      sourcePool: 'Source pool', importTitle: '导入凭证', importBtn: '导入邮箱', clear: '清空', email: '邮箱', tempEmail: '临时邮箱', status: '状态', action: '操作', runHistory: 'Run history', taskTitle: '任务记录', id: 'ID', last: '最后进度 / 错误', steps: '详细步骤', vault: 'Credential vault', accountTitle: '成功号池'
    },
    en: {
      brand: 'OrgRegister', brandSmall: 'account operations', register: 'Register', emails: 'Email pool', tasks: 'Task history', accounts: 'Account vault', settings: 'Settings',
      idle: 'Idle', running: 'Running', total: 'Total emails', ready: 'Ready', success: 'Successful accounts', failed: 'Failed tasks', operations: 'Operations', lead: 'Keep the queue moving.', taskControl: 'Task control',
      proxy: 'Proxy', proxyTest: 'Test proxy', concurrency: 'Concurrency', limit: 'Limit', hideChrome: 'Hide Chrome', start: 'Start tasks', stop: 'Stop tasks', autoHealth: 'Auto health check', interval: 'Interval (minutes)', save: 'Save settings', readyEmails: 'Ready emails', terminal: 'Live board', waiting: 'Waiting for tasks...',
      sourcePool: 'Source pool', importTitle: 'Import credentials', importBtn: 'Import emails', clear: 'Clear', email: 'Email', tempEmail: 'Temp email', status: 'Status', action: 'Action', runHistory: 'Run history', taskTitle: 'Task history', id: 'ID', last: 'Last progress / error', steps: 'Steps', vault: 'Credential vault', accountTitle: 'Account vault'
    },
    ja: {
      brand: 'OrgRegister', brandSmall: 'account operations', register: '登録', emails: 'メールプール', tasks: 'タスク履歴', accounts: 'アカウント保管庫', settings: '設定',
      idle: '待機中', running: '実行中', total: 'メール総数', ready: '処理可能', success: '成功アカウント', failed: '失敗タスク', operations: 'Operations', lead: 'キューを進めましょう。', taskControl: 'タスク管理',
      proxy: 'プロキシ', proxyTest: 'プロキシをテスト', concurrency: '同時実行数', limit: '件数', hideChrome: 'Chromeを非表示', start: 'タスク開始', stop: 'タスク停止', autoHealth: '自動ヘルスチェック', interval: '間隔（分）', save: '設定を保存', readyEmails: '登録可能なメール', terminal: 'ライブボード', waiting: 'タスクの開始を待っています...',
      sourcePool: 'Source pool', importTitle: '認証情報をインポート', importBtn: 'メールをインポート', clear: 'クリア', email: 'メール', tempEmail: '一時メール', status: '状態', action: '操作', runHistory: 'Run history', taskTitle: 'タスク履歴', id: 'ID', last: '最新の進捗 / エラー', steps: '手順', vault: 'Credential vault', accountTitle: 'アカウント保管庫', preferences: '環境設定', language: '言語', languageNote: 'ダッシュボードの表示言語を選択してください。変更はすぐに反映されます。'
    },
    sv: {
      brand: 'OrgRegister', brandSmall: 'account operations', register: 'Registrering', emails: 'E-postpool', tasks: 'Aktivitetshistorik', accounts: 'Kontolager', settings: 'Inställningar',
      idle: 'Inaktiv', running: 'Körs', total: 'Totalt antal e-post', ready: 'Redo', success: 'Lyckade konton', failed: 'Misslyckade uppgifter', operations: 'Operations', lead: 'Håll kön i rörelse.', taskControl: 'Uppgiftskontroll',
      proxy: 'Proxy', proxyTest: 'Testa proxy', concurrency: 'Samtidighet', limit: 'Antal', hideChrome: 'Dölj Chrome', start: 'Starta uppgifter', stop: 'Stoppa uppgifter', autoHealth: 'Automatisk hälsokontroll', interval: 'Intervall (minuter)', save: 'Spara inställningar', readyEmails: 'E-post redo för registrering', terminal: 'Livepanel', waiting: 'Väntar på att uppgifter ska starta...',
      sourcePool: 'Source pool', importTitle: 'Importera uppgifter', importBtn: 'Importera e-post', clear: 'Rensa', email: 'E-post', tempEmail: 'Tillfällig e-post', status: 'Status', action: 'Åtgärd', runHistory: 'Run history', taskTitle: 'Aktivitetshistorik', id: 'ID', last: 'Senaste framsteg / fel', steps: 'Steg', vault: 'Credential vault', accountTitle: 'Kontolager', preferences: 'Inställningar', language: 'Språk', languageNote: 'Välj språk för panelen. Ändringen börjar gälla direkt.'
    },
    zhTW: {
      brand: 'OrgRegister', brandSmall: 'account operations', register: '註冊機', emails: '郵箱池', tasks: '任務記錄', accounts: '成功帳號', settings: '設定',
      idle: '閒置', running: '執行中', total: '郵箱總數', ready: '可處理', success: '成功帳號', failed: '失敗任務', operations: 'Operations', lead: '讓佇列持續前進。', taskControl: '任務控制',
      proxy: '代理', proxyTest: '測試代理', concurrency: '並發', limit: '數量', hideChrome: '隱藏 Chrome', start: '開始任務', stop: '結束任務', autoHealth: '自動驗活', interval: '間隔（分鐘）', save: '儲存設定', readyEmails: '可註冊郵箱', terminal: '即時看板', waiting: '等待任務啟動...',
      sourcePool: 'Source pool', importTitle: '匯入憑證', importBtn: '匯入郵箱', clear: '清空', email: '郵箱', tempEmail: '臨時郵箱', status: '狀態', action: '操作', runHistory: 'Run history', taskTitle: '任務記錄', id: 'ID', last: '最後進度 / 錯誤', steps: '詳細步驟', vault: 'Credential vault', accountTitle: '成功帳號', preferences: '應用偏好', language: '語言', languageNote: '選擇面板顯示語言。切換後立即生效。'
    }
  };
  let locale = 'zh-CN';

  function language() { return ({'en-US': translations.en, 'ja-JP': translations.ja, 'sv-SE': translations.sv, 'zh-TW': translations.zhTW}[locale] || translations.zh); }
  function isEnglish() { return locale === 'en-US'; }
  function languageCode() { return ({'en-US':'en', 'ja-JP':'ja', 'sv-SE':'sv', 'zh-TW':'zh-TW'}[locale] || 'zh-CN'); }
  function setText(selector, key) { const el = document.querySelector(selector); if (el) el.textContent = language()[key]; }
  function applyLanguage() {
    const t = language();
    document.documentElement.lang = languageCode();
    document.querySelectorAll('[data-zh][data-en]').forEach((el) => { el.textContent = isEnglish() ? el.dataset.en : el.dataset.zh; });
    const settingEyebrow = document.querySelector('#view-settings .eyebrow');
    const settingLead = document.querySelector('#view-settings .lead');
    const settingHeading = document.querySelector('#view-settings .settings-panel h2');
    const settingNote = document.querySelector('#view-settings .settings-panel .note');
    if (settingEyebrow) settingEyebrow.textContent = t.preferences || (isEnglish() ? 'Preferences' : '应用偏好');
    if (settingLead) settingLead.textContent = t.settings;
    if (settingHeading) settingHeading.textContent = t.language || (isEnglish() ? 'Language' : '语言');
    if (settingNote) settingNote.textContent = t.languageNote || (isEnglish() ? 'Choose the dashboard language. Changes apply immediately.' : '选择面板显示语言。切换后立即生效。');
    const buttons = document.querySelectorAll('.nav button[data-view]');
    ['register', 'emails', 'tasks', 'accounts'].forEach((view, i) => { if (buttons[i]) buttons[i].textContent = t[view]; });
    settingsButton.textContent = t.settings;
    setText('.top-right #state', $('state')?.textContent === '运行中' || $('state')?.textContent === 'Running' ? 'running' : 'idle');
    const stats = document.querySelectorAll('.stat span'); ['total', 'ready', 'success', 'failed'].forEach((key, i) => { if (stats[i]) stats[i].textContent = t[key]; });
    setText('#view-register .eyebrow', 'operations'); setText('#view-register .lead', 'lead'); setText('#view-register .surface.cream h2', 'taskControl');
    const labels = document.querySelectorAll('#view-register .toolbar .field');
    [['proxy', 0], ['concurrency', 1], ['limit', 2], ['hideChrome', 3], ['autoHealth', 4], ['interval', 5]].forEach(([key, i]) => { if (labels[i]) { const span = labels[i].querySelector('span'); if (span) span.textContent = t[key]; else labels[i].childNodes[0].textContent = t[key]; } });
    if ($('proxyTest')) $('proxyTest').textContent = t.proxyTest; if ($('start')) $('start').textContent = t.start; if ($('stop')) $('stop').textContent = t.stop; if ($('saveSettings')) $('saveSettings').textContent = t.save;
    if ($('importText')) $('importText').placeholder = isEnglish() ? 'Microsoft email----password----UUID----MSA token----temporary email----temporary email password' : '微软邮箱----密码----UUID----MSA_Token----临时邮箱----临时邮箱密码';
    setText('#view-register .surface:nth-of-type(2) h2', 'readyEmails'); setText('#view-register .dark h2', 'terminal');
    const emailHead = document.querySelectorAll('#view-emails th'); ['email', 'tempEmail', 'status', 'action'].forEach((key, i) => { if (emailHead[i]) emailHead[i].textContent = t[key]; });
    setText('#view-emails .eyebrow', 'sourcePool'); setText('#view-emails .surface h2', 'importTitle'); if ($('import')) $('import').textContent = t.importBtn; if ($('clear')) $('clear').textContent = t.clear;
    const taskHead = document.querySelectorAll('#view-tasks th'); ['id', 'email', 'status', 'last', 'steps'].forEach((key, i) => { if (taskHead[i]) taskHead[i].textContent = t[key]; }); setText('#view-tasks .eyebrow', 'runHistory');
    setText('#view-emails .lead', 'emails'); setText('#view-tasks .lead', 'taskTitle');
    setText('#view-accounts .eyebrow', 'vault'); setText('#view-accounts .lead', 'accountTitle');
    document.querySelectorAll('.language-options button').forEach((btn) => btn.classList.toggle('selected', btn.dataset.locale === locale));
    const about = ABOUT_INFO[{ 'en-US':'en', 'ja-JP':'ja', 'sv-SE':'sv', 'zh-TW':'zhTW' }[locale] || 'zh'];
    if ($('about-title')) $('about-title').textContent = about.title;
    if ($('about-content')) $('about-content').textContent = about.content;
    settingsButton.classList.toggle('active', !section.classList.contains('hidden'));
    const activeView = ['register', 'emails', 'tasks', 'accounts', 'settings'].find((view) => !$(`view-${view}`)?.classList.contains('hidden')) || 'register';
    if ($('title')) $('title').textContent = t[activeView] || t.register;
    translateDynamic();
    window.badge = (status) => {
      const labels = locale === 'en-US' ? {unused:'Ready', running:'Running', waiting_captcha:'Waiting for captcha', done:'Registered', registered:'Logged in', banned:'Banned', failed:'Failed', pending:'Queued'} : {unused:'待处理', running:'运行中', waiting_captcha:'等待验证码', done:'新注册成功', registered:'已注册', banned:'已封禁', failed:'失败', pending:'排队中'};
      return `<span class="badge ${esc(status)}">${esc(labels[status] || status)}</span>`;
    };
    window.health = (status) => {
      const labels = locale === 'en-US' ? {alive:'Alive', dead:'Expired', unknown:'Not checked'} : {alive:'存活', dead:'失效', unknown:'未检测'};
      return `<span class="badge ${esc(status || 'unknown')}">${esc(labels[status] || status || labels.unknown)}</span>`;
    };
    document.title = 'OrgRegister';
  }

  function showSettings() {
    ['register', 'emails', 'tasks', 'accounts', 'settings'].forEach((view) => $(`view-${view}`)?.classList.toggle('hidden', view !== 'settings'));
    document.querySelectorAll('.nav button').forEach((btn) => btn.classList.toggle('active', btn.dataset.view === 'settings'));
    $('title').textContent = language().settings;
    applyLanguage();
  }
  settingsButton.addEventListener('click', showSettings);
  document.querySelectorAll('.nav button[data-view]').forEach((button) => {
    button.addEventListener('click', () => {
      section.classList.add('hidden');
      applyLanguage();
    });
  });
  section.addEventListener('click', async (event) => {
    const btn = event.target.closest('[data-locale]'); if (!btn) return;
    locale = btn.dataset.locale;
    const settings = await (await fetch('/api/settings')).json();
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...settings, locale}) });
    applyLanguage();
    if (window.loadEmails) await window.loadEmails();
    if (window.loadTasks) await window.loadTasks();
    if (window.loadAccounts) await window.loadAccounts();
    translateDynamic();
  });
  function translateDynamic() {
    const en = locale === 'en-US';
    const statusLabels = locale === 'en-US' ? {unused:'Ready', running:'Running', waiting_captcha:'Waiting for captcha', done:'Registered', registered:'Logged in', banned:'Banned', failed:'Failed', pending:'Queued', alive:'Alive', dead:'Expired', unknown:'Not checked'} : locale === 'ja-JP' ? {unused:'待機', running:'実行中', waiting_captcha:'認証待ち', done:'登録成功', registered:'ログイン済み', banned:'禁止', failed:'失敗', pending:'キュー', alive:'有効', dead:'無効', unknown:'未確認'} : locale === 'sv-SE' ? {unused:'Redo', running:'Körs', waiting_captcha:'Väntar på captcha', done:'Registrerad', registered:'Inloggad', banned:'Bannlyst', failed:'Misslyckad', pending:'Köad', alive:'Aktiv', dead:'Utgången', unknown:'Ej kontrollerad'} : locale === 'zh-TW' ? {unused:'待處理', running:'執行中', waiting_captcha:'等待驗證碼', done:'註冊成功', registered:'已登入', banned:'已封鎖', failed:'失敗', pending:'排隊中', alive:'存活', dead:'失效', unknown:'未檢測'} : {unused:'待处理', running:'运行中', waiting_captcha:'等待验证码', done:'新注册成功', registered:'已注册', banned:'已封禁', failed:'失败', pending:'排队中', alive:'存活', dead:'失效', unknown:'未检测'};
    document.querySelectorAll('.badge').forEach((el) => {
      const status = [...el.classList].find((name) => statusLabels[name]);
      if (status && el.textContent !== statusLabels[status]) el.textContent = statusLabels[status];
    });
    const labels = en ? {'删除':'Delete', '查看步骤':'View steps', '复制 Session':'Copy session', '复制 Access':'Copy access', '复制 JSON':'Copy JSON', '手动验活':'Check health', '重新获取':'Re-authenticate', '暂无邮箱':'No emails', '暂无可处理邮箱':'No ready emails', '暂无任务':'No tasks', '暂无成功账号':'No accounts'} : {'Delete':'删除', 'View steps':'查看步骤', 'Copy session':'复制 Session', 'Copy access':'复制 Access', 'Copy JSON':'复制 JSON', 'Check health':'手动验活', 'Re-authenticate':'重新获取', 'No emails':'暂无邮箱', 'No ready emails':'暂无可处理邮箱', 'No tasks':'暂无任务', 'No accounts':'暂无成功账号'};
    // Translate only source-language labels; otherwise the observer would
    // toggle English and Chinese text forever after each DOM mutation.
    const sourceLabels = new Set(en ? Object.keys(labels).filter((key) => /[^\x00-\x7F]/.test(key)) : Object.keys(labels).filter((key) => /^[\x00-\x7F]*$/.test(key)));
    document.querySelectorAll('button, .empty').forEach((el) => { const value = el.textContent.trim(); if (sourceLabels.has(value) && labels[value] && value !== labels[value]) el.textContent = labels[value]; });
  }
  fetch('/api/settings').then((r) => r.json()).then(async (settings) => { locale = settings.locale || 'zh-CN'; applyLanguage(); if (window.loadEmails) await window.loadEmails(); if (window.loadTasks) await window.loadTasks(); if (window.loadAccounts) await window.loadAccounts(); translateDynamic(); }).catch(() => applyLanguage());
})();
