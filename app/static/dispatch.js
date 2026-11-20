import {board, explanation, grid, localTime, text, waveOf, waves} from './board.js';

const el = id => document.getElementById(id);
const parts = {orders:'团餐订单',substitutions:'套餐替代',windows:'到站窗口',capacity:'装车容量',allocation:'备用递补',reconcile:'份数对账',archive:'交接签单'};
const desk = {result:JSON.parse(el('initial').textContent),wave:'all',order:'团-008',section:'allocation',receipt:null,pending:false};
const stockStatus = {usable:'可用',expired:'过期',quarantined:'隔离'};

function feedback(message, error=false) {el('notice').textContent=message;el('notice').toggleAttribute('data-error',error);}
function currentOrder() {
  const rows=desk.result.allocation.rows.filter(row=>desk.wave==='all'||waveOf(row)===desk.wave);
  return rows.find(row=>row.order===desk.order) ?? rows[0];
}
function render() {
  const {result,section} = desk;
  const ledger=result.reconcile.totals, spare=ledger.spare;
  const order=currentOrder(); desk.order=order?.order;
  el('batch-name').textContent=result.batch;
  el('metrics').innerHTML=[['应送',ledger.requested,''],['实发',ledger.shipped,'ship'],['缺配',ledger.short,'short'],['争议',ledger.disputed,'dispute'],['备用实发',spare.used,'']].map(([label,value,cls])=>`<div class="tally ${cls}"><span>${label}</span><strong>${value} <small>份</small></strong></div>`).join('');
  el('wave-filter').replaceChildren(new Option('全部波次','all'),...waves(result).map(group=>new Option(group.wave,group.wave)));
  el('wave-filter').value=desk.wave;
  const positions=new Map([...el('wave-board').querySelectorAll('.wave')].map(panel=>[panel.getAttribute('aria-label'),panel.querySelector('.wave-body').scrollTop]));
  el('wave-board').innerHTML=board(result,desk.wave,desk.order);
  el('wave-board').querySelectorAll('.wave').forEach(panel=>{panel.querySelector('.wave-body').scrollTop=positions.get(panel.getAttribute('aria-label'))??0;});
  el('detail-title').textContent=parts[section]; el('active-order').textContent=order && section!=='archive' ? `${order.order} · ${order.station ?? '待核'}` : '';
  el('detail').innerHTML=inspect(order);
  el('stock').innerHTML=`<div class="spare-math"><span>申报 <b>${spare.declared}</b></span><span>实发 <b>${spare.used}</b></span><span>结余 <b>${spare.left}</b></span><span>过期 <b>${spare.expired}</b></span><span>隔离 <b>${spare.quarantined}</b></span></div>`+
    grid(['批号','餐品','已发 / 申报','状态'],result.allocation.stock.filter(row=>row.kind==='spare').map(row=>[row.lot,row.meal??row.raw.meal,`${row.loaded} / ${row.qty}`,stockStatus[row.status]]));
  el('balance').textContent=result.reconcile.status==='MATCHED'?'送餐与备用餐已对平':'份数待复核';
  el('version').textContent=`${localTime(result.at)} · 上海时间 · ${result.ruleset}`;
  document.querySelectorAll('nav a').forEach(link=>{if(link.hash===`#${section}`)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
}
function inspect(order) {
  const {result,section}=desk;
  if(section==='archive')return signature();
  if(section==='reconcile') {
    const totals=result.reconcile.totals;
    return `<div class="slip"><strong>${totals.requested} = ${totals.shipped} + ${totals.short} + ${totals.disputed}</strong><span>送餐差额 ${totals.difference} 份 · 备用差额 ${totals.spare.difference} 份</span></div>`+
      grid(['波次','应送','实发','缺配','争议'],waves(result).map(row=>[row.wave,row.qty,row.shipped,row.short,row.disputed]));
  }
  if(section==='capacity')return grid(['车辆','波次','装载 / 容量','余位','车次行'],result.allocation.vehicles.filter(row=>desk.wave==='all'||row.wave===desk.wave).map(row=>[row.truck,row.wave,`${row.loaded} / ${row.capacity} 份`,row.remaining,row.line]));
  if(section==='substitutions')return grid(['原餐','批准的备用餐','判定','规则行'],[
    ...result.substitutions.rows.map(row=>[row.requested,row.spare,'可替代',row.line]),
    ...result.substitutions.issues.map(row=>[row.raw?.requested,row.raw?.spare,row.code,row.line])]);
  if(section==='windows')return grid(['波次','站点','开始','截止','窗口行'],result.windows.rows.filter(row=>desk.wave==='all'||row.wave===desk.wave).map(row=>[row.wave,row.station,localTime(row.start),localTime(row.end),row.line]));
  if(section==='orders')return grid(['订单','站点','版本','应送','原始行','状态'],result.orders.rows.filter(row=>desk.wave==='all'||waveOf(row)===desk.wave).map(row=>[row.order,row.station,row.revision,row.qty,row.revision_lines.join('、'),({active:'有效',cancelled:'已撤销',conflict:'争议'})[row.state]]));
  if(!order)return '<p class="empty">选择订单查看发餐明细。</p>';
  return `<div class="slip"><strong>${text(order.meal)}</strong><span>应送 ${order.qty} 份</span><span>实发 ${order.shipped} 份</span><span>优先序 ${text(order.rank)}</span><span class="status-word">${explanation(order.code)}</span></div>`+
    grid(['车辆','到站','批号','实发餐品','份数','批准行'],order.loads.map(load=>[load.truck,localTime(load.arrival),load.lot,load.meal,load.qty,load.substitution_line??'原餐']));
}
function signature() {
  const run=desk.receipt;
  if(!run)return '<p class="empty">计算发餐后生成交接签单。</p><button data-history>查看交接历史</button><div id="history"></div>';
  return `<div class="slip"><strong>${text(run.manifest.batch)}</strong><span>${text(run.manifest.generated_at)}</span></div><p class="digest">${text(run.manifest.digest)}</p>
  <div class="receipt"><button data-rerun>重跑发餐</button><a class="download" href="/api/runs/${text(run.id)}/export">下载交接证据</a><button data-history>查看交接历史</button></div>
  ${run.signature?`<p>已交接 · ${text(run.signature.reviewer)}</p>`:'<form id="sign" class="receipt"><label>签单人 <input name="reviewer" maxlength="100" required></label><button>确认交接</button></form>'}<div id="history"></div>`;
}
async function api(path, body) {
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw new Error(result.message||'发餐请求失败，请重试。');return result;
}
async function run(task) {
  if(desk.pending)return;desk.pending=true;feedback('调度中…');
  try{await task();}catch(error){feedback(error.message,true);}finally{desk.pending=false;}
}
function useReceipt(receipt){desk.receipt=receipt;desk.result=receipt.result;if(!desk.result.reconcile.rows.some(row=>row.wave===desk.wave))desk.wave='all';render();}
function setSection(){const next=location.hash.slice(1);desk.section=parts[next]?next:'allocation';render();}
el('operate').addEventListener('submit',event=>{event.preventDefault();run(async()=>{
  const receipt=desk.receipt?await api(`/api/runs/${desk.receipt.id}/rerun`,{}):await api('/api/runs',{sample:el('sample').value});
  useReceipt(receipt);feedback(receipt.reused?'重跑调度一致':'发餐已归档');
});});
el('sample').addEventListener('change',event=>{location.href=`/?sample=${event.target.value}${location.hash}`;});
el('wave-filter').addEventListener('change',event=>{desk.wave=event.target.value;render();});
el('wave-board').addEventListener('click',event=>{const item=event.target.closest('[data-order]');if(!item)return;desk.order=item.dataset.order;location.hash='allocation';desk.section='allocation';render();el('wave-board').querySelector('[aria-pressed=true]')?.focus({preventScroll:true});});
el('pick-file').addEventListener('click',()=>el('upload').click());
el('upload').addEventListener('change',event=>{const [file]=event.target.files;if(!file)return;run(async()=>{
  let source;try{source=JSON.parse(await file.text());}catch{throw new Error('排班格式错误，请选择 JSON 文件。');}
  useReceipt(await api('/api/runs',{source}));feedback('排班已归档');
}).finally(()=>{event.target.value='';});});
el('detail').addEventListener('click',event=>{const button=event.target.closest('[data-rerun],[data-history],[data-id]');if(!button)return;run(async()=>{
  if(button.hasAttribute('data-rerun')){useReceipt(await api(`/api/runs/${desk.receipt.id}/rerun`,{}));feedback('重跑调度一致');}
  if(button.hasAttribute('data-history')){const {runs}=await api('/api/runs');el('history').replaceChildren(...runs.map(entry=>{const action=document.createElement('button');action.dataset.id=entry.id;action.textContent=entry.batch;return action;}));feedback(runs.length?`${runs.length} 笔签单`:'暂无签单');}
  if(button.dataset.id){useReceipt(await api(`/api/runs/${button.dataset.id}`));feedback('已载入交接签单');}
});});
el('detail').addEventListener('submit',event=>{if(event.target.id!=='sign')return;event.preventDefault();run(async()=>{
  desk.receipt.signature=await api(`/api/runs/${desk.receipt.id}/sign`,{reviewer:new FormData(event.target).get('reviewer'),digest:desk.receipt.manifest.digest});render();feedback('交接签单完成');
});});
addEventListener('hashchange',setSection);setSection();
