"""Run local parser checks and analysis using the already checked-out code.

Source exports, saved engineering records and raw test output remain private.
Feedback reports include counts and one immutable, bounded request for scrubbed
whole-rung examples, committed locally for manual review and pushing.
This workflow never fetches, pulls or pushes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback
from typing import Any
from uuid import uuid4

from .access import analyze_access
from .calculations import analyze_calculations
from .calculation_paths import analyze_calculation_paths
from .output_context import analyze_output_context
from .stateful_objects import analyze_stateful_objects
from .sfc_conditions import analyze_sfc_conditions
from .sfc_condition_summary import build_sfc_condition_summary, validate_sfc_condition_summary
from .stateful_object_summary import build_stateful_object_summary, validate_stateful_object_summary
from .output_context_summary import build_output_context_summary, validate_output_context_summary
from .calculation_path_summary import build_calculation_path_summary, validate_calculation_path_summary
from .rung_analysis import analyze_rungs
from .rung_analysis_summary import build_rung_summary, validate_rung_summary
from .relationships import analyze_relationships
from .relationship_summary import build_relationship_summary, validate_relationship_summary
from .conditions import analyze_conditions
from .condition_summary import build_condition_summary, validate_condition_summary
from .binding_context import analyze_binding_context
from .custom_instruction_context import analyze_custom_instruction_context
from .custom_instruction_summary import build_custom_instruction_summary, validate_custom_instruction_summary
from .indexed_access import analyze_indexed_access
from .sfr_context import analyze_sfr_context
from .sfr_summary import build_sfr_summary, validate_sfr_summary
from .aoi_body_context import analyze_aoi_body_context
from .aoi_body_summary import build_aoi_body_summary, validate_aoi_body_summary
from .indexed_access_summary import build_indexed_access_summary, validate_indexed_access_summary
from .binding_context_summary import build_binding_context_summary, validate_binding_context_summary
from .calculation_summary import build_calculation_summary, validate_calculation_summary
from .access_summary import build_access_summary, validate_access_summary
from .diagnostic_sample import (
    MALFORMED_SAMPLE_KIND, UNMATCHED_COLON_SAMPLE_KIND,
    build_diagnostic_sample, validate_diagnostic_sample,
)
from .pid import analyze_pid
from .pid_summary import build_pid_summary, validate_pid_summary
from .pid_members import analyze_pid_members
from .pid_member_summary import build_pid_member_summary, validate_pid_member_summary
from .pid_connections import analyze_pid_connections
from .pid_connection_summary import build_pid_connection_summary, validate_pid_connection_summary
from .reference_summary import build_reference_summary, validate_reference_summary
from .references import _system_flag, _timer_placeholder, analyze_references
from .source import analyze_snapshot, capture_snapshot
from .storage import StorageError, save_run
from .tag_data import analyze_tag_data
from .tag_data_summary import build_tag_data_summary, validate_tag_data_summary
from .work_check_tests import unavailable_result, validate_test_result
from .targeted_samples import build_targeted_samples
from .targeted_sample_history import resolve_targeted_samples, sample_envelope, validate_sample_envelope

MAX_REPORT_BYTES = 32 * 1024
MAX_REPORT_V22_BYTES = 48 * 1024
MAX_REPORT_V28_BYTES = 64 * 1024
# Work32 reserves the new closed summary plus the unchanged full sample envelope.
MAX_REPORT_V32_BYTES = 80 * 1024
_LEGACY_CONSTANTS = {
    "schema_version": 1,
    "report_kind": "l5x_work_machine_check",
    "workflow_version": "work-check-1",
}
_V2_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 2, "workflow_version": "work-check-2"}
_V3_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 3, "workflow_version": "work-check-3"}
_V4_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 4, "workflow_version": "work-check-4"}
_V5_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 5, "workflow_version": "work-check-5"}
_V6_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 6, "workflow_version": "work-check-6"}
_V7_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 7, "workflow_version": "work-check-7"}
_V8_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 8, "workflow_version": "work-check-8"}
_V9_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 9, "workflow_version": "work-check-9"}
_V10_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 10, "workflow_version": "work-check-10"}
_V11_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 11, "workflow_version": "work-check-11"}
_V12_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 12, "workflow_version": "work-check-12"}
_V13_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 13, "workflow_version": "work-check-13"}
_V14_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 14, "workflow_version": "work-check-14"}
_V15_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 15, "workflow_version": "work-check-15"}
_V16_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 16, "workflow_version": "work-check-16"}
_V17_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 17, "workflow_version": "work-check-17"}
_V18_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 18, "workflow_version": "work-check-18"}
_V19_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 19, "workflow_version": "work-check-19"}
_V20_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 20, "workflow_version": "work-check-20"}
_V21_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 21, "workflow_version": "work-check-21"}
_V22_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 22, "workflow_version": "work-check-22"}
_V23_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 23, "workflow_version": "work-check-23"}
_V24_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 24, "workflow_version": "work-check-24"}
_V25_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 25, "workflow_version": "work-check-25"}
_V26_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 26, "workflow_version": "work-check-26"}
_V27_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 27, "workflow_version": "work-check-27"}
_V28_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 28, "workflow_version": "work-check-28"}
_V29_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 29, "workflow_version": "work-check-29"}
_V30_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 30, "workflow_version": "work-check-30"}
_V31_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 31, "workflow_version": "work-check-31"}
_V32_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 32, "workflow_version": "work-check-32"}
_V33_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 33, "workflow_version": "work-check-33"}
_V34_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 34, "workflow_version": "work-check-34"}
_V35_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 35, "workflow_version": "work-check-35"}
_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 36, "workflow_version": "work-check-36"}
_FAILURE_CODES = {"read_error", "reference_error", "save_error", "summary_error", "unexpected_error"}
_SAVE_FAILURE_CODES = frozenset({
    "review_size_limit", "review_validation_error", "review_render_error",
    "save_io_error", "save_workspace_error",
})
_GIT_REPOSITORY_OVERRIDES = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_IMPLICIT_WORK_TREE", "GIT_PREFIX",
    "GIT_NAMESPACE", "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE",
})


class WorkCheckError(ValueError):
    """A fixed workflow error safe to show without raw process or source text."""


def _invalid() -> None:
    raise WorkCheckError("Work-machine report validation failed.")


def _keys(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or value.keys() != expected:
        _invalid()


def _extended_access_populations(coverage: dict[str, Any], nested: dict[str, Any],
                                *, calculation_occurrences: int = 0,
                                pid_occurrences: int = 0) -> tuple[int, int, int]:
    """Bound new access overlays against unchanged source/reference populations.

    Every extended instruction remains unsupported in reference6. Its operand
    rows must therefore come from that population, not from previously bound
    rows. Case variants share one pooled source allowance across these families
    and timers, so a withheld occurrence cannot satisfy two capacity deficits.
    Work21 also shares that allowance with CPT and PID, whose legacy reference
    slots were already catalogued and do not consume the extended-row population.
    Their full occurrence counts include unresolved signatures: those source
    instructions still consume one opcode occurrence each.
    """
    extended = coverage["extended_instructions"]
    counter = extended["counter"]
    message = extended["message"]
    system_get, system_set = extended["system_get"], extended["system_set"]
    reset_step, reset_initial = extended["sfc_reset_step"], extended["sfc_reset_initial"]
    total = sum(extended.values())
    non_data = 2 * counter + 3 * (system_get + system_set) + reset_step + 2 * reset_initial
    data = counter + message + system_get + system_set + reset_step
    invalid_counter = coverage["counter_invalid_forms"]
    invalid_timer = coverage["instructions_by_status"]["unsupported_operand_form"] - invalid_counter
    reference_coverage = nested["coverage"]
    source_opcodes = nested["source_summary"]["instructions"]["counts"]
    required = (
        (coverage["timer_instructions"] + invalid_timer, ("TON", "TOF", "RTO")),
        (counter + invalid_counter, ("CTU", "CTD")),
        (message, ("MSG",)),
        (system_get, ("GSV",)),
        (system_set, ("SSV",)),
        (reset_step + reset_initial, ("SFR",)),
        (calculation_occurrences, ("CPT",)),
        (pid_occurrences, ("PID",)),
    )
    pooled_needed = sum(max(0, count - sum(source_opcodes.get(opcode, 0) for opcode in opcodes))
                        for count, opcodes in required)
    if (invalid_timer < 0
            or total + invalid_counter > reference_coverage["instructions_total"] - reference_coverage["instructions_catalogued"]
            or non_data + data + 3 * invalid_counter > nested["operands"]["by_status"]["unsupported_instruction"]
            or coverage["extended_bound_operands"] > data
            or pooled_needed > source_opcodes.get("withheld", 0)):
        _invalid()
    return total, non_data, invalid_counter


def validate_work_check_report(report: Any) -> None:
    """Reject unknown fields and reconcile test, analysis and overall status."""
    if type(report) is not dict or type(report.get("schema_version")) is not int:
        _invalid()
    version = report["schema_version"]
    constants = {1: _LEGACY_CONSTANTS, 2: _V2_CONSTANTS, 3: _V3_CONSTANTS,
                 4: _V4_CONSTANTS, 5: _V5_CONSTANTS, 6: _V6_CONSTANTS, 7: _V7_CONSTANTS, 8: _V8_CONSTANTS, 9: _V9_CONSTANTS, 10: _V10_CONSTANTS, 11: _V11_CONSTANTS, 12: _V12_CONSTANTS, 13: _V13_CONSTANTS, 14: _V14_CONSTANTS, 15: _V15_CONSTANTS, 16: _V16_CONSTANTS, 17: _V17_CONSTANTS, 18: _V18_CONSTANTS, 19: _V19_CONSTANTS, 20: _V20_CONSTANTS, 21: _V21_CONSTANTS, 22: _V22_CONSTANTS, 23: _V23_CONSTANTS, 24: _V24_CONSTANTS, 25: _V25_CONSTANTS, 26: _V26_CONSTANTS, 27: _V27_CONSTANTS, 28: _V28_CONSTANTS, 29: _V29_CONSTANTS, 30: _V30_CONSTANTS, 31: _V31_CONSTANTS, 32: _V32_CONSTANTS, 33: _V33_CONSTANTS, 34: _V34_CONSTANTS, 35: _V35_CONSTANTS, 36: _CONSTANTS}.get(version)
    if constants is None:
        _invalid()
    extra = ({"diagnostic_sample"} if version >= 2 else set()) | ({"targeted_samples"} if version >= 28 else set())
    _keys(report, set(constants) | {"run_id", "tool_revision", "tests", "analysis", "status"} | extra)
    for key, fixed in constants.items():
        if type(report[key]) is not type(fixed) or report[key] != fixed:
            _invalid()
    if type(report["run_id"]) is not str or re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", report["run_id"]) is None:
        _invalid()
    revision = report["tool_revision"]
    _keys(revision, {"commit", "worktree"})
    if (type(revision["commit"]) is not str or re.fullmatch(r"[0-9a-f]{40}", revision["commit"]) is None
            or revision["worktree"] != "clean"):
        _invalid()
    _keys(report["tests"], {"application", "helpers"})
    for result in report["tests"].values():
        validate_test_result(result, allow_unavailable=True)
    tests_passed = all(result["status"] == "passed" for result in report["tests"].values())
    analysis = report["analysis"]
    _keys(analysis, {"status", "failure_code", "private_run_saved", "reference_summary"}
          | ({"sfc_structure_summary"} if version >= 11 else set())
          | ({"access_summary"} if version >= 13 else set())
          | ({"tag_data_summary"} if version >= 15 else set())
          | ({"pid_summary"} if version >= 16 else set())
          | ({"pid_member_summary"} if version >= 17 else set())
          | ({"calculation_summary"} if version >= 18 else set())
          | ({"rung_analysis_summary"} if version >= 22 else set())
          | ({"relationship_summary"} if version >= 23 else set())
          | ({"condition_summary"} if version >= 24 else set())
          | ({"binding_context_summary"} if version >= 27 else set())
          | ({"custom_instruction_summary", "indexed_access_summary"} if version >= 29 else set())
          | ({"sfr_summary"} if version >= 30 else set())
          | ({"aoi_body_summary"} if version >= 31 else set())
          | ({"pid_connection_summary"} if version >= 32 else set())
          | ({"calculation_path_summary"} if version >= 33 else set())
          | ({"output_context_summary"} if version >= 34 else set())
          | ({"stateful_object_summary"} if version >= 35 else set())
          | ({"sfc_condition_summary"} if version >= 36 else set()))
    if type(analysis["private_run_saved"]) is not bool or type(analysis["status"]) is not str:
        _invalid()
    if analysis["status"] in ("complete", "partial"):
        if not tests_passed or analysis["failure_code"] is not None or not analysis["private_run_saved"]:
            _invalid()
        nested = analysis["reference_summary"]
        validate_reference_summary(nested)
        if version >= 3 and nested["schema_version"] != {3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 12, 12: 12, 13: 12, 14: 12, 15: 12, 16: 12, 17: 12, 18: 12, 19: 12, 20: 12, 21: 12, 22: 12, 23: 12, 24: 12, 25: 12, 26: 12, 27: 12, 28: 12, 29: 12, 30: 12, 31: 12, 32: 12, 33: 12, 34: 12, 35: 12, 36: 12}[version]:
            _invalid()
        expected_analysis = nested["status"]
        if version >= 11:
            from .sfc_summary import validate_sfc_summary
            sfc = analysis["sfc_structure_summary"]
            validate_sfc_summary(sfc)
            if (sfc["schema_version"] != {11: 1, 12: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 2, 18: 2, 19: 2, 20: 2, 21: 2, 22: 2, 23: 2, 24: 2, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2, 30: 2, 31: 2, 32: 2, 33: 2, 34: 2, 35: 2, 36: 2}[version]
                    or sfc["tool_revision"] != revision
                    or sfc["source_sfc_routines"] != nested["source_summary"]["routine_types"]["SFC"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (nested["status"], sfc["status"]) else "complete"
        if version >= 13:
            access = analysis["access_summary"]
            validate_access_summary(access)
            coverage = access["coverage"]
            reference_coverage = nested["coverage"]
            if access["schema_version"] != (4 if version >= 21 else 3 if version >= 20 else 2 if version >= 14 else 1):
                _invalid()
            integer_pseudo_operands = 0
            unsupported_timer_forms = 0
            extended_instructions = extended_non_data = extended_bound = 0
            counter_invalid_forms = 0
            if version >= 20:
                # Validate companion summaries before using their full occurrence
                # counts to constrain the shared withheld-opcode population.
                calculation_occurrences = pid_occurrences = 0
                if version >= 21:
                    validate_calculation_summary(analysis["calculation_summary"])
                    calculation_occurrences = analysis["calculation_summary"]["coverage"]["occurrences_total"]
                    validate_pid_summary(analysis["pid_summary"])
                    pid_occurrences = analysis["pid_summary"]["coverage"]["occurrences_total"]
                extended_instructions, extended_non_data, counter_invalid_forms = _extended_access_populations(
                    coverage, nested, calculation_occurrences=calculation_occurrences,
                    pid_occurrences=pid_occurrences)
                extended_bound = coverage["extended_bound_operands"]
            if version >= 14:
                pseudo_operands = coverage["timer_pseudo_operands_by_kind"]
                integer_pseudo_operands = pseudo_operands["integer_literal"]
                unsupported_timer_forms = coverage["instructions_by_status"]["unsupported_operand_form"] - counter_invalid_forms
                source_opcodes = nested["source_summary"]["instructions"]["counts"]
                # Source4 preserves case and pools non-public spellings, while
                # access accepts ASCII case variants. This is a capacity bound,
                # not evidence that every withheld instruction is a timer.
                timer_capacity = sum(source_opcodes.get(opcode, 0) for opcode in ("TON", "TOF", "RTO", "withheld"))
                if (coverage["timer_instructions"] + unsupported_timer_forms > timer_capacity
                        or pseudo_operands["placeholder"] > nested["operands"]["by_status"]["non_data"]
                        or integer_pseudo_operands > nested["operands"]["by_status"]["literal"]):
                    _invalid()
            if (access["tool_revision"] != revision
                    or coverage["instructions_total"] != reference_coverage["instructions_total"]
                    or coverage["instructions_total"] != nested["source_summary"]["counts"]["instructions"]
                    or coverage["instructions_by_status"]["classified"] - extended_instructions + unsupported_timer_forms > reference_coverage["instructions_catalogued"]
                    or coverage["operands_total"] != nested["operands"]["total"]
                    or coverage["operands_by_role"]["non_data"] - integer_pseudo_operands - extended_non_data > nested["operands"]["by_status"]["non_data"]
                    or coverage["source_rungs"] != reference_coverage["rungs_total"]
                    or coverage["source_rungs"] != nested["source_summary"]["counts"]["rungs"]
                    or coverage["unparsed_rungs"] != reference_coverage["rungs_total"] - reference_coverage["rungs_analyzed"]
                    or coverage["linked_operands"] != nested["operands"]["by_status"]["root_bound"] + extended_bound
                    or coverage["indexed_roots"] > nested["symbols"]["total"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, access["status"]) else "complete"
        if version >= 15:
            tag_data = analysis["tag_data_summary"]
            validate_tag_data_summary(tag_data)
            if tag_data["schema_version"] != 1 or tag_data["tool_revision"] != revision:
                _invalid()
            tag_coverage = tag_data["coverage"]
            source_counts = nested["source_summary"]["counts"]
            owner_counts = {
                "tag": source_counts["total_tag_definitions"],
                "aoi_parameter": source_counts["aoi_parameters"],
                "aoi_local_tag": source_counts["aoi_local_tags"],
                "module_input_tag": source_counts["module_input_tags"],
                "module_output_tag": source_counts["module_output_tags"],
                "module_config_tag": source_counts["module_config_tags"],
            }
            if (tag_coverage["owners_by_kind"] != owner_counts
                    or tag_coverage["owners_by_kind"] != nested["symbols"]["by_kind"]
                    or tag_coverage["owners_total"] != sum(owner_counts.values())
                    or tag_coverage["owners_total"] != nested["symbols"]["total"]
                    or tag_coverage["source_xml_elements"] != nested["source_summary"]["coverage"]["xml_elements"]
                    or tag_coverage["owners_total"] + tag_coverage["contents_total"] + tag_coverage["elements_total"] > tag_coverage["source_xml_elements"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, tag_data["status"]) else "complete"
        if version >= 16:
            pid = analysis["pid_summary"]
            validate_pid_summary(pid)
            pid_coverage = pid["coverage"]
            source = nested["source_summary"]
            reference_coverage = nested["coverage"]
            access_coverage = analysis["access_summary"]["coverage"]
            tag_coverage = analysis["tag_data_summary"]["coverage"]
            source_opcodes = source["instructions"]["counts"]
            # Public source counts preserve exact opcode case. Lowercase PID
            # spellings are pooled with other withheld opcodes, so the pooled
            # count is a capacity bound rather than extra PID evidence.
            exact_pid = source_opcodes.get("PID", 0)
            pid_capacity = exact_pid + source_opcodes.get("withheld", 0)
            if (pid["schema_version"] != 1 or pid["tool_revision"] != revision
                    or pid_coverage["source_rungs"] != reference_coverage["rungs_total"]
                    or pid_coverage["source_rungs"] != source["counts"]["rungs"]
                    or pid_coverage["source_rungs"] != access_coverage["source_rungs"]
                    or pid_coverage["unparsed_rungs"] != reference_coverage["rungs_total"] - reference_coverage["rungs_analyzed"]
                    or pid_coverage["unparsed_rungs"] != access_coverage["unparsed_rungs"]
                    or pid_coverage["source_instructions"] != reference_coverage["instructions_total"]
                    or pid_coverage["source_instructions"] != source["counts"]["instructions"]
                    or pid_coverage["source_instructions"] != access_coverage["instructions_total"]
                    or pid_coverage["source_operands"] != nested["operands"]["total"]
                    or pid_coverage["source_operands"] != access_coverage["operands_total"]
                    or not exact_pid <= pid_coverage["occurrences_total"] <= pid_capacity
                    or pid_coverage["distinct_backing_owners"] > tag_coverage["owners_total"]
                    or pid_coverage["backing_owners_with_data"] > tag_coverage["owners_with_data"]
                    or pid_coverage["backing_owners_without_data"] > tag_coverage["owners_without_data"]
                    or any(count > nested["operands"]["by_status"][status]
                           for status, count in pid_coverage["operands_by_binding"].items())):
                _invalid()
            # PID links repeat for each occurrence. A declaration used by many
            # instructions can legitimately expose the same stored records
            # repeatedly; each occurrence is still bounded by captured totals.
            linked = pid_coverage["storage_by_status"]["linked"]
            member_capacity = sum(tag_coverage["elements_by_kind"][kind]
                                  for kind in ("data_value_member", "structure_member", "array_member"))
            if (pid_coverage["representation_occurrences"]
                    > pid_coverage["occurrences_with_data"] * tag_coverage["contents_total"]
                    or pid_coverage["decorated_representation_occurrences"]
                    > (pid_coverage["occurrences_with_data"] - pid_coverage["occurrences_with_opaque_only"])
                    * tag_coverage["contents_by_format"]["decorated"]
                    or pid_coverage["structure_occurrences"]
                    > linked * tag_coverage["elements_by_kind"]["structure"]
                    or pid_coverage["direct_member_occurrences"] > linked * member_capacity):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, pid["status"]) else "complete"
        if version >= 17:
            pid_members = analysis["pid_member_summary"]
            validate_pid_member_summary(pid_members)
            member_coverage = pid_members["coverage"]
            # This companion indexes distinct captured structures and members,
            # while PID 1 repeats their links for each instruction occurrence.
            # Neither repeated links nor the field catalog create source records.
            # Every represented owner consumes at least one linked occurrence;
            # the remaining occurrences bound any one owner's repeated links.
            max_repeats = max(0, linked - member_coverage["distinct_backing_owners"] + 1)
            if (pid_members["schema_version"] != 1 or pid_members["tool_revision"] != revision
                    or member_coverage["source_pid_partial"] != int(pid["status"] == "partial")
                    or member_coverage["distinct_backing_owners"] > pid_coverage["distinct_backing_owners"]
                    or member_coverage["distinct_backing_owners"] > linked
                    or member_coverage["distinct_backing_owners"] < max(
                        0, pid_coverage["distinct_backing_owners"] - (pid_coverage["occurrences_total"] - linked))
                    or member_coverage["structures_total"] > pid_coverage["structure_occurrences"]
                    or pid_coverage["structure_occurrences"] > member_coverage["structures_total"] * max_repeats
                    or member_coverage["structures_total"] > tag_coverage["elements_by_kind"]["structure"]
                    or member_coverage["members_total"] > pid_coverage["direct_member_occurrences"]
                    or pid_coverage["direct_member_occurrences"] > member_coverage["members_total"] * max_repeats
                    or member_coverage["members_total"] > member_capacity):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, pid_members["status"]) else "complete"
        if version >= 18:
            calculations = analysis["calculation_summary"]
            validate_calculation_summary(calculations)
            calculation_coverage = calculations["coverage"]
            source = nested["source_summary"]
            reference_coverage = nested["coverage"]
            access_coverage = analysis["access_summary"]["coverage"]
            source_opcodes = source["instructions"]["counts"]
            # CPT spelling variants are counted privately and pooled in the
            # public source histogram. The withheld bucket is only capacity.
            exact_cpt = source_opcodes.get("CPT", 0)
            cpt_capacity = exact_cpt + source_opcodes.get("withheld", 0)
            if (calculations["schema_version"] != (2 if version >= 19 else 1)
                    or calculations["tool_revision"] != revision
                    or calculation_coverage["source_rungs"] != reference_coverage["rungs_total"]
                    or calculation_coverage["source_rungs"] != source["counts"]["rungs"]
                    or calculation_coverage["source_rungs"] != access_coverage["source_rungs"]
                    or calculation_coverage["unparsed_rungs"] != reference_coverage["rungs_total"] - reference_coverage["rungs_analyzed"]
                    or calculation_coverage["unparsed_rungs"] != access_coverage["unparsed_rungs"]
                    or calculation_coverage["source_instructions"] != reference_coverage["instructions_total"]
                    or calculation_coverage["source_instructions"] != source["counts"]["instructions"]
                    or calculation_coverage["source_instructions"] != access_coverage["instructions_total"]
                    or calculation_coverage["source_operands"] != nested["operands"]["total"]
                    or calculation_coverage["source_operands"] != access_coverage["operands_total"]
                    or not exact_cpt <= calculation_coverage["occurrences_total"] <= cpt_capacity
                    or calculation_coverage["destination_root_bound"] > nested["operands"]["by_status"]["root_bound"]):
                _invalid()
            # Expression leaves are additional lexical evidence. They are not
            # counted as new legacy operands and may repeat a declaration.
            if version >= 21:
                if (access_coverage["calculation_instructions"] != calculation_coverage["occurrences_by_signature"]["recognized"]
                        or access_coverage["expression_containers_by_status"] != {
                            key: calculation_coverage["expressions_by_status"][key]
                            for key in ("parsed", "unsupported")}
                        or access_coverage["expression_uses_total"] != calculation_coverage["reference_occurrences"]
                        or access_coverage["expression_uses_by_binding"] != calculation_coverage["reference_by_binding"]
                        or access_coverage["expressions_with_binding_gaps"] != calculation_coverage["expressions_with_binding_gaps"]
                        or access_coverage["expression_indexed_roots"] > nested["symbols"]["total"]
                        or access_coverage["bound_by_role"]["write"] < calculation_coverage["destination_root_bound"]):
                    _invalid()
                # CPT destinations and newly bound extended slots are disjoint
                # operand rows. Reserve the known CPT writes before allocating
                # extended bindings across their possible role populations.
                # This checks feasibility without inventing a per-family split
                # that the aggregate report does not retain.
                extended = access_coverage["extended_instructions"]
                extended_capacities = {
                    "read": extended["system_set"],
                    "write": extended["system_get"] + extended["sfc_reset_step"],
                    "read_write": extended["counter"] + extended["message"],
                }
                available_bound = dict(access_coverage["bound_by_role"])
                available_bound["write"] -= calculation_coverage["destination_root_bound"]
                available_roles = dict(access_coverage["operands_by_role"])
                available_roles["write"] -= access_coverage["calculation_instructions"]
                if any(not capacity <= available_roles[role]
                       or not 0 <= available_bound[role] <= available_roles[role]
                       for role, capacity in extended_capacities.items()):
                    _invalid()
                # Bindings beyond the remaining legacy slots must belong to
                # extended slots; conversely, extended bindings cannot exceed
                # either those slots or the remaining bound-role population.
                minimum_extended_bound = sum(
                    max(0, available_bound[role] - (available_roles[role] - capacity))
                    for role, capacity in extended_capacities.items())
                maximum_extended_bound = sum(
                    min(capacity, available_bound[role])
                    for role, capacity in extended_capacities.items())
                if not minimum_extended_bound <= access_coverage["extended_bound_operands"] <= maximum_extended_bound:
                    _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, calculations["status"]) else "complete"
        if version >= 22:
            rungs = analysis["rung_analysis_summary"]
            validate_rung_summary(rungs)
            rung_coverage = rungs["coverage"]
            access_coverage = analysis["access_summary"]["coverage"]
            ladder_totals = nested["source_summary"]["ladder_metrics"]["totals"]
            if (rungs["schema_version"] != 1 or rungs["tool_revision"] != revision
                    or rung_coverage["source_rungs"] != access_coverage["source_rungs"]
                    or rung_coverage["structures"]["unparsed"] != access_coverage["unparsed_rungs"]
                    or rung_coverage["source_instructions"] != access_coverage["instructions_total"]
                    or rung_coverage["source_operands"] != access_coverage["operands_total"]
                    or rung_coverage["branches"] != ladder_totals["branch_groups"]
                    or rung_coverage["branch_legs"] != ladder_totals["branch_legs"]
                    or rung_coverage["empty_legs"] != ladder_totals["empty_branch_legs"]
                    or rung_coverage["block_identification"]["roles_known"] != access_coverage["instructions_by_status"]["classified"]
                    or rung_coverage["block_identification"]["signature_known"] != analysis["pid_summary"]["coverage"]["occurrences_by_signature"]["recognized"]
                    or rung_coverage["expression_uses"] != access_coverage["expression_uses_total"]
                    or rung_coverage["access_gap_operands"] != access_coverage["access_gap_operands"]
                    or rung_coverage["expression_gap_uses"] != (
                        access_coverage["expression_uses_total"] - access_coverage["expression_uses_by_binding"]["root_bound"])
                    or rung_coverage["unknown_role_operands"] != access_coverage["operands_by_role"]["unknown"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, rungs["status"]) else "complete"
        if version >= 23:
            relationships = analysis["relationship_summary"]
            validate_relationship_summary(relationships)
            relationship_coverage = relationships["coverage"]
            access_coverage = analysis["access_summary"]["coverage"]
            rung_coverage = analysis["rung_analysis_summary"]["coverage"]
            series_rungs = rung_coverage["structures"]["series"]
            branched_rungs = rung_coverage["structures"]["branched"]
            empty_branched_rungs = rung_coverage["identification"]["empty"] - rung_coverage["structures"]["empty"]
            minimum_branched_instructions = (relationship_coverage["source_instructions"] if not series_rungs
                                            else branched_rungs - empty_branched_rungs)
            if (relationships["schema_version"] != 1 or relationships["tool_revision"] != revision
                    or relationship_coverage["source_rungs"] != access_coverage["source_rungs"]
                    or relationship_coverage["source_instructions"] != access_coverage["instructions_total"]
                    or relationship_coverage["source_operands"] != access_coverage["operands_total"]
                    or relationship_coverage["expression_uses"] != access_coverage["expression_uses_total"]
                    or relationship_coverage["access_gap_operands"] != access_coverage["access_gap_operands"]
                    or relationship_coverage["expression_gap_uses"] != (
                        access_coverage["expression_uses_total"] - access_coverage["expression_uses_by_binding"]["root_bound"])
                    or relationship_coverage["unknown_role_operands"] != access_coverage["operands_by_role"]["unknown"]
                    or any(relationship_coverage["indexed_operands_by_role"][role]
                           + relationship_coverage["rejected_operands_by_role"][role]
                           != access_coverage["bound_by_role"][role]
                           for role in ("read", "write", "read_write", "unknown"))
                    or relationship_coverage["indexed_expression_uses"] + relationship_coverage["rejected_expression_uses"]
                        != access_coverage["expression_uses_by_binding"]["root_bound"]
                    or relationship_coverage["local_link_rungs"] > series_rungs
                    or not minimum_branched_instructions <= relationship_coverage["excluded_branched_instructions"]
                        <= relationship_coverage["source_instructions"] - series_rungs
                    or (not branched_rungs and relationship_coverage["excluded_branched_instructions"])
                    or relationship_coverage["eligible_instructions"] > access_coverage["instructions_by_status"]["classified"]
                    or relationship_coverage["pattern_skips"]["unparsed"] != rung_coverage["structures"]["unparsed"]
                    or relationship_coverage["pattern_skips"]["empty"] != rung_coverage["identification"]["empty"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, relationships["status"]) else "complete"
        if version >= 24:
            conditions = analysis["condition_summary"]
            validate_condition_summary(conditions)
            if conditions["schema_version"] != (3 if version >= 30 else 2 if version >= 26 else 1):
                _invalid()
            condition_coverage = conditions["coverage"]
            access_coverage = analysis["access_summary"]["coverage"]
            rung_coverage = analysis["rung_analysis_summary"]["coverage"]
            relationship_coverage = analysis["relationship_summary"]["coverage"]
            source_opcodes = nested["source_summary"]["instructions"]["counts"]
            # Output rows include unsupported signatures; predicate and pass
            # rows require recognized signatures. Case variants consume the
            # same withheld population, never one allowance per opcode family.
            opcode_counts = (condition_coverage["output_opcodes"]
                             | condition_coverage["predicate_opcodes"]
                             | (condition_coverage["passthrough_opcodes"] if version >= 26 else {})
                             | (condition_coverage["stateful_opcodes"] if version >= 30 else {}))
            pass_count = condition_coverage["node_kinds"]["pass_through"] if version >= 26 else 0
            stateful_count = condition_coverage["node_kinds"]["stateful_transfer"] if version >= 30 else 0
            withheld_needed = sum(max(0, count - source_opcodes.get(opcode, 0))
                                  for opcode, count in opcode_counts.items())
            if (conditions["tool_revision"] != revision
                    or condition_coverage["source_rungs"] != access_coverage["source_rungs"]
                    or condition_coverage["source_instructions"] != access_coverage["instructions_total"]
                    or condition_coverage["source_operands"] != access_coverage["operands_total"]
                    or condition_coverage["expression_uses"] != access_coverage["expression_uses_total"]
                    or condition_coverage["rung_statuses"]["unparsed"] != rung_coverage["structures"]["unparsed"]
                    or condition_coverage["branch_joins"] != rung_coverage["branches"]
                    or condition_coverage["branch_legs"] != rung_coverage["branch_legs"]
                    or condition_coverage["node_kinds"]["predicate"] > rung_coverage["block_families"]["boolean_condition"]
                    or condition_coverage["outputs_total"] > rung_coverage["block_families"]["boolean_output"]
                    or condition_coverage["node_kinds"]["predicate"] + pass_count + stateful_count + condition_coverage["action_statuses"]["recognized"]
                        > access_coverage["instructions_by_status"]["classified"]
                    or any(count < source_opcodes.get(opcode, 0)
                           for opcode, count in condition_coverage["output_opcodes"].items())
                    or withheld_needed > source_opcodes.get("withheld", 0)
                    or condition_coverage["output_addresses"] > relationship_coverage["addresses_total"]
                    or condition_coverage["target_statuses"]["exact_address"]
                        > relationship_coverage["indexed_operands_by_role"]["write"]
                    or condition_coverage["target_statuses"]["identity_gap"]
                        > relationship_coverage["rejected_operands_by_role"]["write"]
                    or condition_coverage["target_statuses"]["unbound"]
                        > access_coverage["operands_by_role"]["write"] - access_coverage["bound_by_role"]["write"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, conditions["status"]) else "complete"
        if version >= 27:
            context = analysis["binding_context_summary"]
            validate_binding_context_summary(context)
            context_coverage = context["coverage"]
            access_coverage = analysis["access_summary"]["coverage"]
            condition_coverage = analysis["condition_summary"]["coverage"]
            relationship_coverage = analysis["relationship_summary"]["coverage"]
            rack = nested["rack_candidates"]
            unique_rack_operands = sum(rack["matches"][kind]["by_status"]["unique_candidate"]
                                       for kind in ("direct_operands", "alias_operands"))
            rack_categories = {
                "rack_ambiguous_candidate": "ambiguous_candidate",
                "rack_names_unavailable": "candidate_names_unavailable",
                "rack_outside_scope": "outside_visible_scope",
                "rack_no_match": "no_candidate_match",
            }
            known_roles = ("read", "write", "read_write")
            if (context["schema_version"] != 1 or context["tool_revision"] != revision
                    or context_coverage["source_rungs"] != access_coverage["source_rungs"]
                    or context_coverage["source_instructions"] != access_coverage["instructions_total"]
                    or context_coverage["source_operands"] != access_coverage["operands_total"]
                    or context_coverage["expression_uses"] != access_coverage["expression_uses_total"]
                    or context_coverage["operand_binding_gaps"] != access_coverage["access_gap_operands"]
                    or context_coverage["operand_identity_gaps"] != sum(
                        relationship_coverage["rejected_operands_by_role"][role] for role in known_roles)
                    or context_coverage["expression_binding_gaps"] != (
                        access_coverage["expression_uses_total"] - access_coverage["expression_uses_by_binding"]["root_bound"])
                    or context_coverage["expression_identity_gaps"] != relationship_coverage["rejected_expression_uses"]
                    or context_coverage["predicate_gap_occurrences"] != condition_coverage["binding_gap_predicates"]
                    or context_coverage["output_gap_occurrences"] != (
                        condition_coverage["outputs_total"] - condition_coverage["target_statuses"]["exact_address"]
                        - condition_coverage["target_statuses"]["signature_unresolved"])
                    or any(context_coverage["gaps_by_role"][role] > access_coverage["operands_by_role"][role]
                           + (access_coverage["expression_uses_total"] if role == "read" else 0)
                           for role in known_roles)
                    or context_coverage["candidate_roots"] > rack["declarations"]["named"]
                    or any(context_coverage["candidate_address_directions"][direction]
                           and not rack["declarations"]["by_direction"][direction]
                           for direction in ("input", "output"))
                    or (context_coverage["candidate_address_uses"]
                        + context_coverage["gaps_by_category"]["rack_suffix_invalid"]) > unique_rack_operands
                    or any(context_coverage["gaps_by_category"][category] > sum(
                        rack["matches"][kind]["by_status"][match] for kind in ("direct_operands", "alias_operands"))
                        for category, match in rack_categories.items())):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, context["status"]) else "complete"
        if version >= 29:
            custom = analysis["custom_instruction_summary"]
            indexed = analysis["indexed_access_summary"]
            validate_custom_instruction_summary(custom)
            validate_indexed_access_summary(indexed)
            source_counts = nested["source_summary"]["counts"]
            access_counts = analysis["access_summary"]["coverage"]
            for companion in (custom, indexed):
                counts = companion["coverage"]
                if (companion["schema_version"] != 1 or companion["tool_revision"] != revision
                        or counts["source_rungs"] != access_counts["source_rungs"]
                        or counts["source_instructions"] != access_counts["instructions_total"]
                        or counts["source_operands"] != access_counts["operands_total"]):
                    _invalid()
                expected_analysis = "partial" if "partial" in (expected_analysis, companion["status"]) else "complete"
            custom_counts, indexed_counts = custom["coverage"], indexed["coverage"]
            context_counts = analysis["binding_context_summary"]["coverage"]
            known_dynamic = context_counts["gaps_by_category"]["non_static_array_index"]
            if (custom_counts["unknown_family_calls"] != analysis["rung_analysis_summary"]["coverage"]["block_families"]["unknown"]
                    or custom_counts["definitions_total"] != source_counts["aoi_definitions"]
                    or custom_counts["parameters_total"] != source_counts["aoi_parameters"]
                    or custom_counts["routines_total"] > source_counts["routines"]
                    or custom_counts["encoded_regions_total"] > source_counts["encoded_regions"]
                    or indexed_counts["expression_uses"] != access_counts["expression_uses_total"]
                    or indexed_counts["source_aliases"] != nested["aliases"]["total"]
                    # Every existing non-static gap retains an occurrence here,
                    # even when parsing or exact-element analysis is deferred.
                    # Alias declarations are additional records, never substitutes.
                    or indexed_counts["uses_by_kind"]["operand"] + indexed_counts["uses_by_kind"]["expression"] < known_dynamic
                    or indexed_counts["uses_by_kind"]["operand"] < max(0, known_dynamic - context_counts["gaps_by_kind"]["expression"])
                    or indexed_counts["uses_by_kind"]["expression"] < max(0, known_dynamic - context_counts["gaps_by_kind"]["operand"])
                    or sum(indexed_counts["uses_by_role"][role] for role in ("read", "write", "read_write")) < known_dynamic
                    or any(indexed_counts["uses_by_role"][role] > access_counts["operands_by_role"][role]
                           + (access_counts["expression_uses_total"] if role == "read" else 0)
                           + (nested["aliases"]["total"] if role == "unknown" else 0)
                           for role in ("read", "write", "read_write", "unknown", "non_data", "expression_read"))):
                _invalid()
        if version >= 30:
            sfr = analysis["sfr_summary"]
            validate_sfr_summary(sfr)
            sfr_counts = sfr["coverage"]
            access_counts = analysis["access_summary"]["coverage"]
            sfc_counts = analysis["sfc_structure_summary"]["counts"]
            source_opcodes = nested["source_summary"]["instructions"]["counts"]
            if (sfr["schema_version"] != (2 if version >= 31 else 1) or sfr["tool_revision"] != revision
                    or sfr_counts["source_rungs"] != access_counts["source_rungs"]
                    or sfr_counts["source_instructions"] != access_counts["instructions_total"]
                    or sfr_counts["source_operands"] != access_counts["operands_total"]
                    or sfr_counts["source_sfc_routines"] != analysis["sfc_structure_summary"]["source_sfc_routines"]
                    or sfr_counts["source_sfc_contents"] != sfc_counts["contents"]["total"]
                    or sfr_counts["source_sfc_steps"] != sfc_counts["elements"]["by_kind"]["step"]
                    or sfr_counts["calls_by_signature"]["classified"] != access_counts["extended_instructions"]["sfc_reset_step"] + access_counts["extended_instructions"]["sfc_reset_initial"]
                    or sfr_counts["calls_by_selector_kind"]["named"] != access_counts["extended_instructions"]["sfc_reset_step"]
                    or sfr_counts["calls_by_selector_kind"]["initial"] != access_counts["extended_instructions"]["sfc_reset_initial"]
                    or sfr_counts["calls_total"] < source_opcodes.get("SFR", 0)
                    or withheld_needed + max(0, sfr_counts["calls_total"] - source_opcodes.get("SFR", 0)) > source_opcodes.get("withheld", 0)):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, sfr["status"]) else "complete"
        if version >= 31:
            body = analysis["aoi_body_summary"]
            validate_aoi_body_summary(body)
            c = body["coverage"]
            custom_counts = analysis["custom_instruction_summary"]["coverage"]
            access_counts = analysis["access_summary"]["coverage"]
            source_counts = nested["source_summary"]["counts"]
            source_rungs = nested["source_summary"]["coverage"]["rungs"]
            if (body["schema_version"] != 1 or body["tool_revision"] != revision
                    or c["source_rungs"] != access_counts["source_rungs"]
                    or c["source_instructions"] != access_counts["instructions_total"]
                    or c["source_operands"] != access_counts["operands_total"]
                    or c["source_expression_uses"] != access_counts["expression_uses_total"]
                    or c["definitions_total"] != custom_counts["definitions_total"]
                    or c["routines_total"] != custom_counts["routines_total"]
                    or c["parameters_total"] != source_counts["aoi_parameters"]
                    or c["local_tags_total"] != source_counts["aoi_local_tags"]
                    or c["calls_total"] != custom_counts["unknown_family_calls"]
                    or c["calls_by_instance_status"]["declaration_unavailable"] != (
                        custom_counts["unknown_family_calls"] - custom_counts["calls_by_status"]["unique_candidate"])
                    or c["definitions_with_body_gaps"] < (
                        custom_counts["definitions_total"] - custom_counts["definitions_by_status"]["unique_candidate"])
                    or any(value > source_rungs[key] for key, value in c["body_rungs_by_parse_status"].items())
                    or any(value > access_counts["instructions_by_status"][key]
                           for key, value in c["body_instructions_by_access_status"].items())
                    or any(value > access_counts["operands_by_role"][key]
                           for key, value in c["body_operands_by_role"].items())):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, body["status"]) else "complete"
        if version >= 32:
            connections = analysis["pid_connection_summary"]
            validate_pid_connection_summary(connections)
            c = connections["coverage"]
            pid_counts = analysis["pid_summary"]["coverage"]
            relationship_counts = analysis["relationship_summary"]["coverage"]
            condition_counts = analysis["condition_summary"]["coverage"]
            roles = ("read", "write", "read_write", "unknown")
            uses = c["address_links_by_role"]
            if (connections["schema_version"] != 1 or connections["tool_revision"] != revision
                    or c["source_pid_partial"] != int(analysis["pid_summary"]["status"] == "partial")
                    or c["source_members_partial"] != int(analysis["pid_member_summary"]["status"] == "partial")
                    or c["occurrences_total"] != pid_counts["occurrences_total"]
                    or c["slots_total"] != pid_counts["operands_total"]
                    or c["slots_by_status"]["signature_unresolved"] != pid_counts["operands_by_slot"]["unknown"]
                    or c["masters_by_status"]["signature_unresolved"] != (
                        pid_counts["occurrences_total"] - pid_counts["occurrences_by_signature"]["recognized"])
                    or c["slots_by_status"]["literal"] > pid_counts["operands_by_binding"]["literal"]
                    or sum(c["slots_by_status"][key] for key in ("exact_address", "identity_gap", "namespace_gap"))
                        > pid_counts["operands_by_binding"]["root_bound"]
                    or c["control_by_status"]["linked"] > pid_counts["occurrences_with_backing_owner"]
                    or c["addresses_total"] > relationship_counts["addresses_total"]
                    or any(uses[role] > relationship_counts["indexed_operands_by_role"][role] for role in roles)
                    or sum(uses[role] for role in roles) + uses["namespace_gap_operand"]
                        > sum(relationship_counts["indexed_operands_by_role"].values())
                    or uses["expression_read"] + uses["namespace_gap_expression"]
                        > relationship_counts["indexed_expression_uses"]
                    or c["incoming_condition_links"] > condition_counts["node_kinds"]["opaque_transfer"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, connections["status"]) else "complete"
        if version >= 33:
            paths = analysis["calculation_path_summary"]
            validate_calculation_path_summary(paths)
            c = paths["coverage"]
            access_counts = analysis["access_summary"]["coverage"]
            relationship_counts = analysis["relationship_summary"]["coverage"]
            condition_counts = analysis["condition_summary"]["coverage"]
            source_counts = nested["source_summary"]["instructions"]["counts"]
            # Public opcode counts preserve exact spelling; lowercase and other
            # withheld spellings share one pool, not one allowance per opcode.
            if (paths["schema_version"] != 1 or paths["tool_revision"] != revision
                    or c["source_rungs"] != relationship_counts["source_rungs"]
                    or c["source_instructions"] != access_counts["instructions_total"]
                    or c["source_operands"] != access_counts["operands_total"]
                    or c["source_expression_uses"] != access_counts["expression_uses_total"]
                    or c["unparsed_rungs"] != access_counts["unparsed_rungs"]
                    or c["blocks_by_opcode"]["CPT"] != analysis["calculation_summary"]["coverage"]["occurrences_total"]
                    or any(c["blocks_by_opcode"][opcode] < source_counts.get(opcode, 0)
                           for opcode in c["blocks_by_opcode"])
                    or sum(c["blocks_by_opcode"][opcode] - source_counts.get(opcode, 0)
                           for opcode in c["blocks_by_opcode"]) > source_counts.get("withheld", 0)
                    or c["literal_input_operands"] > access_counts["unlinked_operands"]
                    or c["expression_input_operands"] > access_counts["operands_by_role"]["expression_read"]
                    or c["address_input_operands"] > relationship_counts["indexed_operands_by_role"]["read"]
                    or c["eligible_read_inputs"] > relationship_counts["indexed_operands_by_role"]["read"]
                    or c["eligible_expression_uses"] > relationship_counts["indexed_expression_uses"]
                    or c["expression_uses_total"] != access_counts["expression_uses_total"]
                    or c["preserved_predicates"] > condition_counts["node_kinds"]["predicate"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, paths["status"]) else "complete"
        if version >= 34:
            context = analysis["output_context_summary"]
            validate_output_context_summary(context)
            c = context["coverage"]
            access_counts = analysis["access_summary"]["coverage"]
            relationships = analysis["relationship_summary"]["coverage"]
            conditions = analysis["condition_summary"]["coverage"]
            rungs = analysis["rung_analysis_summary"]["coverage"]
            roles = ("read", "write", "read_write", "unknown")
            # Namespace qualification may withhold earlier associations but
            # cannot invent target identities, reader roles or condition nodes.
            if (context["schema_version"] != 1 or context["tool_revision"] != revision
                    or c["source_rungs"] != access_counts["source_rungs"]
                    or c["source_instructions"] != access_counts["instructions_total"]
                    or c["source_operands"] != access_counts["operands_total"]
                    or c["source_expression_uses"] != access_counts["expression_uses_total"]
                    or c["source_condition_nodes"] != conditions["nodes_total"]
                    or c["source_outputs"] != conditions["outputs_total"]
                    or c["outputs_total"] != conditions["outputs_total"]
                    or c["unparsed_rungs"] != access_counts["unparsed_rungs"]
                    or c["output_rungs"] != conditions["rungs_with_outputs"]
                    or c["outputs_by_opcode"] != conditions["output_opcodes"]
                    or c["guard_statuses"] != conditions["guard_statuses"]
                    or c["actions_by_status"] != conditions["action_statuses"]
                    or c["outputs_with_branches"] != conditions["outputs_with_branches"]
                    or c["outputs_with_stateful_conditions"] != conditions["outputs_with_stateful_conditions"]
                    or any(c["targets_by_status"][key] > count for key, count in conditions["target_statuses"].items())
                    or c["contexts_by_status"]["modeled"] + c["contexts_by_status"]["stateful"] > conditions["guard_statuses"]["modeled"]
                    or any(c["contexts_by_status"][key] > conditions["guard_statuses"][key] for key in ("binding_gaps", "opaque"))
                    or c["addresses_total"] > conditions["output_addresses"]
                    or any(c["accepted_operands_by_role"][role] + c["rejected_operands_by_role"][role]
                           > relationships["indexed_operands_by_role"][role] for role in roles)
                    or c["accepted_expression_uses"] + c["rejected_expression_uses"] > relationships["indexed_expression_uses"]
                    or c["condition_read_kinds"]["ons_storage"] > conditions["stateful_opcodes"]["ONS"]
                    or c["condition_read_kinds"]["predicate"] > sum(count * (1 if opcode in ("XIC", "XIO") else 3 if opcode == "LIM" else 2)
                           for opcode, count in conditions["predicate_opcodes"].items())
                    or any(c["hints_by_category"][key] + c["unqualified_hints_by_category"][key]
                           > rungs["candidate_categories"][key] for key in c["hints_by_category"])
                    or sum(c["hints_by_category"].values()) + sum(c["unqualified_hints_by_category"].values())
                           > rungs["candidate_bases"]["text_hint"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, context["status"]) else "complete"
        if version >= 35:
            stateful = analysis["stateful_object_summary"]
            validate_stateful_object_summary(stateful)
            c = stateful["coverage"]
            access_counts = analysis["access_summary"]["coverage"]
            relationship_counts = analysis["relationship_summary"]["coverage"]
            stored_counts = analysis["tag_data_summary"]["coverage"]
            source_counts = nested["source_summary"]["instructions"]["counts"]
            # Uses count object/address associations. A nested control can
            # retain the same source use under more than one candidate object.
            capacity = c["objects_total"]
            if (stateful["schema_version"] != 1 or stateful["tool_revision"] != revision
                    or c["source_rungs"] != access_counts["source_rungs"]
                    or c["source_instructions"] != access_counts["instructions_total"]
                    or c["source_operands"] != access_counts["operands_total"]
                    or c["source_expression_uses"] != access_counts["expression_uses_total"]
                    or c["source_data_elements"] != stored_counts["elements_total"]
                    or c["unparsed_rungs"] != access_counts["unparsed_rungs"]
                    or c["objects_total"] > relationship_counts["addresses_total"]
                    or c["address_uses_total"] > relationship_counts["addresses_total"] * capacity
                    or c["stored_data_total"] > stored_counts["elements_total"] * capacity
                    or c["content_links_total"] > stored_counts["contents_total"] * capacity
                    or any(c["occurrences_by_opcode"][opcode] < source_counts.get(opcode, 0)
                           for opcode in c["occurrences_by_opcode"])
                    or sum(c["occurrences_by_opcode"][opcode] - source_counts.get(opcode, 0)
                           for opcode in c["occurrences_by_opcode"]) > source_counts.get("withheld", 0)
                    or any(c["accepted_operands_by_role"][role] + c["rejected_operands_by_role"][role]
                           > relationship_counts["indexed_operands_by_role"][role] * capacity
                           for role in ("read", "write", "read_write", "unknown"))
                    or c["accepted_expression_uses"] + c["rejected_expression_uses"]
                           > relationship_counts["indexed_expression_uses"] * capacity):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, stateful["status"]) else "complete"
        if version >= 36:
            sequence = analysis["sfc_condition_summary"]
            validate_sfc_condition_summary(sequence)
            c = sequence["coverage"]
            source = analysis["sfc_structure_summary"]["counts"]
            if (sequence["schema_version"] != 1 or sequence["tool_revision"] != revision
                    or c["source_routines"] != source["routines"]["total"]
                    or c["source_contents"] != source["contents"]["total"]
                    or c["source_elements"] != source["elements"]["total"]
                    or c["source_st_lines"] != source["structured_text"]["lines"]
                    or c["transitions_total"] != source["elements"]["by_kind"]["transition"]
                    or c["expression_chars"] > source["structured_text"]["total_characters"] + c["line_spans_total"]):
                _invalid()
            expected_analysis = "partial" if "partial" in (expected_analysis, sequence["status"]) else "complete"
        if expected_analysis != analysis["status"] or nested["source_summary"]["tool_revision"] != revision:
            _invalid()
    elif analysis["status"] == "failed":
        if (not tests_passed or type(analysis["failure_code"]) is not str
                or analysis["failure_code"] not in (_FAILURE_CODES
                    | ({"sfc_structure_error"} if version >= 11 else set())
                    | ({"access_error"} if version >= 13 else set())
                    | ({"tag_data_error"} if version >= 15 else set())
                    | ({"pid_error"} if version >= 16 else set())
                    | ({"pid_member_error"} if version >= 17 else set())
                    | ({"calculation_error"} if version >= 18 else set())
                    | ({"rung_analysis_error"} if version >= 22 else set())
                    | ({"relationship_error"} if version >= 23 else set())
                    | ({"condition_error"} if version >= 24 else set())
                    | ({"binding_context_error"} if version >= 27 else set())
                    | ({"custom_instruction_context_error", "indexed_access_error"} if version >= 29 else set())
                    | ({"sfr_context_error"} if version >= 30 else set())
                    | ({"aoi_body_context_error"} if version >= 31 else set())
                    | ({"pid_connection_error"} if version >= 32 else set())
                    | ({"calculation_path_error"} if version >= 33 else set())
                    | ({"output_context_error"} if version >= 34 else set())
                    | ({"stateful_object_error"} if version >= 35 else set())
                    | ({"sfc_condition_error"} if version >= 36 else set())
                    | (_SAVE_FAILURE_CODES if version >= 25 else set())) or analysis["reference_summary"] is not None):
            _invalid()
        if analysis["private_run_saved"] and analysis["failure_code"] not in ("summary_error", "unexpected_error"):
            _invalid()
    elif analysis["status"] == "not_run":
        if tests_passed or analysis["failure_code"] is not None or analysis["private_run_saved"] or analysis["reference_summary"] is not None:
            _invalid()
    else:
        _invalid()
    if version >= 11 and analysis["status"] in ("failed", "not_run") and analysis["sfc_structure_summary"] is not None:
        _invalid()
    if version >= 13 and analysis["status"] in ("failed", "not_run") and analysis["access_summary"] is not None:
        _invalid()
    if version >= 15 and analysis["status"] in ("failed", "not_run") and analysis["tag_data_summary"] is not None:
        _invalid()
    if version >= 16 and analysis["status"] in ("failed", "not_run") and analysis["pid_summary"] is not None:
        _invalid()
    if version >= 17 and analysis["status"] in ("failed", "not_run") and analysis["pid_member_summary"] is not None:
        _invalid()
    if version >= 18 and analysis["status"] in ("failed", "not_run") and analysis["calculation_summary"] is not None:
        _invalid()
    if version >= 22 and analysis["status"] in ("failed", "not_run") and analysis["rung_analysis_summary"] is not None:
        _invalid()
    if version >= 23 and analysis["status"] in ("failed", "not_run") and analysis["relationship_summary"] is not None:
        _invalid()
    if version >= 24 and analysis["status"] in ("failed", "not_run") and analysis["condition_summary"] is not None:
        _invalid()
    if version >= 27 and analysis["status"] in ("failed", "not_run") and analysis["binding_context_summary"] is not None:
        _invalid()
    if version >= 29 and analysis["status"] in ("failed", "not_run") and any(
            analysis[key] is not None for key in ("custom_instruction_summary", "indexed_access_summary")):
        _invalid()
    if version >= 30 and analysis["status"] in ("failed", "not_run") and analysis["sfr_summary"] is not None:
        _invalid()
    if version >= 31 and analysis["status"] in ("failed", "not_run") and analysis["aoi_body_summary"] is not None:
        _invalid()
    if version >= 32 and analysis["status"] in ("failed", "not_run") and analysis["pid_connection_summary"] is not None:
        _invalid()
    if version >= 33 and analysis["status"] in ("failed", "not_run") and analysis["calculation_path_summary"] is not None:
        _invalid()
    if version >= 34 and analysis["status"] in ("failed", "not_run") and analysis["output_context_summary"] is not None:
        _invalid()
    if version >= 35 and analysis["status"] in ("failed", "not_run") and analysis["stateful_object_summary"] is not None:
        _invalid()
    if version >= 36 and analysis["status"] in ("failed", "not_run") and analysis["sfc_condition_summary"] is not None:
        _invalid()
    expected = "failed" if not tests_passed or analysis["status"] == "failed" else (
        "partial" if analysis["status"] == "partial" else "passed"
    )
    if report["status"] != expected:
        _invalid()
    if version >= 28:
        envelope = report["targeted_samples"]
        validate_sample_envelope(envelope)
        if report["diagnostic_sample"] is not None:
            _invalid()
        if analysis["status"] in ("failed", "not_run"):
            if envelope["status"] != "not_run":
                _invalid()
        elif envelope["status"] == "not_run":
            _invalid()
        elif envelope["status"] == "selected":
            record = envelope["record"]
            source_count = analysis["binding_context_summary"]["coverage"]["source_rungs"]
            if record["source_rungs"] != source_count or record["charged_rungs"] > source_count:
                _invalid()
            found = {row['slot']: row['status'] != 'not_found' for row in record['cases']}
            context_counts = analysis['binding_context_summary']['coverage']
            dynamic = context_counts['gaps_by_category']['non_static_array_index']
            rung_counts = analysis['rung_analysis_summary']['coverage']
            condition_counts = analysis['condition_summary']['coverage']
            opcodes = analysis['reference_summary']['source_summary']['instructions']['counts']
            # The public category count includes expression leaves, whereas
            # this request deliberately selects ordinary operand gaps only.
            # Preserve an exact check when no expression gaps exist; otherwise
            # bound ordinary occurrences by the two known population sizes.
            lower = min(2, max(0, dynamic - context_counts['expression_binding_gaps']))
            upper = min(2, dynamic, context_counts['operand_binding_gaps'])
            found_dynamic = int(found['dynamic_index_1']) + int(found['dynamic_index_2'])
            if (not lower <= found_dynamic <= upper
                    or found['dynamic_index_2'] and not found['dynamic_index_1']
                    or found['unknown_block_1'] != (rung_counts['block_families']['unknown'] > 0)):
                _invalid()
            opaque_cases = int(found['opaque_ons_1']) + int(found['opaque_sfr_1'])
            missing_opcodes = sum(int(found[slot]) and opcodes.get(opcode, 0) == 0
                                  for slot, opcode in (('opaque_ons_1', 'ONS'), ('opaque_sfr_1', 'SFR')))
            historical_opaque = condition_counts['node_kinds']['opaque_transfer'] + (
                condition_counts['node_kinds']['stateful_transfer'] if version >= 30 else 0)
            if (opaque_cases > historical_opaque
                    or missing_opcodes > opcodes.get('withheld', 0)
                    or found['branched_output_1'] and (
                        not rung_counts['structures']['branched']
                        or not condition_counts['action_statuses']['recognized']
                        or not sum(condition_counts['predicate_opcodes'][opcode]
                                   for opcode in ('EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ', 'LIM')))):
                _invalid()
        # A replay is explicitly historical: never compare its immutable source
        # population with the newly analyzed export or pretend it was resampled.
    if version >= 2:
        sample = report["diagnostic_sample"]
        validate_diagnostic_sample(sample)
        if sample is not None:
            if analysis["status"] != "partial":
                _invalid()
            nested = analysis["reference_summary"]
            if nested["source_summary"]["instructions"]["counts"].get(sample["opcode"], 0) == 0:
                _invalid()
            if sample["kind"] == UNMATCHED_COLON_SAMPLE_KIND:
                # This fallback needs dedicated rack evidence. Historical v2
                # reports retain their original malformed-only sample contract.
                if ((version, nested["schema_version"]) not in {(3, 5), (4, 6), (5, 7), (6, 8), (7, 9), (8, 10), (9, 11), (10, 12), (11, 12), (12, 12), (13, 12), (14, 12), (15, 12), (16, 12), (17, 12), (18, 12), (19, 12), (20, 12), (21, 12), (22, 12), (23, 12), (24, 12), (25, 12), (26, 12), (27, 12), (28, 12)}
                        or nested["rack_candidates"]["matches"]["direct_operands"]
                        ["by_status"]["no_candidate_match"] == 0):
                    _invalid()
                # The old analyzer legitimately returned S:FS as missing. Keep
                # that historical evidence readable, but do not repeat it as a
                # mystery under the analyzer which recognizes its exact role.
                if nested["schema_version"] >= 6 and _system_flag(
                        sample["opcode"], sample["argument_index"], sample["raw_text"]):
                    _invalid()
                _report_size(report)
                return
            if sample["kind"] != MALFORMED_SAMPLE_KIND:
                _invalid()
            # Keep historical samples readable under their original analyzer,
            # but a current report cannot label a recognized slot as malformed.
            if nested["schema_version"] in {4, 5, 6, 7, 8, 9, 10, 11, 12} and _timer_placeholder(
                    sample["opcode"], sample["argument_index"], sample["raw_text"]):
                _invalid()
            operands = nested["operands"]
            # Samples are direct operands, never a caller hiding an alias-target
            # failure. Schemas 3 through 12 carry the required shape histogram.
            if (nested["schema_version"] not in {3, 4, 5, 6, 7, 8, 9, 10, 11, 12}
                    or operands["by_reason"]["unsupported_address"]["malformed_address"]
                    <= operands["malformed_address_shapes"]["alias_target_failure"]):
                _invalid()
    _report_size(report)


def _report_limit(version: int) -> int:
    if version in (32, 33, 34, 35, 36):
        return MAX_REPORT_V32_BYTES
    if version in (28, 29, 30, 31):
        return MAX_REPORT_V28_BYTES
    return MAX_REPORT_V22_BYTES if version in (22, 23, 24, 25, 26, 27) else MAX_REPORT_BYTES


def _serialize_report(report: dict[str, Any]) -> str:
    # New companions need room for the complete frozen sample reservation.
    # Work31 and later use compact whitespace; all historical render bytes stay stable.
    layout = {"separators": (",", ":")} if report["schema_version"] in (31, 32, 33, 34, 35, 36) else {"indent": 2}
    return json.dumps(report, sort_keys=True, ensure_ascii=True, **layout) + "\n"


def _report_size(report: dict[str, Any]) -> None:
    """Keep historical caps while reserving work28 space for targeted examples."""
    rendered = _serialize_report(report)
    limit = _report_limit(report["schema_version"])
    if len(rendered.encode("utf-8")) > limit:
        raise WorkCheckError("Work-machine report exceeds its publication size limit.")


def render_work_check_report(report: Any) -> str:
    validate_work_check_report(report)
    rendered = _serialize_report(report)
    if len(rendered.encode("utf-8")) > _report_limit(report["schema_version"]):
        raise WorkCheckError("Work-machine report exceeds its publication size limit.")
    return rendered


def _private_failure(path: Path, details: bytes | str | None = None) -> None:
    """Best-effort diagnostics must not prevent a count-only failure report."""
    try:
        with path.open("a", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
            if details:
                stream.write(details.decode("utf-8", errors="replace") if isinstance(details, bytes) else details)
                stream.write("\n")
    except (OSError, UnicodeError):
        pass


def _git(root: Path, *arguments: str, logs: Path | None = None, raw: bool = False) -> str:
    # Do not inherit alternate work-tree/index settings. Preserve the user's
    # normal Git configuration for local revision checks and report commits.
    environment = {key: value for key, value in os.environ.items() if key.upper() not in _GIT_REPOSITORY_OVERRIDES}
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            timeout=180, env=environment,
        )
        output = result.stdout.decode("utf-8")
        return output if raw or "-z" in arguments else output.strip()
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        if logs is not None:
            _private_failure(logs / "git.log", getattr(exc, "stderr", None))
        action = arguments[0] if arguments and arguments[0] in {
            "status", "rev-parse", "symbolic-ref", "add", "commit", "diff-tree", "show",
        } else "operation"
        message = f"Git {action} failed; existing files and commits were preserved."
        if action == "commit":
            message += " The report remains local; nothing was pushed. Check your Git identity and commit configuration."
        if logs is not None:
            message += " See git.log in the local logs folder if available."
        raise WorkCheckError(message) from exc


def _checkout_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "python-parser").is_dir():
            if Path(_git(parent, "rev-parse", "--show-toplevel")).resolve() == parent and Path.cwd().resolve() == parent:
                return parent
            break
    raise WorkCheckError("Run the work-machine launcher from its repository checkout.")


def _branch(root: Path) -> str:
    # Branch naming is a development convention, not a parser requirement.
    # symbolic-ref still rejects detached HEAD before any analysis is started.
    return _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")


def _check_pinned(root: Path, branch: str, commit: str, report_path: str | None = None) -> None:
    if _branch(root) != branch or _git(root, "rev-parse", "HEAD") != commit:
        raise WorkCheckError("The checked branch or commit changed; local results were preserved for review.")
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    allowed = {""} if report_path is None else {f"?? {report_path}\0", f"A  {report_path}\0"}
    if status not in allowed:
        raise WorkCheckError("Working-tree changes were found; local results were preserved for review.")


def _config_path(root: Path) -> Path:
    value = Path(_git(root, "rev-parse", "--git-path", "plc-work-check.json"))
    destination = root / value if not value.is_absolute() else value
    git_directory = Path(_git(root, "rev-parse", "--absolute-git-dir")).resolve()
    if destination.is_symlink() or destination.resolve() != git_directory / "plc-work-check.json":
        raise WorkCheckError("Saved-source configuration must remain in this checkout's Git directory.")
    return destination.resolve()


def _check_report_file(root: Path, relative_report: str, rendered: str) -> None:
    """Do not treat an edited file at the expected path as our validated report."""
    path = root / relative_report
    try:
        if not path.is_symlink() and path.read_bytes() == rendered.encode("utf-8"):
            return
    except OSError:
        pass
    raise WorkCheckError("Report content changed or became unavailable; local results were preserved. Review before pushing.")


def _source_path(root: Path, supplied: str | None) -> Path:
    if supplied is None:
        try:
            payload = json.loads(_config_path(root).read_text(encoding="utf-8"))
            if (type(payload) is not dict or payload.keys() != {"schema_version", "source"}
                    or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                    or type(payload["source"]) is not str):
                raise ValueError
            path = Path(payload["source"])
            if not path.is_absolute():
                raise ValueError
        except (OSError, ValueError, TypeError):
            raise WorkCheckError("No usable saved source. Run the launcher with an L5X filename or path.") from None
    else:
        path = Path(supplied).expanduser()
        if not path.is_absolute():
            path = root / "confidential" / "plc-code" / path if len(path.parts) == 1 else root / path
    try:
        source = path.resolve()
        if not source.is_file() or source.suffix.lower() != ".l5x":
            raise WorkCheckError("The selected L5X file does not exist; supply its filename or path.")
        return source
    except OSError:
        raise WorkCheckError("The selected L5X file could not be accessed.") from None


def _remember_source(root: Path, source: Path) -> None:
    destination = _config_path(root)
    descriptor, name = tempfile.mkstemp(prefix=".plc-work-check-", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema_version": 1, "source": str(source)}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _private_logs(root: Path, run_id: str) -> Path:
    destination = root / "confidential" / "work-checks" / run_id
    if destination.resolve() != destination:
        raise WorkCheckError("Private output must remain in this checkout's confidential directory.")
    destination.mkdir(parents=True, exist_ok=False)
    if destination.resolve() != destination:
        raise WorkCheckError("Private output path changed during creation.")
    return destination


def _run_suite(root: Path, logs: Path, suite: str) -> dict[str, Any]:
    output = logs / f"{suite}-tests.json"
    try:
        with (logs / f"{suite}-tests.log").open("xb") as stream:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "plc_workbench.work_check_tests", "--suite", suite, "--output", str(output)],
                cwd=root, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                check=False, timeout=1800,
            )
        if output.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError
        payload = json.loads(output.read_text(encoding="utf-8"))
        validate_test_result(payload)
        if completed.returncode != (0 if payload["status"] == "passed" else 1):
            raise ValueError
        # Reconstruct the allowed result instead of forwarding subprocess JSON.
        return {
            "schema_version": 1, "status": payload["status"],
            "counts": {key: payload["counts"][key] for key in (
                "tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes",
            )},
            "failed_test_ids": list(payload["failed_test_ids"]),
            "failure_ids_omitted": payload["failure_ids_omitted"],
        }
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return unavailable_result("runner_error")


def _analyze(root: Path, source: Path, logs: Path, revision: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "failed", "failure_code": "read_error", "private_run_saved": False,
                              "reference_summary": None, "sfc_structure_summary": None,
                              "access_summary": None, "tag_data_summary": None, "pid_summary": None,
                              "pid_member_summary": None, "calculation_summary": None, "rung_analysis_summary": None, "relationship_summary": None, "condition_summary": None,
                              "binding_context_summary": None, "custom_instruction_summary": None, "indexed_access_summary": None, "sfr_summary": None, "aoi_body_summary": None, "pid_connection_summary": None, "calculation_path_summary": None, "output_context_summary": None, "stateful_object_summary": None, "sfc_condition_summary": None,
                              "diagnostic_sample": None, "targeted_samples": sample_envelope()}
    try:
        snapshot = capture_snapshot(source)
        inventory = analyze_snapshot(snapshot)
        result["failure_code"] = "reference_error"
        references = analyze_references(inventory)
        from .sfc_structure import analyze_sfc_structure
        from .sfc_summary import build_sfc_summary
        result["failure_code"] = "sfc_structure_error"
        sfc_structure = analyze_sfc_structure(snapshot, inventory)
        result["failure_code"] = "calculation_error"
        calculations = analyze_calculations(snapshot, inventory, references)
        result["failure_code"] = "access_error"
        access = analyze_access(inventory, references, schema_version=4,
                                snapshot=snapshot, calculations=calculations)
        result["failure_code"] = "rung_analysis_error"
        rung_analysis = analyze_rungs(snapshot, inventory, references, access, calculations)
        result["failure_code"] = "relationship_error"
        relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rung_analysis)
        result["failure_code"] = "condition_error"
        conditions = analyze_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships,
                                        schema_version=3)
        result["failure_code"] = "binding_context_error"
        binding_context = analyze_binding_context(
            snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        companion_inputs = (snapshot, inventory, references, access, calculations,
                            rung_analysis, relationships, conditions, binding_context)
        result["failure_code"] = "custom_instruction_context_error"
        custom_context = analyze_custom_instruction_context(*companion_inputs)
        result["failure_code"] = "indexed_access_error"
        indexed_access = analyze_indexed_access(*companion_inputs)
        result["failure_code"] = "sfr_context_error"
        sfr_inputs = (snapshot, inventory, references, access, calculations, sfc_structure)
        sfr_context = analyze_sfr_context(*sfr_inputs, schema_version=2)
        result["failure_code"] = "aoi_body_context_error"
        aoi_body = analyze_aoi_body_context(*companion_inputs, custom_context)
        result["failure_code"] = "tag_data_error"
        tag_data = analyze_tag_data(snapshot, inventory)
        result["failure_code"] = "pid_error"
        pid = analyze_pid(snapshot, inventory, references, tag_data)
        result["failure_code"] = "pid_member_error"
        pid_members = analyze_pid_members(snapshot, inventory, references, tag_data, pid)
        result["failure_code"] = "pid_connection_error"
        pid_connection_inputs = (snapshot, inventory, references, access, calculations,
                                 rung_analysis, relationships, conditions, tag_data, pid, pid_members)
        pid_connections = analyze_pid_connections(*pid_connection_inputs)
        result["failure_code"] = "calculation_path_error"
        calculation_path_inputs = (snapshot, inventory, references, access, calculations,
                                   rung_analysis, relationships, conditions)
        calculation_paths = analyze_calculation_paths(*calculation_path_inputs)
        result["failure_code"] = "output_context_error"
        output_context = analyze_output_context(*calculation_path_inputs)
        result["failure_code"] = "stateful_object_error"
        stateful_inputs = (*calculation_path_inputs, tag_data)
        stateful_objects = analyze_stateful_objects(*stateful_inputs)
        result["failure_code"] = "sfc_condition_error"
        sfc_condition_inputs = (snapshot, inventory, references, sfc_structure)
        sfc_conditions = analyze_sfc_conditions(*sfc_condition_inputs)
        result["failure_code"] = "save_error"
        workspace = root / "confidential" / "workspaces" / "work-check"
        if workspace.resolve() != workspace:
            raise StorageError("Private workspace must remain inside this checkout.",
                               code="save_workspace_error")
        saved_run = save_run(workspace, snapshot, inventory, references=references,
                             sfc_structure=sfc_structure, include_review=True, access=access, tag_data=tag_data, pid=pid,
                             pid_members=pid_members, calculations=calculations, rung_analysis=rung_analysis, relationships=relationships,
                             conditions=conditions, binding_context=binding_context,
                             custom_instruction_context=custom_context, indexed_access=indexed_access, sfr_context=sfr_context, aoi_body_context=aoi_body,
                             pid_connections=pid_connections, calculation_paths=calculation_paths, output_context=output_context, stateful_objects=stateful_objects, sfc_conditions=sfc_conditions)
        # save_run returns only after finalizing the manifest. A console failure
        # afterwards must not misreport a successfully saved private run.
        result["private_run_saved"] = True
        result["failure_code"] = "unexpected_error"
        print(f"Private review report: {saved_run / 'review.html'}", flush=True)
        result["failure_code"] = "summary_error"
        summary = build_reference_summary(inventory, references, revision=revision)
        sfc_summary = build_sfc_summary(snapshot, inventory, sfc_structure, revision=revision)
        access_summary = build_access_summary(inventory, references, access, revision=revision,
                                              snapshot=snapshot, calculations=calculations)
        tag_data_summary = build_tag_data_summary(snapshot, inventory, tag_data, revision=revision)
        pid_summary = build_pid_summary(snapshot, inventory, references, tag_data, pid, revision=revision)
        pid_member_summary = build_pid_member_summary(
            snapshot, inventory, references, tag_data, pid, pid_members, revision=revision)
        calculation_summary = build_calculation_summary(snapshot, inventory, references, calculations, revision=revision)
        rung_summary = build_rung_summary(snapshot, inventory, references, access, calculations, rung_analysis, revision=revision)
        relationship_summary = build_relationship_summary(
            snapshot, inventory, references, access, calculations, rung_analysis, relationships, revision=revision)
        condition_summary = build_condition_summary(
            snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions, revision=revision)
        context_summary = build_binding_context_summary(
            snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions,
            binding_context, revision=revision)
        custom_summary = build_custom_instruction_summary(*companion_inputs, custom_context, revision=revision)
        indexed_summary = build_indexed_access_summary(*companion_inputs, indexed_access, revision=revision)
        sfr_summary = build_sfr_summary(*sfr_inputs, sfr_context, revision=revision)
        aoi_summary = build_aoi_body_summary(*companion_inputs, custom_context, aoi_body, revision=revision)
        pid_connection_summary = build_pid_connection_summary(
            *pid_connection_inputs, pid_connections, revision=revision)
        calculation_path_summary = build_calculation_path_summary(
            *calculation_path_inputs, calculation_paths, revision=revision)
        output_summary = build_output_context_summary(
            *calculation_path_inputs, output_context, revision=revision)
        stateful_summary = build_stateful_object_summary(
            *stateful_inputs, stateful_objects, revision=revision)
        sfc_condition_summary = build_sfc_condition_summary(
            *sfc_condition_inputs, sfc_conditions, revision=revision)
        # Current releases use the durable targeted reservation. Retain the
        # legacy field as null; its source-order raw sampler must not rotate
        # additional examples outside the new cumulative disclosure budget.
        sample = None
        status = "partial" if "partial" in (summary["status"], sfc_summary["status"], access.status,
                                           tag_data.status, pid.status, pid_members.status, calculations.status, rung_analysis.status,
                                           relationships.status, conditions.status, binding_context.status,
                                           custom_context.status, indexed_access.status, sfr_context.status, aoi_body.status, pid_connections.status, calculation_paths.status, output_context.status, stateful_objects.status, sfc_conditions.status) else "complete"
        result.update(status=status, failure_code=None, reference_summary=summary,
                      sfc_structure_summary=sfc_summary,
                      access_summary=access_summary,
                      tag_data_summary=tag_data_summary,
                      pid_summary=pid_summary,
                      pid_member_summary=pid_member_summary,
                      calculation_summary=calculation_summary,
                      rung_analysis_summary=rung_summary,
                      relationship_summary=relationship_summary,
                      condition_summary=condition_summary,
                      binding_context_summary=context_summary,
                      custom_instruction_summary=custom_summary, indexed_access_summary=indexed_summary, sfr_summary=sfr_summary, aoi_body_summary=aoi_summary,
                      pid_connection_summary=pid_connection_summary,
                      calculation_path_summary=calculation_path_summary,
                      output_context_summary=output_summary,
                      stateful_object_summary=stateful_summary,
                      sfc_condition_summary=sfc_condition_summary,
                      diagnostic_sample=sample)
        def frozen_sample_request() -> dict[str, Any]:
            # Request rung-cases-1 is permanently tied to condition2 eligibility.
            # Replays never invoke this builder; fresh checkouts still select the
            # historical six slots instead of silently changing sample policy.
            sample_conditions = analyze_conditions(
                snapshot, inventory, references, access, calculations,
                rung_analysis, relationships, schema_version=2)
            sample_context = analyze_binding_context(
                snapshot, inventory, references, access, calculations,
                rung_analysis, relationships, sample_conditions)
            return build_targeted_samples(snapshot, inventory, references, access, calculations,
                                          rung_analysis, relationships, sample_conditions, sample_context)
        result["targeted_samples"] = resolve_targeted_samples(root, frozen_sample_request)
    except Exception as exc:
        # Only our exact storage exception may refine the save stage. Do not
        # inspect arbitrary exception attributes, messages, causes or tracebacks:
        # those may contain source text, paths or attacker-controlled values.
        if result["failure_code"] == "save_error" and type(exc) is StorageError:
            code = getattr(exc, "code", None)
            if type(code) is str and code in _SAVE_FAILURE_CODES:
                result["failure_code"] = code
        # All raw exception text stays private, including OS paths and values
        # from unexpected third-party failures.
        _private_failure(logs / "analysis.log")
    return result


def run_check(root: Path, supplied_source: str | None) -> int:
    """Commit only the validated feedback report, without contacting a remote."""
    branch = _branch(root)
    commit = _git(root, "rev-parse", "HEAD")
    _check_pinned(root, branch, commit)
    source = _source_path(root, supplied_source)
    if supplied_source is not None:
        _remember_source(root, source)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    logs = _private_logs(root, run_id)
    print(f"Selected local source: {source}", flush=True)
    print(f"Local logs: {logs}", flush=True)
    results: dict[str, Any] = {}
    for suite in ("application", "helpers"):
        print(f"Running {suite} parser tests (work-machine selection)...", flush=True)
        results[suite] = _run_suite(root, logs, suite)
        result = results[suite]
        count = result["counts"]["tests_run"] if result["counts"] is not None else 0
        print(f"{suite} tests: {result['status']} ({count} run).", flush=True)
    revision = {"commit": commit, "worktree": "clean"}
    if all(result["status"] == "passed" for result in results.values()):
        print("Analyzing source and saving private results...", flush=True)
        analysis = _analyze(root, source, logs, revision)
    else:
        analysis = {"status": "not_run", "failure_code": None, "private_run_saved": False,
                    "reference_summary": None, "sfc_structure_summary": None, "access_summary": None,
                    "tag_data_summary": None, "pid_summary": None, "pid_member_summary": None, "calculation_summary": None, "rung_analysis_summary": None, "relationship_summary": None, "condition_summary": None,
                    "binding_context_summary": None, "custom_instruction_summary": None, "indexed_access_summary": None, "sfr_summary": None, "aoi_body_summary": None, "pid_connection_summary": None, "calculation_path_summary": None, "output_context_summary": None, "stateful_object_summary": None, "sfc_condition_summary": None}
    status = "failed" if analysis["status"] in ("not_run", "failed") else (
        "partial" if analysis["status"] == "partial" else "passed"
    )
    # Targeted examples are separate from the unchanged count-only summaries.
    # The historical raw sample field remains null in current reports.
    sample = analysis.pop("diagnostic_sample", None)
    targeted = analysis.pop("targeted_samples", None)
    if targeted is None:
        # Historical mocked analysis dictionaries remain usable in workflow
        # tests; no fresh selection is made without the current analysis chain.
        targeted = sample_envelope('not_run' if analysis['status'] in ('not_run', 'failed')
                                   else 'unavailable', reason=None if analysis['status'] in ('not_run', 'failed')
                                   else 'selection_error')
    report = dict(_CONSTANTS, run_id=run_id, tool_revision=revision, tests=results,
                  analysis=analysis, status=status, diagnostic_sample=sample, targeted_samples=targeted)
    rendered = render_work_check_report(report)
    _check_pinned(root, branch, commit)
    relative_report = f"public/inspection/work-check-{run_id}.json"
    from .summary_output import publish_summary
    publish_summary(root / relative_report, rendered, input_path=source)
    print(f"Saved work-machine report locally: {relative_report}", flush=True)
    _check_pinned(root, branch, commit, relative_report)
    _check_report_file(root, relative_report, rendered)
    _git(root, "add", "--", relative_report, logs=logs)
    _check_pinned(root, branch, commit, relative_report)
    _check_report_file(root, relative_report, rendered)
    # Git filters can change the staged blob independently of the working file.
    if _git(root, "show", f":{relative_report}", logs=logs, raw=True) != rendered:
        raise WorkCheckError("Staged report content changed; local results were preserved. Review before pushing.")
    # --only limits the commit to this report even if another process stages
    # unrelated changes between the pin check and the commit command.
    _git(root, "commit", "--only", "-m", "test(workflow): record work-machine check",
         "--", relative_report, logs=logs)
    saved_commit = _git(root, "rev-parse", "HEAD")
    _check_pinned(root, branch, saved_commit)
    if (_git(root, "rev-parse", "HEAD^") != commit
            or _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") != relative_report):
        raise WorkCheckError("Commit history changed unexpectedly; local results were preserved. Review before pushing.")
    if _git(root, "show", f"{saved_commit}:{relative_report}", logs=logs, raw=True) != rendered:
        raise WorkCheckError("Committed report content changed; local results were preserved. Review before pushing.")
    print(f"Committed work-machine report locally: {saved_commit[:12]}", flush=True)
    print("Nothing was pulled or pushed. Review the report, then run git push when ready.", flush=True)
    print(f"Check status: {status}. Raw logs and engineering records remain under confidential/.", flush=True)
    return 1 if status == "failed" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local parser tests and analysis without automatic Git synchronization.")
    parser.add_argument("source", nargs="?", help="L5X filename under confidential/plc-code, or an explicit path. Saved locally for later runs.")
    arguments = parser.parse_args(argv)
    try:
        return run_check(_checkout_root(), arguments.source)
    except WorkCheckError as exc:
        print(str(exc), file=sys.stderr)
    except Exception:
        print("Work-machine check could not finish. Existing files and commits were preserved.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
