const API='http://localhost:7000';
let allLeads=[],reviewLeads=[],rejectedLeads=[],followupLeads=[];
let activeTab='ALL',currentPage=1,selected=new Set(),lastChecked=null,activeDetailId=null;
const PAGE_SIZE=20,TABS=['ALL','HOT','WARM','COLD','REVIEW','REJECTED'];
const STATUSES=['New','Contacted','Replied','Meeting','Closed','Dead'];
const PAIN_LABELS={negative_reviews:'Bad Reviews',no_maps_listing:'No Maps',outdated_website:'Old Website',not_mobile_friendly:'Not Mobile',inactive_social:'Inactive Social',hiring_manual_roles:'Hiring Manual'};
const PAIN_KEYS=Object.keys(PAIN_LABELS);
const ST_CLS={New:'st-new',Contacted:'st-contacted',Replied:'st-replied',Meeting:'st-meeting',Closed:'st-closed',Dead:'st-dead'};

document.addEventListener('DOMContentLoaded',()=>{
  initDarkMode();
  renderTabs();
  fetchAll();
  setInterval(fetchReviewCount,60000);
  ['fSearch','fCity','fSource','fSort','fEmail','fPhone'].forEach(id=>{
    document.getElementById(id)?.addEventListener(id==='fSearch'?'input':'change',()=>{currentPage=1;render();});
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail();});
});

function initDarkMode(){
  const dm=localStorage.getItem('cfDarkMode')!=='light';
  if(!dm)document.documentElement.setAttribute('data-theme','light');
  const btn=document.getElementById('dmToggle');
  if(btn){
    btn.textContent=dm?'Dark':'Light';
    btn.onclick=()=>{
      const isL=document.documentElement.getAttribute('data-theme')==='light';
      document.documentElement.setAttribute('data-theme',isL?'':'light');
      localStorage.setItem('cfDarkMode',isL?'dark':'light');
      btn.textContent=isL?'Dark':'Light';
    };
  }
}

function toast(msg,type='success'){
  const t=document.createElement('div');
  t.className='toast toast-'+type;
  t.textContent=msg;
  document.getElementById('toasts').appendChild(t);
  setTimeout(()=>t.remove(),3000);
}

async function api(path,opts={}){
  try{
    const r=await fetch(API+path,{headers:{'Content-Type':'application/json'},...opts});
    if(!r.ok)throw new Error(r.status+' '+r.statusText);
    return await r.json();
  }catch(e){toast(e.message,'error');return null;}
}

async function fetchAll(){
  const rb=document.getElementById('refreshBtn');
  if(rb)rb.textContent='Loading...';
  showLoading();
  const[leads,review,rejected,followup]=await Promise.all([
    api('/api/leads?page=1&page_size=500'),
    api('/api/leads/review-queue'),
    api('/api/leads/rejected'),
    api('/api/leads/followup-today'),
  ]);
  allLeads=(leads?.results||[]).map(normalizeLead);
  reviewLeads=(review?.leads||[]).map(normalizeLead);
  rejectedLeads=(rejected?.leads||[]);
  followupLeads=(followup?.leads||[]).map(normalizeLead);
  updStats();
  if(followupLeads.length){
    const banner=document.getElementById('fuBanner');
    const txt=document.getElementById('fuBannerText');
    if(banner)banner.style.display='flex';
    if(txt)txt.textContent=followupLeads.length+' due today';
    const pill=document.getElementById('statFuPill');
    if(pill)pill.style.display='flex';
    const fu=document.getElementById('statFu');
    if(fu)fu.textContent=followupLeads.length;
  }
  populateFilters();
  renderTabs();
  currentPage=1;
  render();
  if(rb)rb.textContent='Refresh';
}

function updStats(){
  const h=allLeads.filter(l=>l.label==='HOT').length;
  const w=allLeads.filter(l=>l.label==='WARM').length;
  const c=allLeads.filter(l=>l.label==='COLD').length;
  ['statHot','sbHot'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=h;});
  ['statWarm','sbWarm'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=w;});
  ['statCold','sbCold'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=c;});
  ['statReview','sbReview'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=reviewLeads.length;});
}

async function fetchReviewCount(){
  const r=await api('/api/leads/review-queue');
  if(r){
    ['statReview','sbReview'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=r.count||0;});
  }
}

function normalizeLead(l){
  if(!l._normalized){
    l.composite_score=parseFloat(l.composite_score||0);
    l.label=(l.label||'COLD').toUpperCase();
    l.pain_signals_parsed=parsePainSignals(l);
    l._normalized=true;
  }
  return l;
}

function parsePainSignals(l){
  if(l.pain_signals&&typeof l.pain_signals==='object')return l.pain_signals;
  if(l.pain_signals_json){try{return JSON.parse(l.pain_signals_json)}catch(e){}}
  const r={};PAIN_KEYS.forEach(k=>r[k]=!!l[k]);return r;
}

function getFilteredLeads(){
  let src;
  if(activeTab==='REVIEW')src=[...reviewLeads];
  else if(activeTab==='REJECTED')src=[...rejectedLeads];
  else src=[...allLeads];
  if(activeTab==='HOT')src=src.filter(l=>l.label==='HOT');
  else if(activeTab==='WARM')src=src.filter(l=>l.label==='WARM');
  else if(activeTab==='COLD')src=src.filter(l=>l.label==='COLD');
  const se=(document.getElementById('fSearch').value||'').toLowerCase();
  const ci=document.getElementById('fCity').value;
  const so=document.getElementById('fSource').value;
  const ne=document.getElementById('fEmail').checked;
  const np=document.getElementById('fPhone').checked;
  if(se)src=src.filter(l=>(l.company_name||'').toLowerCase().includes(se));
  if(ci)src=src.filter(l=>(l.city||l.location||'').toLowerCase()===ci.toLowerCase());
  if(so)src=src.filter(l=>(l.source||'').toLowerCase()===so.toLowerCase());
  if(ne)src=src.filter(l=>!!(l.email||'').trim());
  if(np)src=src.filter(l=>!!(l.phone||'').trim());
  const sort=document.getElementById('fSort').value;
  src.sort((a,b)=>{
    if(sort==='score_desc')return(b.composite_score||0)-(a.composite_score||0);
    if(sort==='score_asc')return(a.composite_score||0)-(b.composite_score||0);
    if(sort==='date_desc')return(b.created_at||'').localeCompare(a.created_at||'');
    return(a.created_at||'').localeCompare(b.created_at||'');
  });
  return src;
}

function populateFilters(){
  const cities=new Set(),sources=new Set();
  allLeads.forEach(l=>{
    if(l.city||l.location)cities.add((l.city||l.location).trim());
    if(l.source)sources.add(l.source.trim());
  });
  const cs=document.getElementById('fCity');
  cs.innerHTML='<option value="">All Cities</option>';
  [...cities].sort().forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;cs.appendChild(o);});
  const ss=document.getElementById('fSource');
  ss.innerHTML='<option value="">All Sources</option>';
  [...sources].sort().forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=s;ss.appendChild(o);});
}

function renderTabs(){
  const counts={
    ALL:allLeads.length,
    HOT:allLeads.filter(l=>l.label==='HOT').length,
    WARM:allLeads.filter(l=>l.label==='WARM').length,
    COLD:allLeads.filter(l=>l.label==='COLD').length,
    REVIEW:reviewLeads.length,
    REJECTED:rejectedLeads.length
  };
  const bar=document.getElementById('tabsBar');
  if(!bar)return;
  bar.innerHTML=TABS.map(t=>`<button class="tab-btn${activeTab===t?' active':''}" onclick="switchTab('${t}')">${t} <span class="tab-count">${counts[t]}</span></button>`).join('');
}

function switchTab(t){activeTab=t;currentPage=1;selected.clear();updateBulkBar();closeDetail();render();}

function render(){
  const leads=getFilteredLeads();
  const total=leads.length;
  const totalPages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(currentPage>totalPages)currentPage=totalPages;
  const start=(currentPage-1)*PAGE_SIZE;
  const page=leads.slice(start,start+PAGE_SIZE);
  const tb=document.getElementById('leadTableBody');
  if(!tb)return;
  if(!page.length){
    const msgs={ALL:'No leads yet. Run a pipeline search first.',HOT:'No HOT leads.',WARM:'No WARM leads.',COLD:'No COLD leads.',REVIEW:'Review queue empty.',REJECTED:'No rejected leads.'};
    tb.innerHTML=`<tr class="empty-row"><td colspan="9">${msgs[activeTab]||'No data'}</td></tr>`;
  }else{
    tb.innerHTML=page.map(l=>renderRow(l)).join('');
  }
  const lc=document.getElementById('leadCount');
  if(lc)lc.textContent=total+' leads';
  const pi=document.getElementById('pageInfo');
  if(pi)pi.textContent=currentPage+'/'+totalPages;
  const prev=document.getElementById('prevBtn');
  const next=document.getElementById('nextBtn');
  if(prev)prev.disabled=currentPage<=1;
  if(next)next.disabled=currentPage>=totalPages;
  renderTabs();
}

function showLoading(){
  const tb=document.getElementById('leadTableBody');
  if(tb)tb.innerHTML=Array(6).fill('<tr><td colspan="9" style="padding:12px 16px"><div style="height:14px;background:var(--border);border-radius:4px;animation:shimmer 1.5s infinite"></div></td></tr>').join('');
}

function renderRow(l){
  const id=l.id;
  const lbl=l.label||'COLD';
  const sc=Math.round(l.composite_score||0);
  const dotCls=lbl==='HOT'?'hot':lbl==='WARM'?'warm':'cold';
  const sCls=sc>=65?'hot':sc>=40?'warm':'cold';
  const st=l.status||'New';
  const ps=l.pain_signals_parsed||{};
  const firstPain=PAIN_KEYS.find(k=>ps[k]);
  const selCls=selected.has(id)?'selected':'';
  const actCls=activeDetailId===id?'detail-open':'';
  const chk=selected.has(id)?'checked':'';
  return `<tr class="${selCls} ${actCls}" data-id="${id}" onclick="rowClick(${id},event)">
<td class="col-cb"><input type="checkbox" ${chk} onclick="event.stopPropagation();toggleSelect(${id},event)"></td>
<td class="col-dot"><span class="label-dot ${dotCls}"></span></td>
<td class="col-name"><span class="td-name" title="${esc(l.company_name)}">${esc(l.company_name||'Unknown')}</span></td>
<td class="col-score"><span class="score-badge ${sCls}">${sc}</span></td>
<td class="col-source"><span class="source-tag">${esc((l.source||'?').toLowerCase())}</span></td>
<td class="col-city">${esc(l.city||l.location||'')}</td>
<td class="col-status"><span class="status-pill ${st}" id="st-${id}">${st}</span></td>
<td class="col-pain">${firstPain?`<span class="pain-tag">${PAIN_LABELS[firstPain]}</span>`:'-'}</td>
<td class="col-time"><span class="time-tag">${formatTime(l.created_at)}</span></td>
</tr>`;
}

function rowClick(id,e){
  if(e.target.tagName==='INPUT')return;
  if(activeDetailId===id){closeDetail();return;}
  openDetail(id);
}

function openDetail(id){
  const l=allLeads.find(x=>x.id===id)||reviewLeads.find(x=>x.id===id)||rejectedLeads.find(x=>x.id===id);
  if(!l)return;
  activeDetailId=id;
  const body=document.getElementById('detailBody');
  const title=document.getElementById('detailTitle');
  if(body)body.innerHTML=buildDetail(l);
  if(title)title.textContent=l.company_name||'Lead Details';
  const panel=document.getElementById('detailPanel');
  if(panel)panel.classList.add('open');
  document.querySelectorAll('#leadTableBody tr').forEach(r=>{
    r.classList.toggle('detail-open',parseInt(r.dataset.id)===id);
  });
}

function closeDetail(){
  activeDetailId=null;
  const panel=document.getElementById('detailPanel');
  if(panel)panel.classList.remove('open');
  document.querySelectorAll('.detail-open').forEach(r=>r.classList.remove('detail-open'));
}

function buildDetail(l){
  const id=l.id;
  const lbl=l.label||'COLD';
  const cls=lbl.toLowerCase();
  const sc=Math.round(l.composite_score||0);
  const ph=(l.phone||'').trim();
  const em=(l.email||'').trim();
  const ps=l.pain_signals_parsed||{};
  const pains=PAIN_KEYS.filter(k=>ps[k]);
  const signals=parseBuyingSignals(l.buying_signals);
  const rv=(l.review_status||'').toLowerCase()==='pending_review';
  const fitS=l.fit_score!=null?l.fit_score:0;
  const intS=l.buying_intent_score!=null?l.buying_intent_score:0;
  const conS=l.contactability_score!=null?l.contactability_score:0;
  const fitD=l.fit_score!=null?l.fit_score:'--';
  const intD=l.buying_intent_score!=null?l.buying_intent_score:'--';
  const conD=l.contactability_score!=null?l.contactability_score:'--';
  const fuD=l.follow_up_date||'';
  const fuN=l.follow_up_note||l.notes||'';

  let h='';

  // Label + score
  h+=`<div class="d-section">
    <div class="d-label-row">
      <span class="d-lbl ${cls}">${lbl}</span>
      <span class="d-score-num ${cls}">${sc}</span>
    </div>
    <div class="d-meta">${esc(l.source||'?')} &middot; ${esc(l.city||l.location||'')} &middot; ${formatTime(l.created_at)}</div>
  </div>`;

  // Score bars
  h+=`<div class="d-section">
    <div class="d-section-title">Score Breakdown</div>
    <div class="score-row">
      <div class="score-bar-item"><span class="score-bar-label">Fit</span><div class="score-bar-track"><div class="score-bar-fill" style="width:${fitS}%;background:#2563eb"></div></div><span class="score-bar-val">${fitD}</span></div>
      <div class="score-bar-item"><span class="score-bar-label">Intent</span><div class="score-bar-track"><div class="score-bar-fill" style="width:${intS}%;background:#7c3aed"></div></div><span class="score-bar-val">${intD}</span></div>
      <div class="score-bar-item"><span class="score-bar-label">Contact</span><div class="score-bar-track"><div class="score-bar-fill" style="width:${conS}%;background:#16a34a"></div></div><span class="score-bar-val">${conD}</span></div>
    </div>
  </div>`;

  // Contact
  h+=`<div class="d-section"><div class="d-section-title">Contact</div><div class="contact-row">`;
  if(ph){
    h+=`<button class="contact-btn" onclick="copyText('${esc(ph)}',this)">Phone: ${esc(ph)}</button>`;
    h+=`<a class="contact-btn wa" href="https://wa.me/91${ph.replace(/\D/g,'')}" target="_blank">WhatsApp</a>`;
  }
  if(em)h+=`<button class="contact-btn" onclick="copyText('${esc(em)}',this)">Email: ${esc(em)}</button>`;
  if(!ph&&!em)h+=`<span style="font-size:0.78rem;color:var(--text-muted)">No contact info</span>`;
  h+=`</div></div>`;

  // Pain signals
  if(pains.length){
    h+=`<div class="d-section"><div class="d-section-title">Pain Signals</div><div class="pain-chips">`;
    pains.forEach(k=>h+=`<span class="pain-chip">${PAIN_LABELS[k]}</span>`);
    h+=`</div></div>`;
  }

  // Status
  h+=`<div class="d-section"><div class="d-section-title">Status</div>
    <select class="d-status-select" onchange="updateStatus(${id},this.value,this)">
      ${STATUSES.map(s=>`<option${s===(l.status||'New')?' selected':''}>${s}</option>`).join('')}
    </select>
  </div>`;

  // Follow-up
  h+=`<div class="d-section"><div class="d-section-title">Follow-up</div>
    <div class="fu-row">
      <input type="date" id="fu-date-${id}" min="${new Date().toISOString().slice(0,10)}" value="${esc(fuD)}">
      <input type="text" id="fu-note-${id}" placeholder="Note..." value="${esc(fuN)}">
      <button class="fu-set-btn" id="fu-btn-${id}" onclick="setFollowup(${id})">Set</button>
    </div>
    ${fuD?`<div class="fu-confirm">Due: ${fuD}</div>`:''}
  </div>`;

  // Review
  if(rv){
    h+=`<div class="d-section"><div class="review-row">
      <button class="review-approve" onclick="reviewLead(${id},'approved')">Approve</button>
      <button class="review-reject" onclick="reviewLead(${id},'rejected')">Reject</button>
    </div></div>`;
  }

  // AI Analysis
  h+=`<div class="d-section">
    <div class="d-section-title collapsible-head" onclick="togSec('ai-${id}')">
      AI Analysis <span class="collapsible-arrow open" id="arr-ai-${id}">v</span>
    </div>
    <div class="collapsible-body open" id="sec-ai-${id}">
      <dl class="ai-field"><dt>Pain Point</dt><dd>${esc(l.pain_point||'--')}</dd></dl>
      <dl class="ai-field"><dt>Buying Signals</dt><dd>${signals.length?signals.map(s=>'- '+esc(s)).join('\n'):'--'}</dd></dl>
      <dl class="ai-field"><dt>Decision Maker</dt><dd>${esc(l.decision_maker||'--')}</dd></dl>
      <dl class="ai-field"><dt>Objection</dt><dd>${esc(l.objection_1||'--')}</dd></dl>
      <dl class="ai-field"><dt>Rebuttal</dt><dd>${esc(l.rebuttal_1||'--')}</dd></dl>
      <dl class="ai-field"><dt>Best Channel</dt><dd>${esc(l.best_channel||'--')}${l.channel_reason?' - '+esc(l.channel_reason):''}</dd></dl>
      <dl class="ai-field"><dt>Opener</dt><dd>${esc(l.personalized_opener||'--')}</dd></dl>
      ${l.speed_to_close?`<dl class="ai-field"><dt>Speed to Close</dt><dd>${esc(l.speed_to_close)}</dd></dl>`:''}
    </div>
  </div>`;

  // Messages
  if(l.whatsapp_msg||l.linkedin_msg){
    h+=`<div class="d-section">
      <div class="d-section-title collapsible-head" onclick="togSec('msg-${id}')">
        Outreach Messages <span class="collapsible-arrow" id="arr-msg-${id}">v</span>
      </div>
      <div class="collapsible-body" id="sec-msg-${id}">`;
    if(l.whatsapp_msg){
      h+=`<div style="font-size:0.7rem;font-weight:700;color:var(--text-muted);margin-bottom:4px;margin-top:8px">WHATSAPP</div>
          <div class="msg-box">${esc(l.whatsapp_msg)}</div>
          <button class="msg-copy" onclick="copyText('${escAttr(l.whatsapp_msg)}',this)">Copy</button>`;
    }
    if(l.linkedin_msg){
      h+=`<div style="font-size:0.7rem;font-weight:700;color:var(--text-muted);margin-bottom:4px;margin-top:8px">LINKEDIN</div>
          <div class="msg-box">${esc(l.linkedin_msg)}</div>
          <button class="msg-copy" onclick="copyText('${escAttr(l.linkedin_msg)}',this)">Copy</button>`;
    }
    h+=`</div></div>`;
  }

  return h;
}

function togSec(id){
  const b=document.getElementById('sec-'+id);
  const a=document.getElementById('arr-'+id);
  if(!b)return;
  b.classList.toggle('open');
  if(a)a.textContent=b.classList.contains('open')?'v':'>';
}

async function updateStatus(id,status){
  const r=await api(`/api/leads/${id}/status`,{method:'PUT',body:JSON.stringify({status})});
  if(r){
    toast('Status updated to '+status);
    const l=allLeads.find(x=>x.id===id);
    if(l)l.status=status;
    const pill=document.getElementById('st-'+id);
    if(pill){pill.className='status-pill '+status;pill.textContent=status;}
  }
}

async function setFollowup(id){
  const d=document.getElementById('fu-date-'+id).value;
  const n=document.getElementById('fu-note-'+id).value;
  if(!d){toast('Pick a date','error');return;}
  const r=await api(`/api/leads/${id}/followup`,{method:'PUT',body:JSON.stringify({follow_up_date:d,notes:n})});
  if(r){
    toast('Follow-up set for '+d);
    const btn=document.getElementById('fu-btn-'+id);
    if(btn){btn.textContent='Done';setTimeout(()=>btn.textContent='Set',2000);}
    const l=allLeads.find(x=>x.id===id);
    if(l){l.follow_up_date=d;l.follow_up_note=n;}
  }
}

async function reviewLead(id,action){
  const r=await api(`/api/leads/${id}/review`,{method:'PATCH',body:JSON.stringify({action})});
  if(r){
    toast('Lead '+action);
    reviewLeads=reviewLeads.filter(l=>l.id!==id);
    const l=allLeads.find(x=>x.id===id);
    if(l)l.review_status=action;
    ['statReview','sbReview'].forEach(eid=>{const el=document.getElementById(eid);if(el)el.textContent=reviewLeads.length;});
    closeDetail();render();
  }
}

function toggleExpand(id){togSec('ai-'+id);}

function copyText(text,btn){
  navigator.clipboard.writeText(text).then(()=>{
    const tip=document.createElement('span');
    tip.className='copied-tip';
    tip.textContent='Copied!';
    btn.appendChild(tip);
    setTimeout(()=>tip.remove(),1500);
  });
}

function toggleSelect(id,event){
  const cb=event.target;
  if(event.shiftKey&&lastChecked!==null){
    const leads=getFilteredLeads(),ids=leads.map(l=>l.id);
    const a=ids.indexOf(lastChecked),b=ids.indexOf(id);
    const lo=Math.min(a,b),hi=Math.max(a,b);
    for(let i=lo;i<=hi;i++){if(cb.checked)selected.add(ids[i]);else selected.delete(ids[i]);}
    document.querySelectorAll('#leadTableBody tr').forEach(r=>{
      const cid=parseInt(r.dataset.id);
      const c=r.querySelector('input[type=checkbox]');
      if(c)c.checked=selected.has(cid);
    });
  }else{
    if(cb.checked)selected.add(id);else selected.delete(id);
  }
  lastChecked=id;
  updateBulkBar();
  document.querySelectorAll('#leadTableBody tr').forEach(r=>{
    r.classList.toggle('selected',selected.has(parseInt(r.dataset.id)));
  });
}

function toggleSelectAll(chk){
  const leads=getFilteredLeads();
  const start=(currentPage-1)*PAGE_SIZE;
  const page=leads.slice(start,start+PAGE_SIZE);
  page.forEach(l=>{if(chk)selected.add(l.id);else selected.delete(l.id);});
  updateBulkBar();
  document.querySelectorAll('#leadTableBody tr').forEach(r=>{
    const id=parseInt(r.dataset.id);
    r.classList.toggle('selected',selected.has(id));
    const cb=r.querySelector('input[type=checkbox]');
    if(cb)cb.checked=selected.has(id);
  });
}

function updateBulkBar(){
  const bar=document.getElementById('bulkBar');
  const bc=document.getElementById('bulkCount');
  if(!bar)return;
  if(selected.size>0){
    bar.classList.add('show');
    if(bc)bc.textContent=selected.size+' selected';
  }else{
    bar.classList.remove('show');
  }
}

function clearSelection(){selected.clear();updateBulkBar();render();}

async function bulkAction(status){
  const ids=[...selected];let ok=0;
  for(const id of ids){
    const r=await api(`/api/leads/${id}/status`,{method:'PUT',body:JSON.stringify({status})});
    if(r){ok++;const l=allLeads.find(x=>x.id===id);if(l)l.status=status;}
  }
  toast(ok+'/'+ids.length+' leads updated to '+status);
  selected.clear();updateBulkBar();render();
}

async function bulkReview(action){
  const ids=[...selected].filter(id=>reviewLeads.find(l=>l.id===id));
  if(!ids.length){toast('No review-pending leads selected','error');return;}
  let ok=0;
  for(const id of ids){
    const r=await api(`/api/leads/${id}/review`,{method:'PATCH',body:JSON.stringify({action})});
    if(r){ok++;reviewLeads=reviewLeads.filter(l=>l.id!==id);const l=allLeads.find(x=>x.id===id);if(l)l.review_status=action;}
  }
  toast(ok+'/'+ids.length+' leads '+action);
  ['statReview','sbReview'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=reviewLeads.length;});
  selected.clear();updateBulkBar();render();
}

function exportCSV(){
  const leads=getFilteredLeads().filter(l=>selected.size===0||selected.has(l.id));
  const header='Company,City,Phone,Email,Score,Label,Status,Source,Date';
  const rows=leads.map(l=>[l.company_name,l.city||l.location,l.phone,l.email,Math.round(l.composite_score||0),l.label,l.status||'New',l.source,l.created_at||''].map(v=>`"${(v||'').toString().replace(/"/g,'""')}"`).join(','));
  const csv=header+'\n'+rows.join('\n');
  const blob=new Blob([csv],{type:'text/csv'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='leads_'+new Date().toISOString().slice(0,10)+'.csv';
  a.click();
  toast('Exported '+leads.length+' leads');
}

function prevPage(){if(currentPage>1){currentPage--;render();window.scrollTo(0,0);}}
function nextPage(){currentPage++;render();window.scrollTo(0,0);}

function viewFollowups(){
  activeTab='ALL';
  allLeads=[...followupLeads,...allLeads.filter(l=>!followupLeads.find(f=>f.id===l.id))];
  currentPage=1;render();
  toast('Showing '+followupLeads.length+' follow-ups due today','info');
}

function esc(s){if(!s)return '';return s.toString().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function escAttr(s){if(!s)return '';return s.toString().replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/\n/g,'\\n').replace(/\r/g,'');}

function formatTime(dt){
  if(!dt)return '';
  try{
    const d=new Date(dt.includes('T')?dt:dt+'Z');
    const now=new Date(),diff=now-d,mins=Math.floor(diff/60000);
    if(mins<1)return 'now';
    if(mins<60)return mins+'m ago';
    const hrs=Math.floor(mins/60);
    if(hrs<24)return hrs+'h ago';
    const days=Math.floor(hrs/24);
    if(days===1)return '1d ago';
    if(days<30)return days+'d ago';
    return d.toLocaleDateString();
  }catch(e){return dt;}
}

function parseBuyingSignals(bs){
  if(!bs)return [];
  if(Array.isArray(bs))return bs;
  if(typeof bs==='string'){try{return JSON.parse(bs)}catch(e){return bs.split(',').map(s=>s.trim()).filter(Boolean);}}
  return [];
}

window.toggleSelect=toggleSelect;window.toggleSelectAll=toggleSelectAll;
window.updateStatus=updateStatus;window.setFollowup=setFollowup;
window.reviewLead=reviewLead;window.toggleExpand=toggleExpand;window.copyText=copyText;
window.bulkAction=bulkAction;window.bulkReview=bulkReview;window.exportCSV=exportCSV;
window.clearSelection=clearSelection;window.viewFollowups=viewFollowups;
window.prevPage=prevPage;window.nextPage=nextPage;
window.fetchAll=fetchAll;window.switchTab=switchTab;
window.rowClick=rowClick;window.closeDetail=closeDetail;window.togSec=togSec;