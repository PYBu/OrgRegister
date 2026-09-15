(() => {
  const button = document.getElementById('proxyTest');
  if (!button) return;

  const esc = (value) => String(value ?? '-').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const style = document.createElement('style');
  style.textContent = `
    .proxy-modal-backdrop{position:fixed;inset:0;background:rgba(20,20,19,.42);display:flex;align-items:center;justify-content:center;z-index:20;padding:20px}
    .proxy-modal{width:min(420px,100%);background:#fff;border:1px solid #e6dfd8;border-radius:8px;box-shadow:0 18px 60px rgba(20,20,19,.22);padding:24px;color:#3d3d3a}
    .proxy-modal h3{margin:0 0 18px;color:#141413;font:500 22px Georgia,serif}
    .proxy-modal dl{display:grid;grid-template-columns:90px 1fr;gap:10px 14px;margin:0 0 22px}
    .proxy-modal dt{color:#6c6a64}.proxy-modal dd{margin:0;color:#141413;word-break:break-word}
    .proxy-modal-actions{display:flex;justify-content:flex-end}.proxy-modal button{border:0;border-radius:6px;padding:9px 16px;background:#cc785c;color:#fff;cursor:pointer;font-weight:600}
  `;
  document.head.appendChild(style);

  function show(result) {
    document.querySelector('.proxy-modal-backdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.className = 'proxy-modal-backdrop';
    const ok = !!result.ok;
    const lang = document.documentElement.lang;
    const text = lang === 'en' ? {ok:'Proxy available', bad:'Proxy unavailable', ip:'Exit IP', country:'Country', region:'Region', http:'HTTP', org:'Provider', timezone:'Timezone', error:'Error', geo:'Location', unavailable:'Location service unavailable', missing:'Not available', close:'Close', aria:'Proxy test result'} : lang === 'ja' ? {ok:'プロキシは利用可能', bad:'プロキシは利用できません', ip:'出口IP', country:'国', region:'地域', http:'HTTP', org:'プロバイダー', timezone:'タイムゾーン', error:'エラー', geo:'位置情報', unavailable:'位置情報サービスを利用できません', missing:'取得できません', close:'閉じる', aria:'プロキシテスト結果'} : lang === 'sv' ? {ok:'Proxy tillgänglig', bad:'Proxy otillgänglig', ip:'Extern IP', country:'Land', region:'Region', http:'HTTP', org:'Leverantör', timezone:'Tidszon', error:'Fel', geo:'Plats', unavailable:'Platstjänsten är inte tillgänglig', missing:'Ej tillgänglig', close:'Stäng', aria:'Proxytestresultat'} : lang === 'zh-TW' ? {ok:'代理可用', bad:'代理不可用', ip:'出口 IP', country:'國家', region:'地區', http:'HTTP', org:'營運商', timezone:'時區', error:'錯誤', geo:'定位', unavailable:'定位服務暫不可用', missing:'未取得', close:'關閉', aria:'代理測試結果'} : {ok:'代理可用', bad:'代理不可用', ip:'出口 IP', country:'国家', region:'地区', http:'HTTP', org:'运营商', timezone:'时区', error:'错误', geo:'定位', unavailable:'定位服务暂不可用', missing:'未获取', close:'关闭', aria:'代理测试结果'};
    backdrop.innerHTML = `<section class="proxy-modal" role="dialog" aria-modal="true" aria-label="${text.aria}">
      <h3>${ok ? text.ok : text.bad}</h3>
      <dl>
        <dt>${text.ip}</dt><dd>${esc(result.ip || text.missing)}</dd>
        <dt>${text.country}</dt><dd>${esc(result.country || text.missing)}</dd>
        <dt>${text.region}</dt><dd>${esc([result.region, result.city].filter(Boolean).join(' / ') || text.missing)}</dd>
        <dt>${text.http}</dt><dd>${esc(result.status || '-')}</dd>
        ${result.org ? `<dt>${text.org}</dt><dd>${esc(result.org)}</dd>` : ''}
        ${result.timezone ? `<dt>${text.timezone}</dt><dd>${esc(result.timezone)}</dd>` : ''}
        ${result.error ? `<dt>${text.error}</dt><dd>${esc(result.error)}</dd>` : ''}
        ${result.geo_error ? `<dt>${text.geo}</dt><dd>${text.unavailable}</dd>` : ''}
      </dl>
      <div class="proxy-modal-actions"><button type="button">${text.close}</button></div>
    </section>`;
    const close = () => backdrop.remove();
    backdrop.querySelector('button').addEventListener('click', close);
    backdrop.addEventListener('click', (event) => { if (event.target === backdrop) close(); });
    document.addEventListener('keydown', function onKey(event) {
      if (event.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); }
    });
    document.body.appendChild(backdrop);
  }

  button.onclick = async () => {
    button.disabled = true;
    const oldText = button.textContent;
    button.textContent = '测试中';
    try {
      const response = await fetch('/api/proxy/test', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({proxy: document.getElementById('proxy')?.value || ''})
      });
      show(await response.json());
    } catch (error) {
      show({ok: false, error: `${error.name}: ${error.message}`});
    } finally {
      button.disabled = false;
      button.textContent = oldText;
    }
  };
})();
