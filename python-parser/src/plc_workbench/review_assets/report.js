/* All source evidence is inserted with textContent. This application is offline. */
(() => {
  'use strict';
  const PAGE_SIZE = 50;
  // Kept in step with pid_members.FIELD_CATALOG; these are display labels only.
  const PID_MEMBER_LABELS = {
    "SP": "Setpoint",
    "KP": "Proportional term",
    "KI": "Integral term",
    "KD": "Derivative term",
    "BIAS": "Bias",
    "DB": "Deadband",
    "UPD": "Update interval",
    "MAXS": "Upper engineering scale",
    "MINS": "Lower engineering scale",
    "MAXI": "Upper PV input scale",
    "MINI": "Lower PV input scale",
    "MAXCV": "Upper CV scale",
    "MINCV": "Lower CV scale",
    "MINTIE": "Lower tieback scale",
    "MAXTIE": "Upper tieback scale",
    "MAXO": "Upper output limit",
    "MINO": "Lower output limit",
    "SO": "Manual output setting",
    "PV": "Stored process variable",
    "ERR": "Stored error",
    "OUT": "Stored output",
    "TIE": "Stored tieback",
    "PVH": "High PV threshold",
    "PVL": "Low PV threshold",
    "DVP": "Positive deviation threshold",
    "DVN": "Negative deviation threshold",
    "PVDB": "PV alarm deadband",
    "DVDB": "Deviation alarm deadband",
    "CT": "Cascade type flag",
    "CL": "Cascade loop flag",
    "PVT": "PV tracking flag",
    "DOE": "Derivative basis flag",
    "SWM": "Software mode flag",
    "CA": "Control action flag",
    "MO": "Station mode flag",
    "PE": "Equation form flag",
    "NDF": "Derivative smoothing flag",
    "NOBC": "Bias calculation flag",
    "NOZC": "Deadband crossing flag",
    "EN": "Enable flag",
    "INI": "Initialization flag",
    "SPOR": "Setpoint range flag",
    "OLL": "Low output flag",
    "OLH": "High output flag",
    "EWD": "Deadband status flag",
    "DVNA": "Negative deviation alarm flag",
    "DVPA": "Positive deviation alarm flag",
    "PVLA": "Low PV alarm flag",
    "PVHA": "High PV alarm flag",
    "CTL": "Packed control word",
    "DATA": "Internal state array"
  };
  const PID_MEMBER_GROUPS = {
    "setpoint": ["SP"],
    "tuning": ["KP", "KI", "KD", "BIAS", "DB", "UPD"],
    "scaling": ["MAXS", "MINS", "MAXI", "MINI", "MAXCV", "MINCV", "MINTIE", "MAXTIE"],
    "limits": ["MAXO", "MINO"],
    "mode": ["SO", "CT", "CL", "PVT", "DOE", "SWM", "CA", "MO", "PE", "NDF", "NOBC", "NOZC"],
    "process_values": ["PV", "ERR", "OUT", "TIE"],
    "alarms": ["PVH", "PVL", "DVP", "DVN", "PVDB", "DVDB"],
    "status": ["EN", "INI", "SPOR", "OLL", "OLH", "EWD", "DVNA", "DVPA", "PVLA", "PVHA"],
    "internal": ["CTL", "DATA"]
  };
  const data = JSON.parse(document.getElementById('review-data').textContent);
  const inv = data.inventory, refs = data.references, sfc = data.sfc;
  const access = data.access || null;
  const tagData = data.tag_data || null;
  const pid = data.pid || null, pidOccurrences = pid?.occurrences || [];
  const pidMembers = data.pid_members || null;
  const calculations = data.calculations || null, calculationOccurrences = calculations?.occurrences || [];
  const byCalculation = new Map(calculationOccurrences.map(x => [x.id,x]));
  const byCalculationNode = new Map((calculations?.nodes || []).map(x => [x.id,x]));
  const rungCalculations = new Map(), ownerCalculations = new Map();
  const byPidMemberStructure = new Map((pidMembers?.structures || []).map(x => [x.structure_id,x]));
  const byPidMember = new Map((pidMembers?.members || []).map(x => [x.element_id,x]));
  const byPid = new Map(pidOccurrences.map(x => [x.id,x]));
  const byPidOperand = new Map((pid?.operands || []).map(x => [x.id,x]));
  const rungPids = new Map(), ownerPids = new Map();
  const tagContents = tagData?.contents || [], tagElements = tagData?.elements || [];
  const byTagOwner = new Map((tagData?.owners || []).map(x => [x.source_id,x]));
  const byTagContent = new Map(tagContents.map(x => [x.id,x]));
  const byTagElement = new Map(tagElements.map(x => [x.id,x]));
  const tagContentElements = new Map(), tagChildren = new Map(), tagIssues = new Map();
  const accessRoots = access?.roots || [];
  const byOperandAccess = new Map((access?.operands || []).map(x => [x.id, x]));
  const byInstructionAccess = new Map((access?.instructions || []).map(x => [x.id,x]));
  const byRootAccess = new Map(accessRoots.map(x => [x.target_id, x]));
  const accessBindingAdditions = (access?.operands || []).filter(x =>
    x.binding_origin && x.binding_origin !== 'source_references');
  const rungAccessBindings = new Map(), entityAccessBindings = new Map();
  const accessGaps = (access?.instructions || []).filter(x => x.status !== 'classified');
  // A known role is separate from a usable reference. Literal destinations and
  // unresolved roots must remain inspectable even on classified instructions.
  const accessBindingGaps = (access?.operands || []).filter(x =>
    x.role==='read' ? !['root_bound','literal','system_flag'].includes(x.binding_status)
      : ['write','read_write'].includes(x.role) && x.binding_status!=='root_bound');
  const entities = inv.entities || [], rungs = inv.rungs || [], operands = refs.operands || [];
  const elements = sfc.elements || [], patterns = data.patterns || [], findings = data.findings || [];
  const byEntity = new Map(entities.map(x => [x.id, x]));
  const byRung = new Map(rungs.map(x => [x.id, x]));
  const byOperand = new Map(operands.map(x => [x.id, x]));
  const byElement = new Map(elements.map(x => [x.id, x]));
  const byContent = new Map((sfc.contents || []).map(x => [x.id, x]));
  const byPattern = new Map(patterns.map(x => [x.id, x]));
  const byFinding = new Map(findings.map(x => [x.id, x]));
  const bySfcRoutine = new Map((sfc.routines || []).map(x => [x.routine_id, x]));
  const byInstruction = new Map(), rungOperands = new Map(), entityOperands = new Map();
  const entityChildren = new Map(), entityRungs = new Map(), contentElements = new Map();
  const elementChildren = new Map(), contentLinks = new Map(), contentNotes = new Map();
  const elementLinks = new Map(), elementNotes = new Map(), entityAliases = new Map();
  const routinePatterns = new Map(), entityPathCache = new Map();
  function add(map, key, row) { if (!key) return; if (!map.has(key)) map.set(key, []); map.get(key).push(row); }
  tagElements.forEach(x => {add(tagContentElements,x.content_id,x);add(tagChildren,x.parent_id,x);});
  (tagData?.issues || []).forEach(x => add(tagIssues,x.content_id,x));
  entities.forEach(x => add(entityChildren, x.parent_id, x));
  rungs.forEach(r => { add(entityRungs, r.parent_id, r); (r.instructions || []).forEach(i => byInstruction.set(i.id, {instruction:i,rung:r})); });
  operands.forEach(o => {
    add(rungOperands, o.rung_id, o);
    new Set([o.symbol_id, o.target_id, ...(o.alias_chain || [])]).forEach(id => add(entityOperands,id,o));
  });
  // Preserve the original reference index. New access bindings form a separate
  // evidence layer; inherited bindings must not duplicate declaration links.
  accessBindingAdditions.forEach(a => {
    add(rungAccessBindings,a.rung_id,a);
    new Set([a.symbol_id,a.target_id,...(a.alias_chain || [])]).forEach(id=>add(entityAccessBindings,id,a));
  });
  pidOccurrences.forEach(p => {
    add(rungPids,p.rung_id,p);
    const first=byOperand.get(p.operand_ids[0]);
    new Set([first?.symbol_id,first?.target_id,p.backing_owner_id]).forEach(id=>add(ownerPids,id,p));
  });
  calculationOccurrences.forEach(c => {
    add(rungCalculations,c.rung_id,c);
    // Keep each occurrence once per declaration, even when several leaves name it.
    const bindings=[byOperand.get(c.destination_operand_id),...c.node_ids.map(id=>byCalculationNode.get(id)?.binding)];
    const owners=new Set();
    bindings.filter(Boolean).forEach(b=>[b.symbol_id,b.target_id,...(b.alias_chain || [])].forEach(id=>{if(id)owners.add(id);}));
    owners.forEach(id=>add(ownerCalculations,id,c));
  });
  (refs.aliases || []).forEach(a => new Set([a.source_id,a.target_id]).forEach(id => add(entityAliases,id,a)));
  elements.forEach(x => { add(contentElements,x.content_id,x); add(elementChildren,x.parent_id,x); });
  (sfc.links || []).forEach(x => { add(contentLinks,x.content_id,x); new Set([x.from_element_id,x.to_element_id,x.element_id]).forEach(id => add(elementLinks,id,x)); });
  (sfc.annotations || []).forEach(x => { add(contentNotes,x.content_id,x); new Set([x.from_element_id,x.to_element_id,x.element_id]).forEach(id => add(elementNotes,id,x)); });
  patterns.forEach(p => (p.rung_ids || []).forEach(id => routinePatterns.set(id,p)));
  const headings = {
    overview:['Review overview','Explore the captured source, follow its references, and identify evidence that needs engineering review.'],
    objects:['Objects & references','Search declarations and inspect their attributes, aliases and exact source occurrences.'],
    ladder:['Ladder source','Read each captured rung, its parsed instructions and the status of its operand bindings.'],
    sfc:['Sequence structure','Inspect SFC source elements, transition text and authored notes within each captured content version.'],
    patterns:['Ladder patterns','Compare repeated syntax shapes. Matching opcode and branch structure does not establish equivalent behavior.'],
    findings:['Review findings','Trace capture and binding gaps to their source evidence. This queue is not an assessment of process safety.']
  };
  headings.access=['Tag access','Find explicit operand reads and writes from supported ladder signatures. These are possible uses, not proof that an instruction executes.'];
  headings.tagdata=['Stored tag data','Search values and member names retained in this export, then follow their declaration and ladder occurrences.'];
  headings.pid=['PID instruction evidence','Inspect captured PID operand functions, source declarations and stored data. Each row is an instruction occurrence.'];
  headings.calculations=['Calculations','Read captured CPT expressions, their syntax grouping and source references. Expressions are not evaluated.'];
  const navCounts = {objects:entities.length,ladder:rungs.length,sfc:bySfcRoutine.size,patterns:patterns.length,findings:findings.length};
  const labels = {overview:'Overview',objects:'Objects',ladder:'Ladder',sfc:'SFC',patterns:'Patterns',findings:'Findings'};
  if(access){labels.access='Tag access';navCounts.access=accessRoots.length;}
  if(tagData){labels.tagdata='Stored tag data';navCounts.tagdata=tagContents.length;}
  if(pid){labels.pid='PID evidence';navCounts.pid=pidOccurrences.length;}
  if(calculations){labels.calculations='Calculations';navCounts.calculations=calculationOccurrences.length;}
  let state = {view:'overview',query:'',filter:'all',detail:null,contentId:null,listPages:{}};
  const backStack = [];
  const heading = document.getElementById('page-heading');
  const toolbar = document.getElementById('toolbar');
  const content = document.getElementById('content');
  function node(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className=cls; if (text !== undefined && text !== null) n.textContent=String(text); return n; }
  function button(text, action, cls='') { const n=node('button',cls,text); n.type='button'; n.addEventListener('click',action); return n; }
  function fmt(n) { return Number(n || 0).toLocaleString('en-US'); }
  function human(v) { return String(v || 'unknown').replace(/_/g,' '); }
  function short(v, max=120) { const s=String(v ?? ''); return s.length>max ? s.slice(0,max-1)+'…' : s; }
  function badge(v) {
    const good=['complete','parsed','resolved','root_bound','literal','non_data','system_flag','info','read','write','read_write','classified','initialization_field'].includes(v);
    const bad=['error','malformed','ambiguous','alias_cycle'].includes(v);
    return node('span','badge '+(good?'good':bad?'bad':'warn'),human(v));
  }
  function sourceText(value, prose=false) { return node('pre','source-text'+(prose?' note':''),value ?? 'No text captured.'); }
  function link(text, id, cls='') { return button(text,() => openSource(id),'text-link '+cls); }
  function empty(title='No matching records', detail='Try a different search or filter.') {
    const n=node('div','empty'); n.append(node('strong','',title),node('p','',detail)); return n;
  }
  function panel(title,intro) { const p=node('section','panel'); p.append(node('h2','',title)); if(intro) p.append(node('p','panel-intro',intro)); return p; }
  function section(title, intro) { const s=node('section','section'); s.append(node('h2','',title)); if(intro) s.append(node('p','panel-intro',intro)); return s; }
  function values(record) { const dl=node('dl','key-values'); Object.entries(record || {}).forEach(([k,v]) => { dl.append(node('dt','',k),node('dd','',v === null || v === undefined ? 'Not present' : typeof v==='object' ? JSON.stringify(v) : v)); }); return dl; }
  function technical(record) { const d=node('details','technical'); d.append(node('summary','','Source identifiers & location'),values(record)); return d; }
  function entityName(id) { const e=byEntity.get(id); return e ? e.name || '(unnamed '+human(e.kind)+')' : 'Unknown owner'; }
  function entityPath(id) {
    if (entityPathCache.has(id)) return entityPathCache.get(id);
    // Display paths are bounded previews. Full names remain in object evidence.
    // Sharing huge ancestor strings across thousands of search rows would
    // otherwise multiply a bounded source into unbounded browser allocations.
    const names=[], seen=new Set(); let e=byEntity.get(id);
    while(e && !seen.has(e.id) && names.length<8){seen.add(e.id); names.unshift(short(e.name || human(e.kind),80)); e=byEntity.get(e.parent_id);}
    if(e)names.unshift('…');
    const result=names.join(' / '); entityPathCache.set(id,result); return result;
  }
  function rungName(r) { return 'Rung '+short(r.number ?? String(r.ordinal),30)+' · '+short(entityName(r.parent_id),100); }
  function elementName(e) { return e.attributes?.Name || e.attributes?.Operand || human(e.kind)+(e.attributes?.ID !== undefined ? ' '+e.attributes.ID : ''); }
  function sourceName(id) {
    if(byEntity.has(id)) return short(entityName(id));
    if(byRung.has(id)) return rungName(byRung.get(id));
    if(byOperand.has(id)){const o=byOperand.get(id);return short(o.raw_text,60)+' · argument '+(o.argument_index+1);}
    if(byInstruction.has(id)) return byInstruction.get(id).instruction.opcode+' instruction';
    if(byElement.has(id)) return short(elementName(byElement.get(id)));
    if(byContent.has(id)) return short(entityName(byContent.get(id).routine_id))+' · SFC content';
    if(byTagContent.has(id)){const c=byTagContent.get(id);return short(entityName(c.owner_id))+' · '+tagContentName(c);}
    if(byTagElement.has(id))return tagElementName(byTagElement.get(id));
    return 'Source context';
  }
  function sourceCell(id) { return id && (byEntity.has(id)||byRung.has(id)||byOperand.has(id)||byInstruction.has(id)||byElement.has(id)||byContent.has(id)||byTagContent.has(id)||byTagElement.has(id)) ? link(sourceName(id),id) : node('span','muted','No direct source link'); }
  function primary(main,secondary) { const d=node('div'); d.append(main instanceof Node?main:node('div','cell-main',main)); if(secondary)d.append(node('div','cell-sub',secondary)); return d; }
  function accessLabel(o) { const a=byOperandAccess.get(o.id); return ['timer_pseudo_operand','counter_pseudo_operand'].includes(a?.reason)?'initialization_field':a?.role || 'unknown'; }
  function accessCell(o) { return badge(accessLabel(o)); }
  function bindingRoots(binding,reason) {
    const roots=node('div','inline-links');
    if(binding.symbol_id)roots.append(sourceCell(binding.symbol_id));
    if(binding.target_id && binding.target_id!==binding.symbol_id)roots.append(node('span','','→'),sourceCell(binding.target_id));
    if(!roots.childNodes.length)roots.append(node('span','muted',human(reason || 'No root binding')));
    return roots;
  }
  function accessBindingOrigin(a) {
    return {source_references:'Original reference analysis',access_resolver:'Instruction access analysis',access_non_data:'Instruction selector or initialization field'}[a.binding_origin] || 'Original reference analysis';
  }
  function accessBindingTable(rows,caption) {
    const result=node('div');
    result.append(table(['Operand','Instruction / argument','Role','Access binding','Declared / resolved root','Resolved suffix'],rows,a=>{
      const o=byOperand.get(a.id);
      return [link(o.raw_text || '(blank)',o.id),
        (byInstruction.get(a.instruction_id)?.instruction.opcode || 'Instruction')+' · '+(a.argument_index+1),
        accessCell(a),primary(badge(a.binding_status),accessBindingOrigin(a)+(a.binding_reason?' · '+human(a.binding_reason):'')),
        bindingRoots(a,a.binding_reason),node('span','mono',a.suffix || (a.target_id?'(root operand)':'—'))];
    },caption));
    const opcodes=new Set(rows.map(a=>byInstruction.get(a.instruction_id)?.instruction.opcode.toUpperCase()));
    if(opcodes.has('CTU') || opcodes.has('CTD'))result.append(node('p','row-note','Counter preset and accumulator fields describe initialization, not separate runtime reads. A question mark supplies no value. Counter values and configuration are not validated.'));
    if(opcodes.has('MSG'))result.append(node('p','row-note','MSG covers possible reads and writes of its control operand only. Message payload sources, destinations and communication effects are not modeled.'));
    if(opcodes.has('GSV') || opcodes.has('SSV'))result.append(node('p','row-note','GSV/SSV class, instance and attribute selectors are not tag bindings. A blank instance is allowed; system state and the selected attribute are not validated.'));
    if(opcodes.has('SFR'))result.append(node('p','row-note','SFR records a possible write to an explicit step, or an initial-step selector of 0. SFC membership and wider reset effects are not validated.'));
    return result;
  }
  function roleIds(root,role) { return root[role+'_operand_ids'] || []; }
  const accessRoles=['read','write','read_write','unknown'];
  function table(headers, rows, rowFn, caption, options={}) {
    const pageKey=(state.detail?state.detail.type+':'+state.detail.id+':'+(state.contentId||''):state.view)+':'+caption;
    const wrap=node('div'); let page=Math.min(state.listPages[pageKey]||0,Math.max(0,Math.ceil(rows.length/PAGE_SIZE)-1));
    const render=() => {
      wrap.replaceChildren();
      if(!rows.length){wrap.append(empty(options.emptyTitle || 'No records in this section',options.emptyDetail || 'Nothing was captured for this selection.'));return;}
      const box=node('div','table-wrap'), t=node('table');
      const c=node('caption','visually-hidden',caption); t.append(c);
      const head=node('thead'), hr=node('tr'); headers.forEach(h=>{const th=node('th','',h);th.scope='col';hr.append(th);});head.append(hr);t.append(head);
      const body=node('tbody'); rows.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE).forEach((row,index)=>{const tr=node('tr');rowFn(row,page*PAGE_SIZE+index).forEach(value=>{const td=node('td');td.append(value instanceof Node ? value : node('span','',value ?? '—'));tr.append(td);});body.append(tr);});
      t.append(body);box.append(t);wrap.append(box);
      const pager=node('div','pager'); const status=node('span','',fmt(page*PAGE_SIZE+1)+'–'+fmt(Math.min((page+1)*PAGE_SIZE,rows.length))+' of '+fmt(rows.length)+' records');status.setAttribute('role','status');
      const actions=node('div','pager-buttons');
      const change=(delta)=>{page+=delta;state.listPages[pageKey]=page;render();const next=wrap.querySelector(delta>0?'[data-next]':'[data-prev]');if(next && !next.disabled)next.focus();else wrap.querySelector('table').focus();};
      t.tabIndex=-1;
      const prev=button('Previous',()=>change(-1));prev.disabled=page===0;prev.dataset.prev='';prev.setAttribute('aria-label','Previous page: '+caption);
      const next=button('Next',()=>change(1));next.disabled=(page+1)*PAGE_SIZE>=rows.length;next.dataset.next='';next.setAttribute('aria-label','Next page: '+caption);
      actions.append(prev,node('span','','Page '+(page+1)+' / '+Math.ceil(rows.length/PAGE_SIZE)),next);pager.append(status,actions);wrap.append(pager);
    }; render();return wrap;
  }
  function openDetail(type,id,extra={}) { backStack.push({...state});state={...state,detail:{type,id},focusOperand:null,focusInstruction:null,...(type==='pid'?{pidMemberQuery:'',pidMemberGroup:'all'}:{}),...extra};render(true); }
  function openSource(id) {
    if(byTagContent.has(id)){openDetail('tagcontent',id);return;}
    if(byTagElement.has(id)){openDetail('tagelement',id);return;}
    if(byOperand.has(id)){const o=byOperand.get(id);openDetail('rung',o.rung_id,{focusOperand:id});}
    else if(byInstruction.has(id))openDetail('rung',byInstruction.get(id).rung.id,{focusInstruction:id});
    else if(byEntity.has(id))openDetail('entity',id);
    else if(byRung.has(id))openDetail('rung',id);
    else if(byElement.has(id))openDetail('element',id);
    else if(byContent.has(id)){const c=byContent.get(id);openDetail('sfc',c.routine_id,{contentId:id});}
  }
  function go(view) { backStack.length=0;state={view,query:'',filter:'all',detail:null,contentId:null,listPages:{}};render(true); }
  function goBack() { if(backStack.length){state=backStack.pop();render(true);} }
  const searchIndex = new Map();
  function searchable(row, words) { searchIndex.set(row,words.join(' ').toLocaleLowerCase()); }
  entities.forEach(e=>searchable(e,[e.name,e.kind,e.description,entityPath(e.parent_id),...Object.values(e.attributes || {})]));
  rungs.forEach(r=>searchable(r,[r.number,r.text,r.comment,r.parse_status,entityPath(r.parent_id)]));
  patterns.forEach(p=>searchable(p,[p.shape,...(p.opcode_summary||[]).map(o=>o.opcode)]));
  findings.forEach(f=>searchable(f,[f.code,f.message,f.origin,f.severity,f.locator,sourceName(f.source_id)]));
  accessRoots.forEach(r=>searchable(r,[entityName(r.target_id),entityPath(r.target_id)]));
  accessGaps.forEach(i=>searchable(i,[i.opcode,i.status,sourceName(i.rung_id)]));
  accessBindingGaps.forEach(o=>searchable(o,[byOperand.get(o.id)?.raw_text,o.role,o.binding_status,sourceName(o.rung_id)]));
  // Index each data record once, never concatenating a whole descendant tree.
  tagContents.forEach(c=>searchable(c,[short(entityName(c.owner_id)),c.xml_name,c.format_kind,c.direct_text,...Object.values(c.attributes||{})]));
  tagElements.forEach(e=>searchable(e,[short(entityName(e.owner_id)),e.xml_name,e.kind,e.direct_text,...Object.values(e.attributes||{})]));
  pidOccurrences.forEach(p=>searchable(p,[p.signature_status,p.storage_status,sourceName(p.rung_id),entityPath(byRung.get(p.rung_id)?.parent_id),...p.operand_ids.map(id=>byOperand.get(id)?.raw_text)]));
  calculationOccurrences.forEach(c=>searchable(c,[c.signature_status,c.syntax_status,c.error_code,sourceName(c.rung_id),entityPath(byRung.get(c.rung_id)?.parent_id),byOperand.get(c.destination_operand_id)?.raw_text,byOperand.get(c.expression_operand_id)?.raw_text]));
  // Index a member once even when several PID occurrences share its structure.
  (pidMembers?.members || []).forEach(m=>searchable(m,[m.field,pidMemberLabel(m.field),m.group,m.status,byTagElement.get(m.element_id)?.attributes?.Name]));
  const sfcSearch = new Map();elements.forEach(e=>add(sfcSearch,e.routine_id,[e.kind,e.direct_text,...Object.values(e.attributes||{})].join(' ')));
  (sfc.routines || []).forEach(r=>searchable(r,[entityPath(r.routine_id),...(sfcSearch.get(r.routine_id)||[])]));
  function matches(row) { return !state.query || (searchIndex.get(row)||'').includes(state.query.toLocaleLowerCase()); }
  function toolbarFor(placeholder, filterOptions=[]) {
    const box=node('div','toolbar'), search=node('div','search-wrap'), input=node('input');
    input.type='search';input.id='review-search';input.placeholder=placeholder;input.value=state.query;input.setAttribute('aria-label',placeholder);input.autocomplete='off';
    input.addEventListener('input',()=>{state.query=input.value;state.listPages={};renderList();});search.append(input,node('kbd','','Ctrl K'));box.append(search);
    if(filterOptions.length){const label=node('label','filter-wrap','Filter');const select=node('select');select.setAttribute('aria-label','Filter '+labels[state.view]);filterOptions.forEach(([value,title])=>{const option=node('option','',title);option.value=value;select.append(option);});select.value=state.filter;select.addEventListener('change',()=>{state.filter=select.value;state.listPages={};renderList();});label.append(select);box.append(label);}
    toolbar.append(box);
  }
  function countsFilter(rows,key) { const m=new Map();rows.forEach(r=>m.set(r[key],(m.get(r[key])||0)+1));return [['all','All types'],...Array.from(m).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))).map(([k,v])=>[k,human(k)+' ('+fmt(v)+')'])]; }
  function notice(title,text){const n=node('div','notice');const body=node('div');body.append(node('strong','',title),node('div','',text));n.append(node('span','notice-icon','i'),body);return n;}
  function overview() {
    content.append(notice('A source review, ready for engineering interpretation',access
      ? 'Supported ladder operand roles now identify possible reads and writes. Root grouping does not establish member overlap, execution, shutdown effects, alarm priority or sequence behavior.'
      : 'Browse captured evidence and follow exact references. Root bindings do not validate members or establish reads, writes, shutdown effects, alarm priority or sequence behavior.'));
    const cards=node('div','cards');
    [[entities.length,'Source objects',fmt(refs.symbols?.length)+' reference symbols'],[rungs.length,'Ladder rungs',fmt(data.statistics.parsed_rungs)+' parsed syntax trees'],[patterns.length,'Syntax patterns',fmt(data.statistics.repeated_pattern_groups)+' repeated group'+(data.statistics.repeated_pattern_groups===1?'':'s')],[findings.length,'Review findings','Capture and binding gaps']].forEach(([n,title,hint])=>{const card=node('div','metric');card.append(node('div','metric-label',title),node('div','metric-value',fmt(n)),node('div','metric-hint',hint));cards.append(card);});content.append(cards);
    const grid=node('div','grid-two'), capture=panel('Capture at a glance','Status applies to each capture scope. A complete structural result does not mean complete engineering analysis.');
    [['Source inventory',inv.status],['Reference bindings',refs.status],['SFC structure & annotations',sfc.status]].forEach(([title,status])=>{const row=node('div','status-row');row.append(node('span','',title),badge(status));capture.append(row);});
    if(access){const row=node('div','status-row');row.append(node('span','','Explicit ladder operand roles'),badge(access.status));capture.append(row);}
    if(tagData){const row=node('div','status-row');row.append(node('span','','Stored tag data capture'),badge(tagData.status));capture.append(row);}
    if(pid){const row=node('div','status-row');row.append(node('span','','PID operand and storage association'),badge(pid.status));capture.append(row);}
    if(pidMembers){const row=node('div','status-row');row.append(node('span','','PID documented member headers'),badge(pidMembers.status));capture.append(row);}
    if(calculations){const row=node('div','status-row');row.append(node('span','','CPT expression syntax and references'),badge(calculations.status));capture.append(row);}
    capture.append(node('p','row-note',fmt(bySfcRoutine.size)+' SFC routines · '+fmt((sfc.links||[]).length)+' structural links · '+fmt((sfc.annotations||[]).length)+' note attachments'));
    const start=panel('Start your review','Each view links back to the exact evidence in this captured source snapshot.');
    [['objects','Find an object','Inspect declarations, source descriptions and where operands refer to them.'],['patterns','Compare repeated ladder','Group repeated syntax and open each occurrence in its own context.'],['findings','Work through capture gaps','Inspect unresolved and unsupported evidence before choosing a correction.']].forEach(([view,title,detail])=>{const b=button('',()=>go(view),'jump-card');const copy=node('span');copy.append(node('strong','',title),node('small','',detail));b.append(copy,node('span','jump-arrow','→'));start.append(b);});
    grid.append(capture,start);content.append(grid);
    if(access)content.append(button('Explore tag reads and writes',()=>go('access')));
    if(tagData)content.append(button('Explore stored tag data',()=>go('tagdata')));
    if(pid)content.append(button('Explore PID instruction evidence',()=>go('pid')));
    if(calculations)content.append(button('Explore calculations',()=>go('calculations')));
    const meta=panel('Snapshot details','This report is read-only. IDs belong to this byte snapshot and are not persistent equipment or correction identities.');
    meta.append(values({'Source size':fmt(data.snapshot.size_bytes)+' bytes','SHA-256':data.snapshot.sha256,'Report format':data.report_version,'Inventory parser':inv.parser_version,'Reference analyzer':refs.analyzer_version,'SFC analyzer':sfc.analyzer_version}));content.append(meta);
  }
  function objectList(){const rows=entities.filter(e=>matches(e)&&(state.filter==='all'||e.kind===state.filter));content.append(table(['Object','Type','Scope','Description'],rows,e=>[primary(link(e.name || '(unnamed)',e.id),e.attributes?.DataType),human(e.kind),entityPath(e.scope_id),short(e.description || 'No description captured.')],'Source objects',{emptyTitle:'No objects match your search',emptyDetail:'Search by name, scope, description or attribute value.'}));}
  function accessNotice() {
    return notice('Explicit operand uses only','Reads and writes describe possible uses of supported ladder operand slots. Rung conditions, scan order, implicit status flags, SFC/ST code and unsupported instructions are not modeled. A shared root does not prove that members or array elements overlap. Missing accesses do not establish that a tag is unused or read-only.'+(access.schema_version>=2?' Timer initialization fields are not runtime inputs; their values are not validated. Copy roles identify starting operands and length use, not the copied range or overlap.':'')+(access.schema_version>=3?' Counter initialization fields are also not runtime inputs. MSG covers its control operand only; message payloads are not modeled. GSV/SSV class, instance and attribute selectors are not tag bindings; a blank instance is allowed. SFR records a possible write to an explicit step, or an initial-step selector of 0; SFC membership and wider reset effects are not validated.':''));
  }
  function accessList() {
    content.append(accessNotice());
    const c=access.coverage;
    const totals=panel('Access coverage','Counts describe captured operand slots, not execution frequency or migration completeness.');
    totals.append(values({'Classified instructions':c.instructions_by_status.classified,
      'Instructions with unknown roles':accessGaps.length,'Operand slots':c.operands_total,
      'Root-linked operand slots':c.linked_operands,'Known access roles without usable bindings':c.access_gap_operands,
      'Unparsed rungs':c.unparsed_rungs}));
    if(access.schema_version>=2)totals.append(values({'Classified timer instructions':c.timer_instructions,
      'Timer initialization placeholders':c.timer_pseudo_operands_by_kind.placeholder,
      'Timer integer initialization fields':c.timer_pseudo_operands_by_kind.integer_literal}));
    if(access.schema_version>=3)totals.append(values({'Classified counter instructions':c.extended_instructions.counter,
      'Classified MSG control operands':c.extended_instructions.message,
      'Classified GSV instructions':c.extended_instructions.system_get,
      'Classified SSV instructions':c.extended_instructions.system_set,
      'Classified SFR target operands':c.extended_instructions.sfc_reset_step,
      'Classified SFR initial-step selectors':c.extended_instructions.sfc_reset_initial,
      'Counter initialization placeholders':c.counter_pseudo_operands_by_kind.placeholder,
      'Counter integer initialization fields':c.counter_pseudo_operands_by_kind.integer_literal,
      'Counter instructions with invalid initialization forms':c.counter_invalid_forms,
      'Root bindings from additional instruction analysis':c.extended_bound_operands}));
    content.append(totals);
    const rows=accessRoots.filter(matches);
    const roots=section('Resolved tag roots','Read/write is a separate category; it is not counted twice. Open a count to inspect its exact operands and suffixes.');
    roots.append(table(['Root','Scope','Read','Write','Read/write','Unknown'],rows,r=>[
      link(entityName(r.target_id),r.target_id),entityPath(byEntity.get(r.target_id)?.scope_id),
      ...accessRoles.map(role=>button(fmt(roleIds(r,role).length),()=>openDetail('access',r.target_id,{accessRole:role}),'text-link'))
    ],'Root access groups'));content.append(roots);
    const bindingGaps=section('Known roles with unresolved access','A known instruction role does not make its operand a valid tag reference. These slots are excluded from the resolved-root groups.');
    bindingGaps.append(table(['Operand','Role','Binding','Rung'],accessBindingGaps.filter(matches),a=>[
      sourceCell(a.id),badge(a.role),badge(a.binding_status),sourceCell(a.rung_id)
    ],'Unresolved operand accesses',{emptyTitle:'No unresolved access slots match',emptyDetail:'Unknown instruction roles are listed separately below.'}));content.append(bindingGaps);
    const gaps=section('Instructions with unknown roles','These instructions may access data even when the reference parser cannot link their operands. Zero-argument instructions remain visible. Search also matches opcode and rung context.');
    gaps.append(table(['Instruction','Rung','Access classification'],accessGaps.filter(matches),i=>[
      link(i.opcode,i.id),sourceCell(i.rung_id),badge(i.status)
    ],'Unclassified access instructions',{emptyTitle:'No unclassified instructions match',emptyDetail:'This does not cover uncaptured logic, implicit effects or languages outside ladder.'}));content.append(gaps);
  }
  function accessDetail(root) {
    setDetailHeading('ROOT ACCESS',entityName(root.target_id),entityPath(byEntity.get(root.target_id)?.parent_id));
    content.append(accessNotice(),sourceCell(root.target_id));
    const box=node('div','toolbar'),label=node('label','filter-wrap','Operand role'),select=node('select');
    select.setAttribute('aria-label','Access operand role');
    [['all','All roles'],...accessRoles.map(r=>[r,human(r)])].forEach(([v,t])=>{const o=node('option','',t);o.value=v;select.append(o);});
    select.value=state.accessRole || 'all';select.addEventListener('change',()=>{state.accessRole=select.value;render();});label.append(select);box.append(label);content.append(box);
    const roles=state.accessRole && state.accessRole!=='all'?[state.accessRole]:accessRoles;
    const rows=roles.flatMap(role=>roleIds(root,role)).map(id=>byOperandAccess.get(id)).filter(Boolean);
    content.append(table(['Operand','Role','Rung','Instruction / argument','Declared / resolved root','Resolved suffix','Binding analysis'],rows,a=>[
      link(byOperand.get(a.id).raw_text,a.id),accessCell(a),sourceCell(a.rung_id),
      (byInstruction.get(a.instruction_id)?.instruction.opcode||'Instruction')+' · '+(a.argument_index+1),
      bindingRoots(a,a.binding_reason),node('span','mono',a.suffix || '(root operand)'),accessBindingOrigin(a)
    ],'Root access occurrences'));
  }
  function rungList(rows=rungs.filter(r=>matches(r)&&(state.filter==='all'||r.parse_status===state.filter))){return table(['Rung','Routine / scope','Source preview','Parse status'],rows,r=>[link('Rung '+(r.number??r.ordinal),r.id),entityPath(r.parent_id),node('div','snippet',short(r.text,180)),badge(r.parse_status)],'Ladder rungs');}
  function objectDetail(e){
    setDetailHeading('SOURCE OBJECT',e.name || '(unnamed '+human(e.kind)+')',entityPath(e.parent_id));
    const meta=node('div','detail-meta');meta.append(badge(e.kind));if(e.attributes?.DataType)meta.append(badge(e.attributes.DataType));content.append(meta);
    const description=panel('Source description');description.append(sourceText(e.description,true));content.append(description);
    const attributes=panel('Declaration attributes');attributes.append(values(e.attributes));content.append(attributes);
    if(byTagOwner.has(e.id)){
      const stored=section('Stored tag data','Each exported representation is retained separately. Values are not validated or selected as effective runtime settings.');
      const rows=byTagOwner.get(e.id).content_ids.map(id=>byTagContent.get(id)).filter(Boolean);
      if(rows.length)stored.append(tagContentTable(rows,'Object stored data'));
      else stored.append(empty('No Data or DefaultData captured on this declaration','Absence in this export does not supply a zero, default or inherited value. For aliases, inspect the resolved declaration separately.'));
      content.append(stored);
    }
    if(bySfcRoutine.has(e.id))content.append(button('Open SFC structure',()=>openDetail('sfc',e.id)));
    const ownRungs=entityRungs.get(e.id)||[];if(ownRungs.length){const p=section('Routine ladder');p.append(rungList(ownRungs));content.append(p);}
    const child=entityChildren.get(e.id)||[];if(child.length){const p=section('Child declarations');p.append(table(['Object','Type','Description'],child,x=>[link(x.name || '(unnamed)',x.id),human(x.kind),short(x.description || '')],'Child declarations'));content.append(p);}
    const aliases=entityAliases.get(e.id)||[];if(aliases.length){const p=section('Alias bindings','Declared alias targets and root-resolution results; suffixes have not been validated.');p.append(table(['Alias','Declared target','Binding','Resolved root'],aliases,a=>[sourceCell(a.source_id),node('span','mono',a.raw_target),badge(a.status),sourceCell(a.target_id)],'Alias bindings'));content.append(p);}
    if(byRootAccess.has(e.id))content.append(button('Inspect root access occurrences',()=>openDetail('access',e.id,{accessRole:'all'})));
    if(ownerPids.has(e.id)){const p=section('PID instruction occurrences','These occurrences name this declaration or resolve to it. Storage association may remain unresolved.');p.append(pidTable(ownerPids.get(e.id),'Object PID occurrences'));content.append(p);}
    if(ownerCalculations.has(e.id)){const p=section('Calculation occurrences','This declaration appears in a destination binding or a parsed expression reference, directly or through an alias. These links do not establish execution or data dependencies.');p.append(calculationTable(ownerCalculations.get(e.id),'Object calculation occurrences'));content.append(p);}
    const p=section(access?.schema_version>=3?'Original reference occurrences':'Operand occurrences',access
      ? 'Occurrences include the declared root, resolved target and traversed alias chain from the original reference analysis. Roles describe possible explicit operand use; they do not prove execution or member validity.'
      : 'Occurrences include the declared root, resolved target and traversed alias chain. They do not describe reads or writes.');
    p.append(table(['Operand','Rung','Instruction / argument','Binding',...(access?['Operand role']:[])],entityOperands.get(e.id)||[],o=>[link(o.raw_text,o.id),sourceCell(o.rung_id),(byInstruction.get(o.instruction_id)?.instruction.opcode||'Instruction')+' · argument '+(o.argument_index+1),badge(o.status),...(access?[accessCell(o)]:[])],'Object operand occurrences',{emptyTitle:'No captured operand occurrences',emptyDetail:'This does not establish that the object is unused; unsupported source or indirect expressions may refer to it.'}));content.append(p);
    if(entityAccessBindings.has(e.id)){
      const extra=section('Additional instruction access occurrences','These operand bindings come from instruction access analysis. They include the declared root, resolved target and traversed aliases. The original reference findings remain available separately.');
      extra.append(accessBindingTable(entityAccessBindings.get(e.id),'Object additional access occurrences'));content.append(extra);
    }
    content.append(technical({'Source ID':e.id,'Parent ID':e.parent_id,'Scope ID':e.scope_id,'XML location':e.locator}));
  }
  function rungDetail(r){
    setDetailHeading('LADDER SOURCE',rungName(r),entityPath(r.parent_id));
    const meta=node('div','detail-meta');meta.append(badge(r.parse_status),sourceCell(r.parent_id));content.append(meta);
    if(state.focusOperand && byOperand.get(state.focusOperand)?.rung_id===r.id){
      const o=byOperand.get(state.focusOperand),a=byOperandAccess.get(o.id);
      content.append(notice('Selected operand · argument '+(o.argument_index+1),(o.raw_text || '(blank)')+' · original reference binding: '+human(o.status)+(access?' · role: '+human(accessLabel(o)):'')+(a?.binding_origin && a.binding_origin!=='source_references'?' · instruction access binding: '+human(a.binding_status):'')));
    }
    if(state.focusInstruction && byInstruction.get(state.focusInstruction)?.rung.id===r.id)content.append(notice('Selected instruction',byInstruction.get(state.focusInstruction).instruction.opcode));
    const text=panel('Rung text','Exact captured ladder source. No execution behavior is inferred.');text.append(sourceText(r.text));content.append(text);
    if(r.comment !== null){const p=panel('Rung comment');p.append(sourceText(r.comment,true));content.append(p);}
    const inst=section('Parsed instructions');inst.append(table(['Order','Opcode','Arguments','Semantic status',...(access?['Operand-role coverage']:[])],r.instructions || [],(i,n)=>[String(n+1),node('span','mono',i.opcode),node('div','snippet',(i.arguments||[]).join(', ')),human(i.semantic_status),...(access?[badge(byInstructionAccess.get(i.id)?.status)]:[])],'Parsed rung instructions'));content.append(inst);
    if(rungPids.has(r.id)){const p=section('PID evidence on this rung');p.append(pidTable(rungPids.get(r.id),'Rung PID occurrences'));content.append(p);}
    if(rungCalculations.has(r.id)){const p=section('Calculations on this rung');p.append(calculationTable(rungCalculations.get(r.id),'Rung calculation occurrences'));content.append(p);}
    const ops=section(access?.schema_version>=3?'Original reference bindings':'Operand bindings','Root resolution is source evidence only. A binding does not validate a member, array bound, data type or instruction effect.'+(access?.schema_version>=3?' These rows retain the original reference analysis; additional instruction access bindings appear separately below.':''));
    if((rungOperands.get(r.id)||[]).some(o=>byOperandAccess.get(o.id)?.reason==='timer_pseudo_operand'))ops.append(node('p','row-note','Timer preset and accumulator fields describe initialization, not separate runtime reads. A question mark supplies no value here. Timer values, units and configuration are not validated.'));
    ops.append(table(['Operand','Instruction / argument','Binding','Declared / resolved root',...(access?['Operand role']:[])],rungOperands.get(r.id)||[],o=>[node('span','mono',o.raw_text || '(blank)'),(byInstruction.get(o.instruction_id)?.instruction.opcode||'Instruction')+' · '+(o.argument_index+1),primary(badge(o.status),o.reason?human(o.reason):''),bindingRoots(o,o.reason),...(access?[accessCell(o)]:[])],'Rung operand bindings'));content.append(ops);
    if(rungAccessBindings.has(r.id)){
      const extra=section('Instruction access bindings','These bindings use supported instruction operand roles. Selector text is not a tag reference, even if a declaration has the same name. The original reference findings are preserved above.');
      extra.append(accessBindingTable(rungAccessBindings.get(r.id),'Rung instruction access bindings'));content.append(extra);
    }
    const pattern=routinePatterns.get(r.id);if(pattern)content.append(button('Open syntax pattern · '+fmt(pattern.count)+' occurrences',()=>openDetail('pattern',pattern.id)));
    const structure=node('details','technical');structure.append(node('summary','','Parsed branch structure'),sourceText(JSON.stringify(r.structure,null,2)));content.append(structure,technical({'Source ID':r.id,'Routine ID':r.parent_id,'Scope ID':r.scope_id,'XML location':r.locator}));
  }
  function sfcList(){
    const rows=(sfc.routines||[]).filter(matches);
    content.append(table(['Routine','Scope','Content versions','Captured elements'],rows,r=>[button(entityName(r.routine_id),()=>openDetail('sfc',r.routine_id),'text-link'),entityPath(byEntity.get(r.routine_id)?.parent_id),fmt(r.content_ids.length),fmt(r.content_ids.reduce((n,id)=>n+(contentElements.get(id)||[]).length,0))],'SFC routines'));
  }
  function elementTable(rows,caption='SFC elements'){
    return table(['Element','Kind','Parent','Source text'],rows,e=>[primary(link(elementName(e),e.id),e.attributes?.ID!==undefined?'XML ID '+e.attributes.ID:''),human(e.kind),e.parent_id?sourceCell(e.parent_id):node('span','muted','Content root'),node('div','snippet',short(e.direct_text,180))],caption);
  }
  function relationTable(rows,annotation=false){
    return table([annotation?'Annotation source':'Link source',annotation?'Text box':'From element',annotation?'Attached element':'To element','Endpoint status'],rows,l=>{const statuses=node('div');statuses.append(primary(badge(l.from_status),'From endpoint'),primary(badge(l.to_status),'To endpoint'));return[sourceCell(l.element_id),l.from_element_id?sourceCell(l.from_element_id):node('span','muted',human(l.from_status)),l.to_element_id?sourceCell(l.to_element_id):node('span','muted',human(l.to_status)),statuses];},annotation?'Annotation attachments':'Structural links');
  }
  function sfcDetail(routine){
    setDetailHeading('SFC SOURCE',entityName(routine.routine_id),entityPath(byEntity.get(routine.routine_id)?.parent_id));
    content.append(notice('Captured structure and authored notes','Links resolve XML endpoints within a content version. Annotation attachments connect notes to elements. Neither establishes sequence execution, transition meaning or the active online edit version.'));
    const envelope=panel('Routine capture evidence','Opaque protection markers and unmodeled child locations are retained as evidence. Their presence does not reveal hidden payloads; marker absence does not prove unprotected content.');
    if(routine.direct_text)envelope.append(node('h3','','Routine direct text'),sourceText(routine.direct_text));
    envelope.append(table(['Opaque marker','XML location'],routine.protection_markers||[],m=>[m.xml_name,m.locator],'Routine opaque markers',{emptyTitle:'No opaque protection markers captured',emptyDetail:'This count does not classify plaintext encryption metadata.'}));
    if(routine.unmodeled_children?.length)envelope.append(table(['Unmodeled child','XML location'],routine.unmodeled_children,m=>[m.xml_name,m.locator],'Unmodeled routine children'));
    const envelopeDetails=node('details','technical');envelopeDetails.append(node('summary','','Routine capture evidence'),envelope);content.append(envelopeDetails);
    const contents=routine.content_ids.map(id=>byContent.get(id)).filter(Boolean);
    if(!contents.length){content.append(empty('No SFC content was captured','Inspect this routine’s source declaration and findings for missing or opaque content.'));return;}
    const selected=contents.find(c=>c.id===state.contentId)||contents[0];state.contentId=selected.id;
    const selectBox=node('div','toolbar'),label=node('label','filter-wrap','Content version');const select=node('select');select.setAttribute('aria-label','SFC content version');
    contents.forEach((c,n)=>{const option=node('option','','Content '+(n+1)+' · '+(c.edit_kind==='absent'?'edit kind not specified':human(c.edit_kind)));option.value=c.id;select.append(option);});select.value=selected.id;select.addEventListener('change',()=>{state.contentId=select.value;render();});label.append(select);selectBox.append(label,sourceCell(routine.routine_id));content.append(selectBox);
    const rows=contentElements.get(selected.id)||[];
    const textKinds=new Set(['text_box','text_box_text','description','st_line','body','condition','preset','limit_high','limit_low']);
    const block=section('Source elements','All captured elements in this content version, including unmodeled structures. Open any row for exact attributes and text.');block.append(elementTable(rows));content.append(block);
    const text=section('Structured text & notes','Authored source text is preserved as separate elements. Notes are not automatically assigned as engineering descriptions.');text.append(elementTable(rows.filter(e=>textKinds.has(e.kind)),'SFC source text and notes'));content.append(text);
    const links=section('Structural links','XML FromID and ToID resolutions. These links are separate from note attachments.');links.append(relationTable(contentLinks.get(selected.id)||[]));content.append(links);
    const annotations=section('Annotation attachments','Text-box ownership relationships only; these do not contribute control-flow edges.');annotations.append(relationTable(contentNotes.get(selected.id)||[],true));content.append(annotations);
    const metadata=panel('Content attributes');metadata.append(values(selected.attributes));content.append(metadata);
    if(selected.direct_text){const raw=panel('Content direct text','Exact text directly inside this SFC content element. Unexpected text remains a capture finding.');raw.append(sourceText(selected.direct_text));content.append(raw);}
    content.append(technical({'Routine ID':routine.routine_id,'Content ID':selected.id,'XML location':selected.locator}));
  }
  function elementDetail(e){
    setDetailHeading('SFC ELEMENT',elementName(e),entityName(e.routine_id)+' · '+human(e.kind));
    const meta=node('div','detail-meta');meta.append(badge(e.kind),button('Open parent SFC content',()=>openDetail('sfc',e.routine_id,{contentId:e.content_id}),'text-link'));if(e.parent_id)meta.append(sourceCell(e.parent_id));content.append(meta);
    const attrs=panel('Element attributes');attrs.append(values(e.attributes));content.append(attrs);
    const text=panel('Direct source text','Exact text captured on this element. Child text remains separately addressable below.');text.append(sourceText(e.direct_text));content.append(text);
    const children=elementChildren.get(e.id)||[];if(children.length){const p=section('Child elements');p.append(elementTable(children,'Child SFC elements'));content.append(p);}
    const links=elementLinks.get(e.id)||[];if(links.length){const p=section('Structural links involving this element');p.append(relationTable(links));content.append(p);}
    const notes=elementNotes.get(e.id)||[];if(notes.length){const p=section('Annotation attachments involving this element');p.append(relationTable(notes,true));content.append(p);}
    content.append(technical({'Source ID':e.id,'XML element':e.xml_name,'XML ID status':e.block_id_status,'Canonical XML ID':e.canonical_id,'Content ID':e.content_id,'Parent ID':e.parent_id,'XML location':e.locator}));
  }
  function patternSummary(p){return (p.opcode_summary||[]).map(o=>o.opcode+' ×'+o.count+' ['+o.arity+']').join(' · ');}
  function patternList(){
    const rows=patterns.filter(p=>matches(p)&&(state.filter==='all'||(state.filter==='repeated'?p.count>1:p.count===1)));
    content.append(table(['Syntax pattern','Occurrences','First occurrence'],rows,p=>[button(patternSummary(p)||'Empty parsed rung',()=>openDetail('pattern',p.id),'text-link'),fmt(p.count),sourceCell(p.rung_ids[0])],'Ladder syntax patterns'));
  }
  function patternDetail(p){
    setDetailHeading('LADDER PATTERN','Syntax pattern · '+fmt(p.count)+' occurrence'+(p.count===1?'':'s'),patternSummary(p));
    content.append(notice('A structural comparison','This group preserves opcode spelling, argument counts and ordered branch structure. Operand names and values are excluded from grouping. Equal shapes do not imply equal purpose or behavior.'));
    const occurrences=section('Source occurrences','Open each rung to compare its context, operands and comments.');occurrences.append(rungList((p.rung_ids||[]).map(id=>byRung.get(id)).filter(Boolean)));content.append(occurrences);
    const ops=panel('Instruction signature','The number in brackets is the argument count, not a classified instruction role.');ops.append(table(['Opcode','Argument count','Occurrences in shape'],p.opcode_summary||[],o=>[node('span','mono',o.opcode),fmt(o.arity),fmt(o.count)],'Pattern opcode signature'));content.append(ops);
    const shape=node('details','technical');shape.append(node('summary','','Ordered syntax shape'),sourceText(p.shape));content.append(shape,technical({'Pattern ID':p.id}));
  }
  function findingsList(){
    if(access?.schema_version>=3)content.append(notice('Original reference findings are retained','Operand and alias findings come from the original reference analysis. Additional instruction access bindings may resolve a root or identify selector text without removing the original finding. Open its source operand to compare both evidence layers.'));
    const rows=findings.filter(f=>matches(f)&&(state.filter==='all'||f.origin===state.filter));
    content.append(table(['Finding','Origin / severity','Source context','Detail'],rows,f=>[button(human(f.code),()=>openDetail('finding',f.id),'text-link'),primary(badge(f.severity),human(f.origin)),sourceCell(f.source_id),short(f.message,170)],'Review findings',{emptyTitle:'No findings match this selection',emptyDetail:findings.length?'Try another search or origin filter.':'No capture or binding findings were emitted. Engineering interpretation still requires review.'}));
  }
  function findingDetail(f){
    setDetailHeading('REVIEW FINDING',human(f.code),f.message);
    const meta=node('div','detail-meta');meta.append(badge(f.severity),badge(f.origin));content.append(meta);
    const binding=byOperandAccess.get(f.source_id);
    if(f.origin==='operand' && binding?.binding_origin && binding.binding_origin!=='source_references'){
      const current=section('Instruction access analysis','This finding retains the original reference status. The separate access analysis for the same operand is shown below.');
      current.append(accessBindingTable([binding],'Finding instruction access binding'));content.append(current);
    }
    const evidence=panel('Source evidence','Follow the originating record and its context before deciding whether a parser correction is needed.');
    evidence.append(sourceCell(f.source_id));const ids=Array.from(new Set(f.related_ids||[])).filter(id=>id!==f.source_id);
    if(ids.length)evidence.append(table(['Related evidence'],ids,id=>[sourceCell(id)],'Finding related evidence'));content.append(evidence);
    content.append(notice('Review status is not stored here','This report is read-only and belongs to one source snapshot. Keep proposed corrections in your review notes; persistent classifications and editable handoffs are a later stage.'));
    if(f.locator){const location=panel('Source location');location.append(sourceText(f.locator));content.append(location);}
    content.append(technical({'Finding ID':f.id,'Source ID':f.source_id,'Code':f.code,'XML location':f.locator}));
  }
  function setDetailHeading(eyebrow,title,subtitle){
    heading.replaceChildren(button('← Back to previous view',goBack,'back'),node('p','eyebrow',eyebrow),node('h1','',title),node('p','subtitle',subtitle));
  }
  function pidName(p){return 'PID · '+short(byOperand.get(p.operand_ids[0])?.raw_text || '(no storage operand)',100);}
  const PID_MEMBER_HEADERS = {
  "BIAS": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "CA": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "CL": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "CT": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "CTL": {
    "datatype": "DINT",
    "kind": "data_value_member"
  },
  "DATA": {
    "datatype": "REAL",
    "kind": "array_member"
  },
  "DB": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "DOE": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "DVDB": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "DVN": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "DVNA": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "DVP": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "DVPA": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "EN": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "ERR": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "EWD": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "INI": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "KD": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "KI": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "KP": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MAXCV": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MAXI": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MAXO": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MAXS": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MAXTIE": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MINCV": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MINI": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MINO": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MINS": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MINTIE": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "MO": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "NDF": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "NOBC": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "NOZC": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "OLH": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "OLL": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "OUT": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "PE": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "PV": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "PVDB": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "PVH": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "PVHA": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "PVL": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "PVLA": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "PVT": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "SO": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "SP": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "SPOR": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "SWM": {
    "datatype": "BOOL",
    "kind": "data_value_member"
  },
  "TIE": {
    "datatype": "REAL",
    "kind": "data_value_member"
  },
  "UPD": {
    "datatype": "REAL",
    "kind": "data_value_member"
  }
};
  function pidMemberLabel(field){return PID_MEMBER_LABELS[field] || field || 'Uncatalogued member';}
  function pidMemberGroup(field){return Object.keys(PID_MEMBER_GROUPS).find(group=>PID_MEMBER_GROUPS[group].includes(field)) || 'unknown';}
  function pidMemberBadge(status){return node('span','badge '+(['matched','array_header_matched'].includes(status)?'good':'warn'),({matched:'Scalar header matched',array_header_matched:'Array header matched'})[status] || human(status));}
  function pidMemberSection(p){
    const box=section('Saved PID members','Documented labels organize captured member evidence. Type and shape checks do not validate numeric values, units, effective settings or runtime state. Each representation and duplicate member remains separate; missing fields supply no defaults.');
    const structures=p.structure_candidates.map(c=>byPidMemberStructure.get(c.structure_id)).filter(Boolean);
    if(!structures.length){box.append(empty('No eligible PID structure for member comparison','Follow the storage association and declaration evidence above. This does not establish that PID settings are absent.'));return box;}
    const rows=structures.flatMap(s=>s.member_ids.map(id=>({structure:s,member:byPidMember.get(id),element:byTagElement.get(id)}))).filter(x=>x.member&&x.element);
    const missing=structures.flatMap(s=>s.missing_fields.map(field=>({structure:s,field,group:pidMemberGroup(field)})));
    const controls=node('div','toolbar'),searchWrap=node('div','search-wrap'),input=node('input');
    input.type='search';input.id='pid-member-search';input.placeholder='Search member names, labels, saved values or status';input.value=state.pidMemberQuery || '';input.autocomplete='off';input.setAttribute('aria-label','Search saved PID members');searchWrap.append(input);
    const label=node('label','filter-wrap','Member group'),select=node('select');select.setAttribute('aria-label','Filter PID member group');
    const groups=[...new Set([...Object.keys(PID_MEMBER_GROUPS),...rows.map(x=>x.member.group)])];
    [['all','All groups'],...groups.map(group=>[group,human(group)])].forEach(([value,title])=>{const option=node('option','',title);option.value=value;select.append(option);});
    select.value=state.pidMemberGroup || 'all';label.append(select);controls.append(searchWrap,label);box.append(controls);
    const results=node('div');box.append(results);
    const selected=group=>!state.pidMemberGroup||state.pidMemberGroup==='all'||state.pidMemberGroup===group;
    const renderMembers=()=>{
      const query=(state.pidMemberQuery || '').toLocaleLowerCase();
      const filtered=rows.filter(x=>selected(x.member.group)&&(!query||[searchIndex.get(x.member),x.element.attributes?.Value,x.element.attributes?.DataType,x.element.direct_text].join(' ').toLocaleLowerCase().includes(query)));
      const absent=missing.filter(x=>selected(x.group)&&(!query||[x.field,pidMemberLabel(x.field),x.group,'missing'].join(' ').toLocaleLowerCase().includes(query)));
      results.replaceChildren();
      const summary=node('p','row-note',fmt(filtered.length)+' captured member records and '+fmt(absent.length)+' missing catalog fields match this selection.');summary.setAttribute('role','status');results.append(summary);
      results.append(table(['Setting / source member','Saved value / stored type','Group / evidence status','Representation / structure'],filtered,x=>{
        const m=x.member,e=x.element,s=x.structure;
        const identity=primary(sourceCell(e.id),pidMemberLabel(m.field));
        const preview=Object.hasOwn(e.attributes||{},'Value')?(e.attributes.Value===''?'Empty value':short(e.attributes.Value,180)):e.direct_text?.trim()?short(e.direct_text,180):e.kind==='array_member'?'Array member; open source for child records':'No scalar value on this element';
        const type='Stored type: '+(e.attributes?.DataType || 'not specified')+(Object.hasOwn(e.attributes||{},'Dimensions')?'; dimensions: '+short(e.attributes.Dimensions,80):'');
        const header=PID_MEMBER_HEADERS[m.field];
        const expected=header?'; catalog: '+header.datatype+' '+(header.kind==='array_member'?'array header (17 entries; contents unvalidated)':'scalar'):'';
        const value=primary(node('div','snippet',preview),type+expected);
        const status=primary(human(m.group));status.append(pidMemberBadge(m.status));
        if(m.field&&s.duplicate_fields.includes(m.field))status.append(node('div','cell-sub','Duplicate field in this structure; every record is retained.'));
        const context=primary(sourceCell(s.content_id));
        const structureLink=node('div','cell-sub');structureLink.append(sourceCell(s.structure_id));context.append(structureLink);
        return[identity,value,status,context];
      },'PID catalogued member evidence',{emptyTitle:'No captured members match',emptyDetail:'Change the member search or group filter. Missing catalog fields appear separately below.'}));
      const gaps=section('Missing catalog fields','Absence is checked separately for each captured structure. No value is supplied or borrowed from another representation. A named field with a type or shape gap appears in the member table above.');
      gaps.append(table(['Catalog field','Group','Representation','Structure'],absent,x=>[primary(x.field,pidMemberLabel(x.field)),human(x.group),sourceCell(x.structure.content_id),sourceCell(x.structure.structure_id)],'PID missing catalog fields',{emptyTitle:'No missing catalog fields match',emptyDetail:'This does not validate values or runtime behavior. Type, shape and duplicate evidence remain in the captured-member table.'}));results.append(gaps);
    };
    input.addEventListener('input',()=>{state.pidMemberQuery=input.value;state.listPages={};renderMembers();});
    select.addEventListener('change',()=>{state.pidMemberGroup=select.value;state.listPages={};renderMembers();});
    renderMembers();return box;
  }
  function pidSlotLabel(slot){return ({pid_structure:'PID structure',process_variable:'Process variable (PV)',tieback:'Tieback',control_variable:'Control variable (CV)',master_loop:'Master PID operand',inhold_bit:'Inhold bit',inhold_value:'Inhold value',unknown:'Unclassified slot'})[slot] || human(slot);}
  function pidNotice(){return notice('Instruction evidence for loop review','Operand functions identify the positions in a supported PID signature. Read/write effects, active cascade behavior, execution timing and approved loop settings remain unmodeled. Multiple occurrences may share a declaration; this count is not a count of independent loops.');}
  function pidTable(rows,caption='PID instruction occurrences'){
    return table(['Occurrence','Rung','Signature','Storage association'],rows,p=>[
      button(pidName(p),()=>openDetail('pid',p.id),'text-link'),sourceCell(p.rung_id),badge(p.signature_status),badge(p.storage_status)
    ],caption,{emptyTitle:'No PID occurrences match',emptyDetail:'This view covers captured ladder PID instructions. Other control instructions and languages are outside this slice.'});
  }
  function pidList(){
    content.append(pidNotice());
    const c=pid.coverage,totals=panel('PID coverage','Storage links connect exact source records; they do not select effective values.');
    totals.append(values({'Instruction occurrences':pidOccurrences.length,'Distinct backing declarations':c.distinct_backing_owners,
      'Occurrences with stored data':c.occurrences_with_data,'Occurrences with opaque-only data':c.occurrences_with_opaque_only,
      'Occurrences with multiple representations':c.occurrences_with_multiple_representations}));content.append(totals);
    if(pidMembers){const m=pidMembers.coverage,memberTotals=panel('Documented member coverage','These counts inspect each stored structure once, even when several PID instructions reference it. Header matches do not validate values or execution.');memberTotals.append(values({'Stored structures inspected':m.structures_total,'Direct member records':m.members_total,'Structures with member gaps':m.structures_with_gaps,'Missing catalog fields':m.missing_catalog_fields,'Duplicate catalog fields':m.duplicate_catalog_fields}));content.append(memberTotals);}
    content.append(pidTable(pidOccurrences.filter(p=>(matches(p)||p.structure_candidates.some(c=>c.member_ids.some(id=>byPidMember.has(id)&&matches(byPidMember.get(id)))))&&(state.filter==='all'||p.storage_status===state.filter))));
  }
  function pidDetail(p){
    setDetailHeading('PID SOURCE EVIDENCE',pidName(p),sourceName(p.rung_id));
    content.append(pidNotice());
    const meta=node('div','detail-meta');meta.append(badge(p.signature_status),badge(p.storage_status),sourceCell(p.rung_id));content.append(meta);
    const slots=p.operand_ids.map(id=>({evidence:byPidOperand.get(id),operand:byOperand.get(id)}));
    const pv=slots.find(x=>x.evidence?.slot==='process_variable'),storage=slots.find(x=>x.evidence?.slot==='pid_structure'),cv=slots.find(x=>x.evidence?.slot==='control_variable');
    if(pv&&storage&&cv){
      const diagram=panel('Operand arrangement','The arrows show the PV and CV instruction positions. They do not establish process connectivity or execution.');
      const flow=node('div','pid-flow');
      [pv,storage,cv].forEach((x,index)=>{if(index){const arrow=node('span','pid-arrow','→');arrow.setAttribute('aria-hidden','true');flow.append(arrow);}const box=node('div','pid-node');box.append(node('h3','',pidSlotLabel(x.evidence.slot)),link(x.operand.raw_text,x.operand.id));flow.append(box);});
      diagram.append(flow);content.append(diagram);
    }
    const args=section('Operand functions','Setpoint is retained as an SP member in stored PID data when exported. The third instruction operand is Tieback. An explicit master operand alone does not establish an active cascade.');
    args.append(table(['Position / function','Source operand','Binding','Resolved declaration / suffix'],slots,x=>{
      const o=x.operand,e=x.evidence,root=node('div');
      if(o.target_id)root.append(sourceCell(o.target_id));else root.append(node('span','muted','No resolved declaration'));
      if(o.suffix)root.append(node('div','cell-sub',o.suffix));
      return[primary(String(e.argument_index+1),pidSlotLabel(e.slot)),link(o.raw_text,o.id),badge(o.status),root];
    },'PID operand functions'));content.append(args);
    const stored=section('Backing declaration and representations','All associated representations stay separate. Suffix, declaration and shape gaps remain visible; open the source declaration for their context.');
    if(p.backing_owner_id)stored.append(sourceCell(p.backing_owner_id));
    const representations=p.content_ids.map(id=>byTagContent.get(id)).filter(Boolean);
    if(representations.length)stored.append(tagContentTable(representations,'PID stored data representations'));
    else stored.append(empty(p.storage_status==='no_data'?'No Data or DefaultData on this backing declaration':'No backing representations associated',human(p.storage_status)+'. Inspect the operand and declaration evidence above.'));
    content.append(stored);
    const roots=section('PID structure candidates','Each row is a direct Decorated PID structure. Duplicate roots and representations are kept; no candidate is chosen as effective.');
    roots.append(table(['Representation','Structure evidence','Direct member records'],p.structure_candidates,c=>[sourceCell(c.content_id),sourceCell(c.structure_id),fmt(c.member_ids.length)],'PID structure candidates'));content.append(roots);
    if(pidMembers)content.append(pidMemberSection(p));
    else {
    const memberRows=p.structure_candidates.flatMap(c=>c.member_ids.map(id=>({candidate:c,element:byTagElement.get(id)}))).filter(x=>x.element);
    const members=section('Saved PID members','Values retain their exported spelling. Missing members supply no default. SP, tuning, mode and limit fields remain source evidence until engineering review; duplicate values are shown independently.');
    members.append(table(['Member','Saved value / text','Representation','Capture kind'],memberRows,x=>{
      const e=x.element;return[sourceCell(e.id),node('div','snippet',Object.hasOwn(e.attributes||{},'Value')?(e.attributes.Value===''?'Empty value':short(e.attributes.Value,180)):e.direct_text?.trim()?short(e.direct_text,180):'No scalar value on this element'),sourceCell(x.candidate.content_id),human(e.kind)];
    },'PID saved members'));content.append(members);
    }
    content.append(technical({'Instruction ID':p.id,'Rung ID':p.rung_id,'Storage association':p.storage_status}));
  }
  function calculationName(c){return 'CPT · '+short(byOperand.get(c.destination_operand_id)?.raw_text || '(destination not assigned)',100);}
  function calculationNotice(){return notice('Expression syntax and source evidence','Grouping and reference links describe the captured CPT expression. No value is calculated, and no execution, scan order, data type, member validity or control dependency is inferred. Unsupported expressions retain their source without a partial syntax tree or partial reference bindings.');}
  function calculationTable(rows,caption='Calculation occurrences'){
    return table(['Occurrence','Expression preview','Rung','Syntax'],rows,c=>[
      button(calculationName(c),()=>openDetail('calculation',c.id),'text-link'),
      node('div','snippet',short(byOperand.get(c.expression_operand_id)?.raw_text ?? 'Expression function not assigned',180)),
      sourceCell(c.rung_id),primary(badge(c.syntax_status),c.error_code?human(c.error_code):'')
    ],caption,{emptyTitle:'No calculations match',emptyDetail:'This view covers CPT instructions in captured ladder. Other calculation instructions and languages are outside this slice.'});
  }
  function calculationList(){
    content.append(calculationNotice());
    const c=calculations.coverage,totals=panel('Calculation coverage','Counts describe captured instruction and expression occurrences. Repeated references remain separate.');
    totals.append(values({'CPT instruction occurrences':calculationOccurrences.length,
      'Expressions with parsed syntax':c.expressions_by_status.parsed,
      'Unsupported expressions':c.expressions_by_status.unsupported,
      'Unresolved signatures':c.expressions_by_status.signature_unresolved,
      'Expression reference occurrences':c.reference_occurrences,
      'Expressions with reference binding gaps':c.expressions_with_binding_gaps}));
    content.append(totals,calculationTable(calculationOccurrences.filter(c=>matches(c)&&(state.filter==='all'||c.syntax_status===state.filter))));
    if(c.functions_by_spelling){
      const functions=panel('Function coverage','Snapshot totals for fully parsed expressions. Counts ignore letter case; older spellings are not rewritten into newer names.');
      const rows=Object.entries(c.functions_by_spelling).filter(([,count])=>count>0);
      functions.append(table(['Function spelling','Parsed function calls'],rows,([name,count])=>[node('span','mono',name),fmt(count)],'Parsed function spellings',
        {emptyTitle:'No function calls in parsed expressions',emptyDetail:'Unsupported expressions contribute no partial function counts.'}));
      const gaps=c.unsupported_functions;
      if(gaps && (gaps.atan2 || gaps.other)){
        functions.append(node('p','panel-intro','Only the first unsupported function reached in each rejected expression is counted below. Other parsing failures do not contribute function-gap counts.'),
          values({'ATAN2 outside this grammar':gaps.atan2,'Other unsupported function names':gaps.other}));
      }
      content.append(functions);
    }
  }
  function calculationBinding(binding){
    const box=node('div');
    if(!binding){box.append(node('span','muted','No binding assigned'));return box;}
    const roots=node('div','inline-links');
    if(binding.symbol_id)roots.append(sourceCell(binding.symbol_id));
    if(binding.target_id && binding.target_id!==binding.symbol_id)roots.append(node('span','','→'),sourceCell(binding.target_id));
    if(!roots.childNodes.length)roots.append(node('span','muted','No resolved declaration'));
    box.append(roots);
    if(binding.suffix)box.append(node('div','mono cell-sub','Suffix: '+binding.suffix));
    if(binding.alias_chain?.length){
      const aliases=node('details','calculation-aliases');aliases.append(node('summary','','Traversed alias declarations ('+fmt(binding.alias_chain.length)+')'));
      aliases.append(table(['Alias declaration'],binding.alias_chain,id=>[sourceCell(id)],'Calculation aliases '+(binding.symbol_id || '')+' '+(binding.suffix || '')));box.append(aliases);
    }
    if(binding.reason)box.append(node('div','cell-sub',human(binding.reason)));
    return box;
  }
  function calculationOutline(c){
    // Traverse iteratively and render only one page. Child order is syntax order,
    // not evaluation order; node_ids may be stored in a different order.
    const rows=[],seen=new Set(),stack=c.root_node_id?[{id:c.root_node_id,depth:0,parent:null,child:0}]:[];
    while(stack.length){
      const entry=stack.pop(),n=byCalculationNode.get(entry.id);
      if(!n || seen.has(n.id))continue;
      seen.add(n.id);const ordinal=rows.length+1;rows.push({...entry,node:n,ordinal});
      for(let i=n.child_ids.length-1;i>=0;i--)stack.push({id:n.child_ids[i],depth:entry.depth+1,parent:ordinal,child:i+1});
    }
    return rows;
  }
  function calculationSpan(n){return '['+n.start+', '+n.end+')';}
  function calculationDetail(c){
    setDetailHeading('CALCULATION SOURCE EVIDENCE',calculationName(c),sourceName(c.rung_id));
    content.append(calculationNotice());
    const meta=node('div','detail-meta');meta.append(badge(c.signature_status),badge(c.syntax_status),sourceCell(c.rung_id));content.append(meta);
    const destination=byOperand.get(c.destination_operand_id),expression=byOperand.get(c.expression_operand_id);
    if(c.signature_status==='recognized'){
      const dest=panel('Destination operand','The destination slot belongs to the captured CPT signature. A root binding does not validate a writable member or establish that the instruction executes.');
      if(destination){dest.append(sourceText(destination.raw_text),sourceCell(destination.id));const details=node('div','detail-meta');details.append(badge(destination.status));dest.append(details,calculationBinding(destination));}
      else dest.append(empty('No destination operand captured','Inspect the original rung for this instruction.'));
      content.append(dest);
    }else{
      const args=panel('Captured instruction arguments','The CPT signature is unresolved. No destination or expression function is assigned to these arguments.');
      const rows=(rungOperands.get(c.rung_id)||[]).filter(o=>o.instruction_id===c.id);
      args.append(table(['Argument position','Exact source'],rows,o=>[String(o.argument_index+1),link(o.raw_text || '(empty argument)',o.id)],'Unresolved CPT arguments'));
      content.append(args);
    }
    const raw=panel('Original expression','Exact expression operand text, available to select and copy. Character spans below are zero-based, with the end position excluded.');
    if(expression){raw.append(sourceText(expression.raw_text),sourceCell(expression.id));}
    else raw.append(empty('No expression function assigned','Open the rung to inspect the captured instruction and all its arguments.'));
    content.append(raw);
    if(c.syntax_status!=='parsed'){
      const errors={lexical_error:'A source token is outside the supported expression syntax.',syntax_error:'The expression does not match the supported syntax.',unsupported_function:'A function in this expression is not supported by this parser.',length_limit:'The expression exceeds the supported length limit.',token_limit:'The expression exceeds the supported token limit.',depth_limit:'The expression exceeds the supported nesting limit.'};
      const gap=panel('Expression parsing gap','No partial syntax tree or partial expression reference bindings are published. The original source remains available above and on the rung.');
      gap.append(values({'Syntax status':human(c.syntax_status),'Reason':c.error_code?(errors[c.error_code] || human(c.error_code)):'Instruction signature is unresolved.','Error code':c.error_code,'Character offset':c.error_offset}));content.append(gap);
    }else{
      const rows=calculationOutline(c),leaves=rows.filter(x=>x.node.kind==='reference').sort((a,b)=>a.node.start-b.node.start);
      const repeatTotals=new Map(),repeatSeen=new Map();
      leaves.forEach(x=>repeatTotals.set(x.node.raw_text,(repeatTotals.get(x.node.raw_text)||0)+1));
      const references=leaves.map(x=>{const spelling=x.node.raw_text,index=(repeatSeen.get(spelling)||0)+1;repeatSeen.set(spelling,index);return{...x,index,total:repeatTotals.get(spelling)};});
      const bindings=section('Expression reference occurrences','Each reference leaf stays separate, including repeated source spelling. These are possible expression inputs; root links do not prove execution or validate a suffix. Open a declaration to inspect its source.');
      bindings.append(table(['Reference / repeated spelling','Character span','Binding','Declared / resolved root'],references,x=>[
        primary(node('span','mono',x.node.raw_text),x.total>1?'Occurrence '+x.index+' of '+x.total+' with this exact spelling':'One occurrence with this exact spelling'),
        node('span','mono',calculationSpan(x.node)),badge(x.node.binding?.status),calculationBinding(x.node.binding)
      ],'Calculation expression references',{emptyTitle:'No reference leaves in this parsed expression',emptyDetail:'An expression can contain only literal values. No value has been calculated.'}));content.append(bindings);
      const outline=section('Expression grouping','Parent rows precede their children in source syntax order. Indentation and child numbers show grouping, not evaluation order. Parent links refer to row numbers in this outline.');
      outline.append(table(['Row / grouping','Kind / operator','Character span','Leaf source'],rows,x=>{
        const grouping=node('div','calculation-grouping');grouping.style.paddingLeft=Math.min(x.depth,12)*10+'px';
        grouping.append(node('strong','',String(x.ordinal)),node('div','cell-sub',x.parent===null?'Root':'Child '+x.child+' of row '+x.parent),node('div','cell-sub','Depth '+x.depth));
        return[grouping,primary(human(x.node.kind),x.node.operator || (x.node.kind==='group'?'Explicit parentheses':'')),node('span','mono',calculationSpan(x.node)),x.node.raw_text===null?node('span','muted','See child rows'):node('span','mono',x.node.raw_text)];
      },'Calculation syntax grouping'));content.append(outline);
    }
    content.append(technical({'Instruction ID':c.id,'Rung ID':c.rung_id,'Destination operand ID':c.destination_operand_id,'Expression operand ID':c.expression_operand_id,'Root node ID':c.root_node_id}));
  }
  function tagDataNotice(){return notice('Exported values, with source context','These are saved source values, not live readings or approved DeltaV settings. Data and DefaultData representations stay separate; no precedence, numeric conversion, member validity or effective value is inferred. Opaque and duplicate data remain visible.');}
  function tagContentName(c){const ordinal=c.locator.match(/\[([0-9]+)\]$/)?.[1];return c.xml_name+(ordinal?' '+ordinal:'')+' / '+human(c.format_kind);}
  function tagElementName(e){return short(e.attributes?.Name || e.attributes?.Index || e.xml_name,100);}
  function tagElementContext(e){
    const parts=[],seen=new Set();let current=e;
    while(current && !seen.has(current.id) && parts.length<8){seen.add(current.id);parts.unshift(tagElementName(current));current=byTagElement.get(current.parent_id);}
    if(current)parts.unshift('…');return parts.join(' / ');
  }
  function tagElementLocation(e){
    const parts=[],seen=new Set();let current=e;
    while(current && !seen.has(current.id)){seen.add(current.id);parts.unshift(current.xml_name+'['+current.ordinal+']');current=byTagElement.get(current.parent_id);}
    return (byTagContent.get(e.content_id)?.locator || '')+'/'+parts.join('/');
  }
  function tagContentTable(rows,caption='Stored data representations'){
    return table(['Declaration','Representation','Captured elements','Capture issues'],rows,c=>[
      sourceCell(c.owner_id),link(tagContentName(c),c.id),
      fmt((tagContentElements.get(c.id)||[]).length),fmt((tagIssues.get(c.id)||[]).length)
    ],caption);
  }
  function tagElementTable(rows,caption='Stored data elements'){
    return table(['Member / element','Declaration','Data type','Saved value / text','Capture kind'],rows,e=>[
      primary(link(tagElementName(e),e.id),tagElementContext(e)),sourceCell(e.owner_id),e.attributes?.DataType || 'Not specified here',
      node('div','snippet',Object.hasOwn(e.attributes||{},'Value')?(e.attributes.Value===''?'Empty value':short(e.attributes.Value,180)):e.direct_text?.trim()?short(e.direct_text,180):'No scalar value on this element'),human(e.kind)
    ],caption);
  }
  function tagIssueTable(rows){return table(['Capture issue','Evidence'],rows,i=>[human(i.code),sourceCell(i.source_id)],'Stored data capture issues');}
  function tagDataList(){
    content.append(tagDataNotice());
    const selected=c=>state.filter==='all'||c.format_kind===state.filter;
    const matchingElements=tagElements.filter(e=>selected(byTagContent.get(e.content_id))&&matches(e));
    const matchedContents=new Set(matchingElements.map(e=>e.content_id));
    const rows=tagContents.filter(c=>selected(c)&&(matches(c)||matchedContents.has(c.id)));
    const totals=panel('Stored data coverage','Capture counts describe this export only; missing data may reflect its export options.');
    totals.append(values({'Eligible declarations':byTagOwner.size,'Declarations with data':(tagData.owners||[]).filter(o=>o.content_ids.length).length,
      'Data representations':tagContents.length,'Captured data elements':tagElements.length,'Capture issues':(tagData.issues||[]).length}));content.append(totals);
    const reps=section('Data representations','Open one representation to inspect its exact attributes, text and members. Alternate representations are never merged.');reps.append(tagContentTable(rows));content.append(reps);
    const members=section('Members and saved values','Search matches each element’s own name, attributes or text and its declaration name. Displayed context is an authored hierarchy preview, not a validated tag address.');members.append(tagElementTable(matchingElements));content.append(members);
  }
  function tagContentDetail(c){
    setDetailHeading('STORED TAG DATA',entityName(c.owner_id),tagContentName(c));
    content.append(tagDataNotice(),sourceCell(c.owner_id));
    const attrs=panel('Representation attributes');attrs.append(values(c.attributes));content.append(attrs);
    if(c.direct_text){const text=panel('Direct source text','Parsed XML text is retained without interpreting an opaque representation. Original XML bytes remain in the source snapshot.');text.append(sourceText(c.direct_text));content.append(text);}
    const rows=tagContentElements.get(c.id)||[];const members=section('Captured elements','Open a row for complete attributes, direct text and parent/child evidence.');members.append(tagElementTable(rows));content.append(members);
    const issues=tagIssues.get(c.id)||[];if(issues.length){const gaps=section('Capture issues');gaps.append(tagIssueTable(issues));content.append(gaps);}
    content.append(technical({'Source ID':c.id,'Declaration ID':c.owner_id,'XML namespace':c.xml_namespace,'XML location':c.locator}));
  }
  function tagElementDetail(e){
    setDetailHeading('STORED DATA ELEMENT',tagElementName(e),entityName(e.owner_id)+' / '+tagElementContext(e));
    content.append(tagDataNotice());
    const links=node('div','inline-links');links.append(sourceCell(e.owner_id),sourceCell(e.content_id));if(e.parent_id!==e.content_id)links.append(sourceCell(e.parent_id));content.append(links);
    const attrs=panel('Element attributes','Values retain their exported spelling. Types, array indices, bounds and numeric ranges are not validated.');attrs.append(values(e.attributes));content.append(attrs);
    if(e.direct_text){const text=panel('Direct source text');text.append(sourceText(e.direct_text));content.append(text);}
    const children=tagChildren.get(e.id)||[];if(children.length){const p=section('Child data elements');p.append(tagElementTable(children,'Child data elements'));content.append(p);}
    const issues=(tagIssues.get(e.content_id)||[]).filter(i=>i.source_id===e.id);if(issues.length)content.append(tagIssueTable(issues));
    content.append(technical({'Source ID':e.id,'XML element':e.xml_name,'XML namespace':e.xml_namespace,'Capture kind':e.kind,'Parent ID':e.parent_id,'XML location':tagElementLocation(e)}));
  }
  function renderList(){
    content.replaceChildren();
    if(state.view==='overview')overview();
    else if(state.view==='objects')objectList();
    else if(state.view==='ladder')content.append(rungList());
    else if(state.view==='sfc')sfcList();
    else if(state.view==='patterns')patternList();
    else if(state.view==='findings')findingsList();
    else if(state.view==='access')accessList();
    else if(state.view==='tagdata')tagDataList();
    else if(state.view==='pid')pidList();
    else if(state.view==='calculations')calculationList();
  }
  function render(focus=false){
    heading.replaceChildren();toolbar.replaceChildren();content.replaceChildren();
    document.querySelectorAll('.nav-button').forEach(b=>{if(b.dataset.view===state.view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    if(state.detail){
      const d=state.detail;
      if(d.type==='entity')objectDetail(byEntity.get(d.id));
      else if(d.type==='rung')rungDetail(byRung.get(d.id));
      else if(d.type==='sfc')sfcDetail(bySfcRoutine.get(d.id));
      else if(d.type==='element')elementDetail(byElement.get(d.id));
      else if(d.type==='pattern')patternDetail(byPattern.get(d.id));
      else if(d.type==='finding')findingDetail(byFinding.get(d.id));
      else if(d.type==='access')accessDetail(byRootAccess.get(d.id));
      else if(d.type==='tagcontent')tagContentDetail(byTagContent.get(d.id));
      else if(d.type==='tagelement')tagElementDetail(byTagElement.get(d.id));
      else if(d.type==='pid')pidDetail(byPid.get(d.id));
      else if(d.type==='calculation')calculationDetail(byCalculation.get(d.id));
    }else{
      const [title,subtitle]=headings[state.view];heading.append(node('p','eyebrow','SOURCE REVIEW · PHASE 1'),node('h1','',title),node('p','subtitle',subtitle));
      if(state.view==='objects')toolbarFor('Search names, scopes, descriptions or attributes',countsFilter(entities,'kind'));
      else if(state.view==='ladder')toolbarFor('Search rung text, comments or routine names',countsFilter(rungs,'parse_status'));
      else if(state.view==='sfc')toolbarFor('Search SFC routines, elements and source text');
      else if(state.view==='patterns')toolbarFor('Search opcode or syntax shape',[['all','All patterns'],['repeated','Repeated patterns'],['single','Single occurrences']]);
      else if(state.view==='findings')toolbarFor('Search finding codes, source context or detail',countsFilter(findings,'origin'));
      else if(state.view==='access')toolbarFor('Search root names, scopes, opcodes or rung context');
      else if(state.view==='tagdata')toolbarFor('Search declarations, members, saved values or data text',countsFilter(tagContents,'format_kind'));
      else if(state.view==='pid')toolbarFor(pidMembers?'Search PID operands, member labels, groups or source context':'Search PID operands, rung context or association status',countsFilter(pidOccurrences,'storage_status'));
      else if(state.view==='calculations')toolbarFor('Search CPT destinations, expressions, rung context or syntax status',countsFilter(calculationOccurrences,'syntax_status'));
      renderList();
    }
    if(focus){document.getElementById('main').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
  }
  const nav=document.getElementById('navigation');
  Object.keys(labels).forEach(view=>{const b=button('',()=>go(view),'nav-button');b.dataset.view=view;b.append(node('span','',labels[view]));if(navCounts[view]!==undefined)b.append(node('span','nav-count',fmt(navCounts[view])));nav.append(b);});
  const mini=document.getElementById('snapshot-mini');mini.className='snapshot-mini';mini.textContent='SNAPSHOT '+String(data.snapshot.sha256||'').slice(0,12)+'\n'+fmt(data.snapshot.size_bytes)+' bytes';
  document.addEventListener('keydown',event=>{
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){const input=document.getElementById('review-search') || document.getElementById('pid-member-search');if(input){event.preventDefault();input.focus();input.select();}}
    if(event.key==='Escape'&&state.detail&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)){event.preventDefault();goBack();}
  });
  render();
})();
