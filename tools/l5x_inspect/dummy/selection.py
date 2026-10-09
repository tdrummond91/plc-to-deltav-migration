"""Select examples without silently dropping rare local XML variants."""
from __future__ import annotations

from collections import Counter, defaultdict
from .model import Node


def opcode_names(shape: dict) -> set[str]:
    if shape["kind"] == "instruction":
        return {shape["opcode"]}
    names: set[str] = set()
    for child in shape.get("items", shape.get("legs", [])):
        names.update(opcode_names(child))
    return names


def select_nodes(nodes: list[Node], report: dict, per_variant: int) -> tuple[set[int], dict]:
    variants: dict[tuple, int] = {}
    first: dict[int, int] = {}
    by_locator = {node.locator: index for index, node in enumerate(nodes)}
    reasons: dict[int, list[str]] = defaultdict(list)

    for index, node in enumerate(nodes):
        child_runs = []
        for child in node.children:
            name = nodes[child].name
            if not child_runs or child_runs[-1] != name:
                child_runs.append(name)
        key = (node.path, node.attribute_classes, tuple(child_runs),
               node.source_text, node.cdata, node.text_action)
        node.variant = variants.setdefault(key, len(variants) + 1)
        first.setdefault(node.variant, index)
    for variant, index in first.items():
        reasons[index].append(f"first_local_variant:{variant}")

    for sample in report["samples"]:
        index = by_locator[sample["locator"]]
        reasons[index].extend(sample["selected_for"])
    # Include a representative of every encountered instruction, including masked ones.
    seen_opcodes: set[str] = set()
    rungs = {r["id"]: r for r in report["rungs"]}
    for pattern in report["patterns"]:
        new = opcode_names(pattern["shape"]) - seen_opcodes
        if new:
            record = rungs[pattern["rung_ids"][0]]
            reasons[by_locator[record["locator"]]].extend(f"instruction:{op}" for op in sorted(new))
            seen_opcodes.update(new)

    keep: set[int] = set()
    for index in reasons:
        while index is not None and index not in keep:
            keep.add(index)
            index = nodes[index].parent

    def visit(index: int, whole_rung: bool = False) -> None:
        node = nodes[index]
        keep.add(index)
        whole_rung = whole_rung or node.path.endswith("/RLLContent/Rung")
        occurrences: Counter[int] = Counter()
        for child in node.children:
            variant = nodes[child].variant
            occurrences[variant] += 1
            # First N occurrences per variant under this parent, even if interleaved.
            # Mandatory anchors are additional; full selected rungs bypass the quota.
            if whole_rung or child in keep or occurrences[variant] <= per_variant:
                visit(child, whole_rung)

    visit(0)
    return keep, {
        "per_parent_variant_limit": per_variant,
        "local_variants": len(variants),
        "retained_local_variants": len({nodes[i].variant for i in keep}),
        "mandatory_selections": [
            {"source_locator": nodes[i].locator, "reasons": values}
            for i, values in sorted(reasons.items())
        ],
        "instruction_labels_represented": sorted(seen_opcodes),
        "ranked_examples_required": len(report["samples"]),
    }
