import {board, explanation, grid, localTime, text, waveOf, waves} from './board.js';

const el = id => document.getElementById(id);
const parts = {orders:'团餐订单',substitutions:'套餐替代',windows:'到站窗口',capacity:'装车容量',allocation:'备用递补',reconcile:'份数对账',rescue:'故障救援',archive:'交接签单'};
const desk = {result:JSON.parse(el('initial').textContent),wave:'all',order:'团-008',section:'allocation',receipt:null,pending:false,rescue:null};
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
  if(section==='rescue')return rescuePanel();
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
function rescuePanel() {
  if(!desk.receipt)return '<p class="empty">先在「交接签单」计算发餐并归档，才能对故障车发起救援。</p>';
  const failed = [...new Set(desk.result.allocation.vehicles.filter(v=>v.loaded>0).map(v=>v.truck))];
  const record = desk.rescue;
  const head = `<form id="rescue-form" class="receipt"><label>故障车
      <select name="failed_truck" required>${failed.map(t=>`<option${record&&record.failed_truck===t?' selected':''}>${text(t)}</option>`).join('')}</select></label>
    <label>备用车 JSON（可留空，仅用邻近车次余位）<input name="backup" placeholder='{"truck":"备-甲",...}' style="max-width:240px"></label>
    <button type="button" data-rescue-preview>预览救援</button><button class="accent" type="button" data-rescue-publish>发布救援记录</button></form>`;
  if(!record)return head+'<p class="empty">选择故障车后先预览，确认对账相符再发布。</p>';
  const checkLabels={orders_balanced:'订单份数对平',lots_conserved:'批号只搬运不耗餐',capacity_ok:'接运车未超载',windows_ok:'到站在交接窗内',freshness_ok:'批号到站仍有效',fleet_total_conserved:'车队总数守恒',fully_covered:'故障餐全部接走'};
  const checks=Object.entries(record.checks).map(([k,ok])=>`<span class="check ${ok?'ok':'no'}">${text(checkLabels[k])} ${ok?'✓':'✗'}</span>`).join('');
  const orderRows=record.orders.map(r=>[r.order,r.station,r.locked?'锁定':'普通',r.affected_qty,r.rescued_qty,r.undelivered_qty,r.code?explanation(r.code):'已接运']);
  const moveRows=record.moves.map(m=>[m.order,m.lot,m.meal,m.kind==='spare'?'备用':'常规',m.qty,m.from_truck+' → '+m.to_truck,localTime(m.arrival),m.substitution_line??'原餐']);
  const truckRows=record.vehicles.map(v=>[v.truck,({failed:'故障车',rescue:'接运车',backup:'备用车',idle:'未参与'})[v.role],v.original_loaded,v.rescued_loaded,v.final_loaded,v.remaining_capacity,v.undelivered]);
  return head+
    `<div class="slip"><strong>故障车 ${text(record.failed_truck)}</strong><span>状态 ${record.status==='MATCHED'?'对账相符':'待复核'}</span><span>记录号 ${text(record.id.slice(0,12))}…</span></div>
    <div class="rescue-checks">${checks}</div>
    <h4 class="rescue-title">受影响订单改派</h4>${grid(['订单','站点','类型','原车份数','已接运','未送达','判定'],orderRows)}
    <h4 class="rescue-title">救援装载批号</h4>${grid(['订单','批号','餐品','餐类','份数','原车 → 接运车','到站','批准行'],moveRows)}
    <h4 class="rescue-title">车辆份数与未送达量</h4>${grid(['车辆','角色','原车装载','救援接入','最终装载','余位','未送达'],truckRows)}`;
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
function useReceipt(receipt){desk.receipt=receipt;desk.result=receipt.result;desk.rescue=null;if(!desk.result.reconcile.rows.some(row=>row.wave===desk.wave))desk.wave='all';render();}
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
el('detail').addEventListener('click',event=>{const button=event.target.closest('[data-rerun],[data-history],[data-id],[data-rescue-preview],[data-rescue-publish]');if(!button)return;run(async()=>{
  if(button.hasAttribute('data-rescue-preview')||button.hasAttribute('data-rescue-publish')){
    const form=el('rescue-form');const formData=new FormData(form);
    let backup=null;const raw=String(formData.get('backup')??'').trim();
    if(raw){try{backup=JSON.parse(raw);}catch{throw new Error('备用车 JSON 格式错误。');}}
    const payload={failed_truck:formData.get('failed_truck'),backup};
    const path=`/api/runs/${desk.receipt.id}/rescues${button.hasAttribute('data-rescue-preview')?'/preview':''}`;
    const response=await api(path,payload);
    desk.rescue=button.hasAttribute('data-rescue-preview')?response:response;
    if(button.hasAttribute('data-rescue-publish'))feedback(response.reused?'救援重试复用原记录，未重复占位':'救援记录已发布');
    else feedback(response.status==='MATCHED'?'预览对账相符，可发布':'预览存在未送达或待复核项');
    render();return;
  }
  if(button.hasAttribute('data-rerun')){useReceipt(await api(`/api/runs/${desk.receipt.id}/rerun`,{}));feedback('重跑调度一致');}
  if(button.hasAttribute('data-history')){const {runs}=await api('/api/runs');el('history').replaceChildren(...runs.map(entry=>{const action=document.createElement('button');action.dataset.id=entry.id;action.textContent=entry.batch;return action;}));feedback(runs.length?`${runs.length} 笔签单`:'暂无签单');}
  if(button.dataset.id){useReceipt(await api(`/api/runs/${button.dataset.id}`));feedback('已载入交接签单');}
});});
el('detail').addEventListener('submit',event=>{if(event.target.id!=='sign')return;event.preventDefault();run(async()=>{
  desk.receipt.signature=await api(`/api/runs/${desk.receipt.id}/sign`,{reviewer:new FormData(event.target).get('reviewer'),digest:desk.receipt.manifest.digest});render();feedback('交接签单完成');
});});
addEventListener('hashchange',setSection);setSection();
