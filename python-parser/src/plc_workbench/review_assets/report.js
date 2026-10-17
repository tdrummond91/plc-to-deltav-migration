/* All source evidence is inserted with textContent. This application is offline. */
(() => {
  'use strict';
  const PAGE_SIZE = 50;
  const ADDRESS_ROOT_PREVIEW = 120, ADDRESS_SUFFIX_PREVIEW = 160;
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
  const sfcConditions=data.sfc_conditions||null,sequenceConditions=sfcConditions?.transitions||[];
  const bySequenceCondition=new Map(sequenceConditions.map(x=>[x.id,x]));
  const bySequenceTransition=new Map(sequenceConditions.map(x=>[x.transition_id,x]));
  const bySequenceNode=new Map((sfcConditions?.nodes||[]).map(x=>[x.id,x]));
  const bySequenceReference=new Map((sfcConditions?.references||[]).map(x=>[x.id,x]));
  const bySequenceComment=new Map((sfcConditions?.comments||[]).map(x=>[x.id,x]));
  const sequenceContext=data.sfc_context||null;
  const bySequenceContext=new Map((sequenceContext?.references||[]).map(x=>[x.id,x]));
  const bySequenceContextReference=new Map((sequenceContext?.references||[]).map(x=>[x.condition_reference_id,x]));
  const bySequenceAddress=new Map((sequenceContext?.addresses||[]).map(x=>[x.id,x]));
  const bySequenceStepLink=new Map((sequenceContext?.step_links||[]).map(x=>[x.id,x]));
  const bySequenceGap=new Map((sequenceContext?.gaps||[]).map(x=>[x.id,x]));
  const executionContext=data.execution_context||null;
  const executionGroups={tasks:'Tasks',programs:'Programs',schedules:'Program schedules',designations:'Main and fault entries',calls:'Routine calls',control_occurrences:'Control boundaries',routine_contexts:'Routine bodies and callers'};
  const byExecution=new Map(),byExecutionSource=new Map(),byExecutionInstruction=new Map();
  Object.keys(executionGroups).forEach(group=>(executionContext?.[group]||[]).forEach(row=>{
    byExecution.set(row.id,{group,row});
    if(row.instruction_id)byExecutionInstruction.set(row.instruction_id,row.id);
    const sourceId=group==='tasks'?row.task_id:group==='programs'?row.program_id:row.routine_id;
    if(['tasks','programs','routine_contexts'].includes(group)&&sourceId)byExecutionSource.set(sourceId,row.id);
  }));
  const access = data.access || null;
  const tagData = data.tag_data || null;
  const pid = data.pid || null, pidOccurrences = pid?.occurrences || [];
  const pidMembers = data.pid_members || null;
  const pidConnections = data.pid_connections || null;
  const byPidConnection = new Map((pidConnections?.occurrences || []).map(x=>[x.id,x]));
  const byPidConnectionSlot = new Map((pidConnections?.slots || []).map(x=>[x.id,x]));
  const byPidConnectionAddress = new Map((pidConnections?.addresses || []).map(x=>[x.id,x]));
  const calculations = data.calculations || null, calculationOccurrences = calculations?.occurrences || [];
  const calculationPaths=data.calculation_paths||null, calculationPathOccurrences=calculationPaths?.occurrences||[];
  const byCalculationPath=new Map(calculationPathOccurrences.map(x=>[x.id,x]));
  const byCalculationRegion=new Map((calculationPaths?.regions||[]).map(x=>[x.id,x]));
  const calculationPathLinks=calculationPaths?.links||[];
  const rungAnalysis = data.rung_analysis || null, analyzedRungs = rungAnalysis?.rungs || [];
  const relationships = data.relationships || null, addresses = relationships?.addresses || [];
  const conditions = data.conditions || null, conditionalOutputs = conditions?.outputs || [];
  const outputContext=data.output_context||null, contextOutputs=outputContext?.outputs||[], contextAddresses=outputContext?.addresses||[];
  const byOutputContext=new Map(contextOutputs.map(o=>[o.id,o])),byConditionOutputContext=new Map(contextOutputs.map(o=>[o.condition_output_id,o]));
  const byOutputAddress=new Map(contextAddresses.map(a=>[a.id,a]));
  const byOutputRungContext=new Map((outputContext?.rung_contexts||[]).map(r=>[r.id,r]));
  const outputConditionReads=outputContext?.condition_reads||[];
  let outputConditionParents=null;
  const signalContext=data.signal_context||null,signalOutputs=signalContext?.outputs||[],signalAddresses=signalContext?.addresses||[],signalReads=signalContext?.condition_reads||[];
  const bySignalOutput=new Map(signalOutputs.map(o=>[o.id,o])),bySignalAddress=new Map(signalAddresses.map(a=>[a.id,a]));
  const bySignalRead=new Map(signalReads.map(r=>[r.id,r])),bySignalRung=new Map((signalContext?.rung_contexts||[]).map(r=>[r.id,r]));
  const signalReadsByNode=new Map();signalReads.forEach(r=>add(signalReadsByNode,r.condition_node_id,r));
  const SIGNAL_NODE_LIMIT=5000,SIGNAL_EDGE_LIMIT=10000;
  const fileOperations=data.file_operations||null,fileOccurrences=fileOperations?.occurrences||[];
  const byFileOperation=new Map(fileOccurrences.map(o=>[o.id,o]));
  const byFileSlot=new Map((fileOperations?.slots||[]).map(s=>[s.id,s]));
  const fileNodesByInstruction=new Map(),fileIndexesByInstruction=new Map(),fileOperationsByRung=new Map();
  (fileOperations?.expression_nodes||[]).forEach(n=>add(fileNodesByInstruction,n.instruction_id,n));
  const byFileNode=new Map((fileOperations?.expression_nodes||[]).map(n=>[n.id,n]));
  (fileOperations?.index_uses||[]).forEach(u=>add(fileIndexesByInstruction,(u.source_kind==='slot'?byFileSlot.get(u.source_id):byFileNode.get(u.source_id))?.instruction_id,u));
  const fileControlsByInstruction=new Map(),fileStoredByControl=new Map(),fileControlGaps=new Set();
  (fileOperations?.stored_data||[]).forEach(d=>{add(fileStoredByControl,d.control_id,d);if(d.status!=='qualified'||d.type_status==='mismatch')fileControlGaps.add(d.control_id);});
  (fileOperations?.controls||[]).forEach(c=>{c.occurrence_ids.forEach(id=>add(fileControlsByInstruction,id,c));if(c.declaration_kind!=='control'||['unresolved','static_out_of_bounds'].includes(c.bounds_status))fileControlGaps.add(c.id);});
  fileOccurrences.forEach(o=>add(fileOperationsByRung,o.rung_id,o));
  const statefulObjects=data.stateful_objects||null,statefulOccurrences=statefulObjects?.occurrences||[],statefulGroups=statefulObjects?.objects||[];
  const byStatefulOccurrence=new Map(statefulOccurrences.map(o=>[o.id,o])),byStatefulGroup=new Map(statefulGroups.map(o=>[o.id,o]));
  const statefulUsesByObject=new Map(),statefulStoredByObject=new Map(),statefulOccurrencesByRung=new Map();
  statefulOccurrences.forEach(o=>add(statefulOccurrencesByRung,o.rung_id,o));
  (statefulObjects?.address_uses||[]).forEach(u=>add(statefulUsesByObject,u.object_id,u));
  (statefulObjects?.stored_data||[]).forEach(u=>add(statefulStoredByObject,u.object_id,u));
  const statefulIssueContentIds=new Set((tagData?.issues||[]).map(i=>i.content_id));
  const statefulGroupGaps=new Map(statefulGroups.map(o=>[o.id,new Set([
    ...(o.type_conflict?['Declaration conflicts with observed instructions']:[]),
    ...(['unresolved','static_out_of_bounds'].includes(o.bounds_status)?['Array or control type unresolved']:[]),
    ...(o.family==='reset_only'?['No matching timer or counter occurrence']:[]),
    ...(o.family==='mixed'?['Timer and counter instructions share control']:[]),
    ...(o.content_ids.some(id=>statefulIssueContentIds.has(id))?['Stored data capture issues']:[])
  ])]));
  (statefulObjects?.address_uses||[]).forEach(u=>{const gaps=statefulGroupGaps.get(u.object_id);if(u.rejected_operand_ids.length||u.rejected_expression_use_ids.length)gaps.add('Unqualified namespace uses');if(u.member_status==='unknown')gaps.add('Uncatalogued member or suffix');if(u.unknown_operand_ids.length)gaps.add('Unknown operand roles');});
  (statefulObjects?.stored_data||[]).forEach(u=>{const gaps=statefulGroupGaps.get(u.object_id);if(u.status==='namespace_gap')gaps.add('Unqualified stored namespace');if(u.status==='shape_gap')gaps.add('Unqualified stored data shape');if(u.type_status==='mismatch')gaps.add('Stored structure type mismatch');});
  statefulOccurrences.forEach(o=>{if(o.control_address_id&&o.context_status!=='modeled')statefulGroupGaps.get(o.control_address_id).add('Incoming condition needs review');});
  const conditionNodes = conditions?.nodes || [], byConditionNode = new Map(conditionNodes.map(n=>[n.id,n]));
  const conditionNodeOrder = new Map(conditionNodes.map((n,i)=>[n.id,i]));
  const byConditionalOutput = new Map(conditionalOutputs.map(o=>[o.id,o]));
  const outputsByRung = new Map(), outputsByAddress = new Map();
  // Reuse the condition nodes: no duplicated serialized instruction contexts or
  // per-instruction ancestor lists. Older reports retain their original views.
  const instructionConditions = conditions?.schema_version>=2;
  const conditionTransfers = instructionConditions?conditionNodes.filter(n=>['pass_through','stateful_transfer','opaque_transfer'].includes(n.kind)):[];
  const transferByInstruction = new Map(conditionTransfers.map(n=>[n.instruction_id,n]));
  const transfersByRung = new Map();
  const bindingContext = data.binding_context || null, bindingContextGaps = bindingContext?.gaps || [];
  const byBindingContext = new Map(bindingContextGaps.map(g=>[g.source_id,g]));
  const customContext=data.custom_instruction_context || null, customCalls=customContext?.calls || [];
  const customDeclarations=customContext?.declarations || [], byCustomDeclaration=new Map(customDeclarations.map(d=>[d.source_id,d]));
  const byCustomCall=new Map(customCalls.map(c=>[c.instruction_id,c]));
  const indexedAccess=data.indexed_access || null, indexedUses=indexedAccess?.uses || [];
  const aoiBody=data.aoi_body_context||null,aoiBodyDeclarations=aoiBody?.declarations||[],aoiBodyRoutines=aoiBody?.routines||[],aoiBodySymbols=aoiBody?.symbols||[],aoiBodyCalls=aoiBody?.calls||[];
  const byAoiBodyDeclaration=new Map(aoiBodyDeclarations.map(d=>[d.declaration_id,d])),byAoiBodyRoutine=new Map(aoiBodyRoutines.map(r=>[r.routine_id,r])),byAoiBodySymbol=new Map(aoiBodySymbols.map(x=>[x.source_id,x])),byAoiBodyCall=new Map(aoiBodyCalls.map(c=>[c.instruction_id,c]));
  const sfrContext=data.sfr_context || null,sfrCalls=sfrContext?.calls || [],sfrSteps=sfrContext?.steps || [];
  const sfrGaps=sfrContext?.gap_contexts || [],sfrGapsByCall=new Map();
  const bySfrCall=new Map(sfrCalls.map(c=>[c.instruction_id,c])),bySfrStep=new Map(sfrSteps.map(s=>[s.element_id,s])),sfrCallsByRung=new Map();
  const byIndexedUse=new Map(indexedUses.map(u=>[u.id,u])), byIndexedSource=new Map(indexedUses.map(u=>[u.source_id,u])), indexedByRung=new Map();
  const candidateAddresses = bindingContext?.logical_addresses || [];
  const byCandidateAddress = new Map(candidateAddresses.map(a=>[a.id,a]));
  const byRackCandidate = new Map((refs.rack_candidates?.candidates || []).map(c=>[c.source_id,c]));
  const byRackMatch = new Map([...(refs.rack_candidates?.matches?.direct_operands || []),...(refs.rack_candidates?.matches?.alias_operands || [])].map(m=>[m.source_id,m]));
  const localLinks = relationships?.local_links || [], reusePatterns = relationships?.patterns || [];
  const byAddress = new Map(addresses.map(a=>[a.id,a])), byUseAddress = new Map();
  const byReusePattern = new Map(reusePatterns.map(p=>[p.id,p]));
  const byRungReuse = new Map((relationships?.rung_patterns || []).map(p=>[p.rung_id,p]));
  const addressesByRoot = new Map(), linksByRung = new Map(), linksByAddress = new Map();
  const addressRootPreviews = new Map();
  const byIdentityGap = new Map((relationships?.identity_gaps || []).map(g=>[g.id,g]));
  const byRungAnalysis = new Map(analyzedRungs.map(x => [x.id,x]));
  const byRungBlock = new Map((rungAnalysis?.blocks || []).map(x => [x.id,x]));
  const byRungCandidate = new Map((rungAnalysis?.candidates || []).map(x => [x.id,x]));
  const ENGINEERING_FAMILIES = {
    pid_control:'PID / control',calculation:'Calculations',boolean_output:'Boolean outputs',
    timer_counter:'Timers / counters',data_transfer:'Data transfers',communication_system:'Communications / system',
    sequence_control:'Sequence control',control_flow:'Program control flow',io_input:'I/O inputs',io_output:'I/O outputs',
    alarm:'Possible alarms',equipment:'Possible equipment',sensor:'Possible sensors',miscellaneous:'Miscellaneous logic'
  };
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
  const expressionUses = access?.expression_uses || [];
  const byExpressionUse = new Map(expressionUses.map(x => [x.id,x]));
  const byExpressionRoot = new Map((access?.expression_roots || []).map(x => [x.target_id,x]));
  // Operand slots and expression leaves have different identities and counts.
  // Merge only target declarations for navigation; never merge occurrence lists.
  const byRootAccess = new Map((access?.roots || []).map(x => [x.target_id,x]));
  byExpressionRoot.forEach((r,id) => {if(!byRootAccess.has(id))byRootAccess.set(id,{target_id:id});});
  const accessRoots = [...byRootAccess.values()];
  const byOperandAccess = new Map((access?.operands || []).map(x => [x.id, x]));
  const byInstructionAccess = new Map((access?.instructions || []).map(x => [x.id,x]));
  const rungExpressionUses = new Map(), entityExpressionUses = new Map();
  const expressionAccessGaps = (access?.operands || []).filter(x =>
    x.role==='expression_read' && x.binding_status!=='parsed_expression');
  const expressionBindingGaps = expressionUses.filter(x =>
    !['root_bound','literal','system_flag'].includes(x.binding_status));
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
  addresses.forEach(a=>{
    add(addressesByRoot,a.target_id,a);
    ['read_operand_ids','write_operand_ids','read_write_operand_ids','unknown_operand_ids','expression_use_ids'].forEach(key=>a[key].forEach(id=>byUseAddress.set(id,a)));
  });
  localLinks.forEach(l=>{add(linksByRung,l.rung_id,l);add(linksByAddress,l.address_id,l);});
  conditionalOutputs.forEach(o=>{add(outputsByRung,o.rung_id,o);add(outputsByAddress,o.target_address_id,o);});
  conditionTransfers.forEach(n=>add(transfersByRung,n.rung_id,n));
  indexedUses.forEach(u=>add(indexedByRung,u.rung_id,u));
  sfrCalls.forEach(c=>add(sfrCallsByRung,c.rung_id,c));
  sfrGaps.forEach(g=>add(sfrGapsByCall,g.instruction_id,g));
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
  expressionUses.forEach(a => {
    add(rungExpressionUses,a.rung_id,a);
    new Set([a.symbol_id,a.target_id,...(a.alias_chain || [])]).forEach(id=>add(entityExpressionUses,id,a));
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
  headings.calculationpaths=['Calculation inputs and destinations','Inspect captured block inputs, destinations, branch segments and possible local reuse, with unresolved evidence kept visible.'];
  headings.engineering=['Engineering analysis','Explore recognized instruction functions and possible purpose, with every rung accounted for and gaps kept in context.'];
  headings.relationships=['Address relationships','Follow exact expanded address spelling, its captured uses, and possible source-order calculation reuse.'];
  headings.conditions=['Conditional outputs','Trace captured conditions leading to OTE, OTL and OTU instructions, with branch paths and unknown transfers kept visible.'];
  if(outputContext)headings.conditions=['Boolean output context','Inspect coil actions, exact target uses, captured condition readers and authored rung hints with unresolved evidence kept visible.'];
  headings.transfers=['Instruction conditions','Inspect incoming rung conditions and normal-scan condition transfer at other instruction occurrences, including rungs without a coil output.'];
  headings.bindingcontext=['Binding gaps & context','Follow unresolved source occurrences through their alias chains and available rack-name candidates. Candidate addresses remain separate from confirmed root bindings.'];
  headings.instructioncontext=['Instruction & index context','Inspect custom-instruction declaration candidates and symbolic array selectors while unresolved roles and exact-element gaps remain visible.'];
  headings.sfrcontext=['Sequence reset context','Follow captured SFR routine and step candidates across every exported SFC content version. Reset effects and outgoing rung conditions remain unresolved.'];
  headings.statefulobjects=['Timers, counters & resets','Connect captured timer and counter occurrences, reset instructions, exact member uses and separately retained stored values.'];
  headings.sequenceconditions=['Sequence conditions','Inspect captured transition expressions, their source grouping, reference leaves and unresolved evidence.'];
  headings.executioncontext=['Execution context','Inspect source-declared tasks, program entries, routine call candidates and control boundaries with unresolved evidence kept visible.'];
  headings.signalcontext=['Signal relationships','Follow exact addresses through captured output guards, comparison operands, stored-state boundaries and source occurrences.'];
  headings.fileoperations=['File and array operations','Inspect copies, averages, file arithmetic and sequencer writes, with operand roles, symbolic ranges and unresolved evidence.'];
  const navCounts = {objects:entities.length,ladder:rungs.length,sfc:bySfcRoutine.size,patterns:patterns.length,findings:findings.length};
  const labels = {overview:'Overview',...(rungAnalysis?{engineering:'Engineering analysis'}:{}),objects:'Objects',ladder:'Ladder',sfc:'SFC',patterns:'Patterns',findings:'Findings'};
  if(executionContext){labels.executioncontext='Execution context';navCounts.executioncontext=executionContext.calls.length;}
  if(signalContext){labels.signalcontext='Signal relationships';navCounts.signalcontext=signalAddresses.length;}
  if(fileOperations){labels.fileoperations='File and array operations';navCounts.fileoperations=fileOccurrences.length;}
  if(rungAnalysis)navCounts.engineering=analyzedRungs.length;
  if(relationships){labels.relationships='Address relationships';navCounts.relationships=addresses.length;}
  if(statefulObjects){labels.statefulobjects='Timers, counters & resets';navCounts.statefulobjects=statefulOccurrences.length;}
  if(sfcConditions){labels.sequenceconditions='Sequence conditions';navCounts.sequenceconditions=sequenceConditions.length;}
  if(conditions){labels.conditions=outputContext?'Boolean output context':'Conditional outputs';navCounts.conditions=conditionalOutputs.length;}
  if(instructionConditions){labels.transfers='Instruction conditions';navCounts.transfers=conditionTransfers.length;}
  if(bindingContext){labels.bindingcontext='Binding gaps & context';navCounts.bindingcontext=bindingContextGaps.length;}
  if(customContext&&indexedAccess){labels.instructioncontext='Instruction & index context';navCounts.instructioncontext=customCalls.length+indexedUses.length;}
  if(sfrContext){labels.sfrcontext='Sequence reset context';navCounts.sfrcontext=sfrCalls.length;}
  if(access){labels.access='Tag access';navCounts.access=accessRoots.length;}
  if(tagData){labels.tagdata='Stored tag data';navCounts.tagdata=tagContents.length;}
  if(pid){labels.pid='PID evidence';navCounts.pid=pidOccurrences.length;}
  if(calculations){labels.calculations='Calculations';navCounts.calculations=calculationOccurrences.length;}
  if(calculationPaths){labels.calculationpaths='Calculation inputs and destinations';navCounts.calculationpaths=calculationPathOccurrences.length;}
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
    const good=['complete','parsed','parsed_expression','resolved','root_bound','literal','non_data','system_flag','info','read','write','read_write','expression_read','classified','initialization_field'].includes(v);
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
  function rungNumber(r) { return String(r.number ?? '').trim() ? 'Rung '+short(r.number,30) : 'Unnumbered rung · position '+r.ordinal; }
  function rungName(r) { return rungNumber(r)+' · '+short(entityName(r.parent_id),100); }
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
    return {source_references:'Original reference analysis',access_resolver:'Instruction access analysis',access_non_data:'Instruction selector or initialization field',calculation_expression:'Calculation expression analysis'}[a.binding_origin] || 'Original reference analysis';
  }
  function accessBindingTable(rows,caption) {
    const result=node('div');
    result.append(table(['Operand','Instruction / argument','Role','Access binding','Declared / resolved root','Resolved suffix',...(bindingContext?['Binding context']:[])],rows,a=>{
      const o=byOperand.get(a.id);
      return [link(o.raw_text || '(blank)',o.id),
        (byInstruction.get(a.instruction_id)?.instruction.opcode || 'Instruction')+' · '+(a.argument_index+1),
        accessCell(a),primary(badge(a.binding_status),accessBindingOrigin(a)+(a.binding_reason?' · '+human(a.binding_reason):'')),
        a.role==='expression_read'?primary(button('Open expression',()=>openDetail('calculation',a.instruction_id),'text-link'),'Container; inspect its reference leaves'):bindingRoots(a,a.binding_reason),node('span','mono',a.suffix || (a.target_id?'(root operand)':'—')),...(bindingContext?[bindingContextLink(a.id)]:[])];
    },caption));
    const opcodes=new Set(rows.map(a=>byInstruction.get(a.instruction_id)?.instruction.opcode.toUpperCase()));
    if(opcodes.has('CTU') || opcodes.has('CTD'))result.append(node('p','row-note','Counter preset and accumulator fields describe initialization, not separate runtime reads. A question mark supplies no value. Counter values and configuration are not validated.'));
    if(opcodes.has('MSG'))result.append(node('p','row-note','MSG covers possible reads and writes of its control operand only. Message payload sources, destinations and communication effects are not modeled.'));
    if(opcodes.has('GSV') || opcodes.has('SSV'))result.append(node('p','row-note','GSV/SSV class, instance and attribute selectors are not tag bindings. A blank instance is allowed; system state and the selected attribute are not validated.'));
    if(opcodes.has('SFR'))result.append(node('p','row-note','SFR records a possible write to an explicit step, or an initial-step selector of 0. SFC membership and wider reset effects are not validated.'));
    if(opcodes.has('CPT') && access.schema_version>=4)result.append(node('p','row-note','CPT destinations are potential writes. The whole expression is a container, not a single tag or a non-data selector. Only fully parsed expressions publish separate potential read occurrences; unsupported expressions remain access gaps.'));
    return result;
  }
  function expressionUseTable(rows,caption) {
    return table(['Expression reference','Character span','Role','Binding','Declared / resolved root','Resolved suffix','Rung',...(bindingContext?['Binding context']:[])],rows,a=>[
      button(byCalculationNode.get(a.id)?.raw_text || '(reference)',()=>openDetail('calculation',a.instruction_id,{focusCalculationNode:a.id}),'text-link'),
      node('span','mono',calculationSpan(a)),badge(a.role),primary(badge(a.binding_status),a.binding_reason?human(a.binding_reason):''),
      calculationBinding({...a,reason:a.binding_reason}),node('span','mono',a.suffix || (a.target_id?'(root reference)':'—')),sourceCell(a.rung_id),...(bindingContext?[bindingContextLink(a.id)]:[])
    ],caption,{emptyTitle:'No expression read occurrences in this selection',emptyDetail:'Only fully parsed expressions publish reference leaves. Literal-only expressions contribute no reference reads.'});
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
  function openDetail(type,id,extra={}) { backStack.push({...state});state={...state,detail:{type,id},focusOperand:null,focusInstruction:null,focusCalculationNode:null,focusConditionNode:null,...(type==='pid'?{pidMemberQuery:'',pidMemberGroup:'all'}:{}),...extra};render(true); }
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
  analyzedRungs.forEach(a=>{
    const r=byRung.get(a.id),candidates=a.candidate_ids.map(id=>byRungCandidate.get(id));
    searchable(a,[rungName(r),r.number,r.text,r.comment,entityPath(r.parent_id),a.identification,a.structure,a.result_kind,
      ...a.block_ids.map(id=>byRungBlock.get(id)?.opcode),
      ...candidates.flatMap(c=>[ENGINEERING_FAMILIES[c.category],c.basis,c.reason,...c.missing_evidence])]);
  });
  patterns.forEach(p=>searchable(p,[p.shape,...(p.opcode_summary||[]).map(o=>o.opcode)]));
  findings.forEach(f=>searchable(f,[f.code,f.message,f.origin,f.severity,f.locator,sourceName(f.source_id)]));
  accessRoots.forEach(r=>searchable(r,[entityName(r.target_id),entityPath(r.target_id)]));
  addresses.forEach(a=>searchable(a,[addressName(a),entityPath(a.target_id),addressProfile(a)]));
  // One bounded label per output; never copy ancestor conditions or complete
  // rung source into every coil's search record.
  conditionalOutputs.forEach(o=>searchable(o,[o.opcode,conditionTargetName(o),sourceName(o.rung_id),conditionGuardLabel(o.guard_status),conditionActionLabel(o.action),human(o.target_status)]));
  contextOutputs.forEach(o=>searchable(o,[o.opcode,outputContextName(o),sourceName(o.rung_id),human(o.target_status),human(o.context_status),...outputRungHintCategories(o.rung_id)]));
  contextAddresses.forEach(a=>searchable(a,[addressName(byAddress.get(a.id)),human(a.endpoint_kind),human(a.profile)]));
  statefulOccurrences.forEach(o=>searchable(o,[o.opcode,statefulOccurrenceName(o),sourceName(o.rung_id),human(o.target_status),human(o.context_status)]));
  sequenceConditions.forEach(t=>searchable(t,[sequenceConditionName(t),entityPath(t.routine_id),t.raw_text,human(t.status),human(t.reason),...(t.metadata_gaps||[]).map(human),...t.reference_ids.map(id=>human(bySequenceGap.get(bySequenceContextReference.get(id)?.gap_id)?.kind||''))]));
  statefulGroups.forEach(o=>searchable(o,[addressName(byAddress.get(o.id)),human(o.family),human(o.declaration_kind),human(o.bounds_status),...o.producer_ids.map(id=>byStatefulOccurrence.get(id)?.opcode)]));
  conditionTransfers.forEach(n=>searchable(n,[transferOpcode(n),short(sourceName(n.rung_id),240),transferLabel(n),conditionGuardLabel(conditionQuality(n)),...n.operand_ids.slice(0,4).map(id=>short(byOperand.get(id)?.raw_text || '',80))]));
  // Index bounded previews once per occurrence/group. Alias chains, expanded
  // source text and ancestor graphs are inspected only in the selected dossier.
  bindingContextGaps.forEach(g=>searchable(g,[bindingGapName(g),bindingCategory(g.category),human(g.kind),short(sourceName(bindingUse(g)?.rung_id),180),short(byRackCandidate.get(g.candidate_id)?.name,120)]));
  customCalls.forEach(c=>searchable(c,[short(sourceName(c.instruction_id),120),human(c.status),short(entityName(c.declaration_id),120),short(sourceName(c.rung_id),120)]));
  customDeclarations.forEach(d=>searchable(d,[short(entityName(d.source_id),160),human(d.status),human(d.protection_marker)]));
  indexedUses.forEach(u=>searchable(u,[short(indexedRaw(u),200),human(u.kind),human(u.role),human(u.disposition),short(sourceName(u.rung_id),120)]));
  sfrCalls.forEach(c=>searchable(c,[short(sourceName(c.instruction_id),120),short(sourceName(c.target_routine_id),120),human(c.routine_status),human(c.chart_status),human(c.selector_kind),short(sourceName(c.rung_id),120)]));
  candidateAddresses.forEach(a=>searchable(a,[candidateAddressName(a),human(a.profile)]));
  localLinks.forEach(l=>searchable(l,[addressName(byAddress.get(l.address_id)),sourceName(l.rung_id),sourceName(l.producer_instruction_id),sourceName(l.consumer_instruction_id),l.read_kind==='expression'?'Expression read':'Operand read']));
  reusePatterns.forEach(p=>searchable(p,[rungName(byRung.get(p.representative_rung_id)),byRung.get(p.representative_rung_id)?.text,p.rung_ids.length>1?'Repeated operand reuse':'Single occurrence',p.address_variables+' address variables']));
  (relationships?.identity_gaps || []).forEach(g=>searchable(g,[byOperand.get(g.id)?.raw_text,byCalculationNode.get(g.id)?.raw_text,'Expanded suffix cannot form an address',g.kind]));
  accessGaps.forEach(i=>searchable(i,[i.opcode,i.status,sourceName(i.rung_id)]));
  accessBindingGaps.forEach(o=>searchable(o,[byOperand.get(o.id)?.raw_text,o.role,o.binding_status,sourceName(o.rung_id)]));
  expressionAccessGaps.forEach(o=>searchable(o,[byOperand.get(o.id)?.raw_text,o.role,o.binding_status,sourceName(o.rung_id)]));
  expressionBindingGaps.forEach(o=>searchable(o,[byCalculationNode.get(o.id)?.raw_text,o.binding_status,sourceName(o.rung_id)]));
  // Index each data record once, never concatenating a whole descendant tree.
  tagContents.forEach(c=>searchable(c,[short(entityName(c.owner_id)),c.xml_name,c.format_kind,c.direct_text,...Object.values(c.attributes||{})]));
  tagElements.forEach(e=>searchable(e,[short(entityName(e.owner_id)),e.xml_name,e.kind,e.direct_text,...Object.values(e.attributes||{})]));
  pidOccurrences.forEach(p=>searchable(p,[p.signature_status,p.storage_status,sourceName(p.rung_id),entityPath(byRung.get(p.rung_id)?.parent_id),...p.operand_ids.map(id=>byOperand.get(id)?.raw_text)]));
  calculationOccurrences.forEach(c=>searchable(c,[c.signature_status,c.syntax_status,c.error_code,sourceName(c.rung_id),entityPath(byRung.get(c.rung_id)?.parent_id),byOperand.get(c.destination_operand_id)?.raw_text,byOperand.get(c.expression_operand_id)?.raw_text]));
  calculationPathOccurrences.forEach(c=>searchable(c,[c.opcode,c.status,c.gap_reason,c.condition_quality,sourceName(c.rung_id),entityPath(byRung.get(c.rung_id)?.parent_id),byOperand.get(c.destination_operand_id)?.raw_text,...c.input_operand_ids.map(id=>byOperand.get(id)?.raw_text)]));
  // Index a member once even when several PID occurrences share its structure.
  (pidMembers?.members || []).forEach(m=>searchable(m,[m.field,pidMemberLabel(m.field),m.group,m.status,byTagElement.get(m.element_id)?.attributes?.Name]));
  // Bounded previews per record; no copied caller paths or condition subgraphs.
  Object.keys(executionGroups).forEach(group=>(executionContext?.[group]||[]).forEach(row=>searchable(row,[
    executionGroups[group],executionName(group,row),human(row.status),human(row.lexical_status),human(row.body_status),human(row.guard_quality),human(row.argument_shape),executionQualification(row),
    short(entityPath(row.caller_routine_id||row.routine_id||row.program_id||row.task_id),200),
    ...Object.values(row.raw_attributes||{}).slice(0,10).map(value=>short(value,120)),
    ...(row.raw_arguments||[]).slice(0,4).map(value=>short(value,80))
  ])));
  const sfcSearch = new Map();elements.forEach(e=>add(sfcSearch,e.routine_id,[e.kind,e.direct_text,...Object.values(e.attributes||{})].join(' ')));
  (sfc.routines || []).forEach(r=>searchable(r,[entityPath(r.routine_id),...(sfcSearch.get(r.routine_id)||[])]));
  signalAddresses.forEach(a=>searchable(a,[addressName(byAddress.get(a.id)),human(a.profile),human(a.endpoint_kind),entityPath(a.target_id)]));
  signalOutputs.forEach(o=>searchable(o,[o.opcode,byOperand.get(o.target_operand_id)?.raw_text,sourceName(o.rung_id),entityPath(o.routine_id),human(o.guard_quality),human(o.target_status)]));
  signalReads.forEach(r=>searchable(r,[byOperand.get(r.id)?.raw_text,r.kind,r.status,sourceName(r.rung_id),entityPath(byRung.get(r.rung_id)?.parent_id)]));
  fileOccurrences.forEach(o=>searchable(o,[o.opcode,human(o.signature_status),human(o.context_status),human(o.expression_status),sourceName(o.rung_id),byRung.get(o.rung_id)?.comment,entityPath(o.routine_id),...o.slot_ids.map(id=>byFileSlot.get(id)?.raw_text)]));
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
    content.append(notice(rungAnalysis?'Automated analysis in progress':'Captured source for analysis',rungAnalysis
      ? 'Start with Engineering analysis to see recognized functions, possible purpose and unresolved blocks together. These are automated findings; engineering confirmation has not been recorded.' : access
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
    if(pidConnections){const row=node('div','status-row');row.append(node('span','','PID source connections'),badge(pidConnections.status));capture.append(row);}
    if(calculations){const row=node('div','status-row');row.append(node('span','','CPT expression syntax and references'),badge(calculations.status));capture.append(row);}
    if(calculationPaths){const row=node('div','status-row');row.append(node('span','','Calculation inputs and destinations'),badge(calculationPaths.status));capture.append(row);}
    if(statefulObjects){const row=node('div','status-row');row.append(node('span','','Timer, counter and reset context'),badge(statefulObjects.status));capture.append(row);}
    if(sfcConditions){const row=node('div','status-row');row.append(node('span','','SFC transition expression syntax'),badge(sfcConditions.status));capture.append(row);}
    if(executionContext){const row=node('div','status-row');row.append(node('span','','Execution context'),badge(executionContext.status));capture.append(row);}
    if(signalContext){const row=node('div','status-row');row.append(node('span','','Signal relationships'),badge(signalContext.status));capture.append(row);}
    if(sequenceContext){const row=node('div','status-row');row.append(node('span','','SFC reference relationships'),badge(sequenceContext.status));capture.append(row);}
    if(outputContext){const row=node('div','status-row');row.append(node('span','','Boolean output context'),badge(outputContext.status));capture.append(row);}
    if(customContext){const row=node('div','status-row');row.append(node('span','','Custom-instruction declaration context'),badge(customContext.status));capture.append(row);}
    if(indexedAccess){const row=node('div','status-row');row.append(node('span','','Symbolic array selector context'),badge(indexedAccess.status));capture.append(row);}
    if(aoiBody){const row=node('div','status-row');row.append(node('span','','AOI body and instance context'),badge(aoiBody.status));capture.append(row);}
    if(sfrContext){const row=node('div','status-row');row.append(node('span','','SFR routine and step context'),badge(sfrContext.status));capture.append(row);}
    capture.append(node('p','row-note',fmt(bySfcRoutine.size)+' SFC routines · '+fmt((sfc.links||[]).length)+' structural links · '+fmt((sfc.annotations||[]).length)+' note attachments'));
    const start=panel('Start your review','Each view links back to the exact evidence in this captured source snapshot.');
    if(rungAnalysis){const b=button('',()=>go('engineering'),'jump-card');const copy=node('span');copy.append(node('strong','','Explore engineering analysis'),node('small','','Follow function families, branch structure and uncertainty before reviewing individual instructions.'));b.append(copy,node('span','jump-arrow','→'));start.append(b);}
    [['objects','Find an object','Inspect declarations, source descriptions and where operands refer to them.'],['patterns','Compare repeated ladder','Group repeated syntax and open each occurrence in its own context.'],['findings','Work through capture gaps','Inspect unresolved and unsupported evidence before choosing a correction.']].forEach(([view,title,detail])=>{const b=button('',()=>go(view),'jump-card');const copy=node('span');copy.append(node('strong','',title),node('small','',detail));b.append(copy,node('span','jump-arrow','→'));start.append(b);});
    grid.append(capture,start);content.append(grid);
    if(access)content.append(button('Explore tag reads and writes',()=>go('access')));
    if(tagData)content.append(button('Explore stored tag data',()=>go('tagdata')));
    if(pid)content.append(button('Explore PID instruction evidence',()=>go('pid')));
    if(calculations)content.append(button('Explore calculations',()=>go('calculations')));
    if(statefulObjects)content.append(button('Explore timers, counters and resets',()=>go('statefulobjects')));
    if(sfcConditions)content.append(button('Explore sequence conditions',()=>go('sequenceconditions')));
    if(calculationPaths)content.append(button('Explore calculation inputs and destinations',()=>go('calculationpaths')));
    const meta=panel('Snapshot details','This report is read-only. IDs belong to this byte snapshot and are not persistent equipment or correction identities.');
    meta.append(values({'Source size':fmt(data.snapshot.size_bytes)+' bytes','SHA-256':data.snapshot.sha256,'Report format':data.report_version,'Inventory parser':inv.parser_version,'Reference analyzer':refs.analyzer_version,'SFC analyzer':sfc.analyzer_version}));content.append(meta);
  }
  function objectList(){const rows=entities.filter(e=>matches(e)&&(state.filter==='all'||e.kind===state.filter));content.append(table(['Object','Type','Scope','Description'],rows,e=>[primary(link(e.name || '(unnamed)',e.id),e.attributes?.DataType),human(e.kind),entityPath(e.scope_id),short(e.description || 'No description captured.')],'Source objects',{emptyTitle:'No objects match your search',emptyDetail:'Search by name, scope, description or attribute value.'}));}
  function accessNotice() {
    return notice('Explicit operand uses only','Reads and writes describe possible uses of supported ladder operand slots. Rung conditions, scan order, implicit status flags, SFC/ST code and unsupported instructions are not modeled. A shared root does not prove that members or array elements overlap. Missing accesses do not establish that a tag is unused or read-only.'+(access.schema_version>=2?' Timer initialization fields are not runtime inputs; their values are not validated. Copy roles identify starting operands and length use, not the copied range or overlap.':'')+(access.schema_version>=3?' Counter initialization fields are also not runtime inputs. MSG covers its control operand only; message payloads are not modeled. GSV/SSV class, instance and attribute selectors are not tag bindings; a blank instance is allowed. SFR records a possible write to an explicit step, or an initial-step selector of 0; SFC membership and wider reset effects are not validated.':'')+(access.schema_version>=4?' CPT expression reads count individual reference leaves separately from operand slots. Repeated references remain separate; a destination write and an expression read of the same root do not establish execution, member overlap or a dependency.':''));
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
    if(access.schema_version>=4)totals.append(values({'Classified CPT instructions':c.calculation_instructions,
      'Parsed expression containers':c.expression_containers_by_status.parsed,
      'Unsupported expression containers':c.expression_containers_by_status.unsupported,
      'Expression reference read occurrences':c.expression_uses_total,
      'Root-bound expression read occurrences':c.expression_uses_by_binding.root_bound,
      'Roots with expression reads':c.expression_indexed_roots,
      'Expressions with reference binding gaps':c.expressions_with_binding_gaps}));
    if(access.schema_version>=4){
      const bindings=node('details','technical');bindings.append(node('summary','','Expression read binding counts'),
        values(Object.fromEntries(Object.entries(c.expression_uses_by_binding).map(([status,count])=>[human(status),count]))));totals.append(bindings);
    }
    content.append(totals);
    const rows=accessRoots.filter(matches);
    const roots=section('Resolved tag roots','Read/write is a separate operand category; it is not counted twice. Open a count to inspect its exact occurrences and suffixes.'+(access.schema_version>=4?' Expression reads count separate reference leaves, including repetitions. They are not included in operand-read counts.':''));
    roots.append(table(['Root','Scope',access.schema_version>=4?'Operand reads':'Read','Write','Read/write','Unknown',...(access.schema_version>=4?['Expression reads']:[])],rows,r=>[
      link(entityName(r.target_id),r.target_id),entityPath(byEntity.get(r.target_id)?.scope_id),
      ...accessRoles.map(role=>button(fmt(roleIds(r,role).length),()=>openDetail('access',r.target_id,{accessRole:role}),'text-link')),
      ...(access.schema_version>=4?[button(fmt(byExpressionRoot.get(r.target_id)?.read_use_ids.length),()=>openDetail('access',r.target_id,{accessRole:'expression_read'}),'text-link')]:[])
    ],'Root access groups'));content.append(roots);
    const bindingGaps=section('Known roles with unresolved access','A known instruction role does not make its operand a valid tag reference. These slots are excluded from the resolved-root groups.');
    bindingGaps.append(table(['Operand','Role','Binding','Rung',...(bindingContext?['Binding context']:[])],accessBindingGaps.filter(matches),a=>[
      sourceCell(a.id),badge(a.role),badge(a.binding_status),sourceCell(a.rung_id),...(bindingContext?[bindingContextLink(a.id)]:[])
    ],'Unresolved operand accesses',{emptyTitle:'No unresolved access slots match',emptyDetail:'Unknown instruction roles are listed separately below.'}));content.append(bindingGaps);
    if(access.schema_version>=4){
      const expressions=section('Expression access gaps','Unsupported expression syntax contributes no partial read occurrences. Parsed expressions with unresolved reference roots are listed separately. Neither gap removes the original reference finding.');
      expressions.append(table(['Expression','Binding','Rung'],expressionAccessGaps.filter(matches),a=>[
        button(byOperand.get(a.id)?.raw_text || '(expression)',()=>openDetail('calculation',a.instruction_id),'text-link'),badge(a.binding_status),sourceCell(a.rung_id)
      ],'Unsupported expression accesses',{emptyTitle:'No unsupported expression containers match',emptyDetail:'This describes CPT syntax coverage only; it does not establish engineering correctness.'}));
      expressions.append(expressionUseTable(expressionBindingGaps.filter(matches),'Unresolved expression reads'));content.append(expressions);
    }
    const gaps=section('Instructions with unknown roles','These instructions may access data even when the reference parser cannot link their operands. Zero-argument instructions remain visible. Search also matches opcode and rung context.');
    gaps.append(table(['Instruction','Rung','Access classification'],accessGaps.filter(matches),i=>[
      link(i.opcode,i.id),sourceCell(i.rung_id),badge(i.status)
    ],'Unclassified access instructions',{emptyTitle:'No unclassified instructions match',emptyDetail:'This does not cover uncaptured logic, implicit effects or languages outside ladder.'}));content.append(gaps);
  }
  function accessDetail(root) {
    setDetailHeading('ROOT ACCESS',entityName(root.target_id),entityPath(byEntity.get(root.target_id)?.parent_id));
    content.append(accessNotice(),sourceCell(root.target_id));
    if(relationships){const exact=section('Exact expanded addresses','Root access combines all suffixes. These dossiers keep each captured suffix spelling separate.');exact.append(addressTable(addressesByRoot.get(root.target_id)||[],'Root exact address groups'));content.append(exact);}
    const box=node('div','toolbar'),label=node('label','filter-wrap',access.schema_version>=4?'Access occurrences':'Operand role'),select=node('select');
    select.setAttribute('aria-label','Access operand role');
    [['all','All roles'],...accessRoles.map(r=>[r,access.schema_version>=4 && r==='read'?'Operand reads':human(r)]),...(access.schema_version>=4?[['expression_read','Expression reads']]:[])].forEach(([v,t])=>{const o=node('option','',t);o.value=v;select.append(o);});
    select.value=state.accessRole || 'all';select.addEventListener('change',()=>{state.accessRole=select.value;render();});label.append(select);box.append(label);content.append(box);
    const roles=state.accessRole && state.accessRole!=='all'?[state.accessRole]:accessRoles;
    const rows=roles.flatMap(role=>roleIds(root,role)).map(id=>byOperandAccess.get(id)).filter(Boolean);
    if(state.accessRole!=='expression_read')content.append(table(['Operand','Role','Rung','Instruction / argument','Declared / resolved root','Resolved suffix','Binding analysis'],rows,a=>[
      link(byOperand.get(a.id).raw_text,a.id),accessCell(a),sourceCell(a.rung_id),
      (byInstruction.get(a.instruction_id)?.instruction.opcode||'Instruction')+' · '+(a.argument_index+1),
      bindingRoots(a,a.binding_reason),node('span','mono',a.suffix || '(root operand)'),accessBindingOrigin(a)
    ],'Root access occurrences'));
    if(access.schema_version>=4 && (!state.accessRole || ['all','expression_read'].includes(state.accessRole))){
      const expressions=section('Potential expression reads','Each row is one captured reference occurrence. Open it to inspect the exact character span and calculation source.');
      expressions.append(expressionUseTable((byExpressionRoot.get(root.target_id)?.read_use_ids || []).map(id=>byExpressionUse.get(id)),'Root expression read occurrences'));content.append(expressions);
    }
  }
  function addressRootPreview(id){
    // A shared declaration may have a very long name and thousands of suffix
    // groups. Keep it once in source evidence, not in every label/search row.
    if(!addressRootPreviews.has(id))addressRootPreviews.set(id,short(entityName(id),ADDRESS_ROOT_PREVIEW));
    return addressRootPreviews.get(id);
  }
  function addressName(a){return addressRootPreview(a.target_id)+short(a.suffix || '',ADDRESS_SUFFIX_PREVIEW);}
  function shortenedAddress(a){return entityName(a.target_id).length>ADDRESS_ROOT_PREVIEW||(a.suffix || '').length>ADDRESS_SUFFIX_PREVIEW;}
  function addressPreviewNote(){return node('p','row-note','Long address labels and their search text use shortened previews. Open an address dossier for the full suffix, and its declaration for the full root name. Exact identities remain separate.');}
  function addressProfile(a){return ({read_and_write:'Captured reads and writes',read_only:'No captured explicit writer',write_only:'No captured explicit reader',unknown_only:'Unknown roles only'})[a.profile] || human(a.profile);}
  function addressNotice(){const box=node('div');box.append(notice('Exact spelling, captured occurrences','A dossier groups one resolved declaration and its expanded suffix spelling. Different spellings remain separate; this does not validate members or prove whether two addresses overlap. Missing captured readers or writers do not establish dead or uninitialized logic.'));if(addresses.some(shortenedAddress))box.append(addressPreviewNote());return box;}
  function addressCell(id){
    const a=byUseAddress.get(id);
    if(a)return button('Address: '+addressName(a),()=>openDetail('address',a.id),'text-link');
    const gap=byIdentityGap.has(id)?node('span','badge warn','Expanded suffix cannot form an address'):node('span','muted','No exact address group');
    if(byBindingContext.has(id)){const box=node('div');box.append(gap,bindingContextLink(id));return box;}
    return gap;
  }
  function bindingUse(g){return g?.kind==='expression'?byExpressionUse.get(g.source_id):byOperandAccess.get(g?.source_id);}
  function contextNotice(){return notice('Context with explicit limits','A custom-instruction name match identifies a declaration candidate. Its parameter order, operand roles, internal behavior and effects remain unvalidated. Symbolic array selectors identify a root and possible index reads; no index value, selected element, bounds, overlap or execution is inferred. Existing unresolved classifications remain visible.');}
  function executionQualification(row){return row.qualified?'Source qualified':'Namespace gap';}
  function executionName(group,row){
    if(group==='tasks')return short(entityName(row.task_id),160);
    if(group==='programs')return short(entityName(row.program_id),160);
    if(group==='routine_contexts')return short(entityName(row.routine_id),160);
    if(group==='schedules')return row.raw_name===null?'No program name':short(row.raw_name||'(empty program name)',160);
    if(group==='designations')return human(row.kind)+' entry: '+(row.raw_name===null?'not declared':short(row.raw_name||'(empty name)',120));
    if(group==='calls')return 'JSR '+short(row.raw_target_name||'(missing target)',140);
    return row.opcode+(row.raw_label_name!==null?' '+short(row.raw_label_name||'(empty label)',140):' boundary');
  }
  function executionLink(group,row){return button(executionName(group,row),()=>openDetail('executioncontext',row.id),'text-link');}
  function executionRecordLink(id){const found=byExecution.get(id);return found?executionLink(found.group,found.row):node('span','muted','No captured context');}
  function executionEntityLink(id){const contextId=byExecutionSource.get(id);return contextId?executionRecordLink(contextId):sourceCell(id);}
  function executionNotice(){return notice('Declared context and lexical candidates','Task ownership, schedule rows and routine names describe captured source. They do not prove execution, scan order, active edits or effective task settings. Incoming condition links reuse the captured condition graph without expanding caller paths. Parameter roles, types, value flow and call validity remain unvalidated.');}
  function executionTable(group,rows,caption){
    if(group==='tasks')return table(['Task','Type / rate text','Priority / watchdog text','Schedule rows','Qualification'],rows,r=>[
      executionLink(group,r),primary(r.raw_attributes.Type??'Not present','Rate: '+(r.raw_attributes.Rate??'Not present')),primary(r.raw_attributes.Priority??'Not present','Watchdog: '+(r.raw_attributes.Watchdog??'Not present')),fmt(r.schedule_ids.length),executionQualification(r)
    ],caption);
    if(group==='programs')return table(['Program','Declared type','Unique schedule associations','Entry designations','Qualification'],rows,r=>[
      executionLink(group,r),r.raw_attributes.Type??'Not present',fmt(r.schedule_ids.length),fmt(r.designation_ids.length),executionQualification(r)
    ],caption);
    if(group==='schedules')return table(['Scheduled name','Owning task','Source position','Candidate result','Candidates'],rows,r=>[
      executionLink(group,r),executionEntityLink(r.task_id),r.ordinal,primary(badge(r.status),executionQualification(r)),fmt(r.candidate_program_ids.length)
    ],caption);
    if(group==='designations')return table(['Declared entry','Program','Candidate result','Routine candidates'],rows,r=>[
      executionLink(group,r),executionEntityLink(r.program_id),primary(badge(r.status),executionQualification(r)),fmt(r.candidate_routine_ids.length)
    ],caption);
    if(group==='calls')return table(['Call target','Caller routine','Candidate result','Incoming condition','Argument shape','Source rung'],rows,r=>[
      executionLink(group,r),executionEntityLink(r.caller_routine_id),primary(badge(r.status),fmt(r.candidate_routine_ids.length)+' declaration candidates'),human(r.guard_quality),primary(human(r.argument_shape),fmt(r.argument_count)+' captured fields'),sourceCell(r.rung_id)
    ],caption);
    if(group==='control_occurrences')return table(['Boundary / label','Caller routine','Label candidate result','Incoming condition','Argument shape','Source rung'],rows,r=>[
      executionLink(group,r),executionEntityLink(r.caller_routine_id),badge(r.status),human(r.guard_quality),human(r.argument_shape),sourceCell(r.rung_id)
    ],caption);
    return table(['Routine','Body evidence','Incoming / outgoing calls','Entry designations','Boundaries','Qualification'],rows,r=>[
      executionLink(group,r),human(r.body_status),fmt(r.incoming_call_ids.length)+' / '+fmt(r.outgoing_call_ids.length),fmt(r.designation_ids.length),fmt(r.control_occurrence_ids.length),executionQualification(r)
    ],caption);
  }
  const executionCaptions={tasks:'Execution tasks',programs:'Execution programs',schedules:'Execution program schedules',designations:'Execution main and fault entries',calls:'Execution routine calls',control_occurrences:'Execution control boundaries',routine_contexts:'Execution routine bodies'};
  const executionIntros={
    tasks:'Rate, priority and watchdog retain their exported text. No units, numeric conversion or effective values are inferred.',
    programs:'Schedule association counts include unique source-qualified candidates. Missing associations do not establish that a program is unused.',
    schedules:'Repeated, unnamed, missing and ambiguous schedule rows remain separate. Position is source order within its captured container.',
    designations:'MainRoutineName and FaultRoutineName provide entry candidates only; absent and empty attributes remain distinct.',
    calls:'Each JSR occurrence retains its own candidate result and incoming condition. Open a call for parameters, source evidence and the shared condition graph.',
    control_occurrences:'SBR and RET mark captured boundaries. JMP and LBL compare exact routine-and-content label candidates; they do not establish control flow.',
    routine_contexts:'Caller and entry links are retained once per routine. Unsupported languages, missing body evidence and lexical cycles stay visible.'
  };
  function executionContextList(){
    content.append(executionNotice());
    const summary=panel('Captured execution context','Choose one group or search across groups. Search uses bounded source previews; open a record for its complete metadata and source links.');
    const totals={};Object.entries(executionGroups).forEach(([group,label])=>{totals[label]=executionContext[group].length;});summary.append(values(totals));content.append(summary);
    Object.entries(executionGroups).forEach(([group,label])=>{
      if(state.filter!=='all'&&state.filter!==group)return;
      const rows=executionContext[group].filter(matches),sectionNode=section(label,executionIntros[group]);
      sectionNode.append(executionTable(group,rows,executionCaptions[group]));content.append(sectionNode);
    });
  }
  function executionLinkedSection(title,intro,group,ids,caption){
    const sectionNode=section(title,intro);sectionNode.append(executionTable(group,ids.map(id=>byExecution.get(id)?.row).filter(Boolean),caption));content.append(sectionNode);
  }
  function executionCandidateSection(ids,title,caption){
    const sectionNode=section(title,'Candidates are retained independently. A name match does not validate invocation or execution.');
    sectionNode.append(table(['Candidate source','Available context'],ids,id=>[sourceCell(id),executionEntityLink(id)],caption));content.append(sectionNode);
  }
  function executionContextDetail(found){
    if(!found){content.append(empty('No captured execution context'));return;}
    const {group,row:r}=found;
    setDetailHeading('EXECUTION CONTEXT',executionName(group,r),executionGroups[group]);content.append(executionNotice());
    const summary=panel('Captured source context',executionIntros[group]);
    summary.append(values({'Qualification':executionQualification(r),...(r.status?{'Candidate result':human(r.status),'Lexical result before qualification':human(r.lexical_status)}:{}),...(r.body_status?{'Body evidence':human(r.body_status),'In a lexical call cycle':r.in_lexical_call_cycle?'Yes; execution is unproven':'No captured cycle'}:{})}));
    const directId=group==='tasks'?r.task_id:group==='programs'?r.program_id:group==='routine_contexts'?r.routine_id:r.instruction_id||r.schedule_id||r.program_id;
    summary.append(sourceCell(directId));if(r.rung_id)summary.append(sourceCell(r.rung_id));content.append(summary);
    if(r.raw_attributes){const raw=section('Raw exported attributes','Every value retains its source spelling; missing attributes supply no default.');raw.append(values(r.raw_attributes));content.append(raw);}
    if(group==='tasks'){
      executionLinkedSection('Program schedule rows','Source order and repeated declarations remain visible.','schedules',r.schedule_ids,'Task program schedules');
      const events=section('Event metadata','Event attributes are source text only; event delivery and task behavior are not modeled.');events.append(table(['Source position','Qualification','Raw attributes','Source location'],r.event_info,event=>[event.ordinal,executionQualification(event),values(event.raw_attributes),node('span','mono',event.source_locator)],'Task event metadata'));content.append(events);
    }else if(group==='programs'){
      executionLinkedSection('Schedule associations','Only unique qualified candidate associations appear here; unresolved rows remain in Program schedules.','schedules',r.schedule_ids,'Program schedule associations');
      executionLinkedSection('Main and fault entry candidates','The raw declaration and its candidate result remain separate.','designations',r.designation_ids,'Program entry designations');
    }else if(group==='schedules'){
      content.append(executionEntityLink(r.task_id));
      const raw=section('Scheduled name');raw.append(values({'Raw name':r.raw_name,'Source position within container':r.ordinal}));content.append(raw);
      executionCandidateSection(r.candidate_program_ids,'Program declaration candidates','Schedule program candidates');
    }else if(group==='designations'){
      content.append(executionEntityLink(r.program_id));
      const raw=section('Entry declaration');raw.append(values({'Attribute':r.attribute,'Raw name':r.raw_name,'Entry kind':human(r.kind)}));content.append(raw);
      executionCandidateSection(r.candidate_routine_ids,'Routine declaration candidates','Entry routine candidates');
    }else if(group==='routine_contexts'){
      if(r.rung_counts){const body=section('Captured body coverage');body.append(values(r.rung_counts));content.append(body);}
      executionLinkedSection('Incoming routine calls','These calls have a unique qualified lexical candidate. They do not establish when this routine executes.','calls',r.incoming_call_ids,'Routine incoming calls');
      executionLinkedSection('Outgoing routine calls','Every captured call remains visible, including unresolved targets.','calls',r.outgoing_call_ids,'Routine outgoing calls');
      executionLinkedSection('Entry associations','Main and fault designations with a unique qualified candidate.','designations',r.designation_ids,'Routine entry associations');
      executionLinkedSection('Control boundaries','Source instructions retain their incoming condition and label candidates.','control_occurrences',r.control_occurrence_ids,'Routine control boundaries');
    }else{
      content.append(executionEntityLink(r.caller_routine_id));
      if(group==='calls')executionCandidateSection(r.candidate_routine_ids,'Routine declaration candidates','Call routine candidates');
      else{
        executionCandidateSection(r.candidate_label_instruction_ids,'Same-content label candidates','Control label candidates');
        executionCandidateSection(r.other_edit_candidate_ids,'Other captured content labels','Other-content label candidates');
      }
      const args=section('Captured arguments and parameter unknowns','These are source argument positions only. All captured fields remain in source order, including the JSR target field. SBR and RET values are not matched to call parameters; roles and types remain unresolved.');
      args.append(values({'Argument shape':human(r.argument_shape),'Captured fields':r.argument_count,'Empty field count':r.empty_argument_indices.length}));
      args.append(table(['Source position','Raw field','Evidence'],r.raw_arguments,(raw,index)=>[index+1,node('span','mono',raw||'(empty)'),r.empty_argument_indices.includes(index)?'Empty field':'Unvalidated source text'],'Execution captured arguments'));content.append(args);
      const guard=section('Incoming condition evidence','This shared condition describes source-local context before the instruction. It does not prove the call or boundary executes.');
      guard.append(values({'Quality':human(r.guard_quality),'Contains branch join':r.has_branch?'Yes':'No','Contains stored-state condition':r.has_stateful?'Yes':'No','Contains namespace gap':r.has_namespace_gap?'Yes':'No'}));content.append(guard);
      if(r.guard_id)conditionGraph(r.guard_id,'Execution incoming condition nodes','Incoming condition');
    }
    content.append(technical({'Context ID':r.id,'Source location':r.source_locator,'Content location':r.content_locator,'Source start':r.source_start,'Source end':r.source_end}));
  }
  function sfrNotice(){return notice('Reset candidates preserve each content version','SFR routine names are declaration candidates. A named selector is compared with captured Step Operand root and suffix evidence; an initial selector uses explicit InitialStep markers. Step Name and numeric ID are not substituted for Operand. Each exported edit content remains separate. Candidate identity does not prove an active step, selected edit, reset action, execution or outgoing rung condition.');}
  function sfrCallLink(c){return button('Inspect SFR target context',()=>openDetail('sfrcall',c.instruction_id),'text-link');}
  function sfrCallTable(rows,caption){return table(['SFR occurrence','Routine candidate','Chart context','Selector','Content versions','Source rung'],rows,c=>[
    sfrCallLink(c),primary(c.target_routine_id?sourceCell(c.target_routine_id):human(c.routine_status),human(c.routine_status)),human(c.chart_status),human(c.selector_kind),fmt(c.content_matches.length),sourceCell(c.rung_id)
  ],caption);}
  function sfrContextList(){
    content.append(sfrNotice());const c=sfrContext.coverage,p=panel('Sequence reset coverage','Counts describe captured candidate evidence, with no content version selected as active.');
    p.append(values({'SFR occurrences':c.calls_total,'Classified reset forms':c.calls_by_signature.classified,'Named selectors':c.calls_by_selector_kind.named,'Initial-step selectors':c.calls_by_selector_kind.initial,'Captured SFC steps':c.steps_total,'Content candidate comparisons':c.content_matches_total,'Calls with a candidate match':c.matched_calls,'Calls matched in every inspected content':c.fully_matched_calls,'Calls with multiple content versions':c.multiple_content_calls}));content.append(p);
    if(sfrContext.schema_version>=2){const diagnostics=panel('Missing-target diagnostic coverage','Candidate links explain missing named targets without changing the declared routine, selected content or original missing result.');diagnostics.append(values({'Missing named-target contexts':c.gap_contexts_total,'Contexts with nearby candidates':c.gaps_with_candidates,'Contexts without nearby candidates':c.gaps_with_no_candidates,'Candidate links':c.gap_candidate_links_total,'Contexts with excluded peer content':c.gaps_with_excluded_peer_contents}));content.append(diagnostics);}
    content.append(sfrCallTable(sfrCalls.filter(matches),'SFR target contexts'));
  }
  function sfrCallDetail(c){
    setDetailHeading('SEQUENCE RESET CONTEXT','SFR target candidates',sourceName(c.rung_id));content.append(sfrNotice());
    const p=panel('Captured reset call','The existing operand signature and routine candidate remain separate from SFC step matching.');p.append(values({'Signature':human(c.signature_status),'Routine candidate':human(c.routine_status),'Routine candidate count':c.routine_candidate_count,'Chart context':human(c.chart_status),'Selector kind':human(c.selector_kind),'Selector binding':human(c.selector_binding_status)}),sourceCell(c.instruction_id),sourceCell(c.rung_id));if(c.target_operand_id)p.append(sourceCell(c.target_operand_id));if(c.target_routine_id)p.append(sourceCell(c.target_routine_id));content.append(p);
    const versions=section('Exported content candidates','Every content keeps its own result. Open a candidate step for its exact Operand, InitialStep marker, source attributes and chart context. No version is selected as effective.');
    versions.append(table(['Content version','Edit kind','Candidate result','Candidate count','Step candidates'],c.content_matches,m=>{
      const choices=node('div','inline-links');m.candidate_step_ids.slice(0,8).forEach(id=>choices.append(sourceCell(id)));
      if(m.candidate_step_ids.length>8)choices.append(button('Inspect all '+fmt(m.candidate_step_ids.length)+' step candidates',()=>openDetail('sfrcontent',c.instruction_id,{sfrContentId:m.content_id}),'text-link'));
      if(!m.candidate_step_ids.length)choices.append(node('span','muted','No unique target selected'));
      return[sourceCell(m.content_id),human(m.edit_kind),human(m.status),fmt(m.candidate_count),choices];
    },'SFR content candidates'));content.append(versions);
    const gaps=sfrGapsByCall.get(c.instruction_id)||[];
    if(gaps.length){const diagnostics=section('Missing named-target context','These are diagnostic links only. The original missing candidate result remains unchanged; no candidate replaces the SFR target.');diagnostics.append(table(['Missing content','Same-content root / different suffix','Other edit exact identity','Peer chart exact identity','Inspect'],gaps,g=>[sourceCell(g.content_id),fmt(g.same_content_root_step_ids.length),fmt(g.other_edit_exact_step_ids.length),fmt(g.peer_chart_exact_step_ids.length),button('Inspect nearby candidates',()=>openDetail('sfrgap',c.instruction_id,{sfrContentId:g.content_id}),'text-link')],'SFR missing-target contexts'));content.append(diagnostics);}
  }
  function sfrContentDetail(c){
    const match=c.content_matches.find(m=>m.content_id===state.sfrContentId);setDetailHeading('SFR CONTENT CANDIDATES','Step candidates',human(match?.edit_kind));content.append(sfrNotice());
    if(!match){content.append(empty('No retained content match'));return;}
    content.append(sourceCell(match.content_id),table(['Step source','Operand identity binding','Declared root / suffix','Initial marker'],match.candidate_step_ids,id=>{
      const step=bySfrStep.get(id);return[sourceCell(id),human(step?.binding_status),step?.target_id?primary(sourceCell(step.target_id),step.suffix || '(root)'):'Unresolved',human(step?.initial_kind)];
    },'SFR step candidates'));
  }
  function sfrGapDetail(c){
    const g=(sfrGapsByCall.get(c.instruction_id)||[]).find(x=>x.content_id===state.sfrContentId);
    setDetailHeading('SFR MISSING-TARGET DIAGNOSTICS','Nearby source candidates',sourceName(c.rung_id));content.append(sfrNotice());
    if(!g){content.append(empty('No retained diagnostic context'));return;}
    content.append(notice('Original missing result is unchanged','Same-content roots have a different suffix. Other-edit and peer-chart links share captured exact Operand identity but are outside the requested content. None is substituted as the reset target.'));
    const scope=panel('Inspected context'),links=node('div','inline-links');links.append(sourceCell(g.content_id),sourceCell(g.target_routine_id),sourceCell(g.target_operand_id));scope.append(links,values({'Eligible peer contents':g.peer_content_counts.eligible,'Protected peer contents excluded':g.peer_content_counts.protected,'Unsupported peer contents excluded':g.peer_content_counts.unsupported_context,'Incomplete peer contents excluded':g.peer_content_counts.incomplete_context}));content.append(scope);
    for(const [key,label] of [['same_content_root_step_ids','Same content: shared root, different suffix'],['other_edit_exact_step_ids','Other edits of the requested chart: exact identity'],['peer_chart_exact_step_ids','Other charts in the same program: exact identity']]){
      const p=section(label);p.append(table(['Step candidate','Captured chart','Content version','Root / suffix'],g[key],id=>{const step=bySfrStep.get(id);return[sourceCell(id),sourceCell(step?.routine_id),sourceCell(step?.content_id),step?.target_id?primary(sourceCell(step.target_id),step.suffix||'(root)'):'Unresolved'];},label));content.append(p);
    }
    if(g.peer_routines_without_content_ids.length){const missing=section('Peer routines without content','No candidate step search is possible in these captured routines.');missing.append(table(['Routine'],g.peer_routines_without_content_ids,id=>[sourceCell(id)],'Peer routines without content'));content.append(missing);}
  }
  function customCallLink(c){return button(short(sourceName(c.instruction_id),120),()=>openDetail('customcall',c.instruction_id),'text-link');}
  function customCallTable(rows,caption){return table(['Custom instruction occurrence','Declaration candidate status','Declaration','Rung'],rows,c=>[
    customCallLink(c),human(c.status),c.declaration_id?button(short(entityName(c.declaration_id),140),()=>openDetail('customdeclaration',c.declaration_id),'text-link'):'No unique candidate',sourceCell(c.rung_id)
  ],caption);}
  function indexedRaw(u){return byOperand.get(u.source_id)?.raw_text ?? byCalculationNode.get(u.source_id)?.raw_text ?? byEntity.get(u.source_id)?.attributes?.AliasFor ?? '';}
  function indexedLink(u){return button(short(indexedRaw(u),180)||'(blank source)',()=>openDetail('indexeduse',u.id),'text-link');}
  function indexedSourceLink(id){const u=byIndexedSource.get(id);return u?button('Inspect symbolic index context',()=>openDetail('indexeduse',u.id),'text-link'):node('span','muted','No symbolic index context');}
  function indexedUseTable(rows,caption){return table(['Indexed source occurrence','Kind / captured role','Context status','Index read occurrences','Rung or declaration'],rows,u=>[
    indexedLink(u),primary(human(u.kind),human(u.role)),human(u.disposition),fmt(u.index_reads.length),sourceCell(u.rung_id || u.source_id)
  ],caption);}
  function instructionContextList(){
    content.append(contextNotice());
    const c=customContext.coverage,i=indexedAccess.coverage,totals=panel('Context coverage','These counts explain source evidence; they do not reduce existing binding or condition gaps.');
    totals.append(values({'Unrecognized instruction occurrences':c.unknown_family_calls,'Unique declaration candidates':c.calls_by_status.unique_candidate,'Custom definitions':c.definitions_total,'Parameter declarations':c.parameters_total,'Routine declarations':c.routines_total,'Definitions with encoded regions':c.definitions_with_encoded_regions,'Indexed source occurrences':i.uses_total,'Symbolically parsed occurrences':i.symbolic_uses,'Dynamic selectors':i.dynamic_selectors,'Possible index reads':i.index_read_occurrences,'Bound index-read roots':i.bound_index_reads}));content.append(totals);
    if(aoiBody){const bodies=panel('AOI body context','Routine ownership and possible access evidence remain separate from call effects. Zero observed accesses does not mean unused.');bodies.append(values({'Indexed definitions':aoiBodyDeclarations.length,'Owned routines':aoiBodyRoutines.length,'Declared parameters and local tags':aoiBodySymbols.length,'Call instance contexts':aoiBodyCalls.length}));content.append(bodies);}
    const calls=section('Custom-instruction occurrences','Open a call to follow its candidate declaration and inspect parameters, source routines and protection markers.');calls.append(customCallTable(customCalls.filter(matches),'Custom instruction occurrences'));content.append(calls);
    const declarations=section('Custom declarations','Definitions are shown even when no unknown instruction occurrence names them.');declarations.append(table(['Declaration','Name context','Parameters / routines','Encoded / protected context'],customDeclarations.filter(matches),d=>[
      button(short(entityName(d.source_id),160),()=>openDetail('customdeclaration',d.source_id),'text-link'),human(d.status),d.parameters.length+' / '+d.routines.length,fmt(d.encoded_region_ids.length)+' encoded regions · '+human(d.protection_marker)
    ],'Custom declarations'));content.append(declarations);
    const indexed=section('Symbolic indexed operands','Expression containers, unknown-role slots, dynamic alias targets and unsupported grammar stay in separate dispositions.');indexed.append(indexedUseTable(indexedUses.filter(matches),'Indexed source occurrences'));content.append(indexed);
  }
  function customCallDetail(c){
    setDetailHeading('CUSTOM INSTRUCTION CONTEXT',sourceName(c.instruction_id),sourceName(c.rung_id));content.append(contextNotice());
    const p=panel('Declaration candidate','Name matching is limited to the captured controller context; it does not validate a call signature.');p.append(values({'Candidate status':human(c.status)}));const links=node('div','inline-links');links.append(sourceCell(c.instruction_id),sourceCell(c.rung_id));
    if(c.declaration_id)links.append(button('Inspect declaration: '+short(entityName(c.declaration_id),140),()=>openDetail('customdeclaration',c.declaration_id),'text-link'));p.append(links);content.append(p);
    const slots=(rungOperands.get(c.rung_id)||[]).filter(o=>o.instruction_id===c.instruction_id),args=section('Captured call operands','Parameter declarations have not been mapped to these argument positions. Existing roles remain unchanged.');
    args.append(table(['Position','Source operand','Captured role'],slots,o=>[o.argument_index+1,sourceCell(o.id),human(byOperandAccess.get(o.id)?.role)],'Custom call operand slots'));content.append(args);
    if(byAoiBodyCall.has(c.instruction_id))aoiInstancePanel(byAoiBodyCall.get(c.instruction_id));
  }
  function customDeclarationDetail(d){
    setDetailHeading('CUSTOM DECLARATION CONTEXT',entityName(d.source_id),entityPath(d.controller_id));content.append(contextNotice());
    const p=panel('Definition context');p.append(values({'Name context':human(d.status),'Protection marker':human(d.protection_marker),'Encoded regions':d.encoded_region_ids.length}),sourceCell(d.source_id));content.append(p);
    const params=section('Parameter declarations','Usage and flags are exported metadata. They are not assigned to call operands or promoted to runtime access roles.');params.append(table(['Source parameter','Usage','Required','Visible','Data type metadata'],d.parameters,p=>[sourceCell(p.source_id),human(p.usage),human(p.required),human(p.visible),human(p.datatype)],'Custom parameter declarations'));content.append(params);
    const routines=section('Routine declarations','The source view retains captured routine evidence. No internal routine behavior has been expanded into the calling rung.');routines.append(table(['Routine','Declared language','Content form',...(aoiBody?['Body context']:[])],d.routines,r=>[sourceCell(r.source_id),human(r.language),human(r.content),...(aoiBody?[byAoiBodyRoutine.has(r.source_id)?primary(button('Inspect body',()=>openDetail('aoiroutine',r.source_id),'text-link'),human(byAoiBodyRoutine.get(r.source_id).body_status)):'No owned body']:[])],'Custom routine declarations'));content.append(routines);
    if(byAoiBodyDeclaration.has(d.source_id))aoiDeclarationSymbols(byAoiBodyDeclaration.get(d.source_id));
    if(d.encoded_region_ids.length){const encoded=section('Encoded regions','Encoded source is unavailable for behavioral analysis.');encoded.append(table(['Source region'],d.encoded_region_ids,id=>[sourceCell(id)],'Custom encoded regions'));content.append(encoded);}
  }
  function aoiNotice(){return notice('Body evidence is declaration-owned','These indexes describe captured AOI routines and possible operand or expression accesses. They do not execute the AOI, map call arguments to parameters, prove an effect or validate member types. Declared Usage and observed access roles are separate. Zero observed accesses does not mean unused.');}
  function aoiInstancePanel(c){
    const p=panel('First-field instance context','A resolved first-field root and matching type name are candidate evidence only. Array bounds, member types, call signatures and runtime instance effects remain unvalidated.');
    p.append(values({'Declaration candidate':human(c.declaration_status),'Instance context':human(c.instance_status),'Root binding':human(c.binding_status),'Address shape':human(c.address_shape),'Declared type-name comparison':human(c.datatype_status)}));
    const links=node('div','inline-links');if(c.first_operand_id)links.append(sourceCell(c.first_operand_id));if(c.symbol_id)links.append(primary(sourceCell(c.symbol_id),'Directly named declaration'));if(c.target_id)links.append(primary(sourceCell(c.target_id),'Resolved root declaration'));p.append(links);
    if(c.alias_chain.length)p.append(table(['Alias declaration'],c.alias_chain,id=>[sourceCell(id)],'Instance alias chain'));content.append(p);
  }
  function aoiDeclarationSymbols(d){
    content.append(aoiNotice());const p=section('Declaration-owned symbols','Direct-name indexes retain the symbol written in source; resolved-root indexes follow aliases. An occurrence may be in both, so those columns must not be added.');
    p.append(table(['Parameter / local tag','Declared kind / Usage','Context','Direct slots / leaves','Resolved slots / leaves','Inspect'],[...d.parameter_ids,...d.local_tag_ids],id=>{
      const x=byAoiBodySymbol.get(id);return[sourceCell(id),primary(human(x?.kind),byEntity.get(id)?.attributes?.Usage||'No Usage metadata'),human(x?.context_status),x?fmt(x.direct_operand_ids.length)+' / '+fmt(x.direct_expression_use_ids.length):'0 / 0',x?fmt(x.resolved_operand_ids.length)+' / '+fmt(x.resolved_expression_use_ids.length):'0 / 0',x?button('Inspect observed accesses',()=>openDetail('aoisymbol',id),'text-link'):'Unavailable'];
    },'AOI declaration-owned symbols'));content.append(p);
  }
  function aoiRoutineDetail(r){
    setDetailHeading('AOI OWNED BODY',sourceName(r.routine_id),sourceName(r.declaration_id));content.append(aoiNotice());
    const p=panel('Captured routine body');p.append(values({'Body context':human(r.body_status),'Rungs':r.rung_ids.length,'Instructions':r.instruction_ids.length,'Operand slots':r.operand_ids.length,'Expression leaves':r.expression_use_ids.length}));const links=node('div','inline-links');links.append(sourceCell(r.routine_id),sourceCell(r.declaration_id));p.append(links);content.append(p);
    const rows=section('Owned source rungs','Source links retain every block and branch. Body ownership does not imply this routine is executed by a particular call.');rows.append(table(['Rung','Parse status','Instructions'],r.rung_ids,id=>{const rung=byRung.get(id);return[sourceCell(id),human(rung?.parse_status),fmt(rung?.instructions?.length||0)];},'AOI owned rungs'));content.append(rows);
    const slots=section('Owned operand slots');slots.append(aoiAccessTable(r.operand_ids,false,'AOI routine operand slots'));content.append(slots);
    const leaves=section('Owned expression leaves');leaves.append(aoiAccessTable(r.expression_use_ids,true,'AOI routine expression leaves'));content.append(leaves);
  }
  function aoiAccessTable(ids,expression,caption){return table(['Source occurrence','Observed role','Root binding','Source rung'],ids,id=>{
    const use=expression?byExpressionUse.get(id):byOperandAccess.get(id);return[expression?engineeringEvidence(id):sourceCell(id),human(use?.role),human(use?.binding_status),sourceCell(use?.rung_id)];
  },caption);}
  function aoiSymbolDetail(x){
    setDetailHeading('AOI SYMBOL ACCESSES',sourceName(x.source_id),sourceName(x.declaration_id));content.append(aoiNotice());
    const p=panel('Declared symbol','The direct and resolved lists may contain the same occurrence. They explain naming and alias resolution, not independent executions.');p.append(values({'Kind':human(x.kind),'Declared Usage':byEntity.get(x.source_id)?.attributes?.Usage||'No Usage metadata','Context':human(x.context_status)}));const links=node('div','inline-links');links.append(sourceCell(x.source_id),sourceCell(x.declaration_id));p.append(links);content.append(p);
    for(const [key,label,expression] of [['direct_operand_ids','Directly named operand slots',false],['resolved_operand_ids','Resolved-root operand slots',false],['direct_expression_use_ids','Directly named expression leaves',true],['resolved_expression_use_ids','Resolved-root expression leaves',true]]){
      const rows=section(label);rows.append(aoiAccessTable(x[key],expression,label));content.append(rows);
    }
  }
  function indexedUseDetail(u){
    const raw=indexedRaw(u);setDetailHeading('SYMBOLIC INDEX CONTEXT',short(raw,160)||'(blank source)',human(u.disposition));content.append(contextNotice());
    const p=panel('Captured indexed occurrence','Character spans refer to this exact source spelling. The existing access role applies to the containing operand, not to a resolved array element.');p.append(sourceText(raw),values({'Occurrence kind':human(u.kind),'Captured role':human(u.role),'Context status':human(u.disposition)}));
    const links=node('div','inline-links');if(u.kind==='expression'&&byCalculationNode.has(u.source_id))links.append(engineeringEvidence(u.source_id));else links.append(sourceCell(u.source_id));
    if(u.rung_id)links.append(sourceCell(u.rung_id));p.append(links);content.append(p);
    if(u.root_binding){const root=panel('Array root context','A bound root does not resolve the selected element or validate the suffix.');root.append(sourceText(raw.slice(u.root_start,u.root_end)),calculationBinding(u.root_binding));content.append(root);}
    const selectors=section('Selector expressions','Group and dimension identify syntax positions. Constants remain source spelling; no expression is evaluated.');selectors.append(table(['Group / dimension','Exact selector','Kind','Character span'],u.selectors,s=>[(s.group_index+1)+' / '+(s.dimension_index+1),node('span','mono',raw.slice(s.start,s.end)),s.dynamic?'Symbolic expression':'Static spelling','['+s.start+', '+s.end+')'],'Symbolic selector expressions'));content.append(selectors);
    const reads=section('Possible index reads','Repeated references remain separate occurrences. These reads choose an index; they are not data-flow edges or proof of execution.');reads.append(table(['Index reference','Selector position','Root binding','Declaration / suffix'],u.index_reads,r=>[node('span','mono',raw.slice(r.start,r.end)),r.selector_index+1,human(r.binding.status),calculationBinding(r.binding)],'Symbolic index read occurrences'));content.append(reads);
  }
  function bindingGapName(g){return short(g?.kind==='expression'?byCalculationNode.get(g.source_id)?.raw_text:byOperand.get(g?.source_id)?.raw_text,180)||'(blank source)';}
  function bindingCategory(category){return ({rack_unique_candidate:'Unique rack-name candidate',rack_suffix_invalid:'Rack candidate with invalid expanded suffix',rack_ambiguous_candidate:'Ambiguous rack-name candidates',rack_names_unavailable:'Rack candidate names unavailable',rack_outside_scope:'Rack candidate outside visible scope',rack_no_match:'No rack-name match',rack_context_unavailable:'No existing rack-match evidence',non_static_array_index:'Non-static array index',unsupported_address:'Unsupported address form',undeclared_root:'Undeclared root',unresolved_scope:'Unresolved source scope',alias_cycle:'Alias cycle',alias_depth_limit:'Alias depth limit',ambiguous_root:'Ambiguous root',invalid_expanded_suffix:'Invalid expanded suffix',non_address_value:'Value is not an address',other_binding_gap:'Other binding gap'})[category] || human(category);}
  function bindingContextLink(id){return byBindingContext.has(id)?button('Explain binding gap',()=>openDetail('bindingcontext',id),'text-link'):node('span','muted','No indexed binding gap');}
  function bindingContextNotice(){return notice('Candidate context does not resolve a binding','Rack-name candidates come from captured module topology. Their adapter backing data, member mapping, data types and physical channels have not been validated. Logical candidate addresses group matching candidate and suffix spelling only; they never join the exact-address groups. Read and write roles come from instruction access evidence, independently of module input/output direction.');}
  function bindingSourceCell(g){const use=bindingUse(g);return g.kind==='expression'?button(bindingGapName(g),()=>openDetail('calculation',use.instruction_id,{focusCalculationNode:g.source_id}),'text-link'):sourceCell(g.source_id);}
  function candidateAddressName(a){return short(byRackCandidate.get(a.candidate_id)?.name || '(unnamed candidate)',120)+short(a.suffix || '',100);}
  function candidateAddressLink(id){const a=byCandidateAddress.get(id);return a?button('Candidate address: '+candidateAddressName(a),()=>openDetail('candidateaddress',a.id),'text-link'):node('span','muted','No logical candidate address');}
  function bindingGapTable(rows,caption){return table(['Source occurrence','Occurrence kind / role','Gap context','Candidate address','Rung'],rows,g=>{
    const use=bindingUse(g);
    return[button(bindingGapName(g),()=>openDetail('bindingcontext',g.source_id),'text-link'),primary(human(g.kind),human(use?.role)),bindingCategory(g.category),g.candidate_address_id?candidateAddressLink(g.candidate_address_id):'Not grouped',sourceCell(use?.rung_id)];
  },caption,{emptyTitle:'No binding gaps match',emptyDetail:'Clear the search or choose a different gap category. This index does not change existing binding or condition classifications.'});}
  function candidateAddressTable(rows,caption){return table(['Logical candidate address','Captured roles','Operand occurrences','Expression occurrences'],rows,a=>[
    button(candidateAddressName(a),()=>openDetail('candidateaddress',a.id),'text-link'),human(a.profile),fmt(a.operand_ids.length),fmt(a.expression_use_ids.length)
  ],caption,{emptyTitle:'No logical candidate addresses match',emptyDetail:'Only a unique existing rack-name candidate and valid expanded suffix can form a group. The backing mapping remains unverified.'});}
  function bindingContextMode(mode){state.bindingContextMode=mode;state.filter='all';state.listPages={};render();}
  function bindingContextToolbar(){
    const groups=state.bindingContextMode==='addresses';
    toolbarFor(groups?'Search candidate address previews and captured role profiles':'Search source previews, gap categories, candidate names or rung context',groups?[['all','All role profiles'],['read_only','Captured reads only'],['write_only','Captured writes only'],['read_and_write','Captured reads and writes']]:[['all','All binding gaps'],...Array.from(new Set(bindingContextGaps.map(g=>g.category))).sort().map(c=>[c,bindingCategory(c)])]);
    const label=node('label','filter-wrap','Binding evidence'),select=node('select');select.setAttribute('aria-label','Binding evidence');
    [['gaps','Unresolved occurrences'],['addresses','Logical candidate addresses']].forEach(([value,text])=>{const option=node('option','',text);option.value=value;select.append(option);});
    select.value=state.bindingContextMode || 'gaps';select.addEventListener('change',()=>bindingContextMode(select.value));label.append(select);toolbar.querySelector('.toolbar').append(label);
  }
  function bindingContextList(){
    content.append(bindingContextNotice());
    const summary=panel('Unresolved evidence with source context','These are distinct operand and expression occurrences. A candidate explains available context while the original binding, condition quality and output-target status remain unchanged.');
    summary.append(values({'Unresolved occurrences':bindingContextGaps.length,'Operand occurrences':bindingContextGaps.filter(g=>g.kind==='operand').length,'Expression occurrences':bindingContextGaps.filter(g=>g.kind==='expression').length,'Unique rack-name context':bindingContextGaps.filter(g=>g.category==='rack_unique_candidate').length,'Logical candidate addresses':candidateAddresses.length}));content.append(summary);
    if(state.bindingContextMode==='addresses')content.append(candidateAddressTable(candidateAddresses.filter(a=>matches(a)&&(state.filter==='all'||a.profile===state.filter)),'Logical candidate addresses'));
    else content.append(bindingGapTable(bindingContextGaps.filter(g=>matches(g)&&(state.filter==='all'||g.category===state.filter)),'Binding gap occurrences'));
  }
  function rackCandidatePanel(candidateId){
    const candidate=byRackCandidate.get(candidateId),box=panel('Rack-name candidate context','This candidate is an observation from module topology. It is not a bound tag, adapter member assignment or physical channel.');
    if(!candidate){box.append(empty('No unique rack-name candidate','Inspect the gap classification and existing match evidence. No candidate has been selected.'));return box;}
    box.append(values({'Candidate root':candidate.name,'Module direction':human(candidate.direction),'Name origin':human(candidate.name_origin),'Backing mapping':human(candidate.backing_status),'Candidate reason':candidate.reason?human(candidate.reason):'No naming gap'}));
    const links=node('div','inline-links');
    links.append(button('Open rack alias source',()=>openSource(candidate.source_id),'text-link'));
    if(candidate.connection_id)links.append(button('Open connection',()=>openSource(candidate.connection_id),'text-link'));
    if(candidate.module_id)links.append(button('Open module: '+short(entityName(candidate.module_id),100),()=>openSource(candidate.module_id),'text-link'));
    box.append(links,technical({'Candidate source ID':candidate.source_id,'Connection ID':candidate.connection_id,'Module ID':candidate.module_id}));return box;
  }
  function bindingContextDetail(g){
    const use=bindingUse(g),raw=g.kind==='expression'?byCalculationNode.get(g.source_id)?.raw_text:byOperand.get(g.source_id)?.raw_text;
    setDetailHeading('BINDING GAP CONTEXT',bindingGapName(g),sourceName(use.rung_id));content.append(bindingContextNotice());
    const source=panel('Unresolved source occurrence','The captured binding is preserved. Candidate context below does not promote this occurrence to a resolved address.');
    source.append(sourceText(raw),values({'Occurrence kind':human(g.kind),'Operand role':human(use.role),'Binding status':human(use.binding_status),'Binding reason':use.binding_reason?human(use.binding_reason):'No separate binding reason','Expanded suffix':use.suffix || '(empty suffix)','Gap context':bindingCategory(g.category)}));
    const links=node('div','inline-links');links.append(bindingSourceCell(g),sourceCell(use.instruction_id),sourceCell(use.rung_id));source.append(links);content.append(source);
    if(byIndexedSource.has(g.source_id))content.append(indexedSourceLink(g.source_id));
    const chain=use.alias_chain || [];
    if(chain.length){const aliases=section('Captured alias chain','Declaration order follows the recorded chain. Open a declaration to read its complete target and source attributes.');aliases.append(table(['Position','Alias declaration','Declared target preview'],chain,(id,index)=>[index+1,sourceCell(id),short(byEntity.get(id)?.attributes?.AliasFor || '(target absent)',180)],'Binding context alias chain'));content.append(aliases);}
    const match=byRackMatch.get(g.source_id);
    if(match){const evidence=panel('Existing rack-name comparison');evidence.append(values({'Terminal root':match.terminal_root,'Match status':human(match.status),'Candidate count':match.candidate_count}),sourceCell(match.lookup_scope_id));content.append(evidence);}
    if(g.candidate_id)content.append(rackCandidatePanel(g.candidate_id));
    if(g.candidate_address_id)content.append(candidateAddressLink(g.candidate_address_id));
    if(g.predicate_node_id){const p=panel('Condition predicate occurrence','This predicate retains its original binding gap. Candidate context does not establish the predicate value.');p.append(sourceCell(byConditionNode.get(g.predicate_node_id)?.instruction_id));content.append(p);conditionGraph(g.predicate_node_id,'Binding predicate condition nodes','Predicate occurrence');}
    if(g.output_id){const output=byConditionalOutput.get(g.output_id);if(output){const p=panel('Conditional output occurrence','The output target remains unresolved in the condition analysis.');p.append(conditionalOutputTable([output],'Binding gap conditional output'));content.append(p);}}
    content.append(technical({'Source occurrence ID':g.source_id,'Predicate node ID':g.predicate_node_id,'Output ID':g.output_id}));
  }
  function candidateAddressDetail(a){
    setDetailHeading('LOGICAL CANDIDATE ADDRESS',candidateAddressName(a),'Candidate context only · separate from exact-address evidence');content.append(bindingContextNotice(),rackCandidatePanel(a.candidate_id));
    const expanded=panel('Captured suffix spelling','Grouping uses this candidate source and expanded suffix spelling. Member validity, bounds, backing layout and physical channels remain unverified.');expanded.append(sourceText(a.suffix || '(root suffix)'),values({'Captured use profile':human(a.profile),'Operand occurrences':a.operand_ids.length,'Expression occurrences':a.expression_use_ids.length}));content.append(expanded);
    content.append(bindingGapTable([...a.operand_ids,...a.expression_use_ids].map(id=>byBindingContext.get(id)).filter(Boolean),'Candidate address source occurrences'),technical({'Logical candidate address ID':a.id,'Candidate source ID':a.candidate_id}));
  }
  function addressTable(rows,caption){const box=node('div');if(rows.some(shortenedAddress))box.append(addressPreviewNote());box.append(table(['Expanded address / scope','Captured use profile','Operand reads','Writes','Read/write','Unknown roles','Expression reads','Distinct rungs'],rows,a=>[
    primary(button(addressName(a),()=>openDetail('address',a.id),'text-link'),entityPath(byEntity.get(a.target_id)?.parent_id)),addressProfile(a),
    fmt(a.read_operand_ids.length),fmt(a.write_operand_ids.length),fmt(a.read_write_operand_ids.length),fmt(a.unknown_operand_ids.length),fmt(a.expression_use_ids.length),fmt(a.rung_ids.length)
  ],caption,{emptyTitle:'No exact addresses match',emptyDetail:'Clear the search or change the profile filter. Unresolved roots and invalid expanded suffixes are not grouped as addresses.'}));return box;}
  function relationshipMode(mode){state.relationshipMode=mode;state.filter='all';state.listPages={};render();}
  function relationshipsToolbar(){
    toolbarFor(({addresses:'Search exact addresses, suffixes, scopes or captured use labels',links:'Search intermediate addresses, opcodes or rung context',patterns:'Search representative rung source or pattern labels',gaps:'Search source uses or address gap labels'})[state.relationshipMode || 'addresses'],[
      ['all','All address profiles'],['read_and_write','Captured reads and writes'],['read_only','No captured explicit writer'],['write_only','No captured explicit reader'],['unknown_only','Unknown roles only']]);
    const box=toolbar.querySelector('.toolbar'),label=node('label','filter-wrap','Relationship evidence'),select=node('select');
    select.setAttribute('aria-label','Relationship evidence');
    [['addresses','Exact addresses'],['links','Local calculation links'],['patterns','Operand-reuse patterns'],['gaps','Address identity gaps']].forEach(([v,t])=>{const o=node('option','',t);o.value=v;select.append(o);});
    select.value=state.relationshipMode || 'addresses';select.addEventListener('change',()=>relationshipMode(select.value));label.append(select);box.append(label);
    const profile=box.querySelector('select');profile.disabled=(state.relationshipMode || 'addresses')!=='addresses';
  }
  function relationshipLinkTable(rows,caption){return table(['Rung','Earlier destination','Exact intermediate address','Later input','Input kind'],rows,l=>[
    sourceCell(l.rung_id),primary(sourceCell(l.write_operand_id),sourceName(l.producer_instruction_id)),
    button(addressName(byAddress.get(l.address_id)),()=>openDetail('address',l.address_id),'text-link'),
    primary(engineeringEvidence(l.read_id),sourceName(l.consumer_instruction_id)),l.read_kind==='expression'?'Expression read occurrence':'Operand read occurrence'
  ],caption,{emptyTitle:'No local calculation links in this selection',emptyDetail:'The analysis checks contiguous sequences of eligible calculation blocks in unbranched source. Branches, stateful or unknown instructions, range effects and writes to the same root can stop a chain.'});}
  function localLinkNotice(){return node('p','row-note','Each link is a possible reuse of an earlier result by a later input within an eligible, unbranched source sequence. It does not prove execution, value flow or scan order. Branches, unknown or stateful blocks, range effects and potentially overlapping writes stop analysis.');}
  function reusePatternTable(rows,caption){return table(['Representative rung','Rungs','Address variables'],rows,p=>[
    button(rungName(byRung.get(p.representative_rung_id)),()=>openDetail('reusepattern',p.id),'text-link'),fmt(p.rung_ids.length),fmt(p.address_variables)
  ],caption,{emptyTitle:'No operand-reuse patterns match',emptyDetail:'Rungs with insufficient address or expression evidence remain outside this grouping.'});}
  function reuseNotice(){return node('p','row-note','These groups retain operand roles, exact suffixes, shared-root relationships, literal spelling, CPT expression structure and repeated-address relationships in addition to branch and opcode shape. They do not establish behavioral equivalence. Address variables describe repeated exact address identities, not confirmed process objects.');}
  function relationshipsList(){
    content.append(addressNotice());
    const mode=state.relationshipMode || 'addresses',totals=panel('Relationship evidence','Counts distinguish exact address groups, occurrence links and rung pattern groups.');
    const buttons=node('div','inline-links');
    [['addresses',addresses.length,'Exact addresses'],['links',localLinks.length,'Local input-use links'],['patterns',reusePatterns.length,'Operand-reuse patterns'],['gaps',byIdentityGap.size,'Address identity gaps']].forEach(([key,count,title])=>buttons.append(button(title+' ('+fmt(count)+')',()=>relationshipMode(key),'text-link')));totals.append(buttons,values({'Address groups used on multiple rungs':relationships.coverage.cross_rung_addresses,'Address groups with multiple captured writers':relationships.coverage.multiple_writer_addresses}));content.append(totals);
    if(mode==='addresses')content.append(addressTable(addresses.filter(a=>matches(a)&&(state.filter==='all'||a.profile===state.filter)),'Exact address groups'));
    else if(mode==='links'){content.append(localLinkNotice(),relationshipLinkTable(localLinks.filter(matches),'Local calculation links'));}
    else if(mode==='patterns'){
      content.append(reuseNotice(),reusePatternTable(reusePatterns.filter(matches),'Operand-reuse patterns'));
      const skipped=(relationships.rung_patterns || []).filter(p=>p.status==='skipped'&&(!state.query||matches(byRung.get(p.rung_id))||human(p.reason).includes(state.query.toLocaleLowerCase())));
      const gaps=section('Rungs outside operand-reuse grouping','These rungs retain their source and engineering analysis. No partial pattern is substituted.');
      gaps.append(table(['Rung','Reason'],skipped,p=>[sourceCell(p.rung_id),human(p.reason)],'Skipped operand-reuse rungs'));content.append(gaps);
    }else{
      const gaps=section('Expanded suffix gaps','The original binding remains available. An invalid suffix after alias expansion cannot be assigned an exact address identity. Other reference-binding gaps remain in Tag access.');
      gaps.append(table(['Source use','Occurrence kind','Reason'],(relationships.identity_gaps || []).filter(matches),g=>[engineeringEvidence(g.id),g.kind==='expression'?'Expression reference':'Operand','Expanded suffix cannot form an address'],'Address identity gaps'));content.append(gaps);
    }
  }
  function addressDetail(a){
    setDetailHeading('EXACT ADDRESS EVIDENCE',addressName(a),entityPath(byEntity.get(a.target_id)?.parent_id));
    content.append(addressNotice());
    if(byStatefulGroup.has(a.id))content.append(button('Inspect timer, counter and reset context',()=>openDetail('statefulobject',a.id),'text-link'));
    const summary=panel('Captured uses',addressProfile(a));
    summary.append(values({'Resolved declaration':addressRootPreview(a.target_id),'Expanded suffix':a.suffix || '(root address)','Operand read occurrences':a.read_operand_ids.length,'Write occurrences':a.write_operand_ids.length,'Read/write occurrences':a.read_write_operand_ids.length,'Unknown-role occurrences':a.unknown_operand_ids.length,'Expression read occurrences':a.expression_use_ids.length,'Distinct rungs':a.rung_ids.length,'Distinct instructions':a.instruction_ids.length}));
    const links=node('div','inline-links');links.append(sourceCell(a.target_id));
    if(byRootAccess.has(a.target_id))links.append(button('Open root access and other suffixes',()=>openDetail('access',a.target_id),'text-link'));summary.append(links);content.append(summary);
    for(const role of accessRoles){const ids=a[role+'_operand_ids'];if(!ids.length)continue;
      const uses=section(({read:'Operand readers',write:'Operand writers',read_write:'Stateful read/write uses',unknown:'Uses with unknown roles'})[role],role==='unknown'?'A captured reference with an unresolved access role is not counted as an explicit reader or writer.':null);
      uses.append(table(['Source operand','Rung','Instruction / argument','Role'],ids,id=>{const use=byOperandAccess.get(id);return[sourceCell(id),sourceCell(use.rung_id),sourceName(use.instruction_id)+' / '+(use.argument_index+1),accessCell(use)];},'Exact address '+role+' occurrences'));content.append(uses);
    }
    if(a.expression_use_ids.length){const expr=section('Expression readers','Each reference leaf remains one occurrence, including repeated spelling in the same expression.');expr.append(expressionUseTable(a.expression_use_ids.map(id=>byExpressionUse.get(id)),'Exact address expression reads'));content.append(expr);}
    const rungs=section('Rungs using this exact address','This is a source occurrence list across rungs; its order does not establish scan order or execution.');
    rungs.append(table(['Rung'],a.rung_ids,id=>[sourceCell(id)],'Exact address rungs'));content.append(rungs);
    const local=linksByAddress.get(a.id)||[];
    if(local.length){const p=section('Possible local calculation reuse');p.append(localLinkNotice(),relationshipLinkTable(local,'Exact address local links'));content.append(p);}
    if(calculationPaths){const paths=calculationPathOccurrences.filter(c=>c.destination_address_id===a.id||c.input_operand_ids.some(id=>byUseAddress.get(id)?.id===a.id)||c.expression_use_ids.some(id=>byUseAddress.get(id)?.id===a.id));if(paths.length){const p=section('Calculation inputs and destinations using this address');p.append(calculationPathTable(paths,'Exact address calculation blocks'));content.append(p);}}
    const outputs=outputContext?(byOutputAddress.get(a.id)?.output_ids||[]).map(id=>byConditionalOutput.get(byOutputContext.get(id)?.condition_output_id)).filter(Boolean):outputsByAddress.get(a.id)||[];
    if(outputs.length){const p=section('Conditional coil outputs targeting this address','These are captured OTE, OTL or OTU occurrences, not proof of a physical output or process effect.');p.append(conditionalOutputTable(outputs,'Exact address conditional outputs'));content.append(p);}
    if(byOutputAddress.has(a.id))content.append(button('Inspect qualified Boolean output address context',()=>openDetail('outputaddress',a.id),'text-link'));
    content.append(technical({'Address group ID':a.id,'Resolved declaration ID':a.target_id,'Identity rule':'Exact expanded spelling'}));
  }
  function timerCounterNotice(){return notice('Captured timer and counter relationships','These records connect source occurrences through qualified exact control addresses. Incoming conditions describe source structure, not timing, count transitions, execution order or final state. Stored PRE, ACC and status values remain export evidence across every representation; no effective preset, live value, elapsed time or alarm purpose is inferred.');}
  function statefulOccurrenceName(o){return o.control_address_id?addressName(byAddress.get(o.control_address_id)):short(byOperand.get(o.control_operand_id)?.raw_text||'(control unresolved)',160);}
  function statefulOccurrenceLink(o){return button(o.opcode+' · '+statefulOccurrenceName(o),()=>openDetail('statefuloccurrence',o.id),'text-link');}
  function statefulObjectLink(id){const o=byStatefulGroup.get(id);return o?button(addressName(byAddress.get(id)),()=>openDetail('statefulobject',id),'text-link'):node('span','muted','No qualified control address');}
  function statefulObjectGap(o){return Boolean(statefulGroupGaps.get(o.id)?.size);}
  function statefulOccurrenceTable(rows,caption,emptyOptions=null){return table(['Instruction occurrence','Control address','Incoming source condition','Rung'],rows,o=>[
    statefulOccurrenceLink(o),primary(statefulObjectLink(o.control_address_id),human(o.target_status)),outputContextStatus(o.context_status),sourceCell(o.rung_id)
  ],caption,emptyOptions||{emptyTitle:'No timer, counter or reset occurrences in this selection',emptyDetail:'Change the opcode or evidence filter. Unresolved controls remain available in this view.'});}
  function statefulObjectTable(rows,caption){return table(['Qualified control address','Observed family / declared root type','Producer / reset occurrences','Array evidence','Review gaps'],rows,o=>[
    statefulObjectLink(o.id),primary(human(o.family),'Root '+(byEntity.get(o.target_id)?.attributes?.DataType||'type unavailable')+' · '+human(o.declaration_kind)),o.producer_ids.length+' / '+o.reset_ids.length,human(o.bounds_status),[...statefulGroupGaps.get(o.id),...(o.has_tof_reset?['TOF and RES both observed']:[])].join(' · ')||'No gap from these rules'
  ],caption);}
  function statefulObjectsToolbar(){
    const groups=state.statefulMode!=='occurrences';
    toolbarFor(groups?'Search control addresses, timer or counter families, types and bounds':'Search timer, counter and reset opcodes, control addresses or rung context',groups?[['all','All control groups'],['timer','Timer groups'],['counter','Counter groups'],['mixed','Mixed instruction families'],['reset_only','Reset without matching producer']]:[['all','All opcodes'],...['TON','TOF','RTO','CTU','CTD','RES'].map(v=>[v,v])]);
    const select=(labelText,items,current,change)=>{const label=node('label','filter-wrap',labelText),box=node('select');box.setAttribute('aria-label',labelText);items.forEach(([value,text])=>{const option=node('option','',text);option.value=value;box.append(option);});box.value=current;box.addEventListener('change',()=>change(box.value));label.append(box);toolbar.querySelector('.toolbar').append(label);};
    select('Timer and counter view',[['objects','Control groups'],['occurrences','Instruction occurrences']],state.statefulMode||'objects',value=>{state.statefulMode=value;state.filter='all';state.listPages={};render();});
    select('Timer and counter evidence',[['all','All evidence'],['gaps','With unresolved evidence'],['qualified','Qualified evidence']],state.statefulEvidence||'all',value=>{state.statefulEvidence=value;state.listPages={};renderList();});
  }
  function statefulObjectsList(){
    content.append(timerCounterNotice());
    const total=panel('Timer, counter and reset coverage','Control groups require exact qualified addresses. Unresolved controls remain instruction occurrences.');
    total.append(values({'Instruction occurrences':statefulOccurrences.length,'Qualified control groups':statefulGroups.length,'Unresolved controls':statefulOccurrences.filter(o=>o.target_status!=='exact_address').length,'Groups with matched resets':statefulGroups.filter(o=>o.producer_ids.length&&o.reset_ids.length).length,'Reset-only groups':statefulGroups.filter(o=>o.family==='reset_only').length,'Mixed instruction families':statefulGroups.filter(o=>o.family==='mixed').length}));content.append(total);
    const accepts=gap=>!state.statefulEvidence||state.statefulEvidence==='all'||(state.statefulEvidence==='gaps')===gap;
    if(state.statefulMode==='occurrences')content.append(statefulOccurrenceTable(statefulOccurrences.filter(o=>matches(o)&&(state.filter==='all'||o.opcode===state.filter)&&accepts(o.target_status!=='exact_address'||o.context_status!=='modeled'||(byStatefulGroup.has(o.control_address_id)&&statefulObjectGap(byStatefulGroup.get(o.control_address_id))))),'Timer and counter instruction occurrences'));
    else content.append(statefulObjectTable(statefulGroups.filter(o=>matches(o)&&(state.filter==='all'||o.family===state.filter)&&accepts(statefulObjectGap(o))),'Timer and counter control groups'));
  }
  function statefulObjectSections(o){
    const summary=panel('Qualified control identity','An exact spelling association retains the declared type and any literal array bounds separately. A matched reset is a source association, not proof that it executes.');
    summary.append(values({'Control address':addressName(byAddress.get(o.id)),'Observed instruction family':human(o.family),'Declared root data type':byEntity.get(o.target_id)?.attributes?.DataType||'Unavailable','Qualified control kind':human(o.declaration_kind),'Type conflict':o.type_conflict?'Yes':'No','Array evidence':human(o.bounds_status),'TOF and RES co-occurrence':o.has_tof_reset?'Both observed; effects require engineering review':'Not observed together'}));
    const links=node('div','inline-links');links.append(sourceCell(o.target_id),button('Open original exact address evidence',()=>openDetail('address',o.id),'text-link'));summary.append(links);content.append(summary);
    content.append(statefulOccurrenceTable(o.producer_ids.map(id=>byStatefulOccurrence.get(id)),'Timer and counter producer occurrences',{emptyTitle:'No timer or counter producer occurrences observed',emptyDetail:'Only qualified exact address associations are shown.'}),statefulOccurrenceTable(o.reset_ids.map(id=>byStatefulOccurrence.get(id)),'Reset occurrences for this control',{emptyTitle:'No reset occurrences observed for this exact control',emptyDetail:'Only qualified exact address associations are shown.'}));
    if(!o.producer_ids.length)content.append(notice('No matched timer or counter occurrence','This export contains a reset at this address without a qualified TON, TOF, RTO, CTU or CTD occurrence. A CONTROL reset may be valid outside this timer and counter interpretation. Absence here does not prove unused logic.'));
    const uses=section('Observed control and member uses','Direct members, other suffixes and whole-control operands remain separate. Explicit writes and unknown roles do not establish the final control state.');
    uses.append(table(['Exact observed address','Member context','Reads / writes / read-write / unknown','Expression reads','Namespace gaps'],statefulUsesByObject.get(o.id)||[],u=>[
      button(addressName(byAddress.get(u.address_id)),()=>openDetail('statefuluse',u.address_id,{statefulObjectId:o.id}),'text-link'),primary(u.member||'Whole control',human(u.kind)+' · '+human(u.member_status)),['read','write','read_write','unknown'].map(role=>u[role+'_operand_ids'].length).join(' / '),u.expression_use_ids.length,u.rejected_operand_ids.length+u.rejected_expression_use_ids.length
    ],'Timer and counter member uses'));content.append(uses);
    const stored=section('Stored control and member evidence','Each exact captured path remains linked to its own representation, including duplicate or conflicting values. No representation wins, and no time units or effective PRE / ACC values are selected. Namespace and shape gaps are visible but unqualified.');
    stored.append(table(['Stored member / control','Representation','Saved value / source text','Association'],statefulStoredByObject.get(o.id)||[],row=>{
      const e=byTagElement.get(row.element_id),c=byTagContent.get(e?.content_id);
      return[primary(sourceCell(row.element_id),row.member||'Control structure'),c?sourceCell(c.id):'Representation unavailable',node('div','snippet',Object.hasOwn(e?.attributes||{},'Value')?(e.attributes.Value===''?'Empty value':short(e.attributes.Value,180)):e?.direct_text?.trim()?short(e.direct_text,180):'No scalar value on this element'),human(row.status)+' · stored type '+human(row.type_status)];
    },'Timer and counter stored evidence'));content.append(stored);
    const reps=section('All stored representations for the declaration','Opaque data and representations without qualified member links remain available for source inspection.');reps.append(tagContentTable(o.content_ids.map(id=>byTagContent.get(id)).filter(Boolean),'Timer and counter data representations'));content.append(reps);
  }
  function statefulObjectDetail(o){setDetailHeading('TIMER AND COUNTER CONTROL',addressName(byAddress.get(o.id)),human(o.family));content.append(timerCounterNotice());statefulObjectSections(o);}
  function statefulOccurrenceDetail(o){
    setDetailHeading('TIMER COUNTER OR RESET OCCURRENCE',o.opcode+' · '+statefulOccurrenceName(o),sourceName(o.rung_id));content.append(timerCounterNotice());
    const summary=panel('Captured instruction and control','Incoming source conditions are kept separate from an instruction-specific timing or counting trigger. TOF timing and counter transitions require state beyond a static condition.');
    summary.append(values({'Opcode':o.opcode,'Control qualification':human(o.target_status),'Incoming condition context':outputContextStatus(o.context_status)}));
    const links=node('div','inline-links');links.append(sourceCell(o.id),sourceCell(o.rung_id));if(o.control_operand_id)links.append(sourceCell(o.control_operand_id));if(o.control_address_id)links.append(statefulObjectLink(o.control_address_id));summary.append(links);content.append(summary);
    const operands=(rungOperands.get(o.rung_id)||[]).filter(p=>p.instruction_id===o.id);if(operands.length){const captured=section('Captured instruction arguments','Pseudo PRE / ACC arguments and literal spellings remain source evidence. They are not interpreted as per-scan input values or approved settings.');captured.append(table(['Source argument','Role evidence'],operands,p=>[sourceCell(p.id),accessCell(byOperandAccess.get(p.id))],'Timer and counter captured arguments'));content.append(captured);}
    if(o.guard_id&&o.context_status!=='namespace_gap'){const incoming=section('Incoming source condition','This condition immediately precedes the source occurrence. It is not a timing interval, edge detector, runtime enable state or proof of execution.');incoming.append(values({'Evidence quality':outputContextStatus(o.context_status)}));content.append(incoming);conditionGraph(o.guard_id,'Timer and counter incoming condition','Incoming source condition');}
    else content.append(notice('Incoming condition unavailable','The source occurrence remains visible, but its condition link is unavailable or withheld because of unsupported namespace context.'));
    const object=byStatefulGroup.get(o.control_address_id);if(object)statefulObjectSections(object);else content.append(notice('Control association unresolved','Review the captured arguments and declaration evidence. This occurrence has not been assigned to a qualified timer or counter object.'));
  }
  function statefulUseDetail(u){
    const object=byStatefulGroup.get(u.object_id);setDetailHeading('TIMER AND COUNTER MEMBER USE',addressName(byAddress.get(u.address_id)),human(u.kind));content.append(timerCounterNotice(),statefulObjectLink(object.id));
    content.append(values({'Member':u.member||'Whole control','Member qualification':human(u.member_status)}));
    for(const role of ['read','write','read_write','unknown']){const ids=u[role+'_operand_ids'];if(!ids.length)continue;const sectionNode=section('Observed '+human(role)+' operands');sectionNode.append(table(['Source operand','Rung','Instruction','Role evidence'],ids,id=>{const use=byOperandAccess.get(id);return[sourceCell(id),sourceCell(use?.rung_id),sourceCell(use?.instruction_id),accessCell(use)];},'Timer and counter '+role+' operands'));content.append(sectionNode);}
    if(u.expression_use_ids.length){const sectionNode=section('Observed expression readers');sectionNode.append(expressionUseTable(u.expression_use_ids.map(id=>byExpressionUse.get(id)),'Timer and counter expression readers'));content.append(sectionNode);}
    if(u.rejected_operand_ids.length){const sectionNode=section('Unqualified namespace operand uses','These retained source occurrences do not participate in the qualified role associations.');sectionNode.append(table(['Source operand','Rung'],u.rejected_operand_ids,id=>[sourceCell(id),sourceCell(byOperandAccess.get(id)?.rung_id)],'Timer and counter namespace operand gaps'));content.append(sectionNode);}
    if(u.rejected_expression_use_ids.length){const sectionNode=section('Unqualified namespace expression uses');sectionNode.append(expressionUseTable(u.rejected_expression_use_ids.map(id=>byExpressionUse.get(id)),'Timer and counter namespace expression gaps'));content.append(sectionNode);}
  }
  function signalNotice(){return notice('Direct source relationships with visible boundaries','Follow one address or output at a time. Exact spelling and condition ancestry associate captured occurrences; they do not prove execution order, physical wiring, shutdown effects or final state. Comparisons retain every operand and literal. ONS storage is a state boundary. Rung-wide authored hints remain leads, not output classifications.');}
  function signalAddressLink(id){const a=bySignalAddress.get(id);return a?button(addressName(byAddress.get(id)),()=>openDetail('signaladdress',id),'text-link'):node('span','muted','No qualified exact address');}
  function signalOutputTable(rows,caption){return table(['Output occurrence','Target address','Captured action','Guard quality','Rung / routine'],rows,o=>[
    button(o.opcode+' · '+short(byOperand.get(o.target_operand_id)?.raw_text||'(unresolved)',100),()=>openDetail('signaloutput',o.id),'text-link'),signalAddressLink(o.target_address_id),conditionActionLabel(o.action),primary(outputContextStatus(o.guard_quality),[o.has_stateful?'Stored state':'',o.has_opaque?'Unknown transfer':'',o.has_namespace_gap?'Namespace gap':''].filter(Boolean).join(' · ')),primary(sourceCell(o.rung_id),entityPath(o.routine_id))
  ],caption);}
  function signalReadTable(rows,caption){return table(['Source operand','Condition role','Qualification','Exact address','Instruction / rung'],rows,r=>[
    sourceCell(r.id),({xic:'XIC contact',xio:'XIO contact',comparison:'Comparison operand',ons_storage:'ONS stored-state operand'})[r.kind]||human(r.kind),human(r.status),signalAddressLink(r.source_address_id),signalReadSource(r)
  ],caption);}
  function signalReadSource(r){const n=node('div','inline-links');n.append(sourceCell(r.instruction_id),button(sourceName(r.rung_id)+' · edit context',()=>openDetail('signalrung',r.rung_id),'text-link'));return n;}
  function signalAddressTable(rows,caption){return table(['Exact signal address','Captured context','Coil occurrences','Condition operands','Other writers','Unknown-role uses'],rows,a=>[
    signalAddressLink(a.id),primary(human(a.profile),outputEndpoint(a.endpoint_kind)),fmt(a.output_ids.length),fmt(a.condition_read_ids.length),fmt(a.noncoil_writer_operand_ids.length),fmt(a.unknown_operand_ids.length)
  ],caption);}
  function addToolbarSelect(labelText,items,current,change){const label=node('label','filter-wrap',labelText),select=node('select');select.setAttribute('aria-label',labelText);items.forEach(([value,text])=>{const option=node('option','',text);option.value=value;select.append(option);});select.value=current;select.addEventListener('change',()=>change(select.value));label.append(select);toolbar.querySelector('.toolbar').append(label);}
  function signalToolbar(){
    toolbarFor('Search exact addresses, operand text, routine names or gaps');
    addToolbarSelect('Signal view',[['addresses','Exact signal addresses'],['outputs','Output guard dossiers'],['reads','All condition operands']],state.signalMode||'addresses',v=>{state.signalMode=v;state.filter='all';state.listPages={};render();});
  }
  function signalList(){
    content.append(signalNotice());const summary=panel('Signal relationship coverage','All captured condition operands remain visible, including literals and unresolved references. Each output keeps its own guard and source content.');
    summary.append(values({'Exact signal addresses':signalAddresses.length,'Output occurrences':signalOutputs.length,'Condition operand occurrences':signalReads.length,'Qualified condition operand occurrences':signalReads.filter(r=>r.status==='exact_address').length,'Literal and system operands':signalReads.filter(r=>['literal','system_flag'].includes(r.status)).length,'Unresolved condition operands':signalReads.filter(r=>!['exact_address','literal','system_flag'].includes(r.status)).length,'Source rungs':signalContext.rung_contexts.length}));content.append(summary);
    if(state.signalMode==='outputs')content.append(signalOutputTable(signalOutputs.filter(matches),'Signal output guard dossiers'));
    else if(state.signalMode==='reads')content.append(signalReadTable(signalReads.filter(matches),'All signal condition operands'));
    else content.append(signalAddressTable(signalAddresses.filter(matches),'Exact signal address dossiers'));
  }
  function signalWalk(seedIds,reverse=false){
    // Follow the existing DAG once per selected node, without materializing a
    // contact-by-coil product or automatically expanding transitive signals.
    const parents=reverse?conditionParents():null;
    const queued=new Set(),pending=[],seen=new Set();let edges=0,truncated=false;
    const enqueue=id=>{if(!id||queued.has(id)||!byConditionNode.has(id))return;if(queued.size>=SIGNAL_NODE_LIMIT){truncated=true;return;}queued.add(id);pending.push(id);};
    for(const id of seedIds)enqueue(id);
    while(pending.length){const id=pending.pop();seen.add(id);const next=reverse?(parents.get(id)||[]):byConditionNode.get(id).child_ids;
      for(const child of next){if(edges>=SIGNAL_EDGE_LIMIT){truncated=true;break;}edges++;enqueue(child);}if(edges>=SIGNAL_EDGE_LIMIT&&pending.length){truncated=true;break;}}
    return {seen,edges,truncated};
  }
  function signalTraversalNotice(walk){return notice(walk.truncated?'Relationship traversal truncated':'Relationship traversal complete for this selection',fmt(walk.seen.size)+' condition nodes and '+fmt(walk.edges)+' dependency links examined. Per-selection limits: '+fmt(SIGNAL_NODE_LIMIT)+' nodes and '+fmt(SIGNAL_EDGE_LIMIT)+' links.'+(walk.truncated?' Displayed associations are a partial subset. An absent result here cannot establish absence of a dependency.':' This is one direct condition relationship, not a transitive equipment chain.'));}
  function signalDependencyCell(n,labels){
    const box=node('div');box.append(node('span','',n.child_ids.slice(0,8).map(id=>labels.get(id)||'Outside bounded selection').join(' · ')||'No child nodes'));
    if(n.child_ids.length>8)box.append(button('Inspect '+fmt(n.child_ids.length)+' dependency inputs',()=>{state.signalConditionNode=n.id;render();},'text-link'));
    return box;
  }
  function signalProvenance(rungId){
    const r=bySignalRung.get(rungId);if(!r)return;const p=panel('Exact source and edit context','Captured content versions remain separate. No active edit or runtime scan order is selected.');
    p.append(values({'Routine':entityPath(r.routine_id),'Program':r.program_id?entityName(r.program_id):'No program owner','Namespace qualification':r.qualified?'Qualified':'Unqualified','Content location':r.content_locator,'Raw content / edit attributes':r.content_attributes||{}}));
    const links=node('div','inline-links');links.append(sourceCell(rungId),sourceCell(r.routine_id));if(r.execution_routine_context_id)links.append(button('Routine scheduling and callers',()=>openDetail('executioncontext',r.execution_routine_context_id),'text-link'));p.append(links);content.append(p);
    for(const [field,title] of [['candidate_ids_by_category','Rung-wide authored hints'],['unqualified_candidate_ids_by_category','Unqualified rung-wide authored hints']]){const ids=Object.values(r[field]||{}).flat();if(!ids.length)continue;const hints=section(title,'These words belong to the whole rung and do not classify this signal or establish an alarm effect.');hints.append(table(['Candidate category','Supporting source evidence'],ids.map(id=>byRungCandidate.get(id)).filter(Boolean),(c,i)=>[human(c.category),engineeringIdTable(c.evidence_ids,(field==='candidate_ids_by_category'?'Qualified ':'Unqualified ')+human(c.category)+' hint '+(i+1)+' evidence')],title));content.append(hints);}
  }
  function signalOutputDetail(o){
    setDetailHeading('SIGNAL OUTPUT GUARD',o.opcode+' · '+short(byOperand.get(o.target_operand_id)?.raw_text||'(unresolved)',160),sourceName(o.rung_id));content.append(signalNotice());
    const summary=panel('This output occurrence','The action belongs to this source occurrence; another writer may target the same address.');summary.append(values({'Captured action':conditionActionLabel(o.action),'Target qualification':human(o.target_status),'Guard quality':outputContextStatus(o.guard_quality),'Branch join':o.has_branch?'Present':'Absent','Stored-state context':o.has_stateful?'Present':'Absent','Unknown transfer':o.has_opaque?'Present':'Absent'}),signalAddressLink(o.target_address_id));content.append(summary);signalProvenance(o.rung_id);
    const walk=signalWalk([o.guard_id]);content.append(signalTraversalNotice(walk));const rows=[...walk.seen].map(id=>byConditionNode.get(id)),reads=rows.flatMap(n=>signalReadsByNode.get(n.id)||[]),labels=new Map(rows.map((n,i)=>[n.id,'C'+(i+1)]));
    if(o.has_namespace_gap)content.append(notice('Unqualified guard context','The original operands below are retained for inspection. This output does not participate in qualified downstream associations.'));
    const inputs=section('Condition operands upstream of this output','Every captured predicate operand is included when reached: contacts, comparison values and ONS storage. Click an exact address to inspect its captured writers. No input is selected by proximity.');inputs.append(signalReadTable(reads,'Output upstream condition operands'));content.append(inputs);
    const graph=section('Direct guard structure','All joins series conditions; Any joins alternate branches. Unknown transfers retain incoming context without proving a Boolean rule. Contact polarity is shown by its opcode; no overall polarity is inferred.');graph.append(table(['Node','Source meaning','Dependency nodes','Source instruction'],rows,n=>[labels.get(n.id),conditionNodeLabel(n),signalDependencyCell(n,labels),sourceCell(n.instruction_id)],'Signal bounded guard nodes'));content.append(graph);
    const selected=byConditionNode.get(state.signalConditionNode);if(selected&&walk.seen.has(selected.id)){const details=section('Dependency inputs for '+labels.get(selected.id),'Each captured dependency is listed separately. Inputs outside the bounded traversal remain explicitly marked.');details.append(table(['Input','Selected traversal label','Source meaning','Source instruction'],selected.child_ids.slice(0,SIGNAL_EDGE_LIMIT),(id,i)=>[i+1,labels.get(id)||'Outside bounded selection',conditionNodeLabel(byConditionNode.get(id)),sourceCell(byConditionNode.get(id)?.instruction_id)],'Signal selected node dependency inputs'));if(selected.child_ids.length>SIGNAL_EDGE_LIMIT)details.append(notice('Dependency input list truncated','Showing '+fmt(SIGNAL_EDGE_LIMIT)+' of '+fmt(selected.child_ids.length)+' inputs. Inspect the original source for the remaining entries.'));content.append(details);}
    if(o.has_stateful)content.append(statefulNotice());
  }
  function signalRungDetail(r){setDetailHeading('SIGNAL RUNG CONTEXT',sourceName(r.id),entityPath(r.routine_id));content.append(signalNotice());signalProvenance(r.id);content.append(signalReadTable(r.condition_read_ids.map(id=>bySignalRead.get(id)).filter(Boolean),'Signal rung condition operands'),signalOutputTable(r.output_ids.map(id=>bySignalOutput.get(id)).filter(Boolean),'Signal rung output guards'));}
  function signalAddressDetail(a){
    setDetailHeading('SIGNAL ADDRESS DOSSIER',addressName(byAddress.get(a.id)),outputEndpoint(a.endpoint_kind));content.append(signalNotice());const p=panel('Captured address uses','Absence of captured readers or writers does not prove unused logic. Alias overlap, indirect addressing, SFC, external communications and runtime order require separate evidence.');
    p.append(values({'Context':human(a.profile),'Coil writers':a.output_ids.length,'Other writer operands':a.noncoil_writer_operand_ids.length,'Read operands':a.read_operand_ids.length,'Read/write operands':a.read_write_operand_ids.length,'Expression reads':a.expression_use_ids.length,'Unknown-role uses':a.unknown_operand_ids.length}),sourceCell(a.target_id));content.append(p);
    const writes=section('Upstream captured coil writers','Inspect each writer independently. Set, clear and assign actions remain distinct, including competing writers and alternate source contents.');writes.append(signalOutputTable(a.output_ids.map(id=>bySignalOutput.get(id)).filter(Boolean),'Signal address coil writers'));content.append(writes);
    const reads=a.condition_read_ids.map(id=>bySignalRead.get(id)).filter(Boolean),readerSection=section('Direct condition operands at this address','ONS storage remains a state boundary; comparisons retain their other operands on the output guard dossier.');readerSection.append(signalReadTable(reads,'Signal address condition operands'));content.append(readerSection);
    const walk=signalWalk(reads.filter(r=>r.status==='exact_address').map(r=>r.condition_node_id),true);content.append(signalTraversalNotice(walk));const downstream=signalOutputs.filter(o=>!o.has_namespace_gap&&o.guard_quality!=='namespace_gap'&&walk.seen.has(o.guard_id));const consumers=section('Downstream output guard associations','These outputs share a direct condition-DAG path from one of the accepted reads above. This does not establish shutdown behavior, causal influence or final output state.');consumers.append(signalOutputTable(downstream,'Signal downstream output guards'));content.append(consumers);
    for(const [field,title] of [['read_operand_ids','All accepted explicit readers'],['noncoil_writer_operand_ids','Other captured writer operands'],['read_write_operand_ids','Read/write state uses'],['unknown_operand_ids','Unknown-role uses'],['rejected_operand_ids','Namespace-rejected original uses']]){if(!a[field].length)continue;const uses=section(title);uses.append(accessBindingTable(a[field].map(id=>byOperandAccess.get(id)).filter(Boolean),title));content.append(uses);}
    for(const [field,title] of [['expression_use_ids','Accepted expression reads'],['rejected_expression_use_ids','Namespace-rejected expression reads']]){if(!a[field].length)continue;const uses=section(title,'Expression reads remain separate from Boolean condition dependencies.');uses.append(expressionUseTable(a[field].map(id=>byExpressionUse.get(id)).filter(Boolean),title));content.append(uses);}
    if(a.stateful_associations.length){const stateful=section('Timer and counter member associations','These exact member associations retain their qualification. They do not establish elapsed time, an alarm delay or a runtime value.');stateful.append(table(['Control object','Member evidence','Qualification'],a.stateful_associations,r=>[statefulObjectLink(r.object_id),human(r.kind)+(r.member?' · '+r.member:'')+' · '+human(r.member_status),human(r.qualification)],'Signal timer and counter associations'));content.append(stateful);}
  }
  function outputContextName(o){const a=byAddress.get(o.target_address_id);return a?addressName(a):short(byOperand.get(o.target_operand_id)?.raw_text||'(target unresolved)',160);}
  function outputContextLink(o){return button(o.opcode+' · '+outputContextName(o),()=>openDetail('condition',o.condition_output_id),'text-link');}
  function outputContextStatus(status){return ({modeled:'Modeled condition structure',binding_gaps:'Condition binding gaps',opaque:'Contains unknown transfer',stateful:'Contains stored-state condition',namespace_gap:'Namespace context unavailable'})[status]||human(status);}
  function outputEndpoint(kind){return ({module_output:'Module output root',module_input:'Module input root',module_config:'Module configuration root',tag:'Tag declaration',other:'Other declaration'})[kind]||'No accepted target';}
  function outputRungHintCategories(rungId){const r=byOutputRungContext.get(rungId);return r?Object.entries(r.candidate_ids_by_category).filter(([,ids])=>ids.length).map(([category])=>category):[];}
  function outputContextTarget(o){const a=byOutputAddress.get(o.target_address_id);return a?button('Address: '+addressName(byAddress.get(a.id)),()=>openDetail('outputaddress',a.id),'text-link'):primary(sourceCell(o.target_operand_id),'No accepted target address · '+human(o.target_status));}
  function outputContextNotice(){return notice('Captured uses and condition context','Coil actions describe OTE, OTL and OTU normal execution. Exact-address readers and other writers remain separate source occurrences; their order, final state and execution are not inferred. Condition consumers follow existing condition-graph edges, including stored-state and unknown-transfer context. An association does not establish polarity, shutdown behavior or a physical channel. Missing readers do not establish unused or dead logic.');}
  function outputContextTable(rows,caption){return table(['Coil occurrence','Qualified target','Normal-execution action','Condition context','Rung-wide authored hints','Rung'],rows,o=>[
    outputContextLink(o),outputContextTarget(o),conditionActionLabel(o.action),primary(outputContextStatus(o.context_status),o.has_stateful?'Includes stored-state context':''),outputRungHintCategories(o.rung_id).map(human).join(' · ')||'None captured',sourceCell(o.rung_id)
  ],caption,{emptyTitle:'No coil occurrences in this selection',emptyDetail:'Change the target, condition or opcode filter. Unresolved OTE, OTL and OTU targets remain in the occurrence view.'});}
  function outputAddressTable(rows,caption){return table(['Exact target address','Declared endpoint root','Coil occurrences','Read / read-write / expression uses','Other writers / unknown-role uses'],rows,a=>[
    button(addressName(byAddress.get(a.id)),()=>openDetail('outputaddress',a.id),'text-link'),outputEndpoint(a.endpoint_kind),a.output_ids.length,a.read_operand_ids.length+' / '+a.read_write_operand_ids.length+' / '+a.expression_use_ids.length,a.noncoil_writer_operand_ids.length+' / '+a.unknown_operand_ids.length
  ],caption,{emptyTitle:'No qualified output targets in this selection',emptyDetail:'Unbound, malformed and namespace-confounded targets remain visible in the coil occurrence view.'});}
  function outputContextToolbar(){
    const targets=state.outputContextMode==='targets';
    toolbarFor(targets?'Search exact targets, declaration kinds or use profiles':'Search coil targets, opcodes, rung context or authored hints',targets?[['all','All target profiles'],['read_and_write','Targets with captured readers'],['write_only','Targets without captured readers']]:[['all','All coil opcodes'],['OTE','OTE'],['OTL','OTL'],['OTU','OTU']]);
    addToolbarSelect('Output view',[['occurrences','Coil occurrences'],['targets','Exact target addresses']],state.outputContextMode||'occurrences',value=>{state.outputContextMode=value;state.filter='all';state.listPages={};render();});
    if(!targets){
      addToolbarSelect('Target evidence',[['all','All targets'],['exact_address','Qualified exact addresses'],['gaps','Unresolved target addresses']],state.outputTargetFilter||'all',value=>{state.outputTargetFilter=value;state.listPages={};renderList();});
      addToolbarSelect('Condition context',[['all','All condition contexts'],['modeled','Modeled'],['binding_gaps','Binding gaps'],['opaque','Unknown transfer'],['stateful','Stored-state context'],['namespace_gap','Namespace unavailable']],state.outputContextFilter||'all',value=>{state.outputContextFilter=value;state.listPages={};renderList();});
      addToolbarSelect('Authored rung hints',[['all','All authored hint contexts'],['present','With accepted rung hints'],['absent','Without accepted rung hints']],state.outputHintFilter||'all',value=>{state.outputHintFilter=value;state.listPages={};renderList();});
    }
  }
  function outputContextList(){
    content.append(outputContextNotice());
    const c=outputContext.coverage,summary=panel('Boolean output context coverage','Counts describe source occurrences and shared exact addresses. Authored hints remain rung-wide leads for review.');
    summary.append(values({'Coil occurrences':c.outputs_total,'Qualified target addresses':c.addresses_total,'Unresolved target occurrences':c.outputs_total-c.targets_by_status.exact_address,'Targets with multiple coils':c.addresses_with_multiple_coils,'Targets with other writers':c.addresses_with_noncoil_writers,'Targets with unknown-role uses':c.addresses_with_unknown_roles,'Rungs with authored hints':c.rungs_with_hints}));content.append(summary);
    if(state.outputContextMode==='targets')content.append(outputAddressTable(contextAddresses.filter(a=>matches(a)&&(state.filter==='all'||a.profile===state.filter)),'Boolean output target addresses'));
    else content.append(outputContextTable(contextOutputs.filter(o=>matches(o)&&(state.filter==='all'||o.opcode===state.filter)&&(!state.outputTargetFilter||state.outputTargetFilter==='all'||(state.outputTargetFilter==='gaps'?o.target_status!=='exact_address':o.target_status==='exact_address'))&&(!state.outputContextFilter||state.outputContextFilter==='all'||o.context_status===state.outputContextFilter)&&(!state.outputHintFilter||state.outputHintFilter==='all'||(state.outputHintFilter==='present')===Boolean(outputRungHintCategories(o.rung_id).length))),'Boolean output occurrences'));
  }
  function conditionParents(){if(outputConditionParents===null){outputConditionParents=new Map();conditionNodes.forEach(n=>n.child_ids.forEach(id=>add(outputConditionParents,id,n.id)));}return outputConditionParents;}
  function outputAddressConsumers(a){
    // Build one reverse DAG index lazily. Each selection visits each relevant
    // node once; no writer-by-reader pairs or flattened guard trees are cached.
    const parents=conditionParents();
    const reads=outputConditionReads.filter(r=>r.status==='accepted'&&r.source_address_id===a.id),seen=new Set(),pending=reads.map(r=>r.condition_node_id);
    while(pending.length){const id=pending.pop();if(seen.has(id))continue;seen.add(id);for(const parent of parents.get(id)||[])if(!seen.has(parent))pending.push(parent);}
    return {reads,outputs:contextOutputs.filter(o=>o.context_status!=='namespace_gap'&&seen.has(o.guard_id))};
  }
  function outputAuthoredHints(rungId){
    const r=byOutputRungContext.get(rungId);if(!r)return;
    for(const [field,title,description] of [['candidate_ids_by_category','Authored wording on this rung','These existing name, description and comment hints belong to the entire rung. They do not classify a particular coil as an alarm, equipment command or shutdown.'],['unqualified_candidate_ids_by_category','Authored wording with unsupported namespace context','These original hints remain separate because their source namespace context is unqualified. They do not establish an output purpose.']]){
      const ids=Object.values(r[field]).flat();if(!ids.length)continue;
      const sectionNode=section(title,description);sectionNode.append(table(['Rung-wide category','Original supporting evidence'],ids.map(id=>byRungCandidate.get(id)).filter(Boolean),candidate=>{const proof=node('details','technical');proof.append(node('summary','',fmt(candidate.evidence_ids.length)+' source references'),engineeringIdTable(candidate.evidence_ids,'Authored output context '+candidate.id));return[human(candidate.category),proof];},title));content.append(sectionNode);
    }
  }
  function outputContextAddressSections(a){
    const original=byAddress.get(a.id),summary=panel('Qualified target address uses','Every accepted use shares this exact expanded spelling. Other writes may occur; the final state and writer order remain unmodeled.');
    summary.append(values({'Address':addressName(original),'Declared endpoint root':outputEndpoint(a.endpoint_kind),'Coil occurrences':a.output_ids.length,'Operand readers':a.read_operand_ids.length,'Operand writers':a.write_operand_ids.length,'Read/write uses':a.read_write_operand_ids.length,'Expression readers':a.expression_use_ids.length,'Other writer operands':a.noncoil_writer_operand_ids.length,'Unknown-role uses':a.unknown_operand_ids.length}));
    const links=node('div','inline-links');links.append(sourceCell(a.target_id),button('Open original relationship evidence',()=>openDetail('address',a.id),'text-link'));summary.append(links);content.append(summary);
    const coils=section('Coils targeting this exact address','OTE assigns its incoming condition; OTL and OTU set or clear only when true. These source actions do not determine the final target state.');coils.append(outputContextTable(a.output_ids.map(id=>byOutputContext.get(id)).filter(Boolean),'Coils sharing a qualified target'));content.append(coils);
    for(const [field,title,description] of [['read_operand_ids','Accepted operand readers','Explicit operand reads retain their source instruction and binding.'],['read_write_operand_ids','Accepted read/write uses','Stored-state operands remain separate from read-only predicates.'],['noncoil_writer_operand_ids','Other captured writer operands','These accepted writer or read/write operands are separate from the selected coil instructions. No writer order or final state is assigned.'],['unknown_operand_ids','Uses with unknown operand roles','A referenced address with an unresolved role is not promoted to a reader or writer.'],['rejected_operand_ids','Uses with unsupported namespace context','Original source evidence remains available, but these uses do not participate in qualified reader or writer associations.']]){
      if(!a[field].length)continue;const useSection=section(title,description);useSection.append(accessBindingTable(a[field].map(id=>byOperandAccess.get(id)).filter(Boolean),title));content.append(useSection);
    }
    for(const [field,title,description] of [['expression_use_ids','Accepted expression readers','Each CPT reference leaf remains a separate occurrence; a data read is not automatically a Boolean condition dependency.'],['rejected_expression_use_ids','Expression reads with unsupported namespace context','These original references remain outside qualified associations.']]){if(!a[field].length)continue;const useSection=section(title,description);useSection.append(expressionUseTable(a[field].map(id=>byExpressionUse.get(id)).filter(Boolean),title));content.append(useSection);}
    const consumers=outputAddressConsumers(a),readerSection=section('Direct condition-read occurrences','Predicate operands and ONS stored-state reads are retained separately. Repeated reads remain visible; no output-to-output pairs are constructed.');
    readerSection.append(table(['Source read','Condition-read kind','Instruction','Rung'],consumers.reads,r=>[sourceCell(r.id),r.kind==='ons_storage'?'ONS stored-state read':'Predicate operand read',sourceCell(byOperand.get(r.id)?.instruction_id),sourceCell(byConditionNode.get(r.condition_node_id)?.rung_id)],'Qualified condition reads of output target'));content.append(readerSection);
    const outputSection=section('Outputs whose captured condition context reads this address','These outputs are reached through actual condition-graph edges from the accepted predicate or ONS reads above. Sibling-rung proximity is not used. Stored-state and unknown-transfer flags remain visible. An association does not establish polarity, an active interlock or shutdown behavior.');
    outputSection.append(outputContextTable(consumers.outputs,'Outputs with matching condition ancestry'));content.append(outputSection);
    const rejected=outputConditionReads.filter(r=>r.source_address_id===a.id&&r.status!=='accepted');if(rejected.length){const gaps=section('Condition-read associations withheld','The original references have unsupported namespace context and do not contribute to the qualifying output list.');gaps.append(table(['Original read','Rung','Context gap'],rejected,r=>[sourceCell(r.id),sourceCell(byConditionNode.get(r.condition_node_id)?.rung_id),human(r.status)],'Unqualified condition-read occurrences'));content.append(gaps);}
  }
  function outputContextAddressDetail(a){setDetailHeading('BOOLEAN OUTPUT ADDRESS CONTEXT',addressName(byAddress.get(a.id)),outputEndpoint(a.endpoint_kind));content.append(outputContextNotice());outputContextAddressSections(a);}
  function outputContextDetail(o){
    setDetailHeading('BOOLEAN OUTPUT CONTEXT',o.opcode+' · '+outputContextName(o),sourceName(o.rung_id));content.append(outputContextNotice());
    const summary=panel('Captured coil action and condition','The recognized action and incoming source condition remain separate from the target uses and authored wording below.');summary.append(values({'Opcode':o.opcode,'Normal-execution action':conditionActionLabel(o.action),'Qualified target status':human(o.target_status),'Incoming condition context':outputContextStatus(o.context_status),'Contains a completed branch join':o.has_branch?'Yes':'No','Contains stored-state context':o.has_stateful?'Yes':'No'}));const links=node('div','inline-links');links.append(outputContextTarget(o));if(o.target_address_id)links.append(sourceCell(o.target_operand_id));links.append(sourceCell(o.instruction_id),sourceCell(o.rung_id));summary.append(links);content.append(summary);
    outputAuthoredHints(o.rung_id);
    if(o.context_status==='namespace_gap')content.append(notice('Original condition structure has unsupported namespace context','The graph below preserves earlier source evidence. This occurrence is excluded from qualified condition-consumer associations.'));
    if(o.guard_id)conditionGraph(o.guard_id,o.context_status==='namespace_gap'?'Original unqualified output condition nodes':'Qualified output condition nodes',o.context_status==='namespace_gap'?'Original source condition':'Incoming condition evidence');
    if(o.has_stateful)content.append(statefulNotice());
    const a=byOutputAddress.get(o.target_address_id);if(a)outputContextAddressSections(a);
    else content.append(notice('Target uses remain unresolved','No qualified target address is available for this occurrence. Inspect the source operand and existing binding context; no other output group is substituted.'));
    content.append(technical({'Output context ID':o.id,'Original output ID':o.condition_output_id,'Condition node ID':o.guard_id}));
  }
  function conditionTargetName(o){
    const address=byAddress.get(o.target_address_id);
    return address?addressName(address):short(byOperand.get(o.target_operand_id)?.raw_text || '(target unresolved)',180);
  }
  function conditionGuardLabel(status){return ({modeled:'Modeled condition structure',binding_gaps:'Condition binding gaps',opaque:'Contains unknown transfer'})[status] || human(status);}
  function conditionActionLabel(action){return ({assign_condition:'Assign incoming condition',set_if_true:'Set when true',clear_if_true:'Clear when true',unresolved:'Output signature unresolved'})[action] || human(action);}
  function conditionTarget(o){
    const a=byAddress.get(o.target_address_id);
    if(a)return button('Address: '+addressName(a),()=>openDetail('address',a.id),'text-link');
    const evidence=primary(sourceCell(o.target_operand_id),human(o.target_status));if(byBindingContext.has(o.target_operand_id))evidence.append(bindingContextLink(o.target_operand_id));return evidence;
  }
  function conditionNotice(){return notice('Source condition structure for normal execution','Incoming rung context is retained as a symbolic input, not assumed to be true. Contacts and comparisons remain separate source occurrences; intervening writes can change later reads. This is not PLC simulation, scan-order proof, or an assessment of alarms, shutdowns or physical outputs. Prescan and postscan behavior are not modeled.');}
  function conditionalOutputTable(rows,caption){if(outputContext)return outputContextTable(rows.map(o=>byConditionOutputContext.get(o.id)).filter(Boolean),caption);return table(['Output occurrence','Target evidence','Normal-execution action','Condition evidence','Rung'],rows,o=>[
    button(o.opcode+' · '+conditionTargetName(o),()=>openDetail('condition',o.id),'text-link'),conditionTarget(o),conditionActionLabel(o.action),primary(conditionGuardLabel(o.guard_status),o.has_stateful?'Contains stored-state condition':''),sourceCell(o.rung_id)
  ],caption,{emptyTitle:'No conditional outputs in this selection',emptyDetail:'This layer covers captured OTE, OTL and OTU occurrences. Other instruction effects remain in their source and access views.'});}
  function conditionsToolbar(){
    if(outputContext){outputContextToolbar();return;}
    toolbarFor('Search output targets, opcodes, rung context or condition quality',[['all','All output opcodes'],['OTE','OTE'],['OTL','OTL'],['OTU','OTU']]);
    const label=node('label','filter-wrap','Condition quality'),select=node('select');select.setAttribute('aria-label','Condition quality');
    [['all','All condition qualities'],['modeled','Modeled condition structure'],['binding_gaps','Condition binding gaps'],['opaque','Contains unknown transfer']].forEach(([v,t])=>{const option=node('option','',t);option.value=v;select.append(option);});
    select.value=state.conditionQuality || 'all';select.addEventListener('change',()=>{state.conditionQuality=select.value;state.listPages={};renderList();});label.append(select);toolbar.querySelector('.toolbar').append(label);
  }
  function conditionsList(){
    if(outputContext){outputContextList();return;}
    content.append(conditionNotice());
    const summary=panel('Captured coil occurrences','Each row is one output instruction. A modeled guard describes syntax, not an approved engineering function.');
    summary.append(values({'OTE / OTL / OTU occurrences':conditionalOutputs.length,'Modeled condition structure':conditionalOutputs.filter(o=>o.guard_status==='modeled').length,'Condition binding gaps':conditionalOutputs.filter(o=>o.guard_status==='binding_gaps').length,'Contains unknown transfer':conditionalOutputs.filter(o=>o.guard_status==='opaque').length,'Guards containing a branch join':conditions.coverage.outputs_with_branches,...(conditions.schema_version>=3?{'Guards containing stored-state conditions':conditions.coverage.outputs_with_stateful_conditions}:{})}));content.append(summary);
    content.append(conditionalOutputTable(conditionalOutputs.filter(o=>matches(o)&&(state.filter==='all'||o.opcode===state.filter)&&(!state.conditionQuality||state.conditionQuality==='all'||o.guard_status===state.conditionQuality)),'Conditional output occurrences'));
  }
  function transferOpcode(n){return short(byInstruction.get(n.instruction_id)?.instruction.opcode || 'Instruction',80);}
  function transferLabel(n){return n.kind==='pass_through'?'Passes incoming condition':n.kind==='stateful_transfer'?'ONS stored-state condition':'Unknown condition transfer';}
  function conditionQuality(n){return n?.has_opaque?'opaque':n?.has_binding_gap?'binding_gaps':'modeled';}
  function transferNotice(){return notice('Normal-scan condition transfer','A pass-through instruction keeps its incoming rung condition as its outgoing condition during documented normal execution. This is not an execution or write guard: evaluation with a false condition can still change instruction state, including timer, counter and OSF state. The OSF output bit is distinct from its outgoing rung condition. Data operands, values, types, faults and other instruction effects are not evaluated by this view. Inspect source and operand-access evidence separately.');}
  function statefulNotice(){return notice('ONS uses state at this occurrence','During normal evaluation: outgoing = incoming AND NOT storage-before; storage-after = incoming. A false incoming condition makes outgoing false and clears storage. Storage-before means immediately before this instruction occurrence; it is not assumed to be the previous scan value. Shared storage, later writes, task order and the final value are not simulated. The stored-state marker records syntax ancestry without Boolean simplification; a bypass can make a result independent of that state. ONS prescan sets its storage bit; prescan and first-scan execution are not evaluated here. OSF retains its separate pass-through rule; OSR remains deferred.');}
  function statefulPanel(n){
    const panelNode=panel('ONS normal-evaluation rule','This is a symbolic stored-state condition, not a predicted pulse or execution result.');
    panelNode.append(values({'Outgoing condition':'incoming AND NOT storage-before','Storage after this occurrence':'incoming','Known false incoming':'outgoing false; storage cleared','Storage identity':n.operand_ids.length&&byUseAddress.has(n.operand_ids[0])?'Exact address spelling available; member/type validity unverified':'Unresolved storage identity'}),statefulNotice());
    if(n.operand_ids.length){const links=node('div','inline-links');links.append(sourceCell(n.operand_ids[0]),addressCell(n.operand_ids[0]));panelNode.append(links);}return panelNode;
  }
  function transferTable(rows,caption){return table(['Instruction occurrence','Normal-scan condition transfer','Incoming condition evidence','Operand preview','Rung'],rows,n=>[
    button(transferOpcode(n),()=>openDetail('transfer',n.id),'text-link'),transferLabel(n),conditionGuardLabel(conditionQuality(byConditionNode.get(n.child_ids[0]))),
    node('div','snippet',n.operand_ids.slice(0,4).map(id=>short(byOperand.get(id)?.raw_text || '(blank)',80)).join(' · ')+(n.operand_ids.length>4?' · additional operands':'')),sourceCell(n.rung_id)
  ],caption,{emptyTitle:'No instruction condition transfers in this selection',emptyDetail:'Contacts, comparisons and coil outputs have their own condition evidence. This list retains other captured instruction occurrences.'});}
  function transfersList(){
    content.append(conditionNotice(),transferNotice());
    if(conditions.schema_version>=3)content.append(statefulNotice());
    const summary=panel('Instruction occurrences','Each row retains its own source occurrence, including instructions on rungs with no coil output. A pass-through rule can still have an unknown or unbound incoming condition.');
    summary.append(values({'Instruction transfers':conditionTransfers.length,'Documented pass-through':conditionTransfers.filter(n=>n.kind==='pass_through').length,...(conditions.schema_version>=3?{'Stored-state transfer':conditionTransfers.filter(n=>n.kind==='stateful_transfer').length}:{}),'Unknown transfer':conditionTransfers.filter(n=>n.kind==='opaque_transfer').length}));content.append(summary);
    content.append(transferTable(conditionTransfers.filter(n=>matches(n)&&(state.filter==='all'||n.kind===state.filter)),'Instruction condition transfers'));
  }
  function transferDetail(n){
    setDetailHeading('INSTRUCTION CONDITION TRANSFER',transferOpcode(n),sourceName(n.rung_id));
    content.append(conditionNotice(),transferNotice());
    const incoming=byConditionNode.get(n.child_ids[0]);
    const summary=panel('Captured instruction occurrence',n.kind==='pass_through'?'The documented normal-scan rule preserves the incoming rung condition. Data binding gaps do not alter this transfer rule.':n.kind==='stateful_transfer'?'The outgoing condition uses the stored value immediately before this occurrence. Normal evaluation also updates storage.':'The incoming rung condition is retained as context. Outgoing condition behavior remains unmodeled.');
    summary.append(values({'Opcode':transferOpcode(n),'Transfer':transferLabel(n),'Incoming condition evidence':conditionGuardLabel(conditionQuality(incoming)),'Outgoing condition evidence':conditionGuardLabel(conditionQuality(n)),'Reason':human(n.reason)}));
    const links=node('div','inline-links');links.append(sourceCell(n.instruction_id),sourceCell(n.rung_id));summary.append(links);content.append(summary);
    const operands=n.operand_ids.map(id=>byOperandAccess.get(id)).filter(Boolean);
    if(operands.length){const evidence=section('Separate operand-access evidence','Possible reads and writes and their bindings do not establish execution, data validity or the final value. They are separate from the Boolean condition-transfer rule.');evidence.append(accessBindingTable(operands,'Instruction transfer operand access'));content.append(evidence);}
    if(n.kind==='stateful_transfer')content.append(statefulPanel(n));
    conditionGraph(n.id,'Instruction condition nodes','Instruction outgoing condition');
    content.append(technical({'Condition node ID':n.id,'Instruction ID':n.instruction_id,'Evaluation scope':'Normal execution only'}));
  }
  function reachableConditionNodes(guardId){
    // Only the selected condition is traversed. Shared subgraphs are visited once;
    // no recursive formula expansion or per-output ancestor cache is created.
    const seen=new Set(),pending=[guardId],rows=[];
    while(pending.length){const id=pending.pop();if(seen.has(id))continue;seen.add(id);const n=byConditionNode.get(id);if(!n)continue;rows.push(n);for(const child of n.child_ids)if(!seen.has(child))pending.push(child);}
    return rows.sort((a,b)=>conditionNodeOrder.get(a.id)-conditionNodeOrder.get(b.id));
  }
  function conditionNodeLabel(n){
    if(n.kind==='entry')return 'Incoming rung context';
    if(n.kind==='all')return 'All inputs must hold';
    if(n.kind==='any')return 'Any branch input may hold';
    if(n.kind==='stateful_transfer')return 'ONS: incoming AND NOT storage before this occurrence';
    const opcode=byInstruction.get(n.instruction_id)?.instruction.opcode || 'Instruction';
    if(n.kind==='pass_through')return 'Pass through '+short(opcode,80)+' · incoming condition retained';
    return n.kind==='predicate'?'Test '+opcode:'Unknown transfer through '+short(opcode,80);
  }
  function conditionDetail(o){
    if(byConditionOutputContext.has(o.id)){outputContextDetail(byConditionOutputContext.get(o.id));return;}
    setDetailHeading('CONDITIONAL OUTPUT EVIDENCE',o.opcode+' · '+conditionTargetName(o),sourceName(o.rung_id));
    content.append(conditionNotice());
    const summary=panel('Output action',({assign_condition:'During normal execution, OTE writes 1 when its incoming condition is true and writes 0 when false.',set_if_true:'During normal execution, OTL sets its target when its incoming condition is true; a false condition leaves the target unchanged.',clear_if_true:'During normal execution, OTU clears its target when its incoming condition is true; a false condition leaves the target unchanged.',unresolved:'The captured output signature is unresolved. No target action is assigned.'})[o.action]);
    summary.append(values({'Opcode':o.opcode,'Action':conditionActionLabel(o.action),'Guard quality':conditionGuardLabel(o.guard_status),'Target identity':human(o.target_status),...(conditions.schema_version>=3?{'Contains stored-state condition':o.has_stateful?'Yes':'No'}:{})}));
    const links=node('div','inline-links');links.append(conditionTarget(o),sourceCell(o.target_operand_id),sourceCell(o.instruction_id),sourceCell(o.rung_id));summary.append(links);
    const target=byEntity.get(byAddress.get(o.target_address_id)?.target_id);
    if(['module_input_tag','module_output_tag'].includes(target?.kind))summary.append(node('p','row-note','Source declaration kind: '+human(target.kind)+'. This identifies module-tag context; a physical channel or process effect has not been confirmed.'));
    content.append(summary);
    if(o.has_stateful)content.append(statefulNotice());
    conditionGraph(o.guard_id,'Output condition nodes','Output guard');
    content.append(technical({'Output ID':o.id,'Guard node ID':o.guard_id,'Instruction ID':o.instruction_id,'Evaluation scope':'Normal execution only'}));
  }
  function conditionGraph(rootId,caption,rootLabel){
    const rows=reachableConditionNodes(rootId),labels=new Map(rows.map((n,i)=>[n.id,'C'+(i+1)]));
    const selectNode=id=>{state.focusConditionNode=id;render();};
    const childLink=id=>button(labels.get(id)||'Condition',()=>selectNode(id),'text-link');
    const graph=section('Condition structure','Each dependency appears once. All combines conditions in series; Any joins branch results, including empty bypass paths. An unknown transfer keeps its incoming condition as context without assuming Boolean AND behavior. Labels describe this selected condition only.'+(instructionConditions?' Pass-through nodes retain their instruction occurrence and incoming condition; their data operations are not evaluated.':''));
    graph.append(values({[rootLabel]:labels.get(rootId)||'Unavailable','Distinct dependency nodes':rows.length}));
    graph.append(table(['Node','Meaning / inputs','Source instruction','Evidence limits'],rows,n=>{
      const meaning=node('div');meaning.append(node('div','cell-main',conditionNodeLabel(n)));
      if(n.child_ids.length){const children=node('div','inline-links');children.append(node('span','muted',n.kind==='all'?'All of: ':n.kind==='any'?'Any of: ':'Incoming context: '));n.child_ids.slice(0,8).forEach(id=>children.append(childLink(id)));meaning.append(children);if(n.child_ids.length>8)meaning.append(button('Inspect all '+fmt(n.child_ids.length)+' inputs',()=>selectNode(n.id),'text-link'));}
      if(n.operand_ids.length)meaning.append(node('div','cell-sub',n.operand_ids.slice(0,4).map(id=>short(byOperand.get(id)?.raw_text || '(blank)',80)).join(' · ')+(n.operand_ids.length>4?' · additional operands':'')));
      return[button(labels.get(n.id),()=>selectNode(n.id),'text-link'),meaning,sourceCell(n.instruction_id),[n.has_opaque?'Contains unknown transfer':'',n.has_binding_gap?'Contains binding gap':'',n.has_stateful?'Contains stored-state condition':'',n.reason?human(n.reason):''].filter(Boolean).join(' · ') || 'No gap from this rule'];
    },caption));content.append(graph);
    const selected=byConditionNode.get(state.focusConditionNode);
    if(selected&&labels.has(selected.id)){
      const detail=section('Selected condition '+labels.get(selected.id),conditionNodeLabel(selected));
      detail.append(values({'Node kind':human(selected.kind),'Includes a branch join':selected.has_branch?'Yes':'No',...(conditions?.schema_version>=3?{'Contains stored-state condition':selected.has_stateful?'Yes':'No'}:{}),'Reason':selected.reason?human(selected.reason):'No gap from this rule'}));
      if(selected.instruction_id)detail.append(sourceCell(selected.instruction_id));
      if(selected.kind==='stateful_transfer')detail.append(statefulPanel(selected));
      if(instructionConditions&&['pass_through','stateful_transfer','opaque_transfer'].includes(selected.kind)&&state.detail?.type!=='transfer')detail.append(button('Inspect instruction condition transfer',()=>openDetail('transfer',selected.id),'text-link'));
      if(selected.child_ids.length)detail.append(table(['Input occurrence','Condition node','Meaning'],selected.child_ids,(id,i)=>[i+1,childLink(id),conditionNodeLabel(byConditionNode.get(id))],'Selected condition inputs'));
      if(selected.operand_ids.length)detail.append(table(['Source operand','Exact address evidence','Occurrence identity'],selected.operand_ids,id=>[sourceCell(id),addressCell(id),technical({'Operand ID':id})],'Selected condition operands'));
      detail.append(technical({'Condition node ID':selected.id,'Instruction ID':selected.instruction_id}));
      detail.tabIndex=-1;content.append(detail);detail.focus();
    }
  }
  function reusePatternDetail(p){
    setDetailHeading('OPERAND-REUSE PATTERN',fmt(p.rung_ids.length)+' rung'+(p.rung_ids.length===1?'':'s')+' with matching operand reuse',rungName(byRung.get(p.representative_rung_id)));
    content.append(reuseNotice(),values({'Rungs':p.rung_ids.length,'Address variables':p.address_variables}),rungList(p.rung_ids.map(id=>byRung.get(id))));
    const representative=panel('Representative source','Literal and expression structure are part of this grouping. Source names may differ between matching rungs.');representative.append(sourceText(byRung.get(p.representative_rung_id).text));content.append(representative);
    content.append(technical({'Pattern ID':p.id}));
  }
  function engineeringCandidates(a){return a.candidate_ids.map(id=>byRungCandidate.get(id));}
  function engineeringGroup(a){return a.identification==='identified'?'identified':a.identification==='partial'?'partial':'unclassified';}
  function engineeringGroupLabel(a){return ({identified:'Recognized functions',partial:'Possible / partial functions',unclassified:'Unclassified / unparsed'})[engineeringGroup(a)];}
  function engineeringBasis(c){return ({instruction_signature:'Instruction signature',known_mnemonic:'Mnemonic only',structural_pattern:'Structural pattern',module_root:'Module root evidence',declaration_type:'Declared type evidence',text_hint:'Text hint only'})[c.basis] || human(c.basis);}
  function engineeringReason(c){
    if(c.basis==='instruction_signature')return 'Supported '+(ENGINEERING_FAMILIES[c.category] || human(c.category)).toLowerCase()+' instruction signature.';
    if(c.basis==='known_mnemonic')return 'The mnemonic suggests this function; operand effects remain unresolved.';
    if(c.basis==='module_root')return 'A source reference resolves to an exported module root. Read/write roles remain separate.';
    if(c.basis==='declaration_type')return 'A referenced declaration has a PID data type. This suggests loop-related logic; it does not establish a PID execution.';
    if(c.basis==='text_hint')return 'A whole word in a declaration name, description or rung comment suggests this family.';
    return ({conditional_boolean_assign:'Condition blocks lead to one final Boolean assignment.',conditional_boolean_latch:'Condition blocks lead to one final Boolean latch.',conditional_boolean_unlatch:'Condition blocks lead to one final Boolean unlatch.',boolean_assign:'One Boolean assignment block.',boolean_latch:'One Boolean latch block.',boolean_unlatch:'One Boolean unlatch block.',no_supported_function_candidate:'No modeled function candidate for these blocks yet.'})[c.reason] || human(c.reason);
  }
  function engineeringMissing(code){return ({engineering_purpose_unconfirmed:'Engineering purpose is unconfirmed.',instruction_effects_not_analyzed:'Instruction effects have not been analyzed.',execution_not_simulated:'Execution has not been simulated.',channel_type_not_verified:'Channel type has not been verified.',name_or_comment_is_not_behavior:'A name or comment alone does not establish behavior.',pid_execution_not_established:'PID execution has not been established.'})[code] || human(code);}
  function engineeringShape(a){return ({series:'Series · no branch split',branched:'Multiple branch paths',empty:'Empty rung',unparsed:'Structure unavailable'})[a.structure];}
  function engineeringResult(a){return ({single_known_result:'One bound result address',multiple_known_results:'Multiple bound result addresses',no_known_result:'No known local result',stateful_or_external:'Stateful / external candidate'})[a.result_kind];}
  function engineeringFamilies(a){return [...new Set(engineeringCandidates(a).map(c=>c.category))];}
  function engineeringChoose(key,value){state[key]=value;state.listPages={};render();}
  function engineeringToolbar(){
    toolbarFor('Search rung comments, names, opcodes or function families',[
      ['all','All evidence groups'],['identified','Recognized functions'],['partial','Possible / partial functions'],['unclassified','Unclassified / unparsed']]);
    const box=toolbar.querySelector('.toolbar');
    const choice=(title,key,options)=>{
      const label=node('label','filter-wrap',title),select=node('select');select.setAttribute('aria-label',title);
      options.forEach(([value,text])=>{const option=node('option','',text);option.value=value;select.append(option);});
      select.value=state[key] || 'all';select.addEventListener('change',()=>{state[key]=select.value;state.listPages={};renderList();});label.append(select);box.append(label);
    };
    choice('Function family','engineeringFamily',[['all','All function families'],...Object.entries(ENGINEERING_FAMILIES)]);
    choice('Structure / gaps','engineeringShape',[['all','All structures / gaps'],['series','Series without branch split'],['branched','Multiple branch paths'],['empty','Empty rung'],['unparsed','Unparsed structure'],['bypass','Empty branch / bypass'],['no_result','No known local result'],['unknown','Unresolved block functions'],['comment','Missing / ambiguous comment'],['metadata','Missing rung identifiers']]);
  }
  function engineeringMatches(a){
    if(!matches(a)||(state.filter!=='all'&&engineeringGroup(a)!==state.filter))return false;
    if(state.engineeringFamily && state.engineeringFamily!=='all'&&!engineeringFamilies(a).includes(state.engineeringFamily))return false;
    const filter=state.engineeringShape || 'all';
    return filter==='all'||filter===a.structure||(filter==='bypass'&&a.empty_legs>0)||(filter==='no_result'&&a.result_kind==='no_known_result')
      ||(filter==='unknown'&&a.unknown_block_ids.length>0)||(filter==='comment'&&a.comment_status!=='present')||(filter==='metadata'&&a.missing_metadata.length>0);
  }
  function engineeringFamilyBadges(a){
    const box=node('div','engineering-labels'),candidates=engineeringCandidates(a);
    for(const family of engineeringFamilies(a)){
      const evidence=candidates.filter(c=>c.category===family);
      box.append(primary(node('span','badge',ENGINEERING_FAMILIES[family] || human(family)),[...new Set(evidence.map(engineeringBasis))].join(' · ')));
    }
    if(!candidates.length)box.append(node('span','muted','No function candidate yet'));
    return box;
  }
  function engineeringList(){
    if(fileOperations){const p=panel('Inspect file and array operations','Detailed slot and range evidence supplements the base access catalogue, including AVE, FAL and SQO.');p.append(button('Explore file and array operations',()=>go('fileoperations'),'text-link'));content.append(p);}
    if(sfrContext){const reset=panel('Inspect sequence reset candidates','Follow SFR routine and step evidence separately for every exported chart content version.');reset.append(button('Explore sequence reset context',()=>go('sfrcontext'),'text-link'));content.append(reset);}
    if(customContext&&indexedAccess){const context=panel('Inspect custom instructions and dynamic indexes','Follow declaration candidates and symbolic selectors without hiding unresolved block roles or exact-element gaps.');context.append(button('Explore instruction & index context',()=>go('instructioncontext'),'text-link'));content.append(context);}
    if(conditions){const conditional=panel('Follow conditions to coil outputs','Inspect the incoming conditions at OTE, OTL and OTU occurrences, with branch joins, bypasses and unmodeled transfers retained.');conditional.append(button('Explore conditional outputs',()=>go('conditions'),'text-link'));content.append(conditional);}
    if(instructionConditions){const transfers=panel('Follow conditions through other instructions','Inspect normal-scan condition transfer at math, copy, timer, counter and other instruction occurrences, including rungs without a coil output.');transfers.append(button('Explore instruction conditions',()=>go('transfers'),'text-link'));content.append(transfers);}
    if(bindingContext){const gaps=panel('Explain unresolved bindings','Trace unresolved operands and expression reads through source declarations, alias chains and available rack-name candidates.');gaps.append(button('Explore binding gaps & context',()=>go('bindingcontext'),'text-link'));content.append(gaps);}
    if(relationships){const connected=panel('Follow relationships between blocks','Inspect exact address readers and writers, possible local calculation reuse, and patterns that retain repeated-address structure.');connected.append(button('Explore address relationships',()=>go('relationships'),'text-link'));content.append(connected);}
    const groups=[['identified','Recognized instruction functions'],['partial','Possible / partial functions'],['unclassified','Unclassified / unparsed']];
    const cards=node('div','cards engineering-groups');
    for(const [key,title] of groups){const count=analyzedRungs.filter(a=>engineeringGroup(a)===key).length;
      const card=button('',()=>engineeringChoose('filter',key),'metric engineering-group');
      card.append(node('div','metric-label',title),node('div','metric-value',fmt(count)),node('div','metric-hint',key==='identified'?'Instruction roles or signatures recognized; purpose remains unconfirmed':key==='partial'?'Useful clues with unresolved blocks or bindings':'Includes empty rungs and unavailable syntax'));cards.append(card);
    }
    content.append(cards,node('p','panel-intro',fmt(analyzedRungs.length)+' rungs accounted for once in the groups above. Function families may overlap on a rung.'));
    const families=panel('Function families','Counts are rungs with source clues, not confirmed equipment or independent control loops. Select a family to inspect its evidence.');
    const familyGrid=node('div','engineering-families');
    for(const [key,title] of Object.entries(ENGINEERING_FAMILIES)){
      const matches=analyzedRungs.filter(a=>engineeringFamilies(a).includes(key));
      const hints=matches.filter(a=>engineeringCandidates(a).filter(c=>c.category===key).every(c=>c.basis==='text_hint')).length;
      const b=button('',()=>engineeringChoose('engineeringFamily',key),'engineering-family');
      b.append(node('strong','',title),node('span','family-count',fmt(matches.length)),node('small','',matches.length?(hints?fmt(hints)+' with text hints only':'Source evidence available'):'No candidates found'));familyGrid.append(b);
    }
    families.append(familyGrid,node('p','row-note','Alarm shutdown behavior, priorities, sensor roles and equipment identity are not yet modeled. Zero candidates do not establish absence.'));content.append(families);
    const rows=analyzedRungs.filter(engineeringMatches);
    const selection=section('Rung analysis',fmt(rows.length)+' of '+fmt(analyzedRungs.length)+' rungs match the current selection. Open a rung for the evidence, gaps and ordered blocks.');
    selection.append(table(['Rung / source comment','Function clues','Evidence group / layout','Result / gaps'],rows,a=>{
      const r=byRung.get(a.id),gaps=[];
      if(a.structure==='unparsed')gaps.push('Rung structure could not be parsed');
      if(a.unknown_block_ids.length)gaps.push(fmt(a.unknown_block_ids.length)+' base-catalogue block gaps');
      if(a.operand_ids_by_role.unknown.length)gaps.push(fmt(a.operand_ids_by_role.unknown.length)+' base-catalogue operand role gaps');
      if(fileOperationsByRung.has(a.id))gaps.push('Detailed file operation evidence available');
      if(a.access_gap_operand_ids.length+a.expression_gap_use_ids.length)gaps.push(fmt(a.access_gap_operand_ids.length+a.expression_gap_use_ids.length)+' binding / expression gaps');
      if((a.operand_ids_by_role.expression_read || []).some(id=>byOperandAccess.get(id)?.binding_status==='unsupported_expression'))gaps.push('Unsupported calculation expression');
      if(a.empty_legs)gaps.push(fmt(a.empty_legs)+' empty branch legs');
      if(a.comment_status!=='present')gaps.push(human(a.comment_status)+' comment');
      if(a.missing_metadata.length)gaps.push('Missing '+a.missing_metadata.join(', '));
      const comment=a.comment_status==='ambiguous'?'Comment is ambiguous; see source findings.':short(r.comment || 'No comment captured.',160);
      return [primary(link(rungName(r),r.id),comment),engineeringFamilyBadges(a),primary(badge(engineeringGroupLabel(a)),engineeringShape(a)),primary(engineeringResult(a),gaps.join(' · ') || 'No capture/binding gaps in this view')];
    },'Engineering rung analysis',{emptyTitle:'No rungs match these filters',emptyDetail:'Change the evidence group, function family or structure filter, or clear the search.'}));content.append(selection);
    content.append(notice('Local results and branch shape','An internal Boolean write is not automatically a physical output. Series syntax does not prove a single runtime data path; branch paths are structural. No known local result is a lead to investigate, not proof of dead or unreachable logic.'));
  }
  function engineeringEvidence(id){
    if(byFileOperation.has(id))return fileOperationLink(id);
    if(byCalculationNode.has(id)){const n=byCalculationNode.get(id);return button(n.raw_text || 'Expression node',()=>openDetail('calculation',n.instruction_id,{focusCalculationNode:id}),'text-link');}
    if(byPid.has(id))return button(pidName(byPid.get(id)),()=>openDetail('pid',id),'text-link');
    if(byCalculation.has(id))return button(calculationName(byCalculation.get(id)),()=>openDetail('calculation',id),'text-link');
    return sourceCell(id);
  }
  function engineeringIdTable(ids,caption){return table(['Source evidence',...(relationships?['Exact address dossier']:[])],ids,id=>[engineeringEvidence(id),...(relationships?[addressCell(id)]:[])],caption);}
  function engineeringOutline(r){
    const rows=[],stack=[{item:r.structure,depth:0,label:'Series'}];
    while(stack.length){
      const {item,depth,label}=stack.pop();
      if(item.kind==='instruction')rows.push({depth,id:item.instruction_id,label:byInstruction.get(item.instruction_id)?.instruction.opcode || 'Instruction'});
      else if(item.kind==='sequence'){
        rows.push({depth,label:item.items.length?label:label+' · empty / bypass'});
        for(let i=item.items.length-1;i>=0;i--)stack.push({item:item.items[i],depth:depth+1,label:''});
      }else if(item.kind==='branch'){
        rows.push({depth,label:'Branch · '+item.legs.length+' alternatives'});
        for(let i=item.legs.length-1;i>=0;i--)stack.push({item:item.legs[i],depth:depth+1,label:'Path '+(i+1)});
      }
    }
    return table(['Branch outline / source order'],rows,row=>{
      const line=node('div','engineering-outline');line.style.paddingLeft=Math.min(row.depth,12)*12+'px';
      if(row.depth>12)line.append(node('span','muted','Depth '+row.depth+' · '));
      line.append(row.id?link(row.label,row.id):node('span','',row.label));return [line];
    },'Rung branch outline');
  }
  function engineeringRungDetail(r,a){
    const summary=panel('Engineering analysis','Instruction functions and possible purpose from this snapshot. No engineering confirmation has been recorded.');
    const structureAvailable=a.structure!=='unparsed',unavailable='Unavailable: rung not parsed';
    summary.append(values({'Evidence group':engineeringGroupLabel(a),'Structure':engineeringShape(a),'Result evidence':engineeringResult(a),'Captured blocks':a.block_ids.length,'Branches / legs':structureAvailable?a.branch_count+' / '+a.branch_legs:unavailable,'Empty branch legs':structureAvailable?a.empty_legs:unavailable,'A path bypasses all blocks':structureAvailable?(a.nullable?'Yes':'No'):unavailable,'Comment':human(a.comment_status),'Missing rung identifiers':a.missing_metadata.join(', ') || 'None'}));
    const candidates=engineeringCandidates(a);
    summary.append(table(['Possible function / evidence','Why this grouping','Still unresolved'],candidates,c=>{
      const proof=node('div');proof.append(node('p','',engineeringReason(c)));
      const detail=node('details','technical');detail.append(node('summary','','Supporting evidence ('+c.evidence_ids.length+')'),engineeringIdTable(c.evidence_ids,'Candidate evidence '+c.id));proof.append(detail);
      const missing=node('div');for(const item of c.missing_evidence)missing.append(node('p','row-note',engineeringMissing(item)));
      if(!c.missing_evidence.length)missing.append(node('span','muted','No additional gap from this rule; purpose remains unconfirmed.'));
      const rule=node('details','technical');rule.append(node('summary','','Analysis rule'),values({'Rule':c.rule_id,'Version':c.rule_version,'Review status':human(c.review_status)}));missing.append(rule);
      return [primary(ENGINEERING_FAMILIES[c.category] || human(c.category),engineeringBasis(c)),proof,missing];
    },'Rung function candidates',{emptyTitle:'No function candidate yet',emptyDetail:'The rung remains in the unclassified group. Its captured source and any parsed blocks remain below.'}));content.append(summary);
    const blocks=section('Ordered block functions','Every parsed instruction appears in source order. These evidence levels belong to the base access catalogue. Specialized instruction views can supply additional roles and context.');
    blocks.append(table(['Order / instruction','Function family','Evidence level','Operand roles',...(customContext?['Declaration context']:[])],a.block_ids.map(id=>byRungBlock.get(id)),(b,n)=>[
      primary(link(b.opcode,b.id),'Block '+(n+1)),human(b.family),human(b.identification),
      b.operand_ids.map(id=>human(byOperandAccess.get(id)?.role)).join(' · ') || 'No operands',
      ...(customContext?[byCustomCall.has(b.id)?customCallLink(byCustomCall.get(b.id)):'Not an unknown-family call']:[])
    ],'Rung ordered block functions'));content.append(blocks);
    if(r.structure){const outline=node('details','technical');outline.append(node('summary','','Series and branch paths'),engineeringOutline(r));content.append(outline);}
    const uses=section('Explicit inputs and results','Operand reads and writes are possible uses. They do not establish execution, member overlap or a complete input-to-output relationship.');
    const reads=a.operand_ids_by_role.read || [],writes=a.result_operand_ids;
    const readDetail=node('details','technical');readDetail.append(node('summary','','Read operands ('+reads.length+')'),engineeringIdTable(reads,'Engineering read operands'));
    const resultDetail=node('details','technical');resultDetail.append(node('summary','','Result operands ('+writes.length+')'),engineeringIdTable(writes,'Engineering result operands'));
    const exprDetail=node('details','technical');exprDetail.append(node('summary','','Expression reads ('+a.expression_use_ids.length+')'),engineeringIdTable(a.expression_use_ids,'Engineering expression reads'));
    uses.append(readDetail,resultDetail,exprDetail);
    const rw=a.operand_ids_by_role.read_write || [];
    if(rw.length){const detail=node('details','technical');detail.append(node('summary','','Stateful read/write operands ('+rw.length+')'),engineeringIdTable(rw,'Engineering stateful operands'));uses.append(detail);}
    if(a.unknown_block_ids.length){const unknown=node('details','technical');unknown.append(node('summary','','Unresolved block functions ('+a.unknown_block_ids.length+')'),engineeringIdTable(a.unknown_block_ids,'Engineering unknown blocks'));uses.append(unknown);}
    if(a.result_kind==='no_known_result')uses.append(node('p','row-note','No known local result is an investigation candidate. This does not establish that the rung is dead, unused or unreachable.'));
    uses.append(node('p','row-note','A final lexical instruction is not necessarily a definite physical output. I/O candidates require separate module-root evidence.'));content.append(uses);
    if(conditions){const outputs=section('Conditional coil outputs in this rung','Inspect the captured incoming condition for each output occurrence. Source ordering and condition structure do not establish runtime values or an engineering purpose.');outputs.append(conditionalOutputTable(outputsByRung.get(r.id)||[],'Rung conditional outputs'));content.append(outputs);}
    if(instructionConditions){const transfers=section('Instruction condition transfers in this rung','Incoming rung conditions are retained for these occurrences whether or not a coil follows. An incoming condition is not proof of execution or a write.');transfers.append(transferTable(transfersByRung.get(r.id)||[],'Rung instruction condition transfers'));content.append(transfers);}
    if(relationships){
      const related=section('Relationships in this rung');
      const pattern=byRungReuse.get(r.id);
      if(pattern?.status==='grouped'){
        const p=byReusePattern.get(pattern.pattern_id);related.append(button('Open operand-reuse pattern ('+fmt(p.rung_ids.length)+' rungs)',()=>openDetail('reusepattern',p.id),'text-link'),reuseNotice());
      }else if(pattern)related.append(node('p','row-note','Outside operand-reuse grouping: '+human(pattern.reason)+'.'));
      related.append(localLinkNotice(),relationshipLinkTable(linksByRung.get(r.id)||[],'Rung local calculation links'));content.append(related);
    }
  }
  function rungList(rows=rungs.filter(r=>matches(r)&&(state.filter==='all'||r.parse_status===state.filter))){return table(['Rung','Routine / scope','Source preview','Parse status'],rows,r=>[link(rungNumber(r),r.id),entityPath(r.parent_id),node('div','snippet',short(r.text,180)),badge(r.parse_status)],'Ladder rungs');}
  function objectDetail(e){
    setDetailHeading('SOURCE OBJECT',e.name || '(unnamed '+human(e.kind)+')',entityPath(e.parent_id));
    if(byExecutionSource.has(e.id))content.append(button('Inspect execution context',()=>openDetail('executioncontext',byExecutionSource.get(e.id))));
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
    if(entityExpressionUses.has(e.id)){
      const expressions=section('Expression read occurrences','These individual potential reads name this declaration, resolve to it, or traverse it as an alias. Repeated reference leaves remain separate from operand-slot counts.');
      expressions.append(expressionUseTable(entityExpressionUses.get(e.id),'Object expression read occurrences'));content.append(expressions);
    }
    content.append(technical({'Source ID':e.id,'Parent ID':e.parent_id,'Scope ID':e.scope_id,'XML location':e.locator}));
  }
  function rungDetail(r){
    setDetailHeading('LADDER SOURCE',rungName(r),entityPath(r.parent_id));
    const meta=node('div','detail-meta');meta.append(badge(r.parse_status),sourceCell(r.parent_id));content.append(meta);
    if(state.focusOperand && byOperand.get(state.focusOperand)?.rung_id===r.id){
      const o=byOperand.get(state.focusOperand),a=byOperandAccess.get(o.id);
      content.append(notice('Selected operand · argument '+(o.argument_index+1),(o.raw_text || '(blank)')+' · original reference binding: '+human(o.status)+(access?' · role: '+human(accessLabel(o)):'')+(a?.binding_origin && a.binding_origin!=='source_references'?' · instruction access binding: '+human(a.binding_status):'')));
      if(byBindingContext.has(o.id))content.append(bindingContextLink(o.id));
      if(byIndexedSource.has(o.id))content.append(indexedSourceLink(o.id));
    }
    if(state.focusInstruction && byInstruction.get(state.focusInstruction)?.rung.id===r.id)content.append(notice('Selected instruction',byInstruction.get(state.focusInstruction).instruction.opcode));
    if(byExecutionInstruction.has(state.focusInstruction))content.append(button('Inspect execution context',()=>openDetail('executioncontext',byExecutionInstruction.get(state.focusInstruction))));
    if(byCustomCall.has(state.focusInstruction))content.append(customCallLink(byCustomCall.get(state.focusInstruction)));
    if(byFileOperation.has(state.focusInstruction))content.append(fileOperationLink(state.focusInstruction));
    const text=panel('Rung text','Exact captured ladder source. No execution behavior is inferred.');text.append(sourceText(r.text));content.append(text);
    if(r.comment !== null){const p=panel('Rung comment');p.append(sourceText(r.comment,true));content.append(p);}
    if(byRungAnalysis.has(r.id))engineeringRungDetail(r,byRungAnalysis.get(r.id));
    if(fileOperationsByRung.has(r.id)){const p=section('File and array operations on this rung','Open an occurrence for its documented slots, starting addresses and range limitations.');p.append(fileOperationTable(fileOperationsByRung.get(r.id),'Rung file operations'));content.append(p);}
    if(sfrCallsByRung.has(r.id)){const reset=section('SFR target context on this rung','Candidate matches do not establish reset execution or outgoing condition.');reset.append(sfrCallTable(sfrCallsByRung.get(r.id),'Rung SFR target contexts'));content.append(reset);}
    if(indexedByRung.has(r.id)){const indexed=section('Indexed source context on this rung','Array roots and possible selector reads stay separate from exact-address relationships.');indexed.append(indexedUseTable(indexedByRung.get(r.id),'Rung indexed source context'));content.append(indexed);}
    const inst=section('Parsed instructions');inst.append(table(['Order','Opcode','Arguments','Semantic status',...(access?['Operand-role coverage']:[])],r.instructions || [],(i,n)=>[String(n+1),node('span','mono',i.opcode),node('div','snippet',(i.arguments||[]).join(', ')),human(i.semantic_status),...(access?[badge(byInstructionAccess.get(i.id)?.status)]:[])],'Parsed rung instructions'));content.append(inst);
    if(statefulOccurrencesByRung.has(r.id)){const p=section('Timer, counter and reset evidence on this rung');p.append(statefulOccurrenceTable(statefulOccurrencesByRung.get(r.id),'Rung timer counter and reset occurrences'));content.append(p);}
    if(rungPids.has(r.id)){const p=section('PID evidence on this rung');p.append(pidTable(rungPids.get(r.id),'Rung PID occurrences'));content.append(p);}
    if(rungCalculations.has(r.id)){const p=section('Calculations on this rung');p.append(calculationTable(rungCalculations.get(r.id),'Rung calculation occurrences'));content.append(p);}
    if(calculationPaths){const paths=calculationPathOccurrences.filter(c=>c.rung_id===r.id);if(paths.length){const p=section('Calculation inputs and destinations on this rung');p.append(calculationPathTable(paths,'Rung calculation blocks'));content.append(p);}}
    const ops=section(access?.schema_version>=3?'Original reference bindings':'Operand bindings','Root resolution is source evidence only. A binding does not validate a member, array bound, data type or instruction effect.'+(access?.schema_version>=3?' These rows retain the original reference analysis; additional instruction access bindings appear separately below.':''));
    if((rungOperands.get(r.id)||[]).some(o=>byOperandAccess.get(o.id)?.reason==='timer_pseudo_operand'))ops.append(node('p','row-note','Timer preset and accumulator fields describe initialization, not separate runtime reads. A question mark supplies no value here. Timer values, units and configuration are not validated.'));
    ops.append(table(['Operand','Instruction / argument','Binding','Declared / resolved root',...(access?['Operand role']:[])],rungOperands.get(r.id)||[],o=>[node('span','mono',o.raw_text || '(blank)'),(byInstruction.get(o.instruction_id)?.instruction.opcode||'Instruction')+' · '+(o.argument_index+1),primary(badge(o.status),o.reason?human(o.reason):''),bindingRoots(o,o.reason),...(access?[accessCell(o)]:[])],'Rung operand bindings'));content.append(ops);
    if(rungAccessBindings.has(r.id)){
      const extra=section('Instruction access bindings','These bindings use supported instruction operand roles. Selector text is not a tag reference, even if a declaration has the same name. The original reference findings are preserved above.');
      extra.append(accessBindingTable(rungAccessBindings.get(r.id),'Rung instruction access bindings'));content.append(extra);
    }
    if(rungExpressionUses.has(r.id)){
      const expressions=section('Expression read occurrences','Each captured reference leaf is a potential read, separate from its containing expression operand.');
      expressions.append(expressionUseTable(rungExpressionUses.get(r.id),'Rung expression read occurrences'));content.append(expressions);
    }
    const pattern=routinePatterns.get(r.id);if(pattern)content.append(button('Open syntax pattern · '+fmt(pattern.count)+' occurrences',()=>openDetail('pattern',pattern.id)));
    const structure=node('details','technical');structure.append(node('summary','','Parsed branch structure'),sourceText(JSON.stringify(r.structure,null,2)));content.append(structure,technical({'Source ID':r.id,'Routine ID':r.parent_id,'Scope ID':r.scope_id,'XML location':r.locator}));
  }
  function sequenceConditionName(t){return elementName(byElement.get(t.transition_id));}
  function sequenceConditionStatus(t){return ({modeled:'Syntax modeled',binding_gaps:'Reference binding gaps',unsupported:'Unmodeled condition'})[t.status]||human(t.status);}
  function sequenceConditionNotice(){return notice('Source expressions, not evaluated transitions','Syntax grouping and bound roots describe this export. They do not prove Boolean data types, valid members, current values, transition truth, execution order, active edits or process intent. Unsupported source fragments remain accessible through their original SFC links; no partial expression tree is inferred.');}
  function sequenceConditionGaps(t){return t.status!=='modeled'||(t.metadata_gaps||[]).length>0||t.reference_ids.some(id=>bySequenceContextReference.get(id)?.gap_id);}
  function sequenceConditionTable(rows,caption){return table(['Transition','Captured condition','Analysis','References','Content version'],rows,t=>[
    primary(button(sequenceConditionName(t),()=>openDetail('sequencecondition',t.id),'text-link'),entityPath(t.routine_id)),
    node('div','snippet',short(t.raw_text,180)||'(Expression unavailable; inspect source)'),
    primary(sequenceConditionStatus(t),[t.reason&&t.reason!=='none'?human(t.reason):'',...(t.metadata_gaps||[]).map(human),t.status==='modeled'&&t.reference_ids.some(id=>bySequenceContextReference.get(id)?.gap_id)?'Reference relationship diagnostic':''].filter(Boolean).join(' · ')||'Type and runtime interpretation remain unverified'),
    t.reference_ids.length,human(t.edit_kind)
  ],caption,{emptyTitle:'No transition conditions match',emptyDetail:'Clear the search or select another analysis status. Source and type limitations remain visible in each condition.'});}
  function sequenceConditionsList(){
    content.append(sequenceConditionNotice());
    const summary=panel('Transition expression coverage');summary.append(values({'Captured transitions':sequenceConditions.length,'Syntax modeled':sequenceConditions.filter(t=>t.status==='modeled').length,'Reference binding gaps':sequenceConditions.filter(t=>t.status==='binding_gaps').length,'Unmodeled conditions':sequenceConditions.filter(t=>t.status==='unsupported').length,'Conditions with capture metadata gaps':sequenceConditions.filter(t=>(t.metadata_gaps||[]).length).length,'Other SFC text lines outside this analysis':sfcConditions.coverage.unprocessed_st_lines}));content.append(summary);
    if(sequenceContext){const contextSummary=panel('Reference relationships');contextSummary.append(values({'Reference occurrences':sequenceContext.references.length,'Qualified exact addresses':sequenceContext.addresses.length,'Binding diagnostics':sequenceContext.gaps.length,'Step candidate associations':sequenceContext.step_links.length}));content.append(contextSummary);}
    const rows=sequenceConditions.filter(t=>matches(t)&&(state.filter==='all'||(state.filter==='gap'?sequenceConditionGaps(t):state.filter==='context_gap'?t.reference_ids.some(id=>bySequenceContextReference.get(id)?.gap_id):t.status===state.filter)));
    content.append(sequenceConditionTable(rows,'Sequence transition conditions'));
  }
  function sequenceConditionDetail(t){
    setDetailHeading('SEQUENCE CONDITION',sequenceConditionName(t),entityPath(t.routine_id));content.append(sequenceConditionNotice());
    const summary=panel('Captured transition expression');summary.append(values({'Analysis':sequenceConditionStatus(t),'Reason':t.reason&&t.reason!=='none'?human(t.reason):'No syntax rejection','Error character offset':t.error_offset??'None','Content version':human(t.edit_kind),'Capture metadata gaps':(t.metadata_gaps||[]).map(human).join(' · ')||'None reported','Type validation':'Not implemented','Runtime evaluation':'Not implemented'}));
    const links=node('div','inline-links');links.append(sourceCell(t.transition_id),sourceCell(t.routine_id),sourceCell(t.content_id));if(t.condition_id)links.append(sourceCell(t.condition_id));if(t.st_content_id)links.append(sourceCell(t.st_content_id));summary.append(links);content.append(summary);
    const raw=section('Condition source text','Lines remain in captured XML order. Character spans address this joined text; source links retain each original fragment.');raw.append(sourceText(t.raw_text||'No joined expression is available for this source shape. Follow the original condition or transition links above.'));raw.append(table(['Source line','Captured line number','Text'],t.line_ids.map(id=>byElement.get(id)).filter(Boolean),line=>[sourceCell(line.id),line.attributes?.Number??'Not supplied',sourceText(line.direct_text)],'Transition source lines',{emptyTitle:'No source lines captured',emptyDetail:'Inspect the condition and transition source elements for missing, direct or unsupported text.'}));content.append(raw);
    const comments=section('Source comments','Comments are authored evidence. They are not treated as executable expressions or confirmed engineering descriptions.');comments.append(table(['Comment kind','Character span','Exact comment'],t.comment_ids.map(id=>bySequenceComment.get(id)).filter(Boolean),c=>[human(c.kind),c.start+'–'+c.end,primary(sourceText(c.raw_text),c.terminated?'':'Unterminated comment')],'Transition expression comments',{emptyTitle:'No expression comments captured',emptyDetail:'Other notes may appear on the original SFC elements.'}));content.append(comments);
    const nodes=t.node_ids.map(id=>bySequenceNode.get(id)).filter(Boolean),labels=new Map(nodes.map((n,i)=>[n.id,'Node '+(i+1)]));
    const tree=section('Expression grouping','Source operators and child order are preserved. A modeled tree is not proof of Boolean type or a true transition.');
    let chosen=nodes.find(n=>n.id===state.focusSequenceNode)||bySequenceNode.get(t.root_node_id);const detail=node('div');
    const showNode=n=>{chosen=n;state.focusSequenceNode=n.id;detail.replaceChildren();const box=panel(labels.get(n.id)+(n.id===t.root_node_id?' · expression root':''));box.append(values({'Kind':human(n.kind),'Source operator':n.operator||'Not an operator','Character span':n.start+'–'+n.end}),sourceText(t.raw_text.slice(n.start,n.end)));const childLinks=node('div','inline-links');n.children.forEach(id=>{const child=bySequenceNode.get(id);if(child)childLinks.append(button(labels.get(id),()=>showNode(child),'text-link'));});box.append(childLinks);const ref=bySequenceReference.get(n.binding_id);if(ref)box.append(primary(human(ref.binding_status),'Source root binding'),calculationBinding(ref.binding));detail.append(box);};
    tree.append(table(['Node','Syntax kind','Source operator / spelling','Children','Span'],nodes,n=>[button(labels.get(n.id)+(n.id===t.root_node_id?' · root':''),()=>showNode(n),'text-link'),human(n.kind),node('span','mono',n.operator||short(n.raw_text,160)),n.children.map(id=>labels.get(id)).join(', ')||'Leaf',n.start+'–'+n.end],'Transition expression nodes',{emptyTitle:'Expression tree unavailable',emptyDetail:'The complete source expression was not accepted by this analysis; no partial tree is presented.'}));if(chosen)showNode(chosen);tree.append(detail);content.append(tree);
    const references=section('Reference leaves','These are possible source reads in a fully parsed expression. Root binding does not validate suffix members, data types or array bounds.');references.append(table(['Reference spelling','Root binding','Declared / resolved root','Suffix','Span'],t.reference_ids.map(id=>bySequenceReference.get(id)).filter(Boolean),r=>[button(r.raw_text,()=>{const n=bySequenceNode.get(r.node_id);if(n){showNode(n);detail.scrollIntoView({block:'nearest'});}},'text-link'),primary(human(r.binding_status),r.binding?.reason?human(r.binding.reason):''),calculationBinding(r.binding),node('span','mono',r.binding?.suffix||'(root)'),r.start+'–'+r.end],'Transition expression references',{emptyTitle:'No reference leaves captured',emptyDetail:t.status==='unsupported'?'Unsupported conditions publish no partial reference bindings.':'A literal-only expression has no reference leaves.'}));content.append(references);
    if(sequenceContext){
      const contextSection=section('Ladder and chart relationships','Open a reference to inspect qualified ladder readers and writers, chart-step candidates and binding diagnostics. These associations do not establish execution or a transition value.');
      contextSection.append(table(['Reference','Context','Exact address','Step candidates','Diagnostic'],t.reference_ids.map(id=>bySequenceContextReference.get(id)).filter(Boolean),r=>{
        const a=bySequenceAddress.get(r.address_id),g=bySequenceGap.get(r.gap_id);
        return [sequenceContextLink(r),human(r.status),a?sequenceAddressLink(a):'No qualified address',r.step_link_ids.length,g?human(g.kind):'No binding diagnostic'];
      },'Transition reference relationships'));content.append(contextSection);
      const chartLinks=section('Direct chart connections','These are captured diagram links incident to this transition. They do not select an active edit or prove sequence execution.');chartLinks.append(relationTable(elementLinks.get(t.transition_id)||[]));content.append(chartLinks);
      const notes=section('Attached chart notes','Attachments describe source ownership only. Follow a text-box link to read its authored text.');notes.append(relationTable(elementNotes.get(t.transition_id)||[],true));content.append(notes);
    }
  }
  function sequenceContextNotice(){return notice('Source associations with explicit limits','Exact address spelling connects qualified source uses. Step operands provide lexical candidates; no STEP type, member validity, active edit, runtime writer order or transition truth is inferred. Missing captured writers do not prove an uninitialized or unused value.');}
  function sequenceContextLink(r){return button(bySequenceReference.get(r.condition_reference_id)?.raw_text||'Reference',()=>openDetail('sequencecontext',r.id),'text-link');}
  function sequenceAddressLink(a){return button(addressName(a),()=>openDetail('sequenceaddress',a.id),'text-link');}
  function sequenceStepTable(rows){return table(['Step source','Relationship to this condition','Match evidence','Operand spelling','Source qualification'],rows,l=>[
    primary(sourceCell(l.step_element_id),entityPath(l.step_routine_id)+' · '+human(byContent.get(l.step_content_id)?.edit_kind||'absent')),human(l.relation),primary(human(l.match_kind),human(l.evidence)),node('span','mono',byElement.get(l.step_element_id)?.attributes?.Operand||'(missing operand)'),primary(human(l.step_binding_status),l.namespace_qualified?'Namespace qualified':'Unsupported namespace context')
  ],'Sequence step candidates',{emptyTitle:'No step candidates captured',emptyDetail:'The reference remains visible even when no qualified or lexical chart-step candidate was found.'});}
  function sequenceContextDetail(r){
    const original=bySequenceReference.get(r.condition_reference_id),transition=bySequenceCondition.get(r.transition_id),a=bySequenceAddress.get(r.address_id),g=bySequenceGap.get(r.gap_id);
    setDetailHeading('SEQUENCE REFERENCE CONTEXT',original?.raw_text||'Reference',entityPath(r.routine_id));content.append(sequenceContextNotice());
    const summary=panel('Reference source');summary.append(values({'Context qualification':human(r.status),'Original root binding':human(r.binding_status),'Content version':human(r.edit_kind)}));const sourceLinks=node('div','inline-links');if(transition)sourceLinks.append(button('Open transition: '+sequenceConditionName(transition),()=>openDetail('sequencecondition',transition.id),'text-link'));sourceLinks.append(sourceCell(r.content_id));summary.append(sourceLinks);if(original)summary.append(calculationBinding(original.binding));if(a)summary.append(sequenceAddressLink(a));content.append(summary);
    if(g){const gap=section('Binding diagnostic','Candidate names from another scope or a chart operand remain hints. They do not repair the original binding. TRUE/FALSE spellings, when reported, are lexical observations only.');gap.append(values({'Diagnostic':human(g.kind),'Lexical category':human(g.lexical_kind),'Lookup root':g.root_text||'(unavailable)'}),sourceCell(g.lookup_scope_id));
      for(const [field,label] of [['outside_scope_entity_ids','Same-name declarations outside lookup scope'],['unqualified_outside_scope_entity_ids','Unqualified same-name declarations outside lookup scope']])if(g[field].length){const p=panel(label);p.append(table(['Declaration candidate'],g[field],id=>[sourceCell(id)],label));gap.append(p);}content.append(gap);}
    const steps=section('Chart-step candidates','Each association retains the candidate content and routine. Same-content, other-edit and peer-chart candidates are kept separate; none selects an effective step.');steps.append(sequenceStepTable(r.step_link_ids.map(id=>bySequenceStepLink.get(id)).filter(Boolean)));content.append(steps);
    if(a)sequenceAddressSections(a);
  }
  function sequenceAddressSections(a){
    const writers=new Set([...a.write_operand_ids,...a.read_write_operand_ids].map(id=>byOperandAccess.get(id)?.instruction_id).filter(Boolean));
    const summary=panel('Qualified exact address uses');summary.append(values({'Root declaration':entityName(a.target_id),'Exact suffix':a.suffix||'(root)','Transition reference occurrences':a.condition_reference_ids.length,'Distinct captured writer instructions':writers.size,'Operand reads':a.read_operand_ids.length,'Operand writes':a.write_operand_ids.length,'Read/write operands':a.read_write_operand_ids.length,'Unknown-role operands':a.unknown_operand_ids.length,'Expression reads':a.expression_use_ids.length}),sourceCell(a.target_id));
    if(a.relationship_address_id)summary.append(button('Open original RLL relationship evidence',()=>openDetail('address',a.relationship_address_id),'text-link'));content.append(summary);
    if(!writers.size)content.append(notice('No qualified explicit RLL writer captured','Other source forms, implicit instruction effects, communications or uncaptured code may supply this value. This count does not establish an uninitialized value or dead logic.'));
    const users=section('Sequence references sharing this address');users.append(table(['Reference','Transition','Content version'],a.condition_reference_ids.map(id=>bySequenceContextReference.get(id)).filter(Boolean),r=>[sequenceContextLink(r),button(sequenceConditionName(bySequenceCondition.get(r.transition_id)),()=>openDetail('sequencecondition',r.transition_id),'text-link'),human(r.edit_kind)],'Sequence address references'));content.append(users);
    for(const [field,title] of [['read_operand_ids','Qualified ladder readers'],['write_operand_ids','Qualified ladder writers'],['read_write_operand_ids','Qualified ladder read/write uses'],['unknown_operand_ids','Ladder uses with unknown roles']])if(a[field].length){const p=section(title);p.append(accessBindingTable(a[field].map(id=>byOperandAccess.get(id)).filter(Boolean),title));content.append(p);}
    const rejected=Object.values(a.unqualified_operand_ids_by_role).flat();if(rejected.length){const p=section('Ladder uses excluded by namespace qualification','These source occurrences remain available but do not contribute to the qualified reader or writer counts.');p.append(accessBindingTable(rejected.map(id=>byOperandAccess.get(id)).filter(Boolean),'Excluded sequence address uses'));content.append(p);}
    for(const [field,title] of [['expression_use_ids','Qualified ladder expression readers'],['unqualified_expression_use_ids','Excluded ladder expression readers']])if(a[field].length){const p=section(title);p.append(expressionUseTable(a[field].map(id=>byExpressionUse.get(id)).filter(Boolean),title));content.append(p);}
  }
  function sequenceAddressDetail(a){setDetailHeading('SEQUENCE EXACT ADDRESS',addressName(a),'Transition references and captured ladder uses');content.append(sequenceContextNotice());sequenceAddressSections(a);}
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
    if(sfcConditions){const parsed=section('Transition condition analysis','Syntax evidence is kept separate for every captured content version.');parsed.append(sequenceConditionTable(sequenceConditions.filter(t=>t.content_id===selected.id),'SFC content transition conditions'));content.append(parsed);}
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
    if(bySequenceTransition.has(e.id))content.append(button('Inspect transition expression',()=>openDetail('sequencecondition',bySequenceTransition.get(e.id).id),'text-link'));
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
  function pidConnectionNotice(){return notice('Observed source connections','Counts describe captured operand and expression uses at one exact expanded address spelling. They do not establish runtime data flow, scan order, execution, an active cascade or independent engineering loops. Unknown roles and namespace gaps remain separate; zero observed writers or readers does not prove an unused or uninitialized value.');}
  function pidConnectionAddressLink(id){const a=byAddress.get(id);return a?button(addressName(a),()=>openDetail('pidaddress',id),'text-link'):node('span','muted','No exact address association');}
  function pidConnectionCounts(a){return a?['read_operand_ids','write_operand_ids','read_write_operand_ids','unknown_operand_ids','expression_use_ids'].map(key=>fmt(a[key].length)):[0,0,0,0,0];}
  function pidConnectionAddressTable(ids,caption){return table(['Exact address','Member / association','Operand reads','Writes','Read/write','Unknown roles','Expression reads'],ids.map(id=>byPidConnectionAddress.get(id)).filter(Boolean),a=>[
    pidConnectionAddressLink(a.id),primary(a.field?pidMemberLabel(a.field):human(a.kind),a.field || ''),...pidConnectionCounts(a)
  ],caption);}
  function pidConnectionSections(p){
    const c=byPidConnection.get(p.id);if(!c)return;
    content.append(pidConnectionNotice());
    const slots=section('Slot connections and observed usage','PV, CV, tieback, master and inhold are instruction positions. Setpoint uses appear below under the SP member. A linked address retains all its captured uses, including multiple writers.');
    slots.append(table(['Operand function','Source operand','Identity evidence','Exact address','Operand reads','Writes','Read/write','Unknown roles','Expression reads'],c.slot_ids.map(id=>byPidConnectionSlot.get(id)).filter(Boolean),s=>[
      pidSlotLabel(s.slot),sourceCell(s.id),human(s.status),pidConnectionAddressLink(s.address_id),...pidConnectionCounts(byPidConnectionAddress.get(s.address_id))
    ],'PID slot connections'));content.append(slots);
    const members=section('Member connections by function','Direct member spelling associates an observed address with this PID declaration. Saved headers remain separate evidence; a matching spelling does not validate a member value, type or effective configuration.');
    members.append(values({'Control declaration association':human(c.control_status)}));
    if(c.control_owner_id)members.append(sourceCell(c.control_owner_id));
    const rows=Object.entries(c.member_address_ids_by_group).filter(([group])=>group!=='unknown').flatMap(([group,ids])=>ids.map(id=>({group,a:byPidConnectionAddress.get(id)}))).filter(x=>x.a);
    members.append(table(['Function group','Member / label','Exact address','Operand reads','Writes','Read/write','Unknown roles','Expression reads'],rows,({group,a})=>[
      human(group),primary(a.field,pidMemberLabel(a.field)),pidConnectionAddressLink(a.id),...pidConnectionCounts(a)
    ],'PID member connections',{emptyTitle:'No direct member addresses associated',emptyDetail:'This only describes captured source references; missing observations do not establish unused members.'}));
    for(const [key,title,detail] of [
      ['whole_owner_address_ids','Whole-declaration uses','Whole-structure uses remain separate from direct member evidence.'],
      ['deferred_address_ids','Deferred suffix uses','Nested members, element indices and bit suffixes retain exact spelling but are not promoted to direct member connections.'],
      ['unknown_member_address_ids','Uncatalogued member spelling','These exact addresses have a direct member spelling outside the documented PID member catalogue.']
    ])if(c[key].length){const extra=section(title,detail);extra.append(pidConnectionAddressTable(c[key],'PID '+title.toLocaleLowerCase()));members.append(extra);}
    content.append(members);
    const master=section('Explicit master operand candidates','Only the explicit master slot supplies this association. Candidate occurrences share an exact declaration identity; repeated occurrences, missing occurrences and self-reference remain visible. No active cascade is inferred.');
    master.append(values({'Candidate status':human(c.master.status),'Self-reference':c.master.self_reference?'Yes':'No','Candidate occurrences':c.master.occurrence_ids.length}));
    const masterLinks=node('div','inline-links');
    if(c.master.operand_id)masterLinks.append(sourceCell(c.master.operand_id));
    if(c.master.owner_id)masterLinks.append(sourceCell(c.master.owner_id));
    master.append(masterLinks);
    master.append(pidTable(c.master.occurrence_ids.map(id=>byPid.get(id)).filter(Boolean),'PID explicit master candidates'));content.append(master);
    const incoming=section('Incoming condition evidence','These links reuse the captured condition nodes immediately before this PID occurrence. They are context evidence, not a PID execution guard; outgoing PID condition behavior remains unmodeled.');
    const transfer=transferByInstruction.get(p.id);
    incoming.append(table(['Incoming source condition','Condition evidence','Source rung'],c.incoming_condition_ids,id=>{
      const n=byConditionNode.get(id);return [transfer?button(conditionNodeLabel(n),()=>openDetail('transfer',transfer.id,{focusConditionNode:id}),'text-link'):sourceCell(n?.instruction_id),conditionGuardLabel(conditionQuality(n)),sourceCell(p.rung_id)];
    },'PID incoming conditions',{emptyTitle:'No incoming condition context captured',emptyDetail:'The absence of a link does not establish unconditional execution.'}));content.append(incoming);
  }
  function pidConnectionAddressDetail(a){
    const exact=byAddress.get(a.id);
    setDetailHeading('PID CONNECTION EVIDENCE',addressName(exact),human(a.kind));
    content.append(pidConnectionNotice());
    const summary=panel('Observed exact-address usage','Accepted uses and namespace gaps are counted separately. A namespace gap is retained evidence, not an association to the PID declaration.');
    summary.append(values({'Declaration':addressRootPreview(a.owner_id),'Expanded suffix':exact.suffix || '(root address)','Member':a.field || 'No direct catalogued member','Group':a.group?human(a.group):'No direct member group','Saved member headers':a.member_ids.length,'Namespace operand gaps':a.namespace_gap_operand_ids.length,'Namespace expression gaps':a.namespace_gap_expression_use_ids.length}));
    const links=node('div','inline-links');links.append(sourceCell(a.owner_id),button('Open complete exact address dossier',()=>openDetail('address',a.id),'text-link'));summary.append(links);content.append(summary);
    for(const role of accessRoles){const ids=a[role+'_operand_ids'];if(!ids.length)continue;
      const uses=section(({read:'Observed operand readers',write:'Observed operand writers',read_write:'Observed read/write uses',unknown:'Observed uses with unknown roles'})[role]);
      uses.append(table(['Source operand','Rung','Instruction / argument','Role'],ids,id=>{const use=byOperandAccess.get(id);return[sourceCell(id),sourceCell(use.rung_id),sourceName(use.instruction_id)+' / '+(use.argument_index+1),accessCell(use)];},'PID connection '+role+' occurrences'));content.append(uses);
    }
    if(a.expression_use_ids.length){const uses=section('Observed expression readers');uses.append(expressionUseTable(a.expression_use_ids.map(id=>byExpressionUse.get(id)),'PID connection expression reads'));content.append(uses);}
    if(a.member_ids.length){const headers=section('Saved direct member headers','Each stored representation and duplicate header remains separate. These are exported values, not effective settings.');headers.append(table(['Member evidence'],a.member_ids,id=>[sourceCell(id)],'PID connection saved member headers'));content.append(headers);}
    if(a.namespace_gap_operand_ids.length){const gaps=section('Namespace gaps in operand uses','These observations are excluded from the accepted PID connection counts above.');gaps.append(table(['Source operand','Rung'],a.namespace_gap_operand_ids,id=>[sourceCell(id),sourceCell(byOperandAccess.get(id)?.rung_id)],'PID connection namespace operand gaps'));content.append(gaps);}
    if(a.namespace_gap_expression_use_ids.length){const gaps=section('Namespace gaps in expression uses','These observations are excluded from the accepted PID connection counts above.');gaps.append(expressionUseTable(a.namespace_gap_expression_use_ids.map(id=>byExpressionUse.get(id)),'PID connection namespace expression gaps'));content.append(gaps);}
  }
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
    if(pidConnections){const c=pidConnections.coverage,connections=panel('Observed PID connections','Open an occurrence for slot usage, grouped member addresses, explicit master candidates and incoming condition evidence.');connections.append(values({'Exact addresses':c.addresses_total,'Slot observations':c.slots_total,'Direct member addresses':c.address_kinds.direct_member,'Master candidate links':c.master_candidate_links,'Occurrences with incoming context':c.occurrences_with_condition_context}));content.append(connections,pidConnectionNotice());}
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
      if(relationships){const exact=node('div','cell-sub');exact.append(addressCell(o.id));root.append(exact);}
      return[primary(String(e.argument_index+1),pidSlotLabel(e.slot)),link(o.raw_text,o.id),badge(o.status),root];
    },'PID operand functions'));content.append(args);
    if(pidConnections)pidConnectionSections(p);
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
  const FILE_PURPOSES={COP:'Copy a span of data',CPS:'Synchronous copy of a span',AVE:'Average an array region',FAL:'Apply an expression across iterations',SQO:'Select and mask a sequence output'};
  const FILE_RANGES={
    COP:'The length describes destination elements. Starting addresses alone do not identify every affected source or destination member.',
    CPS:'The length describes destination elements. This source record does not simulate copy synchronization or identify every affected member.',
    AVE:'The array start, dimension and control fields describe the selected region. The parser does not compute the average or expand its bounds.',
    FAL:'Mode, control position, expression and destination selectors describe the iteration. Symbolic selectors remain symbolic; no iteration is executed.',
    SQO:'The control position selects array data. The mask selects replacement bits; other destination bits are retained. No mask or output value is evaluated.'
  };
  function fileOperationName(o){return o.opcode+' · '+short(byFileSlot.get(o.destination_slot_id)?.raw_text||'(destination unresolved)',100);}
  function fileOperationLink(id){const o=byFileOperation.get(id);return o?button(fileOperationName(o),()=>openDetail('fileoperation',id),'text-link'):sourceCell(id);}
  function fileOperationGap(o){return o.signature_status!=='recognized'||o.qualification!=='qualified'||o.context_status!=='modeled'||['unsupported','signature_unresolved','namespace_gap'].includes(o.expression_status)||o.slot_ids.some(id=>!['exact_address','literal','non_data','parsed_expression','symbolic_address'].includes(byFileSlot.get(id)?.status))||(fileNodesByInstruction.get(o.id)||[]).some(n=>n.kind==='reference'&&!['exact_address','symbolic_address','literal'].includes(n.status))||(fileIndexesByInstruction.get(o.id)||[]).some(u=>u.status!=='parsed'||['unbound','invalid_identity','namespace_gap'].includes(u.root_status)||u.index_reads.some(r=>!['exact_address','literal'].includes(r.status)))||(fileControlsByInstruction.get(o.id)||[]).some(c=>fileControlGaps.has(c.id));}
  function fileOperationTable(rows,caption){return table(['Operation / destination','Purpose','Signature / qualification','Source rung'],rows,o=>[
    fileOperationLink(o.id),FILE_PURPOSES[o.opcode]||human(o.span_kind),primary(human(o.signature_status),human(o.qualification)),sourceCell(o.rung_id)
  ],caption,{emptyTitle:'No file operations match',emptyDetail:'This view covers COP, CPS, AVE, FAL and SQO. Search or filter by operation, source text or evidence gaps.'});}
  function fileOperationList(){
    const p=panel('File operation evidence','Each source occurrence remains separate, including invalid signatures and unresolved slots. Array ranges and current values remain unevaluated.');
    p.append(values({'Operations':fileOccurrences.length,'Source slots':byFileSlot.size,'Expression nodes':fileOperations.expression_nodes.length,'Control addresses':fileOperations.controls.length}),node('p','row-note','The base access catalogue remains available. Detailed roles here supplement its unknown slots.'));
    content.append(p,fileOperationTable(fileOccurrences.filter(o=>matches(o)&&(state.filter==='all'||state.filter===o.opcode||(state.filter==='gaps'&&fileOperationGap(o)))),'File operation occurrences'));
  }
  function fileBindingCell(binding,status){
    const box=node('div');box.append(node('span','',human(status||binding?.status||'unavailable')));
    if(binding?.target_id&&['exact_address','root_bound'].includes(status))box.append(node('span','',' · '),sourceCell(binding.target_id),node('span','muted',binding.suffix||' (root)'));
    return box;
  }
  function fileOperationDetail(o){
    setDetailHeading('FILE AND ARRAY OPERATION',fileOperationName(o),sourceName(o.rung_id));
    const p=panel(FILE_PURPOSES[o.opcode]||o.opcode,FILE_RANGES[o.opcode]||'Captured file operation context.');
    p.append(values({'Signature':human(o.signature_status),'Source qualification':human(o.qualification),'Incoming condition':human(o.context_status),'Expression':human(o.expression_status)}));
    const links=node('div','inline-links');links.append(sourceCell(o.id),sourceCell(o.rung_id));if(o.routine_id)links.append(sourceCell(o.routine_id));p.append(links);content.append(p);
    const provenance=panel('Source content and edit context','Each exported content container stays separate; no active edit is selected.');
    provenance.append(values({'Content location':o.content_locator,'Rung location':o.rung_locator}));
    if(o.content_attributes)provenance.append(table(['Source attribute','Captured value'],Object.entries(o.content_attributes),([key,value])=>[key,String(value)],'File operation content attributes'));
    content.append(provenance);
    const slots=section('Documented operand slots','Length and position pseudo-fields belong to stored control initialization. They are not ordinary runtime input reads. A starting address does not establish the full accessed range.');
    slots.append(table(['Slot / source','Meaning','Possible role','Binding / qualification','Selector form'],o.slot_ids.map(id=>byFileSlot.get(id)),s=>[
      primary(sourceCell(s.id),'Argument '+(s.position+1)),human(s.kind),human(s.role),fileBindingCell(s.binding,s.status),human(s.selector_kind)
    ],'File operation slots'));content.append(slots);
    const nodes=fileNodesByInstruction.get(o.id)||[];
    if(o.opcode==='FAL'){
      const expression=section('File arithmetic expression','Expression structure and reference leaves are retained without evaluating values or expanding iterations. Unsupported expressions expose a gap instead of a partial result.');
      if(o.error_code)expression.append(values({'Expression gap':human(o.error_code),'Character offset':o.error_offset}));
      const labels=new Map(nodes.map((n,i)=>[n.id,'E'+(i+1)]));
      expression.append(table(['Node','Kind / operator','Source value or reference','Binding','Inputs'],nodes,n=>[
        labels.get(n.id),human(n.kind)+(n.operator?' · '+n.operator:''),n.raw_text?sourceText(n.raw_text):'—',n.binding?fileBindingCell(n.binding,n.status):'Not a reference',(n.child_ids||[]).map(id=>labels.get(id)||'Unavailable').join(', ')||'Leaf'
      ],'File arithmetic expression nodes',{emptyTitle:'No parsed expression nodes',emptyDetail:o.expression_status==='parsed'?'The parsed expression has no retained nodes.':'Inspect the expression slot and its recorded gap.'}));content.append(expression);
    }
    const indexes=fileIndexesByInstruction.get(o.id)||[];
    if(indexes.length){const p=section('Symbolic index selectors','Index references identify inputs used to choose an element. The root is kept separate from the unresolved exact element; no current index is substituted.');
      for(const u of indexes){const source=u.source_kind==='slot'?byFileSlot.get(u.source_id):byFileNode.get(u.source_id),raw=source?.raw_text||'',box=panel(short(raw,160));
        box.append(values({'Selector parsing':human(u.status),'Possible role':human(u.role)}),fileBindingCell(u.root_binding,u.root_status));
        if(u.selectors.length)box.append(table(['Selector source','Kind'],u.selectors,s=>[sourceText(raw.slice(s.start,s.end)),s.dynamic?'Symbolic':'Static'],'File index selectors '+u.id));
        if(u.index_reads.length)box.append(table(['Index input','Binding / qualification'],u.index_reads,r=>[sourceText(raw.slice(r.start,r.end)),fileBindingCell(r.binding,r.status)],'File index reads '+u.id));
        p.append(box);
      }content.append(p);
    }
    const controls=fileControlsByInstruction.get(o.id)||[];
    if(controls.length){const control=section('Control declaration and stored representations','Stored data is source evidence. Multiple exported representations remain separate; no runtime or effective value is selected.');
      for(const c of controls){const box=panel(entityName(c.target_id)+(c.suffix||''));box.append(values({'Declaration':human(c.declaration_kind),'Bounds evidence':human(c.bounds_status)}),sourceCell(c.target_id));
        if(c.content_ids.length)box.append(table(['Stored representation'],c.content_ids,id=>[button('Inspect '+human(byTagContent.get(id)?.format_kind||'stored data'),()=>openDetail('tagcontent',id),'text-link')],'File control stored data '+c.id));
        else box.append(node('p','muted','No stored representation is attached to this control.'));
        const members=fileStoredByControl.get(c.id)||[];
        if(members.length)box.append(table(['Stored member','Capture qualification','Type evidence','Source data'],members,m=>[m.member||'Control structure',human(m.status),human(m.type_status),button('Inspect stored element',()=>openDetail('tagelement',m.element_id),'text-link')],'File control members '+c.id));
        control.append(box);
      }content.append(control);
    }
    if(o.guard_id)conditionGraph(o.guard_id,'File operation incoming condition nodes','Incoming source conditions');
    content.append(notice('Range and execution remain unresolved','The parser does not expand memory spans, prove bounds or overlaps, select a live control position, or establish execution and physical output effects. These records supplement exact-address uses; a missing exact-address link does not prove unused data.'));
    content.append(technical({'Instruction ID':o.id,'Incoming condition ID':o.guard_id,'Expression root ID':o.expression_root_id}));
  }
  function calculationPathStatus(status){return status==='eligible'?'Eligible for local links':'Unresolved block';}
  function calculationPathName(c){return c.opcode+' · '+short(byOperand.get(c.destination_operand_id)?.raw_text||'(destination unresolved)',100);}
  function calculationPathLink(id){const c=byCalculationPath.get(id);return c?button(calculationPathName(c),()=>openDetail('calculationpath',id),'text-link'):sourceCell(id);}
  function calculationPathDestination(c){const address=byAddress.get(c.destination_address_id);return address?button('Address: '+addressName(address),()=>openDetail('address',address.id),'text-link'):node('span','muted','No accepted destination address'+(c.gap_reason?' · '+human(c.gap_reason):''));}
  function calculationPathNotice(){return notice('Source blocks and possible local reuse','Inputs and destinations describe captured operand roles. A reuse link connects an earlier exact destination spelling to a later input only within one branch segment. Links stop at forks, joins, other instructions and unresolved blocks; they never cross rungs. Intervening predicates can change the condition between linked blocks. These links do not establish execution, a write guard, numeric results or confirmed data flow. Missing links do not establish dead ends.');}
  function calculationPathTable(rows,caption){return table(['Calculation block','Input slots / expression reads','Destination evidence','Branch depth','Incoming condition','Recognition / gap','Rung'],rows,c=>[
    calculationPathLink(c.id),fmt(c.input_operand_ids.length)+' / '+fmt(c.expression_use_ids.length),calculationPathDestination(c),c.branch_depth,human(c.condition_quality),primary(badge(calculationPathStatus(c.status)),c.gap_reason?human(c.gap_reason):'No block eligibility gap'),sourceCell(c.rung_id)
  ],caption,{emptyTitle:'No calculation blocks in this selection',emptyDetail:'This view covers MOV, CLR, ADD, SUB, MUL, DIV, ABS, LN, SQR and CPT occurrences in captured ladder.'});}
  function calculationPathReuseTable(rows,caption){return table(['Earlier destination block','Exact address','Later input block','Input occurrence','Condition context'],rows,l=>[
    calculationPathLink(l.producer_instruction_id),byAddress.has(l.address_id)?button(addressName(byAddress.get(l.address_id)),()=>openDetail('address',l.address_id),'text-link'):node('span','muted','Unavailable'),calculationPathLink(l.consumer_instruction_id),engineeringEvidence(l.read_id),l.producer_condition_id===l.consumer_condition_id?'Same captured condition node':'Condition nodes differ; inspect both blocks'
  ],caption,{emptyTitle:'No possible local reuse links',emptyDetail:'No eligible earlier exact destination was retained in this segment. This does not establish a dead end or unused result.'});}
  function calculationPathList(){
    content.append(calculationPathNotice());
    const summary=panel('Captured calculation blocks','Every selected occurrence stays visible, including unrecognized signatures and unresolved inputs or destinations.');
    summary.append(values({'Blocks':calculationPathOccurrences.length,'Branch segments':byCalculationRegion.size,'Possible local reuse links':calculationPathLinks.length,'Blocks with gaps':calculationPathOccurrences.filter(c=>c.status==='gap').length}));content.append(summary);
    content.append(calculationPathTable(calculationPathOccurrences.filter(c=>matches(c)&&(state.filter==='all'||c.status===state.filter)),'Calculation block occurrences'));
  }
  function calculationPathDetail(c){
    setDetailHeading('CALCULATION INPUTS AND DESTINATIONS',calculationPathName(c),sourceName(c.rung_id));
    content.append(calculationPathNotice());
    const region=byCalculationRegion.get(c.region_id),rungRegions=(calculationPaths?.regions||[]).filter(r=>r.rung_id===c.rung_id),segmentNumber=region?rungRegions.findIndex(r=>r.id===region.id)+1:0,summary=panel('Captured block and branch segment');
    summary.append(values({'Opcode':c.opcode,'Eligibility':calculationPathStatus(c.status),'Gap':c.gap_reason?human(c.gap_reason):'No block eligibility gap','Branch depth':c.branch_depth,'Source segment on this rung':segmentNumber?'Segment '+segmentNumber+' of '+rungRegions.length:'Unavailable','Segment begins at':region?human(region.start_reason):'Unavailable','Segment ends at':region?human(region.end_reason):'Unavailable','Blocks in this segment':region?.blocks_count??0,'Incoming condition quality':human(c.condition_quality)}));
    const links=node('div','inline-links');links.append(sourceCell(c.id),sourceCell(c.rung_id));if(byCalculation.has(c.id))links.append(button('Inspect CPT expression',()=>openDetail('calculation',c.id),'text-link'));const transfer=transferByInstruction.get(c.id);if(transfer)links.append(button('Inspect instruction condition transfer',()=>openDetail('transfer',transfer.id),'text-link'));summary.append(links);content.append(summary);
    if(region){const segment=section('Blocks in this branch segment','Segment numbers follow retained source order within this rung. Separate sibling segments never share local reuse links; open the rung for its complete branch outline.');segment.append(calculationPathTable(calculationPathOccurrences.filter(other=>other.region_id===region.id),'Branch segment blocks'));content.append(segment);}
    const inputs=section('Operand inputs','Literal operands remain source evidence. CPT expression containers are separate from their individual reference reads.');inputs.append(accessBindingTable(c.input_operand_ids.map(id=>byOperandAccess.get(id)).filter(Boolean),'Calculation input slots'));content.append(inputs);
    if(c.expression_use_ids.length){const reads=section('CPT expression reads','Repeated reference leaves remain separate source occurrences.');reads.append(expressionUseTable(c.expression_use_ids.map(id=>byExpressionUse.get(id)).filter(Boolean),'Calculation expression reads'));content.append(reads);}
    const destination=section('Destination operand','A captured destination role does not validate a writable member or confirm a final value.');if(c.destination_operand_id){const destinationLinks=node('div','inline-links');destinationLinks.append(sourceCell(c.destination_operand_id),calculationPathDestination(c));destination.append(destinationLinks);}else destination.append(node('p','muted','Destination role or exact address is unresolved; inspect the captured arguments.'));content.append(destination);
    if(c.status==='gap'){const argumentsPanel=section('Captured arguments for this block','The eligibility gap above is explicit; original operand binding evidence remains available.');argumentsPanel.append(table(['Source operand','Binding / role'],(rungOperands.get(c.rung_id)||[]).filter(o=>o.instruction_id===c.id),o=>[sourceCell(o.id),accessCell(o)],'Calculation block arguments'));content.append(argumentsPanel);}
    const reuse=section('Possible local reuse','Both endpoints are in the same branch segment. Condition changes remain visible and do not establish that either block executes.');reuse.append(calculationPathReuseTable(calculationPathLinks.filter(l=>l.producer_instruction_id===c.id||l.consumer_instruction_id===c.id),'Calculation block local reuse'));content.append(reuse);
    if(c.incoming_condition_id)conditionGraph(c.incoming_condition_id,'Calculation incoming condition nodes','Incoming condition evidence');
    else content.append(notice('Incoming condition unavailable','No supported condition context was attached to this occurrence.'));
    content.append(technical({'Instruction ID':c.id,'Branch segment ID':c.region_id,'Incoming condition ID':c.incoming_condition_id}));
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
    if(byCalculationPath.has(c.id))content.append(button('Inspect calculation inputs and destinations',()=>openDetail('calculationpath',c.id),'text-link'));
    setDetailHeading('CALCULATION SOURCE EVIDENCE',calculationName(c),sourceName(c.rung_id));
    content.append(calculationNotice());
    const meta=node('div','detail-meta');meta.append(badge(c.signature_status),badge(c.syntax_status),sourceCell(c.rung_id));content.append(meta);
    const selectedUse=byExpressionUse.get(state.focusCalculationNode);
    if(selectedUse?.instruction_id===c.id){
      const selected=panel('Selected expression read','This is one potential read occurrence, identified by its exact character span. Repeated spelling at other positions remains separate.');
      selected.append(sourceText(byCalculationNode.get(selectedUse.id)?.raw_text),values({'Character span':calculationSpan(selectedUse),'Binding':human(selectedUse.binding_status)}),
        calculationBinding({...selectedUse,reason:selectedUse.binding_reason}),sourceCell(selectedUse.rung_id),technical({'Calculation node ID':selectedUse.id,'Expression operand ID':selectedUse.expression_operand_id}));
      if(relationships)selected.append(addressCell(selectedUse.id));
      content.append(selected);
    }
    const destination=byOperand.get(c.destination_operand_id),expression=byOperand.get(c.expression_operand_id);
    if(c.signature_status==='recognized'){
      const dest=panel('Destination operand','The destination slot belongs to the captured CPT signature. A root binding does not validate a writable member or establish that the instruction executes.');
      if(destination){dest.append(sourceText(destination.raw_text),sourceCell(destination.id));const details=node('div','detail-meta');details.append(badge(destination.status));if(access?.schema_version>=4)details.append(accessCell(destination));dest.append(details,calculationBinding(destination));if(relationships)dest.append(addressCell(destination.id));}
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
      bindings.append(table(['Reference / repeated spelling','Character span','Binding','Declared / resolved root',...(relationships?['Exact address dossier']:[])],references,x=>[
        primary(node('span','mono',x.node.raw_text),x.total>1?'Occurrence '+x.index+' of '+x.total+' with this exact spelling':'One occurrence with this exact spelling'),
        node('span','mono',calculationSpan(x.node)),badge(x.node.binding?.status),calculationBinding(x.node.binding),...(relationships?[addressCell(x.node.id)]:[])
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
    else if(state.view==='engineering')engineeringList();
    else if(state.view==='relationships')relationshipsList();
    else if(state.view==='conditions')conditionsList();
    else if(state.view==='statefulobjects')statefulObjectsList();
    else if(state.view==='sequenceconditions')sequenceConditionsList();
    else if(state.view==='executioncontext')executionContextList();
    else if(state.view==='transfers')transfersList();
    else if(state.view==='bindingcontext')bindingContextList();
    else if(state.view==='instructioncontext')instructionContextList();
    else if(state.view==='sfrcontext')sfrContextList();
    else if(state.view==='objects')objectList();
    else if(state.view==='signalcontext')signalList();
    else if(state.view==='ladder')content.append(rungList());
    else if(state.view==='sfc')sfcList();
    else if(state.view==='patterns')patternList();
    else if(state.view==='findings')findingsList();
    else if(state.view==='access')accessList();
    else if(state.view==='tagdata')tagDataList();
    else if(state.view==='pid')pidList();
    else if(state.view==='calculations')calculationList();
    else if(state.view==='calculationpaths')calculationPathList();
    else if(state.view==='fileoperations')fileOperationList();
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
      else if(d.type==='sequencecondition')sequenceConditionDetail(bySequenceCondition.get(d.id));
      else if(d.type==='sequencecontext')sequenceContextDetail(bySequenceContext.get(d.id));
      else if(d.type==='executioncontext')executionContextDetail(byExecution.get(d.id));
      else if(d.type==='signaladdress')signalAddressDetail(bySignalAddress.get(d.id));
      else if(d.type==='signaloutput')signalOutputDetail(bySignalOutput.get(d.id));
      else if(d.type==='signalrung')signalRungDetail(bySignalRung.get(d.id));
      else if(d.type==='sequenceaddress')sequenceAddressDetail(bySequenceAddress.get(d.id));
      else if(d.type==='pattern')patternDetail(byPattern.get(d.id));
      else if(d.type==='finding')findingDetail(byFinding.get(d.id));
      else if(d.type==='access')accessDetail(byRootAccess.get(d.id));
      else if(d.type==='address')addressDetail(byAddress.get(d.id));
      else if(d.type==='condition')conditionDetail(byConditionalOutput.get(d.id));
      else if(d.type==='statefulobject')statefulObjectDetail(byStatefulGroup.get(d.id));
      else if(d.type==='statefuloccurrence')statefulOccurrenceDetail(byStatefulOccurrence.get(d.id));
      else if(d.type==='statefuluse')statefulUseDetail((statefulUsesByObject.get(state.statefulObjectId)||[]).find(u=>u.address_id===d.id));
      else if(d.type==='outputaddress')outputContextAddressDetail(byOutputAddress.get(d.id));
      else if(d.type==='transfer')transferDetail(byConditionNode.get(d.id));
      else if(d.type==='bindingcontext')bindingContextDetail(byBindingContext.get(d.id));
      else if(d.type==='customcall')customCallDetail(byCustomCall.get(d.id));
      else if(d.type==='customdeclaration')customDeclarationDetail(byCustomDeclaration.get(d.id));
      else if(d.type==='aoiroutine')aoiRoutineDetail(byAoiBodyRoutine.get(d.id));
      else if(d.type==='aoisymbol')aoiSymbolDetail(byAoiBodySymbol.get(d.id));
      else if(d.type==='indexeduse')indexedUseDetail(byIndexedUse.get(d.id));
      else if(d.type==='sfrcall')sfrCallDetail(bySfrCall.get(d.id));
      else if(d.type==='sfrcontent')sfrContentDetail(bySfrCall.get(d.id));
      else if(d.type==='sfrgap')sfrGapDetail(bySfrCall.get(d.id));
      else if(d.type==='candidateaddress')candidateAddressDetail(byCandidateAddress.get(d.id));
      else if(d.type==='reusepattern')reusePatternDetail(byReusePattern.get(d.id));
      else if(d.type==='tagcontent')tagContentDetail(byTagContent.get(d.id));
      else if(d.type==='tagelement')tagElementDetail(byTagElement.get(d.id));
      else if(d.type==='pid')pidDetail(byPid.get(d.id));
      else if(d.type==='pidaddress')pidConnectionAddressDetail(byPidConnectionAddress.get(d.id));
      else if(d.type==='calculation')calculationDetail(byCalculation.get(d.id));
      else if(d.type==='calculationpath')calculationPathDetail(byCalculationPath.get(d.id));
      else if(d.type==='fileoperation')fileOperationDetail(byFileOperation.get(d.id));
    }else{
      const [title,subtitle]=headings[state.view];heading.append(node('p','eyebrow','SOURCE REVIEW · PHASE 1'),node('h1','',title),node('p','subtitle',subtitle));
      if(state.view==='engineering')engineeringToolbar();
      else if(state.view==='relationships')relationshipsToolbar();
      else if(state.view==='conditions')conditionsToolbar();
      else if(state.view==='statefulobjects')statefulObjectsToolbar();
      else if(state.view==='sequenceconditions')toolbarFor('Search transitions, expressions, comments or gaps',[['all','All transition conditions'],['gap','Unresolved evidence'],['modeled','Syntax modeled'],['binding_gaps','Reference binding gaps'],['unsupported','Unmodeled conditions'],...(sequenceContext?[['context_gap','Relationship binding diagnostics']]:[])]);
      else if(state.view==='executioncontext')toolbarFor('Search task, program, routine, target, raw metadata previews or gaps',[['all','All execution context groups'],...Object.entries(executionGroups)]);
      else if(state.view==='signalcontext')signalToolbar();
      else if(state.view==='transfers')toolbarFor('Search instruction opcodes, operand previews or rung context',[['all','All transfers'],['pass_through','Documented pass-through'],...(conditions?.schema_version>=3?[['stateful_transfer','ONS stored-state transfer']]:[]),['opaque_transfer','Unknown transfer']]);
      else if(state.view==='bindingcontext')bindingContextToolbar();
      else if(state.view==='instructioncontext')toolbarFor('Search instruction names, declarations, index expressions or context status');
      else if(state.view==='sfrcontext')toolbarFor('Search SFR routines, selector kinds, chart context or rung names');
      else if(state.view==='objects')toolbarFor('Search names, scopes, descriptions or attributes',countsFilter(entities,'kind'));
      else if(state.view==='ladder')toolbarFor('Search rung text, comments or routine names',countsFilter(rungs,'parse_status'));
      else if(state.view==='sfc')toolbarFor('Search SFC routines, elements and source text');
      else if(state.view==='patterns')toolbarFor('Search opcode or syntax shape',[['all','All patterns'],['repeated','Repeated patterns'],['single','Single occurrences']]);
      else if(state.view==='findings')toolbarFor('Search finding codes, source context or detail',countsFilter(findings,'origin'));
      else if(state.view==='access')toolbarFor('Search root names, scopes, opcodes or rung context');
      else if(state.view==='tagdata')toolbarFor('Search declarations, members, saved values or data text',countsFilter(tagContents,'format_kind'));
      else if(state.view==='pid')toolbarFor(pidMembers?'Search PID operands, member labels, groups or source context':'Search PID operands, rung context or association status',countsFilter(pidOccurrences,'storage_status'));
      else if(state.view==='calculations')toolbarFor('Search CPT destinations, expressions, rung context or syntax status',countsFilter(calculationOccurrences,'syntax_status'));
      else if(state.view==='calculationpaths')toolbarFor('Search opcodes, inputs, destinations, rung context or gaps',[['all','All calculation blocks'],['eligible','Eligible for local links'],['gap','Unresolved blocks']]);
      else if(state.view==='fileoperations')toolbarFor('Search operations, operands, rung comments or evidence gaps',[['all','All file operations'],['gaps','Unresolved evidence'],...Object.keys(FILE_PURPOSES).map(op=>[op,op+' · '+FILE_PURPOSES[op]])]);
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
