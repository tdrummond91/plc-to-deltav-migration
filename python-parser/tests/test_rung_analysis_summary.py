"""Rung publication admits only closed counts, never private evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.rung_analysis_summary import (
    RungSummaryError, build_rung_summary, render_rung_summary, validate_rung_summary,
)
from test_rung_analysis import capture


def summary(texts=('XIC(A)OTE(D);',), **kwargs):
    return build_rung_summary(*capture(texts, **kwargs))


class RungSummaryTests(unittest.TestCase):
    def test_complete_and_partial_counts_are_deterministic_and_bounded(self) -> None:
        report = summary(('XIC(A)OTE(D);', 'CPT(D,A+A);', 'Mystery(A);', '[XIC(B),]OTE(D);', ';', 'XIC(A'))
        coverage = report['coverage']
        self.assertEqual(coverage['source_rungs'], 6)
        self.assertEqual(coverage['source_instructions'], 6)
        self.assertEqual(coverage['expression_uses'], 2)
        self.assertEqual(coverage['unknown_blocks'], 1)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(coverage['identification'], {'empty': 1, 'identified': 3, 'partial': 0, 'unidentified': 1, 'unparsed': 1})
        rendered = render_rung_summary(report)
        self.assertLessEqual(len(rendered), 4096)
        self.assertEqual(json.loads(rendered), report)
        self.assertEqual(rendered, render_rung_summary(deepcopy(report)))

    def test_comment_text_identifiers_and_instruction_names_never_published(self) -> None:
        private = '<Rung><Text>OTE(UniquePlantName);</Text><Comment>alarm ConfidentialName</Comment></Rung>'
        rendered = render_rung_summary(summary(rung_xml=private))
        for text in ('UniquePlantName', 'ConfidentialName', 'OTE', 'rung:', 'instruction:', 'evidence_ids', 'candidate_ids'):
            self.assertNotIn(text, rendered)
        self.assertEqual(json.loads(rendered)['coverage']['candidate_bases']['text_hint'], 1)

    def test_empty_branched_rung_is_coherent_without_instruction_blocks(self) -> None:
        report = summary(('[,];',))
        self.assertEqual(report['coverage']['structures']['branched'], 1)
        self.assertEqual(report['coverage']['identification']['empty'], 1)
        validate_rung_summary(report)

    def test_exact_keys_and_native_count_types_reject_leaks(self) -> None:
        base = summary()
        mutations = (
            lambda x: x.update(name='private'),
            lambda x: x['coverage'].update(opcode='private'),
            lambda x: x['coverage']['block_families'].update(private=1),
            lambda x: x['coverage'].update(source_rungs=True),
            lambda x: x['coverage'].update(source_rungs=-1),
            lambda x: x['coverage'].update(source_rungs=1.0),
            lambda x: x.update(status='approved'),
            lambda x: x.update(engineering_review='approved'),
            lambda x: x.update(schema_version=True),
        )
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(RungSummaryError):
                render_rung_summary(candidate)

    def test_population_and_status_contradictions_rejected(self) -> None:
        base = summary()
        mutations = (
            lambda c: c.update(source_instructions=1),
            lambda c: c.update(source_rungs=2),
            lambda c: c.update(candidates_total=0),
            lambda c: c.update(unknown_blocks=1),
            lambda c: c.update(access_gap_operands=99),
            lambda c: c.update(expression_gap_uses=1),
            lambda c: c.update(missing_number=2),
            lambda c: c.update(branches=1, branch_legs=1),
            lambda c: c.update(empty_legs=1),
        )
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(RungSummaryError):
                validate_rung_summary(candidate)
        candidate = deepcopy(base)
        candidate['status'] = 'partial'
        with self.assertRaises(RungSummaryError):
            validate_rung_summary(candidate)

    def test_revision_validation_and_copy(self) -> None:
        inputs = capture()
        revision = {'commit': 'a' * 40, 'worktree': 'clean'}
        report = build_rung_summary(*inputs, revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(report['tool_revision']['commit'], 'a' * 40)
        for rev in ({'commit': None, 'worktree': 'clean'}, {'commit': 'a' * 40, 'worktree': 'unavailable'},
                    {'commit': '../private', 'worktree': 'modified'}, {'commit': None, 'worktree': 'unknown'}):
            candidate = deepcopy(report)
            candidate['tool_revision'] = rev
            with self.subTest(revision=rev), self.assertRaises(RungSummaryError):
                validate_rung_summary(candidate)

    def test_unknown_block_populations_require_compatible_rung_groups(self) -> None:
        base = summary()
        forged = []
        candidate = deepcopy(base)
        candidate['coverage']['identification'].update(identified=0, unidentified=1)
        candidate['status'] = 'partial'
        forged.append(candidate)  # An unidentified rung needs an unknown block.
        candidate = deepcopy(base)
        candidate['coverage']['block_identification'].update(roles_known=1, unknown=1)
        candidate['coverage']['unknown_blocks'] = 1
        forged.append(candidate)  # All rungs identified cannot contain unknown blocks.
        candidate = deepcopy(base)
        candidate['coverage']['identification'].update(identified=0, partial=1)
        candidate['coverage']['block_identification'].update(roles_known=0, unknown=2)
        candidate['coverage']['unknown_blocks'] = 2
        candidate['status'] = 'partial'
        forged.append(candidate)  # A partial rung needs at least one identified block.
        for candidate in forged:
            with self.subTest(coverage=candidate['coverage']), self.assertRaises(RungSummaryError):
                validate_rung_summary(candidate)

    def test_empty_and_unparsed_rungs_cannot_supply_known_results(self) -> None:
        for text in (';', 'XIC(A'):
            candidate = summary((text,))
            candidate['coverage']['results'].update(no_known_result=0, single_known_result=1)
            with self.subTest(text=text), self.assertRaises(RungSummaryError):
                validate_rung_summary(candidate)
        candidate = summary((';', 'XIC(A)OTE(D);'))
        candidate['coverage']['structures'].update(empty=0, series=2)
        with self.assertRaises(RungSummaryError):
            validate_rung_summary(candidate)

    def test_branch_counts_cannot_exceed_the_source_parser_budget(self) -> None:
        candidate = summary(('[XIC(A),]OTE(D);',))
        candidate['coverage'].update(branches=500_000_000_000, branch_legs=1_000_000_000_000)
        with self.assertRaises(RungSummaryError):
            validate_rung_summary(candidate)

    def test_forged_private_records_cannot_supply_public_counts(self) -> None:
        inputs = capture()
        inputs[-1].rungs[0]['comment_status'] = 'present'
        with self.assertRaises(RungSummaryError):
            build_rung_summary(*inputs)

    def test_tiny_render_budget_rejects_output(self) -> None:
        report = summary()
        with patch('plc_workbench.rung_analysis_summary.MAX_REPORT_BYTES', 100), self.assertRaises(RungSummaryError):
            render_rung_summary(report)


if __name__ == '__main__':
    unittest.main()
