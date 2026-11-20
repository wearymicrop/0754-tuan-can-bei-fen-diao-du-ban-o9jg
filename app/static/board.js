export const text = value => String(value ?? '—').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const clock = new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
export const localTime = value => value === undefined || value === null ? '—' : clock.format(new Date(typeof value==='number'?value*1000:value));
const codeLabels = {TRUCK_FULL:'满载缺配',NO_VALID_STOCK:'有效库存不足',NO_ON_TIME_TRUCK:'无准点车辆',ORDER_CONFLICT:'改签争议',WINDOW_MISSING:'缺到站窗口',WINDOW_CONFLICT:'到站窗口互斥'};
export const explanation = code => codeLabels[code] ?? '已排发';
export function grid(headers,rows) {
  if (!rows.length) return '<p class="empty">当前没有对应记录。</p>';
  return `<div class="table-wrap"><table><thead><tr>${headers.map(name=>`<th>${text(name)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(value=>`<td>${text(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
export const waveOf = row => typeof row.wave === 'string' && row.wave ? row.wave : '待确认';
export function waves(result) {
  const start = name => Math.min(...result.windows.rows.filter(row=>row.wave===name).map(row=>row.start));
  return [...result.reconcile.rows].sort((a,b)=>start(a.wave)-start(b.wave)||a.wave.localeCompare(b.wave,'zh'));
}
export function board(result, visible, selected) {
  const byWave = waves(result).filter(row=>visible==='all'||row.wave===visible);
  if (!byWave.length) return '<p class="empty">选择一个有订单的波次。</p>';
  return byWave.map(wave=>{
    const trips = result.allocation.vehicles.filter(row=>row.wave===wave.wave);
    const orders = result.allocation.rows.filter(row=>waveOf(row)===wave.wave).sort((a,b)=>a.order.localeCompare(b.order,'zh'));
    return `<article class="wave" aria-label="${text(wave.wave)}"><div class="wave-head"><h3>${text(wave.wave)}</h3><span>${wave.orders} 单 · ${trips.length} 车</span></div>
    <p class="wave-balance"><strong>${wave.shipped} / ${wave.qty} 份</strong> · 缺配 ${wave.short} · 争议 ${wave.disputed}</p><div class="wave-body">${orders.map(order=>{
      const active = order.order===selected, status=order.disputed?'dispute':order.short?'short':'ship';
      return `<button type="button" class="order-card" data-order="${text(order.order)}" aria-pressed="${active}"><b>${text(order.order)} · ${text(order.station)}</b>
        <small>${text(order.meal)} ${order.locked===true?'<span class="lock">锁定</span>':''}${order.code?' · '+explanation(order.code):''}</small><span class="count ${status}">${order.shipped}/${order.qty}</span></button>`;
    }).join('')}</div></article>`;
  }).join('');
}
