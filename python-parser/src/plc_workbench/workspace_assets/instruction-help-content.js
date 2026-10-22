/* Read-only instruction help. Worked values are invented, never source simulation. */
(() => {
  'use strict';
  const BASE = 'https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/';
  const timerRef = page => `${BASE}timer-and-counter-instructions/${page}.html`;
  const bitRef = page => `${BASE}bit-instructions1/${page}.html`;
  const NUMERIC = 'Assume an enabled instruction, compatible numeric types, finite values within range, and no other writer to the example destination.';
  const EDGE = 'Assume normal cyclic execution after the stated prior evaluation, unique storage, and no other writes. Startup/prescan behavior is excluded from this example.';
  const TIMER = 'Assume a standard Logix TIMER with millisecond PRE/ACC, normal repeated execution through each stated condition, no pauses, resets, or other writers.';
  const definition = (name, arity, assumptions, input, operation, result, caveat = '', reference = '') =>
    ({name, arity, assumptions, input, operation, result, caveat, reference});
  const catalog = Object.create(null);
  catalog.XIC = definition('Examine if closed', 1, 'Assume the incoming path is TRUE and this instruction is evaluated.',
    'ExampleBit = TRUE.', 'Test whether ExampleBit is TRUE.', 'This instruction passes a TRUE path result.',
    'A FALSE incoming path remains FALSE. A contact tests a stored bit; its name does not establish physical wiring.');
  catalog.XIO = definition('Examine if open', 1, catalog.XIC.assumptions,
    'ExampleBit = FALSE.', 'Test whether ExampleBit is FALSE.', 'This instruction passes a TRUE path result.', catalog.XIC.caveat);
  const comparisons = [
    ['EQU', 'Equal', '5 and 5', '5 = 5', 'TRUE'], ['NEQ', 'Not equal', '5 and 5', '5 is not equal to 5', 'FALSE'],
    ['LES', 'Less than', '4 and 7', '4 < 7', 'TRUE'], ['LEQ', 'Less than or equal', '7 and 7', '7 <= 7', 'TRUE'],
    ['GRT', 'Greater than', '90 and 90', '90 > 90', 'FALSE'], ['GEQ', 'Greater than or equal', '90 and 90', '90 >= 90', 'TRUE'],
  ];
  comparisons.forEach(([opcode, name, input, operation, result]) => {
    catalog[opcode] = definition(name, 2, 'Assume the incoming path is TRUE, this instruction is evaluated, and both numbers use compatible types.',
      `Example operands are ${input}.`, `Compare ${operation}.`, `The comparison and outgoing path are ${result}.`,
      'The result also depends on the incoming path. Numeric conversion and precision require the actual source types.');
  });
  catalog.OTE = definition('Output energize', 1, 'Assume each stated execution occurs and no other instruction writes ExampleOutput.',
    'Incoming path TRUE, then FALSE on the next execution.', 'Write the incoming path result to ExampleOutput each time.',
    'ExampleOutput becomes TRUE, then FALSE.', 'This assigns a Boolean value; it does not establish a physical actuator or alarm purpose.');
  catalog.OTL = definition('Output latch', 1, catalog.OTE.assumptions,
    'ExampleOutput starts FALSE; incoming path is TRUE, then FALSE.', 'Set the bit on the TRUE execution; the FALSE execution leaves it alone.',
    'ExampleOutput is TRUE after both executions.', 'Other writers, including an unlatch, can change the stored bit.');
  catalog.OTU = definition('Output unlatch', 1, catalog.OTE.assumptions,
    'ExampleOutput starts TRUE; incoming path is TRUE, then FALSE.', 'Clear the bit on the TRUE execution; the FALSE execution leaves it alone.',
    'ExampleOutput is FALSE after both executions.', catalog.OTL.caveat);
  catalog.MOV = definition('Move value', 2, NUMERIC, 'ExampleSource = 7.5; use REAL source and destination.',
    'Copy the source value into ExampleDestination.', 'ExampleDestination = 7.5.', 'Destination type conversion can affect the real source result.');
  catalog.CLR = definition('Clear value', 1, NUMERIC, 'ExampleDestination = 12.5.', 'Write zero to ExampleDestination.', 'ExampleDestination = 0.');
  const arithmetic = [
    ['ADD', 'Add', 3, '12 and 3', '12 + 3', '15'], ['SUB', 'Subtract', 3, '12 and 3', '12 - 3', '9'],
    ['MUL', 'Multiply', 3, '4 and 3', '4 × 3', '12'], ['DIV', 'Divide', 3, '12 and 3', '12 / 3', '4'],
    ['ABS', 'Absolute value', 2, '-7', 'absolute value of -7', '7'],
    ['LN', 'Natural logarithm', 2, '1', 'natural logarithm of 1', '0'],
    ['SQR', 'Square root', 2, '9', 'square root of 9', '3'],
  ];
  arithmetic.forEach(([opcode, name, arity, input, operation, result]) => {
    catalog[opcode] = definition(name, arity, NUMERIC, `Example input: ${input}.`, `Calculate ${operation}.`,
      `Write ${result} to ExampleDestination.`, 'Check the actual operand types, conversion, range, and mathematical domain.');
  });
  catalog.CPT = definition('Compute expression', 2, NUMERIC, 'ExampleA = 6, ExampleB = 4, ExampleC = 2; expression (ExampleA + ExampleB) / ExampleC.',
    'Evaluate the parentheses first: (6 + 4) / 2 = 10 / 2.', 'Write 5 to ExampleDestination.',
    'This invented calculation does not evaluate the captured expression. Its supported syntax and types still need review.');

  catalog.TON = definition('Timer on delay', 3, TIMER,
    'Initially PRE = 1000 ms, ACC = 0, DN = FALSE after a FALSE execution; incoming path then stays TRUE for 1100 ms.',
    'Accumulate enabled elapsed time toward the preset.', 'On an execution at or after 1000 ms, DN is TRUE. A later FALSE execution clears ACC to 0 and DN to FALSE.',
    'Timer fields are stored state. Scan timing affects when completion is observed; other timer types may use different units.', timerRef('timer-on-delay--ton-'));
  catalog.TOF = definition('Timer off delay', 3, TIMER,
    'PRE = 1000 ms; a prior TRUE execution established ACC = 0 and DN = TRUE. The incoming path then stays FALSE.',
    'Accumulate elapsed time while the incoming condition is FALSE.', 'DN stays TRUE during the delay and becomes FALSE when an execution observes the preset reached.',
    'A TRUE execution sets DN and clears ACC. Completion clears DN, unlike an on-delay timer.', timerRef('timer-off-delay--tof-'));
  catalog.RTO = definition('Retentive timer on', 3, TIMER,
    'PRE = 1000 ms, ACC = 300 ms, DN = FALSE after an enabled interval; the incoming condition becomes FALSE.',
    'Retain the accumulated time while disabled; continue accumulating when enabled again.',
    'ACC remains 300 ms during FALSE. After at least another 700 ms of enabled time is observed, DN is TRUE.',
    'FALSE does not clear the accumulator. Reset and externally written state must be reviewed separately.', timerRef('retentive-timer-on--rto-'));
  catalog.CTU = definition('Count up', 3, EDGE,
    'ACC = 2, PRE = 3, CU = FALSE, and no overflow/underflow; the incoming condition changes from FALSE to TRUE.',
    'Recognize one rising transition and increment the accumulator once.', 'ACC becomes 3 and DN is TRUE. Staying TRUE on later executions adds no further count.',
    'Counted transitions must be observed by execution; this is not a count of all scans.', timerRef('count-up--ctu-'));
  catalog.CTD = definition('Count down', 3, EDGE,
    'ACC = 3, CD = FALSE, and no overflow/underflow; the incoming condition changes from FALSE to TRUE.',
    'Recognize one rising transition and decrement the accumulator once.', 'ACC becomes 2. Staying TRUE on later executions adds no further decrement.',
    'The decrement occurs on a rising transition, not a falling transition. Done-bit interpretation also needs the preset and counter state.', timerRef('count-down--ctd-'));
  catalog.ONS = definition('One shot', 1, EDGE,
    'Storage bit = FALSE after a prior FALSE evaluation; incoming path is TRUE on two successive executions.',
    'Remember the first rising transition using the storage bit.', 'The ONS outgoing path is TRUE on the first execution and FALSE on the second.',
    'The argument is storage, not a separate pulse-output operand. Downstream conditions still matter.', bitRef('one-shot--ons-1'));
  catalog.OSR = definition('One shot rising', 2, EDGE,
    'Storage and output bits = FALSE after a prior FALSE evaluation; incoming path is TRUE on two successive executions.',
    'Detect the rising transition and set the output bit for one execution.', 'Output bit is TRUE on the first execution, then FALSE on the second.',
    'The pulse belongs to the output bit. The instruction passes its incoming path condition onward.', bitRef('one-shot-rising--osr-1'));
  catalog.OSF = definition('One shot falling', 2, EDGE,
    'Storage = TRUE and output = FALSE after a prior TRUE evaluation; incoming path is FALSE on two successive executions.',
    'Detect the falling transition and set the output bit for one execution.', 'Output bit is TRUE on the first FALSE execution, then FALSE on the second.',
    'The pulse belongs to the output bit. The incoming and outgoing path conditions remain FALSE in this example.', bitRef('one-shot-falling--osf-1'));
  catalog.RES = definition('Reset stored structure', 1, 'Assume an enabled RES targeting an invented TIMER used by TON or RTO, with no other writer during this example.',
    'PRE = 1000 ms, ACC = 450 ms; timer status bits may be set.', 'Reset the timer accumulator and its control-status bits.',
    'ACC = 0 and status bits are FALSE; PRE remains 1000 ms.',
    'RES is not a whole-object clear. COUNTER and CONTROL targets have their own reset fields; the captured target type is not inferred here.', timerRef('reset--res-'));
  catalog.PID = definition('Proportional integral derivative control', 7, 'Conceptual example only: suppose an enabled automatic loop has compatible engineering-unit PV and setpoint. No tuning or output value is assumed.',
    'Invented PV = 45 and setpoint = 50.', 'Compare measurement with target; configured control action, tuning, update timing, and stored history govern control-variable behavior.',
    'PV is 5 units below the setpoint. No CV value or direction is predicted.',
    'PV is the measured value, setpoint is the target, and CV is the control variable. Tieback, master-loop, hold, modes, scaling, and target classes require source-specific review.',
    `${BASE}special-instructions/proportional-integral-derivative--pid-.html`);

  function valid(instruction) {
    return Boolean(instruction && typeof instruction === 'object' && !Array.isArray(instruction)
      && typeof instruction.opcode === 'string' && instruction.opcode.trim() && instruction.opcode.length <= 80
      && Array.isArray(instruction.arguments) && instruction.arguments.length <= 32
      && Array.from(instruction.arguments).every(argument => typeof argument === 'string' && argument.length <= 4096)
      && instruction.arguments.reduce((size, argument) => size + argument.length, 0) <= 64000);
  }
  const el = (tag, text, className = '') => {
    const element = document.createElement(tag); element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  function render(instruction) {
    const root = el('section', undefined, 'instruction-help-content');
    root.setAttribute('aria-label', 'Instruction help');
    if (!valid(instruction)) {
      root.append(el('h2', 'Instruction help unavailable'),
        el('p', 'The captured instruction record is incomplete or outside the help display limits. Its effects remain unresolved; no example or input/output roles are inferred.', 'instruction-help-caveat'));
      return root;
    }
    const entry = catalog[instruction.opcode.toUpperCase()];
    const supported = entry && instruction.arguments.length === entry.arity && instruction.arguments.every(argument => argument.trim());
    root.append(el('h2', `${instruction.opcode} — ${supported ? entry.name : 'Unresolved instruction'}`));
    root.append(el('h3', 'How it works'), el('p', window.PLCRungExplanation?.summary?.(instruction)
      || 'The shared instruction explanation is unavailable. Read the captured arguments and source before interpreting effects.'));
    const captured = el('section', undefined, 'instruction-help-arguments'); captured.append(el('h3', 'Captured arguments'));
    const list = el('ol');
    const colors = instruction.arguments.reduce((size, argument) => size + argument.length, 0) <= 4096
      ? window.PLCSourceColors?.create?.([instruction]) : null;
    instruction.arguments.forEach(argument => {
      const row = el('li'), value = el('code');
      if (colors) colors.append(value, argument); else value.textContent = argument;
      row.append(value); list.append(row);
    });
    captured.append(list);
    if (!instruction.arguments.length) captured.append(el('p', 'No arguments were captured.'));
    root.append(captured);
    if (!supported) {
      root.append(el('p', 'Unknown/custom opcode or unsupported argument shape. No worked result or input/output roles are inferred. Inspect the original definition and calling context.', 'instruction-help-caveat'));
      return root;
    }
    const example = el('section', undefined, 'instruction-help-example');
    example.append(el('h3', 'Invented worked example'),
      el('p', 'These values are independent of your captured source.'), el('p', entry.assumptions, 'instruction-help-assumptions'));
    [['Input / initial state', entry.input], ['Operation', entry.operation], ['Result', entry.result]].forEach(([heading, text]) => {
      const step = el('p'); step.append(el('strong', `${heading}: `), el('span', text)); example.append(step);
    });
    root.append(example);
    if (entry.caveat) root.append(el('p', entry.caveat, 'instruction-help-caveat'));
    root.append(el('p', 'This is instruction help, not a simulation of your source. Branch gating, execution order, types, other writers, and retained state still require review.', 'instruction-help-caveat'));
    if (entry.reference) {
      const link = el('a', `Rockwell reference: ${instruction.opcode}`); link.href = entry.reference;
      link.target = '_blank'; link.rel = 'noopener noreferrer'; root.append(link);
    }
    return root;
  }
  window.PLCInstructionHelpContent = Object.freeze({valid, render});
})();
