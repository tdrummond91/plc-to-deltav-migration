"""Rack source records and frozen summaries from invented, in-memory XML."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest

from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary import (
    LEGACY_CONSTANTS, MODULE_COUNT_KEYS, RACK_COUNT_KEYS, V3_CONSTANTS,
    SummaryError, build_summary, render_summary, validate_summary,
)


RACK_KINDS = {"module_rack_connection", "module_rack_input_alias", "module_rack_output_alias"}


def inventory(body: str):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="SyntheticController">' + body +
        '</Controller></RSLogix5000Content>').encode("utf-8")))


def module(rack: str, ordinary: str = "") -> str:
    return ('<Modules><Module Name="SyntheticCard"><Communications><Connections>' +
            ordinary + rack + '</Connections></Communications></Module></Modules>')


def earlier_summary(current: dict, version: int) -> dict:
    result = deepcopy(current)
    result.update(LEGACY_CONSTANTS if version == 2 else V3_CONSTANTS)
    for key in RACK_COUNT_KEYS | (MODULE_COUNT_KEYS if version == 2 else frozenset()):
        del result["counts"][key]
    return result


class RackSourceTests(unittest.TestCase):
    def test_empty_attributes_have_exact_parent_scope_and_no_invented_name(self) -> None:
        result = inventory(module("<RackConnection><InAliasTag/><OutAliasTag/></RackConnection>"))
        controller = next(e for e in result.entities if e.kind == "controller")
        card = next(e for e in result.entities if e.kind == "module")
        connection = next(e for e in result.entities if e.kind == "module_rack_connection")
        rack = [e for e in result.entities if e.kind in RACK_KINDS]
        self.assertEqual(len(rack), 3)
        self.assertEqual(connection.parent_id, card.id)
        for entity in rack:
            self.assertEqual(entity.scope_id, controller.id)
            self.assertIsNone(entity.name)
            self.assertEqual(entity.attributes, {})
            self.assertEqual(entity.parent_id, card.id if entity is connection else connection.id)
            self.assertTrue(entity.id.startswith(entity.kind + "_"))
        self.assertEqual([d.code for d in result.diagnostics], ["module_rack_backing_not_analyzed"])
        self.assertEqual(result.diagnostics[0].source_id, connection.id)
        self.assertEqual(result.diagnostics[0].locator, connection.locator)
        self.assertEqual(result.diagnostics[0].severity, "warning")
        self.assertEqual((result.schema_version, result.parser_version), (3, "source-inventory-3"))
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.coverage["unmodeled_xml_paths"], [])

    def test_raw_attributes_descriptions_and_source_positions_are_retained(self) -> None:
        source = module('<RackConnection Name="InventedLink" Custom="RAW_CONNECTION">'
                        '<Description>Connection description</Description>'
                        '<InAliasTag Name="InventedInput" AliasFor="Unverified:I.Member" Custom="RAW_INPUT">'
                        '<Description>Input description</Description></InAliasTag>'
                        '<OutAliasTag Name="" AliasFor="Unverified:O.Member"/>'
                        '</RackConnection>')
        result = inventory(source)
        connection, input_alias, output_alias = [e for e in result.entities if e.kind in RACK_KINDS]
        self.assertEqual(connection.attributes, {"Name": "InventedLink", "Custom": "RAW_CONNECTION"})
        self.assertEqual(connection.description, "Connection description")
        self.assertEqual(input_alias.attributes, {"Name": "InventedInput", "AliasFor": "Unverified:I.Member",
                                                "Custom": "RAW_INPUT"})
        self.assertEqual(input_alias.description, "Input description")
        self.assertEqual(output_alias.name, "")
        self.assertEqual(output_alias.attributes, {"Name": "", "AliasFor": "Unverified:O.Member"})
        self.assertEqual([d.code for d in result.diagnostics], ["module_rack_backing_not_analyzed",
                         "module_rack_content_not_analyzed", "module_rack_content_not_analyzed"])
        self.assertEqual([d.source_id for d in result.diagnostics[1:]], [connection.id, input_alias.id])
        self.assertTrue(input_alias.locator.endswith("/RackConnection[1]/InAliasTag[1]"))

    def test_content_warning_is_tied_to_exact_record_and_ignores_formatting_whitespace(self) -> None:
        clean = inventory(module('<RackConnection>\n  <InAliasTag> \t </InAliasTag>\n'
                                 '  <OutAliasTag/>\n</RackConnection>'))
        self.assertEqual([d.code for d in clean.diagnostics], ["module_rack_backing_not_analyzed"])
        for body, expected_kind in (
            ('<RackConnection>PRIVATE_TEXT<InAliasTag/></RackConnection>', "module_rack_connection"),
            ('<RackConnection><Vendor/><InAliasTag/></RackConnection>', "module_rack_connection"),
            ('<RackConnection><InAliasTag>PRIVATE_TEXT</InAliasTag></RackConnection>', "module_rack_input_alias"),
            ('<RackConnection><OutAliasTag><Data/></OutAliasTag></RackConnection>', "module_rack_output_alias"),
        ):
            with self.subTest(body=body):
                result = inventory(module(body))
                warnings = [d for d in result.diagnostics if d.code == "module_rack_content_not_analyzed"]
                self.assertEqual(len(warnings), 1)
                entity = next(e for e in result.entities if e.kind == expected_kind)
                self.assertEqual(warnings[0].source_id, entity.id)
                self.assertEqual(warnings[0].locator, entity.locator)
                self.assertEqual(warnings[0].severity, "warning")
                self.assertNotIn("PRIVATE_TEXT", render_summary(build_summary(result)))

    def test_duplicate_and_empty_records_keep_distinct_deterministic_identities(self) -> None:
        body = module('<RackConnection/><RackConnection><InAliasTag/><InAliasTag/>'
                      '<OutAliasTag/><OutAliasTag/></RackConnection>')
        first, second = inventory(body), inventory(body)
        self.assertEqual(first, second)
        rack = [e for e in first.entities if e.kind in RACK_KINDS]
        self.assertEqual(len(rack), 6)
        self.assertEqual(len({e.id for e in rack}), 6)
        self.assertEqual(len({e.locator for e in rack}), 6)
        self.assertEqual([first.counts[key] for key in sorted(RACK_COUNT_KEYS)], [2, 2, 2])
        self.assertEqual(len(first.diagnostics), 2)
        self.assertTrue(all(d.code == "module_rack_backing_not_analyzed" for d in first.diagnostics))
        validate_summary(build_summary(first))

    def test_rack_counts_do_not_change_ordinary_module_or_controller_alias_counts(self) -> None:
        body = module('<RackConnection><InAliasTag/><OutAliasTag/></RackConnection>',
                      '<Connection Name="Ordinary"><InputTag/><OutputTag/></Connection>')
        body += '<Tags><Tag Name="Probe" TagType="Alias" AliasFor="Unverified:I"/></Tags>'
        result = inventory(body)
        expected = {"modules": 1, "module_connections": 1, "module_input_tags": 1, "module_output_tags": 1,
                    "module_rack_connections": 1, "module_rack_input_aliases": 1, "module_rack_output_aliases": 1,
                    "aliases": 1, "total_tag_definitions": 1, "controller_tags": 1}
        for key, count in expected.items():
            self.assertEqual(result.counts[key], count, key)

    def test_only_full_supported_parent_roles_capture_rack_declarations(self) -> None:
        rack = '<RackConnection><InAliasTag/><OutAliasTag/></RackConnection>'
        wrong_contexts = (
            '<Vendor>' + module(rack) + '</Vendor>',
            '<Modules><Module Name="M"><Connections>' + rack + '</Connections></Module></Modules>',
            '<Communications><Connections>' + rack + '</Connections></Communications>',
            module('<Connection Name="Ordinary">' + rack + '</Connection>'),
            module('<Vendor>' + rack + '</Vendor>'),
        )
        for body in wrong_contexts:
            with self.subTest(body=body):
                result = inventory(body)
                self.assertFalse(any(e.kind in RACK_KINDS for e in result.entities))
                self.assertTrue(all(result.counts[key] == 0 for key in RACK_COUNT_KEYS))
                self.assertIn("module_rack_connection_not_analyzed", {d.code for d in result.diagnostics})
                self.assertNotIn("module_rack_backing_not_analyzed", {d.code for d in result.diagnostics})
                self.assertTrue(any(row["path"].endswith("/InAliasTag")
                                    for row in result.coverage["unmodeled_xml_paths"]))

    def test_alias_children_require_direct_rack_parent_and_unknown_subcontent_stays_unmodeled(self) -> None:
        result = inventory(module('<RackConnection><InAliasTag><Data><Value>PRIVATE_DATA</Value></Data>'
                                  '</InAliasTag><Vendor><OutAliasTag/></Vendor><InputTag/>'
                                  '<RackConnection><InAliasTag/></RackConnection></RackConnection>'))
        self.assertEqual(result.counts["module_rack_connections"], 1)
        self.assertEqual(result.counts["module_rack_input_aliases"], 1)
        self.assertEqual(result.counts["module_rack_output_aliases"], 0)
        self.assertEqual(result.counts["module_input_tags"], 0)
        paths = {row["path"] for row in result.coverage["unmodeled_xml_paths"]}
        self.assertTrue(any(path.endswith("/InAliasTag/Data/Value") for path in paths))
        self.assertTrue(any(path.endswith("/Vendor/OutAliasTag") for path in paths))
        self.assertTrue(any(path.endswith("/RackConnection/RackConnection/InAliasTag") for path in paths))
        self.assertNotIn("PRIVATE_DATA", render_summary(build_summary(result)))

    def test_empty_inventory_has_all_rack_counts_zero(self) -> None:
        result = inventory("")
        self.assertTrue(all(result.counts[key] == 0 for key in RACK_COUNT_KEYS))
        self.assertEqual(result.status, "complete")
        self.assertEqual(build_summary(result)["schema_version"], 4)

    def test_aggregate_contains_only_new_counts_and_fixed_warning_vocabulary(self) -> None:
        result = inventory(module('<RackConnection Private="PRIVATE_VALUE"><InAliasTag Name="PRIVATE_INPUT"/>'
                                  '<OutAliasTag AliasFor="PRIVATE_TARGET"/></RackConnection>'))
        report = build_summary(result)
        self.assertEqual(report["schema_version"], 4)
        self.assertEqual(report["exporter_version"], "aggregate-summary-4")
        self.assertEqual(report["parser_version"], "source-inventory-3")
        self.assertEqual(report["diagnostics"]["by_code"], {"module_rack_backing_not_analyzed": 1, "withheld": 0})
        rendered = render_summary(report)
        self.assertNotIn("PRIVATE_", rendered)
        self.assertNotIn(result.snapshot["sha256"], rendered)

    def test_current_aggregate_rejects_missing_or_impossible_rack_counts(self) -> None:
        original = build_summary(inventory(module('<RackConnection><InAliasTag/><OutAliasTag/></RackConnection>')))
        for mutate in (
            lambda report: report["counts"].pop("module_rack_connections"),
            lambda report: report["counts"].update(module_rack_connections=0),
            lambda report: report["counts"].update(modules=0),
            lambda report: report["counts"].update(module_rack_input_aliases=True),
            lambda report: report["counts"].update(module_rack_output_aliases=-1),
        ):
            value = deepcopy(original)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(SummaryError):
                validate_summary(value)

    def test_rack_only_aggregate_cannot_remove_or_relabel_mandatory_backing_warning(self) -> None:
        original = build_summary(inventory(module('<RackConnection/>')))
        self.assertEqual(original['counts']['module_rack_connections'], 1)
        self.assertEqual(original['counts']['module_rack_input_aliases'], 0)
        self.assertEqual(original['counts']['module_rack_output_aliases'], 0)
        self.assertEqual(original['status'], 'partial')
        for status in ('partial', 'complete'):
            removed = deepcopy(original)
            removed['status'] = status
            removed['diagnostics'] = {'total': 0, 'by_code': {'withheld': 0},
                                      'by_severity': {'info': 0, 'warning': 0, 'error': 0, 'withheld': 0}}
            with self.subTest(status=status, mutation='removed'), self.assertRaises(SummaryError):
                validate_summary(removed)
            relabeled = deepcopy(original)
            relabeled['status'] = status
            relabeled['diagnostics']['by_severity'].update(warning=0, info=1)
            with self.subTest(status=status, mutation='relabeled'), self.assertRaises(SummaryError):
                validate_summary(relabeled)
        extra_warning = deepcopy(original)
        extra_warning['diagnostics']['by_code']['module_rack_backing_not_analyzed'] = 2
        extra_warning['diagnostics']['by_severity']['warning'] = 2
        extra_warning['diagnostics']['total'] = 2
        with self.assertRaises(SummaryError):
            validate_summary(extra_warning)

    def test_historical_v2_v3_summaries_validate_without_new_fields_or_diagnostics(self) -> None:
        current = build_summary(inventory(""))
        for version in (2, 3):
            old = earlier_summary(current, version)
            validate_summary(old)
            self.assertEqual(json.loads(render_summary(old)), old)
            added_count = deepcopy(old)
            added_count["counts"]["module_rack_connections"] = 0
            with self.assertRaises(SummaryError):
                validate_summary(added_count)
            for code in ("module_rack_backing_not_analyzed", "module_rack_content_not_analyzed"):
                added_warning = deepcopy(old)
                added_warning["diagnostics"]["by_code"][code] = 0
                with self.subTest(code=code), self.assertRaises(SummaryError):
                    validate_summary(added_warning)
            wrong_version = deepcopy(old)
            wrong_version["parser_version"] = "source-inventory-3"
            with self.assertRaises(SummaryError):
                validate_summary(wrong_version)
        old_v3 = earlier_summary(current, 3)
        old_v3["status"] = "partial"
        old_v3["diagnostics"] = {"total": 1, "by_code": {"module_rack_connection_not_analyzed": 1, "withheld": 0},
                                 "by_severity": {"info": 0, "warning": 1, "error": 0, "withheld": 0}}
        validate_summary(old_v3)
        old_v2 = earlier_summary(old_v3 | {"counts": current["counts"]}, 2)
        with self.assertRaises(SummaryError):
            validate_summary(old_v2)

    def test_publisher_requires_current_private_inventory_contract(self) -> None:
        source = inventory("")
        for schema, parser in ((1, "source-inventory-1"), (2, "source-inventory-2"), (2, "source-inventory-3")):
            with self.subTest(schema=schema, parser=parser), self.assertRaises(SummaryError):
                build_summary(replace(source, schema_version=schema, parser_version=parser))


if __name__ == "__main__":
    unittest.main()
