/* Reviewer instructions are bundled locally with the report application. */
function renderReviewGuide(api) {
  'use strict';
  const {node, button, panel, values, labels, go, back, data, context} = api;
  const page = node('div', 'review-guide');
  const list = (items, ordered=false) => {
    const result = node(ordered ? 'ol' : 'ul', 'guide-list');
    items.forEach(text => result.append(node('li', '', text)));
    return result;
  };
  const intro = panel('What this review is for',
    'Check whether the captured control logic is represented clearly and correctly, and identify the information needed to describe its intended operation. Your feedback will guide corrections and the control-strategy document.');
  intro.append(list([
    'Confirm the report covers the export and equipment you were assigned to review. Keep the report file or run-folder name with your notes.',
    'Open the relevant sections, follow the source links, and compare each interpretation with the logic, descriptions and approved engineering records available to you.',
    'Record a response for each item you check. State what you verified, what needs changing, or exactly which evidence is missing. Use the feedback template below.'
  ], true));
  intro.append(node('p', 'guide-callout',
    'The report is read-only. It does not save review decisions, edit the controller, or approve a design. Record your responses in your review notes or review register and return them through your agreed review process.'));
  if(context && back) intro.append(button('Return to the selected record', back));
  page.append(intro);

  const navigation = panel('Find and follow the evidence');
  navigation.append(list([
    'Use the left navigation to choose a subject. Search applies to the current section; it is not a search of the entire report. Clear the search and filters if expected records seem to be missing.',
    'Open a name or evidence link to inspect its detail. Use Back to previous view to return with your earlier selection. Previous and Next below a table change its page.',
    'On a detail page, Prepare review feedback brings the selected record ID into this guide. Source identifiers & location contains additional IDs and source locations when needed.',
    'Ctrl+K focuses the available search box. Keyboard users can use Tab to reach links and buttons, and Enter to open them. Expand the checklists below for the subject you are reviewing.'
  ]));
  page.append(navigation);

  const responses = panel('Choose a clear response',
    'These are suggested responses for your notes. They are not buttons that change the report or approval states assigned by the tool.');
  const responseCards = node('div', 'guide-responses');
  [
    ['Checked', 'The stated interpretation matches the evidence you checked. Name that evidence and the scope you reviewed. This does not approve unrelated logic or the complete migration.'],
    ['Needs correction', 'Something is wrong or misleading. Quote the displayed result, provide the replacement or expected behavior, and explain what supports the change.'],
    ['Evidence missing', 'You cannot confirm the interpretation yet. Name the unanswered question and the document, configuration, source export or operating information needed to resolve it.'],
    ['Not applicable', 'This check does not apply to this item. Explain why; do not use this response for something you have not reviewed.']
  ].forEach(([title, text]) => {
    const card = node('section', 'guide-response');
    card.append(node('h3', '', title), node('p', '', text)); responseCards.append(card);
  });
  responses.append(responseCards, node('p', 'muted',
    'If an item has not been checked, leave it marked Not reviewed in your notes. A green source status or a resolved address is not a recorded engineering approval.'));
  page.append(responses);

  const checks = panel('What to check by subject',
    'Expand the subjects relevant to your assignment. The links open sections available in this report. If a subject has no captured evidence, document what is needed rather than treating an empty view as proof of absence.');
  const topics = [
    ['Coverage, names and comments', ['overview', 'objects', 'ladder', 'findings'], [
      'Confirm the controller, programs and routines are the intended source. Check whether any routine body, content version or description is missing or unsupported.',
      'Check tag descriptions, aliases, routine names and rung comments for correct association. A missing description and an incorrect association need different corrections.',
      'Identify which missing information prevents review. Give the routine/object name and the missing source or identifier.'
    ], 'Name the affected item, the missing or incorrect description, and the source that supplies the correct information.'],
    ['Rungs, Boolean outputs and branching', ['engineering', 'conditions', 'transfers', 'signalcontext', 'patterns'], [
      'Follow the inputs and conditions to each destination. Check contact polarity, comparisons, branch alternatives, and whether all paths to the output are represented.',
      'Check output actions, latch/unlatch pairs, one-shot behavior, timer/counter conditions, resets and additional writers. Keep state-dependent behavior distinct from a simple input-to-output path.',
      'Check the proposed purpose of the logic. Matching patterns or a shared address can suggest a relationship without proving equipment identity or execution order.'
    ], 'State the input/condition, affected output, and the path or action that is missing, misclassified or unclear.'],
    ['I/O, instruments and equipment', ['rackbacking', 'objects', 'access', 'assemblies'], [
      'Check address spelling, aliases, module/channel correspondence, signal direction, data type and source description.',
      'Compare units, range and equipment purpose with the instrument index, wiring or channel configuration when available. Source address correspondence alone does not confirm a physical terminal.',
      'For valves, pumps and sensors, identify commands, feedbacks, permissives and failure indications separately. Explain any grouping that should be split or combined.'
    ], 'Give the signal/equipment identity, expected role or channel, and the engineering reference supporting it.'],
    ['PID loops, selectors and cascade relationships', ['pid', 'assemblies', 'signalcontext'], [
      'Check the process variable (PV), setpoint (SP), output (CV), scaling, engineering units and signal direction.',
      'Check manual/automatic selection, tracking, limits and any selector feeding the loop. Identify which values are stored export values and which behavior needs operating context.',
      'Confirm proposed master/slave or cascade relationships from the connected logic. A shared reference by itself does not prove a working cascade.'
    ], 'Name the loop and exact field or connection, what it should contain, and the logic or loop documentation that confirms it.'],
    ['Analog calculations and data movement', ['calculations', 'calculationpaths', 'fileoperations'], [
      'Check every input, operator, constant, unit conversion and destination, including scaling, limits, selection and rounding where shown.',
      'Follow single-path calculations and each branch separately. Check intermediate values, other writers, file/array lengths and symbolic selectors.',
      'A possible source-order link is not proof that a value reaches the destination at runtime. Identify the condition or selector information needed where it remains unresolved.'
    ], 'Provide the expression or block, expected input/output meaning, and the specific operand, conversion or path needing correction.'],
    ['Sequences, transitions and stored state', ['sfc', 'sequenceconditions', 'sfrcontext', 'statefulobjects', 'executioncontext'], [
      'Check initial and reset targets, steps, actions, transition conditions and alternative paths against the intended operating sequence.',
      'Check timers, counters, holds, aborts and restarts where source evidence exists. Specify missing behavior rather than assuming it from a step name.',
      'Keep alternate source contents and routine calls distinct. Explain which source or operating description is required to determine active execution or a disputed target.'
    ], 'Identify the current step/state, triggering condition and expected next action or transition, with supporting source.'],
    ['Alarms, interlocks and shutdown effects', ['alarmevidence', 'conditions', 'signalcontext', 'assemblies'], [
      'Check initiating conditions, messages, reset/latch behavior and delays or hysteresis where captured.',
      'Distinguish an operator warning from a permissive, interlock or shutdown action. Confirm affected equipment and alarm priority from approved logic or alarm documentation.',
      'Names containing alarm-related wording are leads for review. No explicit alarm record in the export does not establish that no alarm exists; HMI or external configuration may be needed.'
    ], 'State the cause, displayed message, intended consequence, reset behavior and priority, and identify the evidence for each.'],
    ['Communications, external uses and apparent dead ends', ['communication', 'relationships', 'access', 'assemblies'], [
      'Check configured local/remote data, message purpose and expected communication partners against the interface configuration.',
      'Investigate values with no known local reader or writer, and paths with no known result. Check external consumers, indirect addressing, initialization and missing source before calling code unused.',
      'Distinguish exported configuration from live transfer success, direction and device-specific meaning.'
    ], 'Identify the endpoint or address, expected producer/consumer, and the external configuration or operating evidence needed.'],
    ['Unresolved items and report usability', ['residuals', 'bindingcontext', 'findings'], [
      'Read the stated reason before deciding how to resolve an unknown. Missing source, an unsupported form and a runtime-dependent value require different evidence.',
      'Check whether the proposed category is useful and whether the explanation identifies the next question clearly. Give a better category or description with a reason when needed.',
      'Report confusing labels, hidden context, broken links, difficult searches, clipped text and misleading groupings. Include the section, record and the steps that reproduce the problem.'
    ], 'Describe the question you could not answer or task you could not complete, and what information or presentation would help.']
  ];
  topics.forEach(([title, views, items, answer]) => {
    const item = node('details', 'guide-topic');
    item.append(node('summary', '', title), list(items));
    const prompt = node('p', 'guide-answer');
    prompt.append(node('strong', '', 'In your response: '), node('span', '', answer));
    item.append(prompt);
    const links = node('div', 'inline-links');
    views.filter(view => Object.hasOwn(labels, view)).forEach(view => links.append(button('Open ' + labels[view], () => go(view), 'text-link')));
    item.append(links); checks.append(item);
  });
  page.append(checks);

  const feedback = panel('Write feedback that can be acted on',
    'Use one entry per issue or clearly defined checked item. Copy the template into your review notes, replace the bracketed prompts, and keep the report identity with the response.');
  if(context) feedback.append(values({'Selected section': context.section, 'Selected record': context.title, 'Record ID': context.id, 'Detail context': context.subtitle, ...context.selections}));
  const template = node('textarea', 'guide-template');
  template.id = 'review-feedback-template'; template.readOnly = true; template.rows = 15;
  template.setAttribute('aria-label', 'Copyable review feedback template');
  template.value = [
    'Report file / run folder: [name of the report being reviewed]',
    'Source snapshot SHA-256: ' + String(data.snapshot.sha256 || '[copy from Overview]'),
    'Section: ' + (context?.section || '[section name]'),
    'Object / routine / rung: ' + (context?.title || '[name and location]'),
    'Record ID: ' + (context?.id || '[copy from Source identifiers & location]'),
    ...(context?.subtitle ? ['Detail context: ' + context.subtitle] : []),
    ...Object.entries(context?.selections || {}).map(([name,value]) => name + ': ' + value),
    'Response: [Checked / Needs correction / Evidence missing / Not applicable]',
    'Issue type: [interpretation / missing information / grouping / description / navigation or appearance / target design decision]',
    'Displayed result: [quote the relevant label, value or explanation]',
    'Expected result or unanswered question: [exact correction or information needed]',
    'Supporting evidence: [source location, drawing, procedure or configuration reference]',
    'Operational importance: [what decision or function is affected; explain urgency]',
    'Reviewer / date: [name / date]'
  ].join('\n');
  feedback.append(template, button('Select feedback template', () => { template.focus(); template.select(); }),
    node('p', 'muted', 'After selecting, press Ctrl+C (Command+C on macOS), then paste into your review notes. The template is read-only; no response is saved or sent by this report.'));
  const example = node('details', 'guide-topic');
  example.append(node('summary', '', 'Example of a useful correction'), node('pre', 'source-text note', [
    'Illustrative example — replace these details with the actual item you reviewed.',
    'Section: PID evidence',
    'Object: Example_Loop; record ID: [ID from the selected report]',
    'Response: Needs correction',
    'Issue type: interpretation',
    'Displayed result: The PV input is labeled Example_SP.',
    'Expected result: The PV input should be Example_PV; Example_SP is the setpoint.',
    'Supporting evidence: The PID source operands and loop drawing [document/revision] identify those connections.',
    'Operational importance: The current labels would reverse the process variable and setpoint in the strategy description.',
    'Reviewer / date: [name / date]'
  ].join('\n')));
  feedback.append(example, node('p', 'muted',
    'For a Checked response, name the fields and evidence you verified. For Evidence missing, name the required information and who or what could supply it. For an interface issue, give the click/search steps and what you expected to see.'));
  page.append(feedback);

  const glossary = panel('Terms used in the report');
  glossary.append(values({
    'Source evidence': 'Names, values, instructions and relationships captured from the export. These describe the source, not a live operating state.',
    'Candidate / possible purpose': 'An interpretation supported by a pattern or relationship that still needs confirmation of its engineering meaning.',
    'Partial / unresolved': 'Some information or interpretation is missing. Read the specific reason; it does not mean that every result is unusable.',
    'Complete': 'The stated capture or analysis scope finished. It does not certify equipment behavior or engineering approval.',
    'Binding / alias': 'A binding links a reference to its source declaration. An alias is another name for an underlying tag or address; a bound root does not always identify an exact member or array element.',
    'Opaque / unknown transfer': 'The available evidence does not determine how the instruction passes or changes its incoming condition. Review the source question before treating the path as a known Boolean result.',
    'Qualified source correspondence': 'The address relationship meets the stated source checks. This is distinct from confirming physical wiring, equipment purpose or actual execution.',
    'Source occurrence / record ID': 'One captured use and its identifier in this report. Keep the report identity with the ID; IDs are not persistent equipment numbers across exports.',
    'Routine / rung / operand': 'A routine is a named body of logic. A rung is one ladder-logic statement. An operand is the value, address or other argument supplied to an instruction.',
    'AOI / MSG': 'Add-On Instruction, a reusable custom instruction definition / message instruction, used for configured data exchange. Inspect their definitions or communication context for the captured meaning.',
    'Guard / permissive': 'A guard is the captured condition leading to an instruction. Whether it implements a process permissive or interlock needs engineering context.',
    'AI / AO / DI / DO': 'Analog input, analog output, digital input and digital output. Confirm the device role and direction from its configuration and wiring.',
    'PV / SP / CV': 'Process variable, setpoint and control output. Check the actual loop connections, units and scaling.',
    'SFC / transition': 'Sequential Function Chart / a condition used to move between steps. A source relationship does not establish the live active step.',
    'Read / write': 'A possible source use of a value. Conditions, execution order and indirect or external access can affect actual behavior.',
    'No known local result': 'No result was identified within the analyzed local evidence. External uses or missing information may still explain the logic.'
  }));
  page.append(glossary);
  return page;
}
