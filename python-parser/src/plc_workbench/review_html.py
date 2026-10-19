"""Render a private, self-contained engineering review with no network access.

Source evidence lives only in an inert JSON block. The bundled application
creates text nodes and buttons; it never treats evidence as markup or a URL.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any

MAX_REVIEW_HTML_BYTES = 80 * 1024 * 1024
MAX_REVIEW_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_REVIEW_V3_HTML_BYTES = 160 * 1024 * 1024
MAX_REVIEW_V3_PAYLOAD_BYTES = 128 * 1024 * 1024
MAX_REVIEW_V9_HTML_BYTES = 192 * 1024 * 1024
MAX_REVIEW_V9_PAYLOAD_BYTES = 160 * 1024 * 1024
MAX_REVIEW_V11_HTML_BYTES = 200 * 1024 * 1024
MAX_REVIEW_V11_PAYLOAD_BYTES = 168 * 1024 * 1024
MAX_REVIEW_V12_HTML_BYTES = 216 * 1024 * 1024
MAX_REVIEW_V12_PAYLOAD_BYTES = 184 * 1024 * 1024
MAX_REVIEW_V13_HTML_BYTES = 224 * 1024 * 1024
MAX_REVIEW_V13_PAYLOAD_BYTES = 192 * 1024 * 1024
MAX_REVIEW_V14_HTML_BYTES = 232 * 1024 * 1024
MAX_REVIEW_V14_PAYLOAD_BYTES = 200 * 1024 * 1024


class ReviewHtmlError(ValueError):
    """A source-free failure to render a bounded private report."""


class ReviewHtmlSizeLimitError(ReviewHtmlError):
    """The payload or escaped final document exceeded its versioned budget."""


def _limits(version: int) -> tuple[int, int]:
    if version == 14:
        return MAX_REVIEW_V14_PAYLOAD_BYTES, MAX_REVIEW_V14_HTML_BYTES
    if version == 13:
        return MAX_REVIEW_V13_PAYLOAD_BYTES, MAX_REVIEW_V13_HTML_BYTES
    if version == 12:
        return MAX_REVIEW_V12_PAYLOAD_BYTES, MAX_REVIEW_V12_HTML_BYTES
    if version == 11:
        return MAX_REVIEW_V11_PAYLOAD_BYTES, MAX_REVIEW_V11_HTML_BYTES
    if version in (9, 10):
        return MAX_REVIEW_V9_PAYLOAD_BYTES, MAX_REVIEW_V9_HTML_BYTES
    if version in (3, 4, 5, 6, 7, 8):
        return MAX_REVIEW_V3_PAYLOAD_BYTES, MAX_REVIEW_V3_HTML_BYTES
    return MAX_REVIEW_PAYLOAD_BYTES, MAX_REVIEW_HTML_BYTES


def _payload(data: dict[str, Any]) -> str:
    if (type(data) is not dict or type(data.get('schema_version')) is not int
            or (data.get('schema_version'), data.get('report_version')) not in
               ((1, 'engineering-review-1'), (2, 'engineering-review-2'),
                (3, 'engineering-review-3'), (4, 'engineering-review-4'),
                (5, 'engineering-review-5'), (6, 'engineering-review-6'),
                (7, 'engineering-review-7'), (8, 'engineering-review-8'),
                (9, 'engineering-review-9'), (10, 'engineering-review-10'),
                (11, 'engineering-review-11'), (12, 'engineering-review-12'), (13, 'engineering-review-13'), (14, 'engineering-review-14'))
            or (data.get('schema_version') == 1 and 'access' in data)
            or (data.get('schema_version') in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14) and type(data.get('access')) is not dict)
            or (data.get('schema_version') in (1, 2) and 'tag_data' in data)
            or (data.get('schema_version') in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14) and type(data.get('tag_data')) is not dict)
            or (data.get('schema_version') in (1, 2, 3) and 'pid' in data)
            or (data.get('schema_version') in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14) and type(data.get('pid')) is not dict)
            or (data.get('schema_version') in (1, 2, 3, 4) and 'pid_members' in data)
            or (data.get('schema_version') in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14) and type(data.get('pid_members')) is not dict)
            or (data.get('schema_version') in (1, 2, 3, 4, 5) and 'calculations' in data)
            or (data.get('schema_version') in (6, 7, 8, 9, 10, 11, 12, 13, 14) and type(data.get('calculations')) is not dict)
            or (data.get('schema_version') not in (7, 8, 9, 10, 11, 12, 13, 14) and 'rung_analysis' in data)
            or (data.get('schema_version') in (7, 8, 9, 10, 11, 12, 13, 14) and type(data.get('rung_analysis')) is not dict)
            or (data.get('schema_version') not in (8, 9, 10, 11, 12, 13, 14) and 'relationships' in data)
            or (data.get('schema_version') in (8, 9, 10, 11, 12, 13, 14) and type(data.get('relationships')) is not dict)
            or (data.get('schema_version') not in (9, 10, 11, 12, 13, 14) and 'conditions' in data)
            or (data.get('schema_version') in (9, 10, 11, 12, 13, 14) and type(data.get('conditions')) is not dict)
            or (data.get('schema_version') in (9, 10, 11, 12, 13, 14)
                and (type(data['conditions'].get('schema_version')) is not int
                     or data['conditions'].get('schema_version') != (1 if data['schema_version'] == 9 else 3 if data['schema_version'] in (13, 14) else 2)))
            or (data.get('schema_version') not in (11, 12, 13, 14) and 'binding_context' in data)
            or (data.get('schema_version') in (11, 12, 13, 14)
                and (type(data.get('binding_context')) is not dict
                     or type(data['binding_context'].get('schema_version')) is not int
                     or data['binding_context'].get('schema_version') != 1
                     or data['binding_context'].get('analyzer_version') != 'binding-context-1'))
            or (data['schema_version'] not in (12, 13, 14) and any(key in data for key in ('custom_instruction_context', 'indexed_access')))
            or (data['schema_version'] in (12, 13, 14) and any(
                type(data.get(key)) is not dict
                or type(data[key].get('schema_version')) is not int or data[key]['schema_version'] != 1
                or data[key].get('analyzer_version') != version
                for key, version in (('custom_instruction_context', 'custom-instruction-context-1'),
                                     ('indexed_access', 'indexed-access-1'))))
            or (data['schema_version'] not in (13, 14) and 'sfr_context' in data)
            or (data['schema_version'] in (13, 14) and (type(data.get('sfr_context')) is not dict
                or type(data['sfr_context'].get('schema_version')) is not int
                or data['sfr_context']['schema_version'] != (2 if data['schema_version'] == 14 else 1)
                or data['sfr_context'].get('analyzer_version') != ('sfr-context-2' if data['schema_version'] == 14 else 'sfr-context-1')))
            or (data['schema_version'] != 14 and 'aoi_body_context' in data)
            or (data['schema_version'] == 14 and (type(data.get('aoi_body_context')) is not dict
                or type(data['aoi_body_context'].get('schema_version')) is not int
                or data['aoi_body_context']['schema_version'] != 1
                or data['aoi_body_context'].get('analyzer_version') != 'aoi-body-context-1'))
            or any(type(data.get(key)) is not dict
                   for key in ('snapshot', 'inventory', 'references', 'sfc', 'statistics'))
            or any(type(data.get(key)) is not list for key in ('patterns', 'findings'))):
        raise ReviewHtmlError('Engineering review data is not supported.')
    payload_limit, html_limit = _limits(data['schema_version'])
    output = io.StringIO()
    size = escaped_size = 0
    try:
        for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).iterencode(data):
            size += len(chunk.encode('utf-8'))
            if size > payload_limit:
                raise ReviewHtmlSizeLimitError('Engineering review exceeds the report size limit.')
            # A single encoder chunk can contain a whole large source string.
            # Escape bounded slices and reject expansion before retaining it.
            for start in range(0, len(chunk), 32_768):
                escaped = (chunk[start:start + 32_768].replace('&', '\\u0026')
                           .replace('<', '\\u003c').replace('>', '\\u003e')
                           .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))
                escaped_size += len(escaped.encode('utf-8'))
                if escaped_size > html_limit:
                    raise ReviewHtmlSizeLimitError('Engineering review exceeds the report size limit.')
                output.write(escaped)
        return output.getvalue()
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        if isinstance(exc, ReviewHtmlError):
            raise
        raise ReviewHtmlError('Engineering review data could not be rendered.') from None


def _hash(value: str) -> str:
    return base64.b64encode(hashlib.sha256(value.encode('utf-8')).digest()).decode('ascii')


def render_review_html(data: dict[str, Any]) -> str:
    """Render canonical review data; the result contains proprietary evidence."""
    payload = _payload(data)
    asset_dir = Path(__file__).with_name('review_assets')
    try:
        css = (asset_dir / 'report.css').read_text(encoding='utf-8')
        script = (asset_dir / 'report.js').read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        raise ReviewHtmlError('Engineering review resources are unavailable.') from None
    policy = ("default-src 'none'; "
              f"script-src 'sha256-{_hash(script)}'; style-src 'sha256-{_hash(css)}'; "
              "connect-src 'none'; img-src 'none'; font-src 'none'; object-src 'none'; "
              "frame-src 'none'; base-uri 'none'; form-action 'none'")
    page = (_TEMPLATE.replace('__POLICY__', policy).replace('__CSS__', css)
            .replace('__APP__', script).replace('__PAYLOAD__', payload))
    _, html_limit = _limits(data['schema_version'])
    if len(page.encode('utf-8')) > html_limit:
        raise ReviewHtmlSizeLimitError('Engineering review exceeds the report size limit.')
    return page


_TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="__POLICY__">
<title>L5X engineering review</title><style>__CSS__</style></head>
<body><a class="skip-link" href="#main">Skip to review</a>
<div class="shell"><aside class="sidebar" aria-label="Report navigation">
<div class="brand"><span class="brand-mark" aria-hidden="true">L5</span>
<div><strong>L5X workbench</strong><span>Engineering review</span></div></div>
<div class="rail-label">SOURCE EXPLORER</div>
<nav id="navigation" aria-label="Review sections"></nav>
<div class="rail-foot"><span class="private-badge">PRIVATE · OFFLINE</span>
<p>This report contains source names, code and values. Keep it with your private project files.</p>
<div id="snapshot-mini"></div></div></aside>
<div class="workspace"><header class="topbar"><span>PLC migration <span aria-hidden="true">/</span> Phase 1</span>
<span class="topbar-badge">Read-only source evidence</span></header>
<main id="main" tabindex="-1"><div id="page-heading"></div>
<div id="toolbar"></div><div id="content"></div></main>
<footer>Captured source evidence. Effects, safety behavior and engineering meaning require review.</footer>
</div></div><noscript><p class="noscript">Enable JavaScript to navigate this offline report. The private JSON artifact in the same run contains the underlying evidence.</p></noscript>
<script type="application/json" id="review-data">__PAYLOAD__</script>
<script>__APP__</script></body></html>'''
