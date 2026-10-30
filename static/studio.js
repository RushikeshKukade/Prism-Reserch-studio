/* Product workflow: company context, evidence trail and explicitly manual monitors. */
let studioSnapshot=null;
let contextRequest=0;
const MONITOR_KEY='prism-assessment-monitor-rules-v1';
const MONITOR_METRICS={revenue_yoy_pct:'Quarterly revenue growth',reported_margin_pct:'Reported operating margin',momentum20_pct:'20-session price change'};
const STUDIO_VIEWS={
  research:['Ask research','RESEARCH / INDIA','From a question<br>to a clearer view<span>.</span>','Explore what changed, inspect the evidence, and decide what to watch next.'],
  universe:['Trading universes','UNIVERSES / NIFTY 200 & 500','Choose the universe.<br>Check the data<span>.</span>','Build a research shortlist from official constituents, liquidity and data coverage.'],
  current:['Market context','MARKETS / INDIA','The market around<br>your research<span>.</span>','Dated observations provide context. Company evidence stays a separate layer.'],
  dashboard:['Company fundamentals','COMPANIES / HISTORICAL ANALYSIS','Put the numbers<br>in perspective<span>.</span>','Compare annual performance on explicit periods and disclosed accounting bases.'],
  monitors:['Your monitors','MONITORS / LOCAL RULES','Know what you<br>want to watch<span>.</span>','Turn a research question into an explicit, checkable condition.'],
  sources:['Evidence library','EVIDENCE / PRIMARY DISCLOSURES','Follow the answer<br>to its source<span>.</span>','Keep the company, reporting period, announcement and accounting basis together.'],
  quality:['Data health','RESEARCH CONTROLS / HISTORICAL DATA','See the gaps<br>before the conclusion<span>.</span>','Inspect missing metadata, observation age and limits to comparability.'],
  changes:['Explain the change','ANALYSIS / FY2023 TO FY2024','Separate scale<br>from margin<span>.</span>','A reproducible arithmetic breakdown, with no invented business explanation.'],
  evaluation:['Trust & evaluation','RESEARCH CONTROLS / EVALUATION','Test the answer.<br>Show the limits<span>.</span>','Check expected values, unsupported questions, reference linkage and data handling.'],
  method:['Methodology','RESEARCH CONTROLS / METHODOLOGY','Understand what<br>powers the answer<span>.</span>','A small, inspectable research component built for this assessment.']
};
function updateStudioHeading(view){
  const [label,eyebrow,title,description]=STUDIO_VIEWS[view]||STUDIO_VIEWS.research;
  $('view-label').textContent=label;$('page-eyebrow').textContent=eyebrow;
  $('page-title').innerHTML=title;$('page-description').textContent=description;
}
function initStudio(){
  const companies=metadata.universe.companies;
  $('workspace-coverage').innerHTML=`<span>NIFTY 200 / NIFTY 500</span><span>${companies.length} listed securities</span><span>${new Set(companies.map(c=>c.sector)).size} sectors</span><span>Verified filing analysis: ${metadata.data.companies.length} companies</span>`;
  const options=companies.map(c=>`<option value="${esc(c.id)}">${esc(c.name)} (${esc(c.id)})</option>`).join('');
  $('context-company').innerHTML=options;$('context-company').value='INFY';
  $('monitor-company').innerHTML=options;$('monitor-company').value='INFY';
  $('current-symbol').innerHTML='<option value="NIFTY50">NIFTY 50</option><option value="NIFTYIT">NIFTY IT</option><option value="INDIAVIX">India VIX</option>'+options;
  $('universe-nav-count').textContent=companies.length;
  $('universe-sector').innerHTML='<option value="">All sectors</option>'+[...new Set(companies.map(c=>c.sector))].sort().map(sector=>`<option>${esc(sector)}</option>`).join('');
  ['universe-search','universe-sector','universe-coverage-filter','universe-eligibility','universe-sort'].forEach(id=>$(id).addEventListener(id==='universe-search'?'input':'change',()=>{explorerPage=1;renderUniverseExplorer();}));
  $('universe-previous').onclick=()=>{explorerPage=Math.max(1,explorerPage-1);renderUniverseExplorer();};
  $('universe-next').onclick=()=>{explorerPage++;renderUniverseExplorer();};
  $('export-universe').onclick=exportUniverse;
  $('export-research-pack').onclick=exportResearchPack;
  $('universe-index').onchange=()=>{explorerPage=1;updateUniverseSectors();loadUniverseExplorer();};
  $('universe-screen-form').onsubmit=event=>{event.preventDefault();explorerPage=1;loadUniverseExplorer();};
  updateUniverseSectors();
  $('context-company').onchange=loadResearchContext;
  $('monitor-form').onsubmit=saveMonitor;
  $('check-monitors').onclick=loadMonitors;
  updateMonitorCount();
}
async function loadResearchContext(){
  const request=++contextRequest;
  try{
    const d=await api('/api/current');
    if(request!==contextRequest)return;
    studioSnapshot=d;
    const entity=metadata.universe.companies.find(c=>c.id===$('context-company').value);
    const filing=d.fundamentals.companies.find(c=>c.id===entity.id);
    const price=d.series.find(r=>r.id===entity.id);
    const name=filing?.name||entity.name;
    $('research-context-content').innerHTML=`<div class="context-company-line"><span class="company-avatar">${esc(entity.id.slice(0,3))}</span><div><strong>${esc(name)}</strong><small>NSE: ${esc(entity.id)} · ${esc(entity.sector)}</small></div><span class="context-period">${filing?esc(d.fundamentals.period):'Market-data coverage'}</span></div><div class="context-numbers"><div><small>REVENUE · ₹ CRORE</small><strong>${filing?indian(filing.revenue):'—'}</strong><span>${filing?pct(filing.revenue_yoy_pct)+' reported YoY':'Filing not verified'}</span></div><div><small>OPERATING MARGIN</small><strong>${filing?filing.reported_margin_pct.toFixed(1)+'%':'—'}</strong><span>${filing?'Issuer headline measure':'Filing not verified'}</span></div><div><small>PRICE CONTEXT</small><strong>${price?'₹'+fmtPrice(price.price):'Not available'}</strong><span>${price?esc(ist(price.provider_timestamp)):'Refresh in Market context'}</span></div></div><div class="evidence-path"><span>${filing?'Official filing':'Dated price observation'}</span><b>→</b><span>${esc(entity.id)}</span><b>→</b><span>${filing?'Revenue & margin':'Price history'}</span><b>→</b><span>Research question</span></div><div class="context-actions"><button id="context-ask" class="text-button">${filing?'Inspect this quarter’s revenue':'Inspect current price'} ↗</button><button id="context-monitor" class="text-button">Define a monitor ↗</button></div><p class="context-note">${filing?'Quarter ended '+esc(d.fundamentals.period_end)+' · announced '+esc(filing.announced_on)+' · '+esc(filing.basis):'This company has universe membership and market-data coverage only. Its financial-statement figures have not been verified. No operating margin or revenue is estimated.'}</p>`;
    $('context-ask').onclick=()=>ask((filing?'Show latest revenue for ':'Show current price for ')+entity.id);
    $('context-monitor').onclick=()=>{openMonitorBuilder(entity.id);if(!filing)$('monitor-metric').value='momentum20_pct';};
    if(!lastResult){
      if(filing)renderEvidenceStarter(filing,d.fundamentals);
      else $('evidence-tray-content').innerHTML=`<div class="tray-label">SELECTED COMPANY</div><h3>${esc(entity.name)}</h3><p class="tray-review-note">${esc(entity.sector)} · ISIN ${esc(entity.isin)}</p><div class="tray-source"><a href="${esc(metadata.universe.source_url)}" target="_blank" rel="noopener noreferrer">Official constituent list ↗</a><p>Retrieved ${esc(metadata.universe.retrieved_at)}</p></div>${price?`<div class="tray-source"><a href="${esc(price.source_url)}" target="_blank" rel="noopener noreferrer">Dated provider history ↗</a><p>Quote ${esc(ist(price.provider_timestamp))}; complete history through ${esc(price.completed_session)}</p></div>`:''}<div class="tray-gap"><span>FINANCIAL EVIDENCE GAP</span><p>No verified quarterly or annual filing is loaded for this company. A price is not evidence of revenue or operating profitability.</p></div>`;
    }
  }catch(error){$('research-context-content').innerHTML=`<p class="warning">Company context unavailable: ${esc(error.message)}. Historical research remains available.</p>`;}
}
function renderEvidenceStarter(c,f){
  $('evidence-tray-content').innerHTML=`<div class="tray-label">SELECTED COMPANY</div><h3>${esc(c.name)} / ${esc(f.period)}</h3><div class="tray-source">${sourceLink(c.source)}<p>${esc(c.source.locator)}</p></div><dl class="evidence-dates"><dt>Period end</dt><dd>${esc(f.period_end)}</dd><dt>Announced</dt><dd>${esc(c.announced_on)}</dd><dt>Verified</dt><dd>${esc(f.verified_on)}</dd></dl><div class="tray-limitation"><span>ACCOUNTING CONTEXT</span><p>${esc(c.basis)}</p></div><div class="tray-gap"><span>OPEN QUESTION</span><p>Do hiring or other operating signals support this picture? Those feeds are not connected. No inference is made from missing evidence.</p></div>`;
}
function renderEvidenceTrail(result,question){
  const sources=result.evidence||[];
  const review=result.status==='research_review';
  $('evidence-tray-content').innerHTML=`<div class="tray-label">YOUR QUESTION</div><h3>${esc(question)}</h3><div class="answer-status">${sources.length?`${sources.length} linked disclosure${sources.length>1?'s':''}`:review?'Context review · broader references':'Insufficient evidence'}</div>${sources.map(s=>`<div class="tray-source">${sourceLink(s)}<p>${esc(s.locator)}</p><small>Verified ${esc(s.verified_on)}<br>Announced ${esc(s.publication_date||'not recorded')}</small></div>`).join('')}${review?`<p class="tray-review-note">Review references provide context; they are not a claim-by-claim evidence audit.</p>${result.review.references.slice(0,4).map(s=>`<div class="tray-source">${sourceLink(s)}</div>`).join('')}`:''}<div class="tray-limitation"><span>INTERPRETATION LIMIT</span><p>${sources.length?esc(sources[0].basis):review?'Observed conditions are not validated trading performance.':'The assistant has not substituted a supported metric for an unsupported request.'}</p></div><button id="tray-library" class="outline-button">Open evidence library ↗</button>`;
  $('tray-library').onclick=()=>setView('sources');
}
async function loadEvidenceLibrary(){
  const historical=metadata?.data.companies||[];
  let html='<div class="library-group-label">HISTORICAL ANNUAL DISCLOSURES / FY2023–FY2024</div>'+historical.map(c=>evidence({...c.source,rows:c.source_rows,basis:c.basis,verified_on:metadata.data.verified_on})).join('');
  try{
    const d=await api('/api/current');
    const f=d.fundamentals;
    html='<div class="library-group-label">RECENT QUARTERLY DISCLOSURES / '+esc(f.period)+'</div>'+f.companies.map(c=>evidence({...c.source,rows:[`Revenue INR ${c.revenue} crore; reported INR growth ${c.revenue_yoy_pct}% YoY; headline operating margin ${c.reported_margin_pct}%.`],basis:c.basis,verified_on:f.verified_on,publication_date:c.announced_on})).join('')+html;
  }catch(error){html='<p class="warning">Recent disclosures could not be loaded.</p>'+html;}
  $('source-list').innerHTML=html;
}
function readMonitors(){
  try{
    const saved=JSON.parse(localStorage.getItem(MONITOR_KEY)||'[]');
    return Array.isArray(saved)?saved.filter(r=>r&&metadata.universe.companies.some(c=>c.id===r.company)&&Object.hasOwn(MONITOR_METRICS,r.metric)&&['above','below'].includes(r.operator)&&Number.isFinite(r.threshold)&&typeof r.id==='string').slice(0,20):[];
  }catch(error){return [];}
}
function updateMonitorCount(){const count=readMonitors().length;$('monitor-count').textContent=count;}
function openMonitorBuilder(company){
  setView('monitors');
  $('monitor-company').value=metadata.universe.companies.some(c=>c.id===company)?company:'INFY';
  $('monitor-feedback').textContent='Choose the observation and threshold you want to test. No trading rule is inferred from the answer.';
  $('monitor-threshold').focus();
}
async function saveMonitor(event){
  event.preventDefault();
  const rules=readMonitors(), threshold=Number($('monitor-threshold').value);
  if(!Number.isFinite(threshold)||threshold< -100||threshold>1000){$('monitor-feedback').textContent='Enter a threshold between -100 and 1,000.';return;}
  if(rules.length>=20){$('monitor-feedback').textContent='This prototype supports 20 saved rules. Remove one before adding another.';return;}
  const rule={id:crypto.randomUUID(),company:$('monitor-company').value,metric:$('monitor-metric').value,operator:$('monitor-operator').value,threshold};
  try{localStorage.setItem(MONITOR_KEY,JSON.stringify([...rules,rule]));$('monitor-feedback').textContent='Monitor saved in this browser. It runs only when you open or check this view.';updateMonitorCount();await loadMonitors();}
  catch(error){$('monitor-feedback').textContent='Browser storage is unavailable. The rule was not saved.';}
}
function monitorObservation(rule,snapshot){
  if(rule.metric==='momentum20_pct'){
    const row=snapshot.series.find(r=>r.id===rule.company);
    return !row||row.indicators_stale||row.freshness!=='recent_observation'?{available:false,detail:'Price history is missing or stale. Refresh Market context first.'}:{available:Number.isFinite(row.momentum20_pct),value:row.momentum20_pct,detail:'Completed daily session '+row.completed_session,source:row.source_url};
  }
  const row=snapshot.fundamentals.companies.find(c=>c.id===rule.company);
  return !row||snapshot.fundamentals.needs_review?{available:false,detail:'The disclosure is missing or its verification needs review.'}:{available:Number.isFinite(row[rule.metric]),value:row[rule.metric],detail:snapshot.fundamentals.period+' · verified '+snapshot.fundamentals.verified_on,source:row.source.url};
}
async function loadMonitors(){
  const rules=readMonitors();updateMonitorCount();
  $('monitor-summary').textContent=rules.length+' saved rule'+(rules.length===1?'':'s')+' · checked on demand';
  if(!rules.length){$('monitor-list').innerHTML='<div class="monitor-empty"><span>◎</span><h3>A good monitor starts with a clear question.</h3><p>For example: is reported revenue growth above a threshold you choose?<br>Set a company, observation and condition above to get started.</p></div>';return;}
  let snapshot;
  try{snapshot=await api('/api/current');}
  catch(error){$('monitor-list').innerHTML='<p class="warning">Observations unavailable. Your saved rules are retained; no condition has been evaluated.</p>';return;}
  $('monitor-list').innerHTML=rules.map(rule=>{
    const observation=monitorObservation(rule,snapshot);
    const met=observation.available&&(rule.operator==='above'?observation.value>rule.threshold:observation.value<rule.threshold);
    return `<article class="monitor-card"><div class="monitor-card-top"><span class="monitor-company">${esc(rule.company)}</span><span class="monitor-state ${!observation.available?'unknown':met?'met':'not-met'}">${!observation.available?'Needs data':met?'Condition met':'Condition not met'}</span></div><h3>${esc(MONITOR_METRICS[rule.metric])} ${esc(rule.operator)} ${rule.threshold}%</h3><div class="monitor-reading">${observation.available?observation.value.toFixed(2)+'%':'—'}<small>${esc(observation.detail)}</small></div><p class="table-note">This is a condition check, not a buy or sell signal. Equality does not meet a strict above/below rule.</p><div class="monitor-actions">${observation.source?`<a href="${esc(observation.source)}" target="_blank" rel="noopener noreferrer">Inspect source ↗</a>`:''}<button class="text-button" data-remove-monitor="${esc(rule.id)}">Remove rule</button></div></article>`;
  }).join('');
  $('monitor-list').querySelectorAll('[data-remove-monitor]').forEach(button=>button.onclick=async()=>{
    try{localStorage.setItem(MONITOR_KEY,JSON.stringify(readMonitors().filter(r=>r.id!==button.dataset.removeMonitor)));await loadMonitors();}
    catch(error){$('monitor-feedback').textContent='Could not update browser storage.';}
  });
}


let explorerSnapshot=null,explorerPage=1,explorerRequest=0;
const EXPLORER_PAGE_SIZE=25;
function updateUniverseSectors(){
  const u=metadata.universes[$('universe-index').value];
  $('universe-sector').innerHTML='<option value="">All sectors</option>'+[...new Set(u.companies.map(c=>c.sector))].sort().map(sector=>'<option>'+esc(sector)+'</option>').join('');
}
async function loadUniverseExplorer(){
  const request=++explorerRequest;
  explorerSnapshot=null;
  ['universe-coverage','universe-diagnostics','universe-source','universe-warnings','universe-page-label'].forEach(id=>$(id).textContent='');
  $('export-research-pack').disabled=true;
  $('export-universe').disabled=true;
  $('universe-body').innerHTML='<tr><td colspan="7">Checking selected universe…</td></tr>';
  const query=new URLSearchParams({index:$('universe-index').value,min_history:$('screen-history').value,min_price:$('screen-price').value,min_turnover_crore:$('screen-turnover').value});
  try{
    const data=await api('/api/trading-universe?'+query);
    if(request!==explorerRequest)return;
    explorerSnapshot=data;renderUniverseExplorer();$('export-universe').disabled=false;$('export-research-pack').disabled=false;
  }catch(error){
    if(request!==explorerRequest)return;
    explorerSnapshot=null;
    $('universe-body').innerHTML='<tr><td colspan="7">'+esc(error.message)+'</td></tr>';
    $('universe-coverage').innerHTML='';
  }
}
function filteredUniverse(){
  if(!explorerSnapshot)return [];
  const term=$('universe-search').value.trim().toLowerCase(),sector=$('universe-sector').value,coverage=$('universe-coverage-filter').value,eligibility=$('universe-eligibility').value;
  const rows=explorerSnapshot.rows.filter(c=>(!term||(c.name+' '+c.id).toLowerCase().includes(term))&&(!sector||c.sector===sector)&&(!coverage||coverage==='price'&&c.observation||coverage==='missing'&&!c.observation||coverage==='filing'&&c.filing)&&(!eligibility||eligibility==='pass'&&c.screen.eligible||eligibility==='excluded'&&!c.screen.eligible));
  const sort=$('universe-sort').value,metric=sort==='day'?'day_change_pct':sort==='turnover'?'turnover20_crore':'momentum20_pct';
  return rows.sort((a,b)=>sort==='name'?a.name.localeCompare(b.name):((b.observation?.[metric]??-Infinity)-(a.observation?.[metric]??-Infinity)));
}
function renderUniverseExplorer(){
  if(!explorerSnapshot)return;
  const u=explorerSnapshot.universe,c=explorerSnapshot.counts;
  $('universe-coverage').innerHTML=[[c.constituents,u.name+' securities'],[c.price_available,'price observations'],[c.eligible,'pass selected data screen'],[c.verified_filings,'verified quarterly filings']].map(([value,label])=>'<div><strong>'+value+'</strong><span>'+esc(label)+'</span></div>').join('');
  $('universe-warnings').innerHTML=u.warnings.map(w=>'<p class="table-note">'+esc(w)+'</p>').join('');
  const rows=filteredUniverse(),pages=Math.max(1,Math.ceil(rows.length/EXPLORER_PAGE_SIZE));explorerPage=Math.min(explorerPage,pages);
  const start=(explorerPage-1)*EXPLORER_PAGE_SIZE;
  $('universe-body').innerHTML=rows.slice(start,start+EXPLORER_PAGE_SIZE).map(c=>{
    const r=c.observation;
    return '<tr><td><strong>'+esc(c.name)+'</strong><br><small>NSE: '+esc(c.id)+' · '+esc(c.series)+'</small></td><td>'+esc(c.sector)+'</td><td>'+(r?'₹'+fmtPrice(r.price):'Unavailable')+'<br><small>'+(r?esc(ist(r.provider_timestamp)):'No provider observation')+'</small></td><td>'+(r?pct(r.momentum20_pct):'—')+'<br><small>'+(r?'Through '+esc(r.completed_session):'')+'</small></td><td>'+(r?.turnover20_crore!=null?r.turnover20_crore.toFixed(2):'Unavailable')+'<br><small>20 completed observations</small></td><td><span class="coverage-pill '+(c.screen.eligible?'has-price':'missing-price')+'">'+(c.screen.eligible?'Passes data screen':'Excluded / needs data')+'</span><span class="coverage-pill '+(c.filing?'has-filing':'missing-price')+'">'+(c.filing?'Filing verified':'Filing not verified')+'</span><small>'+esc(c.screen.reasons.join('; '))+'</small></td><td><button class="research-button" data-explore-company="'+esc(c.id)+'">Research ↗</button></td></tr>';
  }).join('')||'<tr><td colspan="7">No security matches these filters.</td></tr>';
  $('universe-body').querySelectorAll('[data-explore-company]').forEach(button=>button.onclick=()=>{$('context-company').value=button.dataset.exploreCompany;lastResult=null;$('result').innerHTML='';setView('research');});
  $('universe-page-label').textContent=rows.length?(start+1)+'–'+Math.min(start+EXPLORER_PAGE_SIZE,rows.length)+' of '+rows.length+' securities · page '+explorerPage+'/'+pages:'0 matching securities';
  $('universe-previous').disabled=explorerPage===1;$('universe-next').disabled=explorerPage===pages;
  $('universe-source').innerHTML='Universe: <a href="'+esc(u.source_url)+'" target="_blank" rel="noopener noreferrer">official '+esc(u.name)+' list ↗</a> · retrieved '+esc(ist(u.retrieved_at))+'. '+esc(u.membership_note);
  $('universe-method').textContent=explorerSnapshot.methodology;
  const diag=explorerSnapshot.diagnostics;
  $('universe-diagnostics').innerHTML='<p>'+esc(diag.note)+'</p><h3>Why securities were excluded</h3>'+ (diag.exclusion_reasons.length?'<ul>'+diag.exclusion_reasons.map(r=>'<li>'+r.count+' · '+esc(r.reason)+'</li>').join('')+'</ul>':'<p>No exclusions under the applied settings.</p>')+'<h3>Sector balance before and after screening</h3><div class="table-wrap"><table><thead><tr><th>Sector</th><th>Universe count</th><th>Passed count</th><th>Universe share</th><th>Passed share</th></tr></thead><tbody>'+diag.sector_composition.map(r=>'<tr><td>'+esc(r.sector)+'</td><td>'+r.universe_count+'</td><td>'+r.eligible_count+'</td><td>'+r.universe_pct.toFixed(1)+'%</td><td>'+(r.eligible_pct===null?'—':r.eligible_pct.toFixed(1)+'%')+'</td></tr>').join('')+'</tbody></table></div><p class="table-note">Report fingerprint: '+esc(explorerSnapshot.report_sha256)+'</p>';

}
function exportUniverse(){
  if(!explorerSnapshot)return;
  const rows=filteredUniverse(),u=explorerSnapshot.universe,p=explorerSnapshot.parameters;
  const headers=['Universe','Company','NSE symbol','Series','Sector','ISIN','Price INR','Provider timestamp','20-session change percent','Average traded value 20 observations INR crore','History count','Passes research screen','Exclusion reasons','Minimum history','Minimum price INR','Minimum traded value INR crore','Quarterly filing verified','Constituent retrieved at','Constituent source','Price source'];
  const data=rows.map(c=>{const r=c.observation;return [u.name,c.name,c.id,c.series,c.sector,c.isin,r?.price??'',r?.provider_timestamp??'',r?.momentum20_pct??'',r?.turnover20_crore??'',r?.history_count??'',c.screen.eligible?'yes':'no',c.screen.reasons.join('; '),p.min_history,p.min_price,p.min_turnover_crore,c.filing?'yes':'no',u.retrieved_at,u.source_url,r?.source_url||''];});
  const csv='﻿'+[headers,...data].map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');
  download('prism-'+u.id+'-trading-universe.csv',csv,'text/csv;charset=utf-8');
}

function exportResearchPack(){
  if(!explorerSnapshot)return;
  const d=explorerSnapshot,u=d.universe,rows=filteredUniverse();
  // One file keeps the human-readable brief and complete machine-readable evidence together.
  const lines=['# '+u.name+' research screening brief','',
    'Generated: '+new Date().toISOString(),
    'Purpose: create an inspectable India research shortlist; no buy/sell recommendation.',
    '', '## Applied settings', JSON.stringify(d.parameters),
    '', '## Coverage',`${d.counts.constituents} constituents; ${d.counts.price_available} price observations; ${d.counts.eligible} pass the data screen; ${d.counts.verified_filings} verified filings.`,
    `${rows.length} securities match the current display filters.`,
    '', '## Interpretation',d.diagnostics.note,
    ...d.diagnostics.exclusion_reasons.map(r=>`- ${r.count}: ${r.reason}`),
    '', '## Next research steps',
    '- Inspect excluded securities and provider errors before widening the screen.',
    '- Review sector composition; a liquidity filter can change the sector mix.',
    '- Verify filings for shortlisted companies before making fundamental comparisons.',
    '', '## Sources and limitations',u.source_url,'Retrieved: '+u.retrieved_at,
    'Source SHA-256: '+u.source_sha256,u.membership_note,d.methodology,
    ...(u.warnings||[]),
    '', '## Reproducible evidence',
    'Report SHA-256: '+d.report_sha256,
    'Hash definition: SHA-256 of the UTF-8 bytes of report.canonical_report_json. This original server serialization is preserved to avoid browser number-format changes. Timestamps are part of the evidence.',
    'The JSON below includes all selected-universe rows, applied settings, source metadata, and explicit display filters. It contains no API credentials.',
    '```json',JSON.stringify({report:d,display_filters:{search:$('universe-search').value,sector:$('universe-sector').value,coverage:$('universe-coverage-filter').value,eligibility:$('universe-eligibility').value,sort:$('universe-sort').value},displayed_symbols:rows.map(r=>r.id)},null,2),'```'];
  download('prism-'+u.id+'-research-pack.md',lines.join('\n'),'text/markdown;charset=utf-8');
}
