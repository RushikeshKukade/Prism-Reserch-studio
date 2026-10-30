const $ = id => document.getElementById(id);
let metadata, lastResult;
let aiConfigured = false;
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const indian = n => new Intl.NumberFormat('en-IN', {maximumFractionDigits:0}).format(n);
const sourceLink = s => `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a>`;
function evidence(s) { return `<article class="evidence">${sourceLink(s)}<p>${esc(s.locator)}</p><p>${esc(s.basis)}</p>${s.rows.map(r=>`<code>${esc(r)}</code>`).join('')}<p>Verified ${esc(s.verified_on)} · Publication date: ${esc(s.publication_date||'not recorded')}</p></article>`; }
function setView(view) {
  document.body.dataset.view=view;
  $('research-layout').hidden=view!=='research';
  $('monitors').hidden=view!=='monitors';
  $('universe').hidden=view!=='universe';
  if(view==='universe')loadUniverseExplorer();
  updateStudioHeading(view);
  if(view==='research')loadResearchContext();
  if(view==='monitors')loadMonitors();
  if(view==='sources')loadEvidenceLibrary();
  $('current').hidden=view!=='current';
  $('coverage-status').textContent=view==='current'?'PUBLIC MARKET DATA':'HISTORICAL ANALYSIS';
  $('coverage-note').textContent=view==='current'?'Dated provider observations · may be delayed':'FY2023–FY2024 analysis remains separate';
  if(view==='current'){loadCurrent();$('active-fy').textContent='Market observations';document.querySelector('.coverage small').textContent='Prices refresh separately from filings';}else{$('active-fy').textContent=$('year-filter').value==='2024'?'FY 2023–24':'FY 2022–23';document.querySelector('.coverage small').textContent='Historical annual results · INR crore';}
  $('dashboard').hidden = view !== 'dashboard';
  ['quality','changes','evaluation'].forEach(id=>$(id).hidden=id!==view);
  if(view==='quality')loadQuality();
  if(view==='changes')loadChanges();
  if(view==='evaluation')loadEvaluation();
  $('ask-form').closest('section').hidden = view !== 'research';
  $('overview').hidden = true;
  $('result').hidden = view !== 'research';
  $('library').hidden = view !== 'sources';
  $('method').hidden = view !== 'method';
  ['current','universe','dashboard','research','monitors','quality','changes','evaluation','sources','method'].forEach(v=>$(v+'-tab').classList.toggle('active',v===view));
}
['current','universe','dashboard','research','monitors','quality','changes','evaluation','sources','method'].forEach(v=>$(v+'-tab').onclick=()=>setView(v));
['current','universe','dashboard','research','monitors','quality','changes','evaluation','sources','method'].forEach(v=>$('mobile-'+v).onclick=()=>setView(v));
function download(name, body, type) {
  const a=document.createElement('a'),url=URL.createObjectURL(new Blob([body],{type}));
  a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function render(result, question) {
  lastResult={question,...result};
  const ok=result.status==='answered';
  const review=result.status==='research_review';
  let html=`<div class="result-head ${ok||review?'':'status-refused'}"><span>${review?'REVIEW & SUGGESTIONS':ok?'RESEARCH RESULT':'INSUFFICIENT EVIDENCE'}</span><span>${review?'Current-market suitability: unverified':ok?result.evidence.length+' source'+(result.evidence.length===1?'':'s'):'No unsupported claims'}</span></div><p class="answer">${esc(result.answer)}</p>`;
  if(review) {
    html+=`<div class="suggestion-box"><div class="eyebrow">INDIA RESEARCH / REVIEWED ${esc(result.review.review_date)} IST</div><h2>${esc(result.review.verdict)}</h2>${result.review.sections.map(section=>`<article><h3>${esc(section.title)}</h3><p>${esc(section.text)}</p></article>`).join('')}<div class="review-references">${result.review.references.map(r=>`<p><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)} ↗</a></p>`).join('')}<p>${esc(result.review.reference_note)}</p></div></div>`;
  }
  if(ok) {
    html+=`<div class="table-wrap"><table><thead><tr><th>Company</th><th>Financial year</th><th>Value</th><th>Period ending</th><th>Evidence</th></tr></thead><tbody>${result.rows.map(r=>`<tr><td>${esc(r.company)}</td><td>${esc(r.year)}</td><td class="number">${esc(r.display)}</td><td>${esc(r.period_end)}</td><td><a href="#evidence-${esc(r.source_id)}">${esc(r.source_id)}</a></td></tr>`).join('')}</tbody></table></div>`;
    const maxYear=result.rows.filter(r=>r.metric!=='change').map(r=>r.year).sort().at(-1);
    const chartRows=result.rows.filter(r=>r.metric!=='change'&&r.year===maxYear), max=Math.max(...chartRows.map(r=>r.value));
    html+=`<div class="result-chart" aria-label="${esc(maxYear)} comparison">${chartRows.map(r=>`<div class="chart-row"><span>${esc(r.company)}</span><div class="bar-track"><div class="bar" data-width="${r.value/max*100}"></div></div><span>${esc(r.display)}</span></div>`).join('')}</div>`;
    html+=result.warnings.map(w=>`<p class="warning">${esc(w)}</p>`).join('');
    if(result.calculations.length) html+=`<details open><summary>Calculation trail</summary>${result.calculations.map(c=>`<p><strong>${esc(c.company)} · ${esc(c.year)}</strong><br>${esc(c.formula)}<br>${esc(c.substitution)} [${c.source_ids.map(esc).join(', ')}]</p>`).join('')}</details>`;
    html+=`<details open id="evidence-details"><summary>Source evidence</summary>${result.evidence.map(s=>`<div id="evidence-${esc(s.id)}">${evidence(s)}</div>`).join('')}</details>`;
  }
  if(ok) html+=`<section class="ai-brief"><div class="ai-brief-top"><div><div class="eyebrow">OPTIONAL / OPENAI</div><h3>Turn evidence into a research brief</h3></div><button type="button" class="outline-button" id="generate-brief" ${aiConfigured?'':'disabled'}>Generate brief ↗</button></div><p class="table-note">${aiConfigured?'Sends this question and its evidence to OpenAI. API charges may apply.':'Not configured. Add your API key to the local .env file; see the README.'} The verified answer above stays available.</p><div id="ai-brief-content" aria-live="polite"></div></section>`;
  html+=`<div class="answer-actions"><button class="outline-button" id="result-monitor">Define a monitor ↗</button><span>Choose an observation to follow next.</span></div><details class="audit-details"><summary>Research audit</summary><div class="metrics"><span>${result.latency_ms} ms engine time</span><span>Evidence engine: 0 model calls · ₹0 model cost</span><span>${esc(result.snapshot||'Fixed snapshot')} · verified ${esc(result.verified_on)}</span><button class="export" id="export-json">Export answer JSON ↓</button></div></details>`;
  $('result').innerHTML=html;
  $('result').querySelectorAll('[data-width]').forEach(b=>b.style.width=b.dataset.width+'%');
  renderEvidenceTrail(result,question);
  $('result-monitor').onclick=()=>openMonitorBuilder(result.rows?.[0]?.company_id||$('context-company').value);
  $('export-json').onclick=()=>download('prism-research-answer.json',JSON.stringify(lastResult,null,2),'application/json');
  if($('generate-brief')) $('generate-brief').onclick=generateBrief;
  $('result').querySelectorAll('a[href^="#evidence-"]').forEach(a=>a.onclick=()=>{$('evidence-details').open=true;});
}
async function ask(question) {
  if(!question.trim()) {$('question').focus();return;}
  lastResult=null;
  setView('research');$('question').value=question;$('submit').disabled=true;$('submit').textContent='Checking evidence…';
  try {
    const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');render(data,question);
  } catch(e) {$('result').innerHTML=`<p class="error">Could not complete the request: ${esc(e.message)}. Check that the local server is running.</p>`;}
  finally {$('submit').disabled=false;$('submit').innerHTML='Run research <span>↗</span>';}
}
$('ask-form').onsubmit=e=>{e.preventDefault();ask($('question').value);};
$('question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask($('question').value);}};
async function init() {
  const res=await fetch('/api/meta');if(!res.ok)throw Error('Cannot load snapshot');metadata=await res.json();
  await loadAiStatus();
  const companies=metadata.data.companies;
  renderDashboard();
  initStudio();
  setView('research');
  $('companies').innerHTML=companies.map(c=>`<div class="side-company"><span class="tiny-logo">${esc(c.id.slice(0,3))}</span>${esc(c.name)}</div>`).join('')+'<button class="text-button" id="browse-universe">Browse '+metadata.universe.count+' companies ↗</button>';
  $('browse-universe').onclick=()=>setView('universe');
  const reviewButton=document.createElement('button');reviewButton.type='button';reviewButton.textContent='Review this approach for India ↗';reviewButton.onclick=()=>ask('Review current Indian markets');$('suggestions').appendChild(reviewButton);
  const labels=['Compare revenue ↗','Highest operating margin ↗','Infosys revenue growth ↗','TCS margin change ↗','HCLTech operating profit ↗'];
  [['Current TCS price ↗','Show current price for TCS'],['Recent Infosys revenue ↗','Show latest revenue for Infosys']].forEach(([label,q])=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>ask(q);$('suggestions').appendChild(b);});
  metadata.examples.forEach((q,i)=>{let b=document.createElement('button');b.textContent=labels[i];b.type='button';b.onclick=()=>ask(q);$('suggestions').appendChild(b);});
  const max=Math.max(...companies.map(c=>c.years['2024'].revenue));
  $('cards').innerHTML=companies.map(c=>{const d=c.years['2024'],growth=(d.revenue/c.years['2023'].revenue-1)*100;return `<article class="company-card"><div class="company-top"><strong>${esc(c.name)}</strong><span class="ticker">NSE: ${esc(c.id)}</span></div><small>CONSOLIDATED REVENUE</small><div class="value">₹${indian(d.revenue)}</div><span class="growth">↗ ${growth.toFixed(2)}% YoY</span><div class="bar-track"><div class="bar" data-width="${d.revenue/max*100}"></div></div>${sourceLink(c.source)}</article>`;}).join('');
  $('cards').querySelectorAll('[data-width]').forEach(b=>b.style.width=b.dataset.width+'%');
  $('source-list').innerHTML=companies.map(c=>evidence({...c.source,rows:c.source_rows,basis:c.basis,verified_on:metadata.data.verified_on})).join('');
}
init().catch(e=>{$('result').innerHTML=`<p class="error">${esc(e.message)}. Start the app with python app.py, then reload.</p>`;});

let sortMetric='revenue', sortAscending=false;
function dashboardRows() {
  const y=$('year-filter').value;
  return metadata.data.companies.map(c=>{const d=c.years[y];return {company:c,year:y,revenue:d.revenue,profit:d.operating_profit,margin:100*d.operating_profit/d.revenue,growth:y==='2024'?(d.revenue/c.years['2023'].revenue-1)*100:null};});
}
function renderWatchlist() {
  const term=$('watchlist-search').value.trim().toLowerCase();
  const rows=dashboardRows().filter(r=>(r.company.name+' '+r.company.id+' '+r.company.legal_name).toLowerCase().includes(term)).sort((a,b)=>((a[sortMetric]??-Infinity)-(b[sortMetric]??-Infinity))*(sortAscending?1:-1));
  $('watchlist-body').innerHTML=rows.length?rows.map(r=>`<tr><td><div class="watch-company"><span class="company-avatar">${esc(r.company.id.slice(0,3))}</span><div><strong>${esc(r.company.name)}</strong><small>NSE: ${esc(r.company.id)}</small></div></div></td><td class="number">${indian(r.revenue)}</td><td>${indian(r.profit)}${r.company.id==='TCS'&&r.year==='2024'?' *':''}</td><td>${r.margin.toFixed(2)}%</td><td class="${r.growth===null?'neutral':'up'}">${r.growth===null?'Not covered':'+'+r.growth.toFixed(2)+'%'}</td><td><button class="research-button" data-company="${esc(r.company.id)}">Explore ↗</button></td></tr>`).join(''):'<tr><td colspan="6">No matching company in this three-company snapshot.</td></tr>';
  $('watchlist-body').querySelectorAll('[data-company]').forEach(b=>b.onclick=()=>{const c=metadata.data.companies.find(c=>c.id===b.dataset.company);ask(`Show ${c.name} revenue in FY${$('year-filter').value}`);$('question').focus();});
}
function renderDashboard() {
  const rows=dashboardRows(), year=$('year-filter').value, current=year==='2024';
  const total=rows.reduce((sum,r)=>sum+r.revenue,0), prior=metadata.data.companies.reduce((sum,c)=>sum+c.years['2023'].revenue,0);
  const largest=[...rows].sort((a,b)=>b.revenue-a.revenue)[0], margin=[...rows].sort((a,b)=>b.margin-a.margin)[0], fastest=[...rows].sort((a,b)=>(b.growth??0)-(a.growth??0))[0];
  $('active-fy').textContent=current?'FY 2023–24':'FY 2022–23';$('table-year').textContent=year;
  const kpis=[
    ['COVERED REVENUE · ₹ CRORE','₹'+indian(total),current?`<span class="up">↗ ${((total/prior-1)*100).toFixed(2)}% YoY</span> across selected peers`:'3 selected companies · FY2023', '↗'],
    ['LARGEST BY REVENUE',largest.company.name,`₹${indian(largest.revenue)} crore · ${year}`, '▥'],
    ['HIGHEST DISCLOSED MARGIN',margin.margin.toFixed(2)+'%',`${margin.company.name} · disclosed operating basis${current?' *':''}`, '◈'],
    ['FASTEST REVENUE GROWTH',current?'+'+fastest.growth.toFixed(2)+'%':'Not covered',current?`${fastest.company.name} · FY2024 vs FY2023`:'FY2022 baseline is outside the snapshot', '↗']
  ];
  $('kpis').innerHTML=kpis.map(k=>`<article class="kpi"><span class="kpi-corner">${k[3]}</span><div class="kpi-label">${k[0]}</div><div class="kpi-value">${k[1]}</div><div class="kpi-sub">${k[2]}</div></article>`).join('');
  $('pulse').innerHTML=`<div class="pulse-row"><span class="pulse-icon">↗</span><div><small>GROWTH LEADER</small><strong>${current?fastest.company.name:'Baseline unavailable'}</strong><p>${current?'+'+fastest.growth.toFixed(2)+'% revenue YoY':'FY2023 growth needs FY2022 data'}</p></div></div><div class="pulse-row"><span class="pulse-icon">▤</span><div><small>EVIDENCE COVERAGE</small><strong>3 official disclosures</strong><p>12 numeric facts · two annual periods</p></div></div><div class="pulse-row"><span class="pulse-icon">◷</span><div><small>REPORTING PERIOD</small><strong>Year ended 31 March ${year}</strong><p>INR crore · consolidated financials</p></div></div>`;
  renderWatchlist();renderPeerChart();
}
function renderPeerChart() {
  const year=$('year-filter').value, metric=$('metric-filter').value;
  const years=year==='2024'?['2023','2024']:['2023'];
  const values=[];
  const val=(c,y)=>{const d=c.years[y];return metric==='margin'?100*d.operating_profit/d.revenue:metric==='growth'?(y==='2024'?(d.revenue/c.years['2023'].revenue-1)*100:null):d.revenue;};
  metadata.data.companies.forEach(c=>years.forEach(y=>{const v=val(c,y);if(v!==null)values.push(v);}));
  const max=Math.max(...values,1);
  document.querySelector('.chart-legend').innerHTML=(metric==='growth'?(year==='2024'?['2024']:[]):years).map(y=>`<span><i class="${y==='2024'?'legend-current':'legend-previous'}"></i> FY${y}</span>`).join('');
  $('peer-chart').innerHTML=metadata.data.companies.map(c=>`<div class="peer-row"><span class="peer-name">${esc(c.name)}</span><div class="pair">${years.map(y=>{const v=val(c,y);return v===null?'':`<div class="peer-bar-line"><div class="peer-bar-bg"><div class="peer-bar-fill ${y==='2023'?'previous':''}" data-width="${v/max*100}"></div></div><small>${metric==='revenue'?indian(v):v.toFixed(2)+'%'}</small></div>`;}).join('')||'<small class="neutral">FY2022 baseline not covered</small>'}</div></div>`).join('');
  $('peer-chart').querySelectorAll('[data-width]').forEach(b=>b.style.width=b.dataset.width+'%');
  $('chart-caption').textContent=metric==='margin'?'Operating profit ÷ revenue × 100. Disclosed definitions differ; TCS FY2024 excludes a legal-claim settlement.':metric==='growth'?'(FY2024 revenue ÷ FY2023 revenue − 1) × 100. FY2023 growth is not available without FY2022.':'Annual revenue in INR crore. Bars start at zero; this is a financial comparison, not a share-price history.';
}
$('year-filter').onchange=renderDashboard;
$('metric-filter').onchange=renderPeerChart;
$('watchlist-search').oninput=renderWatchlist;
$('open-assistant').onclick=()=>{setView('research');$('question').focus();};
$('open-sources').onclick=()=>setView('sources');
 document.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>{sortAscending=b.dataset.sort===sortMetric?!sortAscending:false;sortMetric=b.dataset.sort;renderWatchlist();});
$('export-watchlist').onclick=()=>{
  const lines=[['Company','NSE symbol','Financial year ending','Revenue INR crore','Operating profit INR crore','Operating margin percent','Revenue growth percent','Metric basis','Official source'],...dashboardRows().map(r=>[r.company.name,r.company.id,r.year,r.revenue,r.profit,r.margin.toFixed(4),r.growth===null?'':r.growth.toFixed(4),r.company.basis,r.company.source.url])];
  download('prism-india-watchlist-FY'+$('year-filter').value+'.csv','\ufeff'+lines.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n'),'text/csv;charset=utf-8');
};

async function api(path) {const r=await fetch(path);const data=await r.json();if(!r.ok)throw Error(data.error||'Report unavailable');return data;}
const signed=n=>(n>=0?'+':'−')+indian(Math.abs(n));
const statusChip=s=>`<span class="check-status ${s}">${esc(s)}</span>`;
async function loadQuality() {
  try {
    const q=await api('/api/quality');
    $('quality-content').innerHTML=`<div class="kpi-grid quality-kpis">${[['Passed checks',q.counts.pass,'pass'],['Warnings to review',q.counts.warning,'warning'],['Failed checks',q.counts.fail,'fail']].map(([label,value,status])=>`<article class="kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div>${statusChip(status)}</article>`).join('')}</div><p class="warning">${esc(q.limitations)}</p><article class="dash-panel"><div class="table-note">Checked against ${esc(q.as_of)} · freshness threshold: 730 days after financial period end</div><div class="table-wrap"><table><thead><tr><th>Company</th><th>Check</th><th>Status</th><th>Finding / next action</th></tr></thead><tbody>${q.checks.map(c=>`<tr><td>${esc(c.company)}</td><td>${esc(c.check)}</td><td>${statusChip(c.status)}</td><td>${esc(c.detail)}</td></tr>`).join('')}</tbody></table></div></article>`;
  }catch(e){$('quality-content').innerHTML=`<p class="error">Quality checks unavailable: ${esc(e.message)}</p>`;}
}
let bridgeRequest=0;
async function loadChanges() {
  const request=++bridgeRequest;
  try {
    const b=await api('/api/changes/'+$('bridge-company').value);
    if(request!==bridgeRequest)return;
    const parts=[['FY2023 operating profit',b.profit_before,'base'],['Revenue-scale effect',b.scale_effect,'effect'],['Margin effect',b.margin_effect,'effect'],['FY2024 operating profit',b.profit_after,'base']];
    const max=Math.max(b.profit_before,b.profit_after,Math.abs(b.scale_effect),Math.abs(b.margin_effect));
    $('changes-content').innerHTML=`<div class="kpi-grid quality-kpis"><article class="kpi"><div class="kpi-label">REVENUE GROWTH</div><div class="kpi-value">${b.revenue_growth_pct.toFixed(2)}%</div><div class="kpi-sub">FY2024 vs FY2023</div></article><article class="kpi"><div class="kpi-label">MARGIN CHANGE</div><div class="kpi-value">${b.margin_change_pp>=0?'+':''}${b.margin_change_pp.toFixed(2)} pp</div><div class="kpi-sub">${b.margin_before_pct.toFixed(2)}% → ${b.margin_after_pct.toFixed(2)}%</div></article><article class="kpi"><div class="kpi-label">OPERATING-PROFIT CHANGE</div><div class="kpi-value">₹${signed(b.profit_change)}</div><div class="kpi-sub">crore · disclosed operating basis</div></article></div><article class="dash-panel"><div class="eyebrow">${esc(b.company.toUpperCase())} / EXACT ARITHMETIC BRIDGE</div><h2 class="analytics-heading">Where the profit change comes from</h2><div class="bridge-chart">${parts.map(([label,value,type])=>`<div class="bridge-line"><span>${label}</span><div class="bridge-track"><div class="bridge-fill ${value<0?'negative':type}" data-width="${Math.abs(value)/max*100}"></div></div><strong>₹${type==='effect'?signed(value):indian(value)}</strong></div>`).join('')}</div><div class="reconcile">₹${signed(b.scale_effect)} + ₹${signed(b.margin_effect)} = ₹${signed(b.profit_change)} crore <span>✓ Reconciles at full precision</span></div><p class="table-note">Bars show component magnitude from zero, not a time series. Rounded display values may differ from the full-precision sum.</p><details open><summary>Calculation method</summary>${b.formulas.map(f=>`<p>${esc(f)}</p>`).join('')}<p>Scale: (${b.revenue_after} − ${b.revenue_before}) × (${b.profit_before} / ${b.revenue_before}) = ${b.scale_effect.toFixed(4)} crore</p><p>Margin: ${b.revenue_after} × (${b.profit_after} / ${b.revenue_after} − ${b.profit_before} / ${b.revenue_before}) = ${b.margin_effect.toFixed(4)} crore</p></details><p class="warning">${esc(b.limitation)}</p><p class="warning">${esc(b.basis)}</p>${sourceLink(b.source)}<p class="table-note">${esc(b.source.locator)}</p></article>`;
    $('changes-content').querySelectorAll('[data-width]').forEach(el=>el.style.width=el.dataset.width+'%');
  }catch(e){$('changes-content').innerHTML=`<p class="error">Change analysis unavailable: ${esc(e.message)}</p>`;}
}
async function loadEvaluation() {
  try {
    const e=await api('/api/evaluation');
    if(!e.available){$('evaluation-content').innerHTML=`<p class="warning">${esc(e.message)}</p>`;return;}
    if(!e.cases){$('evaluation-content').innerHTML='<p class="warning">Saved report uses an older format. Run python evaluate.py, then reload this report.</p>';return;}
    const numeric=e.cases.filter(c=>c.numeric_ok!==null), refused=e.cases.filter(c=>c.status==='insufficient_information');
    const cards=[['CASES PASSED',e.passed_cases+'/'+e.case_count,'Handcrafted regression cases'],['NUMERIC CHECKS',numeric.filter(c=>c.numeric_ok).length+'/'+numeric.length,'Explicit expected values'],['EXPECTED REFUSALS',refused.filter(c=>c.status_ok).length+'/'+refused.length,'Out-of-scope queries'],['CITATION LINKAGE',e.cases.filter(c=>c.citation_ok).length+'/'+e.case_count,'IDs resolve; no semantic verification']];
    $('evaluation-content').innerHTML=`${e.stale?'<p class="warning">STALE REPORT: code, data or tests changed since this evaluation. Run python evaluate.py before interpreting these results.</p>':'<div class="report-current">✓ Saved report matches the current engine, data, analysis and evaluation files.</div>'}<div class="kpi-grid">${cards.map(([label,value,note])=>`<article class="kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-sub">${note}</div></article>`).join('')}</div><article class="dash-panel"><div class="panel-heading"><div><div class="eyebrow">REPRODUCIBLE CHECKS</div><h2>Question-level results</h2></div><span class="badge">${e.test_methods} test methods passed</span></div><div class="eval-summary"><span>Median: <b>${e.engine_timing.median_ms} ms</b></span><span>p95: <b>${e.engine_timing.p95_ms} ms</b></span><span>${e.model_calls} model calls</span><span>₹${e.model_cost_inr} model cost</span></div><p class="table-note">${esc(e.engine_timing.note)}</p><p class="warning">${esc(e.evaluation_scope)} Citation linkage checks that answer references resolve; it does not prove the source supports the claim.</p><div class="table-wrap"><table><thead><tr><th>ID / category</th><th>Question</th><th>Expected</th><th>Observed</th><th>Result</th></tr></thead><tbody>${e.cases.map(c=>`<tr><td><strong>${esc(c.id)}</strong><br><small>${esc(c.category)}</small></td><td>${esc(c.question)}</td><td>${c.status==='answered'?'Answer':'Refuse'}</td><td>${c.actual_status==='answered'?'Answer':'Refuse'}</td><td>${statusChip(c.passed?'pass':'fail')}</td></tr>`).join('')}</tbody></table></div><p class="table-note">Saved ${esc(new Date(e.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}))} IST · engine fingerprint ${esc(e.fingerprint.slice(0,12))}…</p><p class="table-note">Reload reads the saved report. To rerun the tests, use python evaluate.py locally.</p></article>`;
  }catch(err){$('evaluation-content').innerHTML=`<p class="error">Evaluation unavailable: ${esc(err.message)}</p>`;}
}
$('bridge-company').onchange=loadChanges;
$('refresh-evaluation').onclick=loadEvaluation;

let currentData=null;
const fmtPrice=n=>n===null||n===undefined?'—':new Intl.NumberFormat('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n);
const pct=n=>n===null||n===undefined?'—':(n>=0?'+':'')+n.toFixed(2)+'%';
const ist=t=>t?new Date(t).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})+' IST':'Not fetched';
const trendLabel=t=>({above_50_and_200:'Above 50 / 200 MA',below_50_and_200:'Below 50 / 200 MA',mixed:'Mixed',insufficient_history:'Insufficient history'}[t]||'Unavailable');
async function loadCurrent(refresh=false){
  const button=$('current-refresh');button.disabled=true;button.textContent=refresh?'Fetching observations…':'Reading snapshot…';
  try{
    const response=await fetch(refresh?'/api/current/refresh':'/api/current',refresh?{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}:{});
    if(!response.ok)throw Error('Market-data service unavailable');
    const payload=await response.json();
    if(response.status===202){marketRefreshTimer=-1;pollMarketRefresh();return;}
    currentData=payload;renderCurrent();
    if(!refresh&&(!currentData.attempted_at||Date.now()-new Date(currentData.attempted_at).getTime()>300000))await loadCurrent(true);
  }catch(error){$('current-status').innerHTML=`<p class="error">${esc(error.message)}. Cached data is not presented as fresh. Try refresh when the connection is available.</p>`;}
  finally{if(!marketRefreshTimer){button.disabled=false;button.textContent='Refresh market data ↻';}}
}
function renderCurrent(){
  const d=currentData;
  const errors=Object.entries(d.errors||{});
  $('current-status').innerHTML=`<span>Last refresh attempt: ${esc(ist(d.attempted_at))} · ${d.series.length}/${d.expected_series} series available · Refresh on view after 5 minutes; manual refresh limited to one batch per minute.</span>${errors.length?'<p class="warning">Provider errors: '+errors.map(([key,value])=>esc(key+': '+value)).join('; ')+'. Retained observations keep their original timestamps.</p>':''}${!d.series.length?'<p class="warning">No market observations yet. Select Refresh market data to fetch the public provider.</p>':''}`;
  $('current-cards').innerHTML=d.series.filter(r=>r.kind!=='equity'||['TCS','INFY','HCLTECH'].includes(r.id)).map(r=>`<article class="kpi"><div class="kpi-label">${esc(r.name)} <span class="quote-state ${r.freshness==='recent_observation'?'recent':'old'}">${r.refresh_error?'REFRESH FAILED':r.freshness==='recent_observation'?'DATED QUOTE':esc(r.freshness.toUpperCase())}</span></div><div class="kpi-value">${r.kind==='equity'?'₹':''}${fmtPrice(r.price)}</div><div class="kpi-sub ${r.day_change_pct>=0?'up':'negative-text'}">${pct(r.day_change_pct)} vs prior daily close</div><div class="quote-time">${esc(ist(r.provider_timestamp))}</div><a class="quote-source" href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer">Yahoo Finance ↗</a></article>`).join('');
  const nifty=d.series.find(r=>r.id==='NIFTY50'), sector=d.series.find(r=>r.id==='NIFTYIT'),vix=d.series.find(r=>r.id==='INDIAVIX');
  $('current-context').innerHTML=[['NIFTY 50 TREND',nifty?trendLabel(nifty.trend):'Unavailable',nifty?'Completed session: '+nifty.completed_session:'No valid benchmark data'],['NIFTY IT / 20 SESSIONS',sector?pct(sector.momentum20_pct):'Unavailable',sector?'Indicator basis: '+sector.price_basis:'No sector observations'],['INDIA VIX',vix?fmtPrice(vix.price)+' index points':'Unavailable',vix?ist(vix.provider_timestamp):'No volatility observation']].map(([label,value,note])=>`<div class="pulse-row"><div><small>${esc(label)}</small><strong>${esc(value)}</strong><p>${esc(note)}</p></div></div>`).join('')+`<p class="pulse-foot">${esc(d.limitations)}</p>`;
  $('current-watchlist').innerHTML=d.series.filter(r=>r.kind==='equity').slice(0,10).map(r=>`<tr><td><strong>${esc(r.name)}</strong><br><small>${esc(r.symbol)}</small></td><td>₹${fmtPrice(r.price)}<br><small>${esc(ist(r.provider_timestamp))}<br>${esc(r.freshness)}</small></td><td>${pct(r.momentum20_pct)}</td><td>${fmtPrice(r.sma50)}</td><td>${fmtPrice(r.sma200)}</td><td>${r.volatility20_pct===null?'—':r.volatility20_pct.toFixed(2)+'%'}</td><td>${r.indicators_stale?'STALE / ':''}${esc(trendLabel(r.trend))}<br><small>Through ${esc(r.completed_session)}</small></td></tr>`).join('')||'<tr><td colspan="7">No current company price observations available.</td></tr>';
  const f=d.fundamentals;
  $('recent-period').textContent=f.period+' · ended '+f.period_end;
  $('recent-results').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Company</th><th>Revenue · ₹ crore</th><th>Revenue YoY · reported INR</th><th>Headline operating margin</th><th>Announcement</th><th>Source & basis</th></tr></thead><tbody>${f.companies.map(c=>`<tr><td>${esc(c.name)}</td><td>${indian(c.revenue)}</td><td>${pct(c.revenue_yoy_pct)}</td><td>${c.reported_margin_pct.toFixed(1)}%</td><td>${esc(c.announced_on)}</td><td>${sourceLink(c.source)}<p class="table-note">${esc(c.basis)}</p></td></tr>`).join('')}</tbody></table></div>`;
  $('recent-status').textContent=(f.needs_review?'REVIEW REQUIRED: disclosure verification is over 120 days old. ':'')+'Manually verified '+f.verified_on+'. '+f.update_method+' Quarterly values must not be compared directly with annual totals. No guarantee that these remain the latest filings after verification.';
  renderCurrentChart();
}
let currentChartRequest=0;
const historyCache=new Map();
async function renderCurrentChart(){
  const request=++currentChartRequest;
  if(!currentData)return;
  const r=currentData.series.find(r=>r.id===$('current-symbol').value);
  if(!r){$('current-chart').innerHTML='<p class="warning">No observations for this instrument. Refresh or choose another.</p>';return;}
  let history=historyCache.get(r.id);
  if(!history||history.retrieved_at!==r.retrieved_at){
    try{history=await api('/api/history/'+encodeURIComponent(r.id));historyCache.set(r.id,history);}
    catch(error){$('current-chart').innerHTML='<p class="warning">History unavailable for this instrument.</p>';return;}
  }
  if(request!==currentChartRequest)return;
  const bars=history.history.slice(-Number($('current-window').value));
  if(bars.length<2){$('current-chart').innerHTML='<p class="warning">Not enough complete daily bars for a chart.</p>';return;}
  const values=bars.map(b=>b.adjusted_close),lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1;
  const points=values.map((v,i)=>(45+i/(values.length-1)*510).toFixed(2)+','+(165-(v-lo)/span*130).toFixed(2)).join(' ');
  $('current-chart').innerHTML=`<div class="current-chart-stat"><strong>${fmtPrice(values.at(-1))}</strong><span>${esc(r.price_basis)} · through ${esc(r.completed_session)}</span></div><svg class="price-chart" viewBox="0 0 600 200" role="img" aria-label="${esc(r.name)} historical daily price chart"><line x1="45" x2="555" y1="35" y2="35" stroke="#e1e9e5"/><line x1="45" x2="555" y1="100" y2="100" stroke="#e1e9e5"/><line x1="45" x2="555" y1="165" y2="165" stroke="#e1e9e5"/><text x="3" y="39" fill="#8a9d96" font-size="9">${fmtPrice(hi)}</text><text x="3" y="169" fill="#8a9d96" font-size="9">${fmtPrice(lo)}</text><polyline points="${points}" fill="none" stroke="#2b7d69" stroke-width="2.5"/><text x="45" y="190" fill="#8a9d96" font-size="9">${esc(bars[0].date)}</text><text x="490" y="190" fill="#8a9d96" font-size="9">${esc(bars.at(-1).date)}</text></svg><p class="chart-caption">${bars.length} complete observations. Price axis is scaled to the displayed range. ${esc(r.kind==='volatility'?'Volatility index points, not percent return.':r.kind==='index'?'Index level; adjusted-price history.':'Provider-adjusted history can differ from the current unadjusted quote.')} ${r.indicators_stale?'HISTORY IS STALE.':''}</p>`;
}
$('current-refresh').onclick=()=>loadCurrent(true);
$('current-symbol').onchange=renderCurrentChart;
$('current-window').onchange=renderCurrentChart;
$('current-review').onclick=()=>ask('Review current Indian markets');

let marketRefreshTimer=null;
async function pollMarketRefresh(){
  if(marketRefreshTimer)clearTimeout(marketRefreshTimer);
  const button=$('current-refresh');button.disabled=true;
  try{
    const job=await api('/api/refresh-status');
    button.textContent=job.state==='running'?`Refreshing ${job.completed}/${job.total}…`:'Refresh market data ↻';
    if(job.state==='running'){
      $('current-status').textContent=`Refreshing ${job.completed}/${job.total} observations; ${job.errors} provider errors so far. Previously cached observations retain their dates.`;
      marketRefreshTimer=setTimeout(pollMarketRefresh,2000);
    }else{
      marketRefreshTimer=null;button.disabled=false;
      if(job.state==='failed')$('current-status').textContent=job.message;
      else await loadCurrent(false);
    }
  }catch(error){marketRefreshTimer=null;button.disabled=false;$('current-status').textContent='Could not check refresh status. Existing cached observations are retained.';}
}
$('view-all-companies').onclick=()=>setView('universe');

async function loadAiStatus() {
  try {
    const state=await api('/api/ai/status');
    aiConfigured=state.configured;
    $('ai-connection-status').textContent=aiConfigured
      ? 'OpenAI brief configured · '+state.model+' · API access not yet verified'
      : 'OpenAI brief: not configured · core research works without a key';
  } catch(error) {
    aiConfigured=false;
    $('ai-connection-status').textContent='OpenAI status unavailable · core research remains available';
  }
}
async function generateBrief() {
  const active=lastResult, button=$('generate-brief'), panel=$('ai-brief-content');
  if(!active || !button || !panel) return;
  button.disabled=true;
  panel.textContent='Preparing a brief from the displayed evidence…';
  try {
    const response=await fetch('/api/brief',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:active.question})});
    const data=await response.json();
    if(lastResult!==active) return;
    if(!response.ok) throw Error(data.error||'Brief unavailable');
    active.ai_brief=data;
    if(data.status!=='generated') {
      panel.innerHTML='<p class="warning">'+esc(data.message)+'</p>';
      return;
    }
    const b=data.brief;
    panel.innerHTML='<p class="ai-brief-notice">'+esc(data.notice)+'</p><p>'+esc(b.summary)+'</p>'
      +'<h4>Observations</h4><ul>'+b.observations.map(o=>'<li>'+esc(o.text)+' '+o.source_ids.map(id=>'<a href="#evidence-'+esc(id)+'">['+esc(id)+']</a>').join(' ')+'</li>').join('')+'</ul>'
      +'<h4>Limitations to carry forward</h4><ul>'+b.limitations.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>'
      +'<h4>Questions for further research</h4><ul>'+b.follow_up_questions.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>'
      +'<p class="table-note">'+esc(data.model)+' · '+data.model_calls+' API request(s) for this click'
      +(data.cached?' · reused cached brief':'')+' · tokens for original generation: '+esc(data.usage.total_tokens??'not reported')+'</p>';
    panel.querySelectorAll('a[href^="#evidence-"]').forEach(a=>a.onclick=()=>{$('evidence-details').open=true;});
  } catch(error) {
    if(lastResult===active) panel.innerHTML='<p class="warning">'+esc(error.message)+'. The verified answer remains available.</p>';
  } finally {
    if(lastResult===active) button.disabled=false;
  }
}
