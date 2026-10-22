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
import re
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
MAX_REVIEW_V15_HTML_BYTES = 240 * 1024 * 1024
MAX_REVIEW_V15_PAYLOAD_BYTES = 208 * 1024 * 1024
MAX_REVIEW_V16_HTML_BYTES = 248 * 1024 * 1024
MAX_REVIEW_V16_PAYLOAD_BYTES = 216 * 1024 * 1024
MAX_REVIEW_V17_HTML_BYTES = 264 * 1024 * 1024
MAX_REVIEW_V17_PAYLOAD_BYTES = 232 * 1024 * 1024
MAX_REVIEW_V18_HTML_BYTES = 280 * 1024 * 1024
MAX_REVIEW_V18_PAYLOAD_BYTES = 248 * 1024 * 1024
MAX_REVIEW_V19_HTML_BYTES = 296 * 1024 * 1024
MAX_REVIEW_V19_PAYLOAD_BYTES = 264 * 1024 * 1024
MAX_REVIEW_V20_HTML_BYTES = 312 * 1024 * 1024
MAX_REVIEW_V20_PAYLOAD_BYTES = 280 * 1024 * 1024
MAX_REVIEW_V21_HTML_BYTES = 328 * 1024 * 1024
MAX_REVIEW_V21_PAYLOAD_BYTES = 296 * 1024 * 1024
MAX_REVIEW_V22_HTML_BYTES = 360 * 1024 * 1024
MAX_REVIEW_V22_PAYLOAD_BYTES = 328 * 1024 * 1024
MAX_REVIEW_V23_HTML_BYTES = 368 * 1024 * 1024
MAX_REVIEW_V23_PAYLOAD_BYTES = 336 * 1024 * 1024
MAX_REVIEW_V24_HTML_BYTES = 376 * 1024 * 1024
MAX_REVIEW_V24_PAYLOAD_BYTES = 344 * 1024 * 1024
MAX_REVIEW_V25_HTML_BYTES = 384 * 1024 * 1024
MAX_REVIEW_V25_PAYLOAD_BYTES = 352 * 1024 * 1024
MAX_REVIEW_V26_HTML_BYTES = 392 * 1024 * 1024
MAX_REVIEW_V26_PAYLOAD_BYTES = 360 * 1024 * 1024
MAX_REVIEW_V27_HTML_BYTES = 408 * 1024 * 1024
MAX_REVIEW_V27_PAYLOAD_BYTES = 376 * 1024 * 1024
MAX_REVIEW_V28_HTML_BYTES = 416 * 1024 * 1024
MAX_REVIEW_V28_PAYLOAD_BYTES = 384 * 1024 * 1024
MAX_REVIEW_V29_HTML_BYTES = 480 * 1024 * 1024
MAX_REVIEW_V29_PAYLOAD_BYTES = 448 * 1024 * 1024
MAX_REVIEW_V30_HTML_BYTES = 488 * 1024 * 1024
MAX_REVIEW_V30_PAYLOAD_BYTES = 456 * 1024 * 1024
MAX_REVIEW_V31_HTML_BYTES = 496 * 1024 * 1024
MAX_REVIEW_V31_PAYLOAD_BYTES = 464 * 1024 * 1024
MAX_REVIEW_V32_HTML_BYTES = 496 * 1024 * 1024
MAX_REVIEW_V32_PAYLOAD_BYTES = 464 * 1024 * 1024
MAX_REVIEW_V33_HTML_BYTES = 496 * 1024 * 1024
MAX_REVIEW_V33_PAYLOAD_BYTES = 464 * 1024 * 1024
MAX_REVIEW_V34_HTML_BYTES = 504 * 1024 * 1024
MAX_REVIEW_V34_PAYLOAD_BYTES = 472 * 1024 * 1024
MAX_REVIEW_V35_HTML_BYTES = 504 * 1024 * 1024
MAX_REVIEW_V35_PAYLOAD_BYTES = 472 * 1024 * 1024


class ReviewHtmlError(ValueError):
    """A source-free failure to render a bounded private report."""


class ReviewHtmlSizeLimitError(ReviewHtmlError):
    """The payload or escaped final document exceeded its versioned budget."""


def _limits(version: int) -> tuple[int, int]:
    if version == 35:
        return MAX_REVIEW_V35_PAYLOAD_BYTES, MAX_REVIEW_V35_HTML_BYTES
    if version == 34:
        return MAX_REVIEW_V34_PAYLOAD_BYTES, MAX_REVIEW_V34_HTML_BYTES
    if version == 33:
        return MAX_REVIEW_V33_PAYLOAD_BYTES, MAX_REVIEW_V33_HTML_BYTES
    if version == 32:
        return MAX_REVIEW_V32_PAYLOAD_BYTES, MAX_REVIEW_V32_HTML_BYTES
    if version == 31:
        return MAX_REVIEW_V31_PAYLOAD_BYTES, MAX_REVIEW_V31_HTML_BYTES
    if version == 30:
        return MAX_REVIEW_V30_PAYLOAD_BYTES, MAX_REVIEW_V30_HTML_BYTES
    if version == 29:
        return MAX_REVIEW_V29_PAYLOAD_BYTES, MAX_REVIEW_V29_HTML_BYTES
    if version == 28:
        return MAX_REVIEW_V28_PAYLOAD_BYTES, MAX_REVIEW_V28_HTML_BYTES
    if version == 27:
        return MAX_REVIEW_V27_PAYLOAD_BYTES, MAX_REVIEW_V27_HTML_BYTES
    if version == 26:
        return MAX_REVIEW_V26_PAYLOAD_BYTES, MAX_REVIEW_V26_HTML_BYTES
    if version == 25:
        return MAX_REVIEW_V25_PAYLOAD_BYTES, MAX_REVIEW_V25_HTML_BYTES
    if version == 24:
        return MAX_REVIEW_V24_PAYLOAD_BYTES, MAX_REVIEW_V24_HTML_BYTES
    if version == 23:
        return MAX_REVIEW_V23_PAYLOAD_BYTES, MAX_REVIEW_V23_HTML_BYTES
    if version == 22:
        return MAX_REVIEW_V22_PAYLOAD_BYTES, MAX_REVIEW_V22_HTML_BYTES
    if version == 21:
        return MAX_REVIEW_V21_PAYLOAD_BYTES, MAX_REVIEW_V21_HTML_BYTES
    if version == 20:
        return MAX_REVIEW_V20_PAYLOAD_BYTES, MAX_REVIEW_V20_HTML_BYTES
    if version == 19:
        return MAX_REVIEW_V19_PAYLOAD_BYTES, MAX_REVIEW_V19_HTML_BYTES
    if version == 18:
        return MAX_REVIEW_V18_PAYLOAD_BYTES, MAX_REVIEW_V18_HTML_BYTES
    if version == 17:
        return MAX_REVIEW_V17_PAYLOAD_BYTES, MAX_REVIEW_V17_HTML_BYTES
    if version == 16:
        return MAX_REVIEW_V16_PAYLOAD_BYTES, MAX_REVIEW_V16_HTML_BYTES
    if version == 15:
        return MAX_REVIEW_V15_PAYLOAD_BYTES, MAX_REVIEW_V15_HTML_BYTES
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


def _payload(data: dict[str, Any], *, debug: bool = False) -> str:
    if (type(data) is not dict or type(data.get('schema_version')) is not int
            or (data.get('schema_version'), data.get('report_version')) not in
               ((1, 'engineering-review-1'), (2, 'engineering-review-2'),
                (3, 'engineering-review-3'), (4, 'engineering-review-4'),
                (5, 'engineering-review-5'), (6, 'engineering-review-6'),
                (7, 'engineering-review-7'), (8, 'engineering-review-8'),
                (9, 'engineering-review-9'), (10, 'engineering-review-10'),
                (11, 'engineering-review-11'), (12, 'engineering-review-12'), (13, 'engineering-review-13'), (14, 'engineering-review-14'), (15, 'engineering-review-15'), (16, 'engineering-review-16'), (17, 'engineering-review-17'), (18, 'engineering-review-18'), (19, 'engineering-review-19'), (20, 'engineering-review-20'), (21, 'engineering-review-21'), (22, 'engineering-review-22'), (23, 'engineering-review-23'), (24, 'engineering-review-24'), (25, 'engineering-review-25'), (26, 'engineering-review-26'), (27, 'engineering-review-27'), (28, 'engineering-review-28'), (29, 'engineering-review-29'), (30, 'engineering-review-30'), (31, 'engineering-review-31'), (32, 'engineering-review-32'), (33, 'engineering-review-33'), (34, 'engineering-review-34'), (35, 'engineering-review-35'))
            or (data.get('schema_version') == 1 and 'access' in data)
            or (data.get('schema_version') in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('access')) is not dict)
            or (data.get('schema_version') in (1, 2) and 'tag_data' in data)
            or (data.get('schema_version') in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('tag_data')) is not dict)
            or (data.get('schema_version') in (1, 2, 3) and 'pid' in data)
            or (data.get('schema_version') in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('pid')) is not dict)
            or (data.get('schema_version') in (1, 2, 3, 4) and 'pid_members' in data)
            or (data.get('schema_version') in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('pid_members')) is not dict)
            or (data.get('schema_version') in (1, 2, 3, 4, 5) and 'calculations' in data)
            or (data.get('schema_version') in (6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('calculations')) is not dict)
            or (data.get('schema_version') not in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'rung_analysis' in data)
            or (data.get('schema_version') in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('rung_analysis')) is not dict)
            or (data.get('schema_version') not in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'relationships' in data)
            or (data.get('schema_version') in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('relationships')) is not dict)
            or (data.get('schema_version') not in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'conditions' in data)
            or (data.get('schema_version') in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and type(data.get('conditions')) is not dict)
            or (data.get('schema_version') in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35)
                and (type(data['conditions'].get('schema_version')) is not int
                     or data['conditions'].get('schema_version') != (1 if data['schema_version'] == 9 else 6 if data['schema_version'] in (33, 34, 35) else 5 if data['schema_version'] == 32 else 4 if data['schema_version'] == 31 else 3 if data['schema_version'] in (13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) else 2)))
            or (data.get('schema_version') not in (11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'binding_context' in data)
            or (data.get('schema_version') in (11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35)
                and (type(data.get('binding_context')) is not dict
                     or type(data['binding_context'].get('schema_version')) is not int
                     or data['binding_context'].get('schema_version') != 1
                     or data['binding_context'].get('analyzer_version') != 'binding-context-1'))
            or (data['schema_version'] not in (12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and any(key in data for key in ('custom_instruction_context', 'indexed_access')))
            or (data['schema_version'] in (12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and any(
                type(data.get(key)) is not dict
                or type(data[key].get('schema_version')) is not int or data[key]['schema_version'] != 1
                or data[key].get('analyzer_version') != version
                for key, version in (('custom_instruction_context', 'custom-instruction-context-1'),
                                     ('indexed_access', 'indexed-access-1'))))
            or (data['schema_version'] not in (13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'sfr_context' in data)
            or (data['schema_version'] in (13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('sfr_context')) is not dict
                or type(data['sfr_context'].get('schema_version')) is not int
                or data['sfr_context']['schema_version'] != (2 if data['schema_version'] in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) else 1)
                or data['sfr_context'].get('analyzer_version') != ('sfr-context-2' if data['schema_version'] in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) else 'sfr-context-1')))
            or (data['schema_version'] not in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'aoi_body_context' in data)
            or (data['schema_version'] in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('aoi_body_context')) is not dict
                or type(data['aoi_body_context'].get('schema_version')) is not int
                or data['aoi_body_context']['schema_version'] != (2 if data['schema_version'] in (31, 32, 33, 34, 35) else 1)
                or data['aoi_body_context'].get('analyzer_version') != ('aoi-body-context-2' if data['schema_version'] in (31, 32, 33, 34, 35) else 'aoi-body-context-1')))
            or (data['schema_version'] not in (15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'pid_connections' in data)
            or (data['schema_version'] in (15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('pid_connections')) is not dict
                or type(data['pid_connections'].get('schema_version')) is not int
                or data['pid_connections']['schema_version'] != (2 if data['schema_version'] in (32, 33, 34, 35) else 1)
                or data['pid_connections'].get('analyzer_version') != ('pid-connections-2' if data['schema_version'] in (32, 33, 34, 35) else 'pid-connections-1')))
            or (data['schema_version'] not in (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'calculation_paths' in data)
            or (data['schema_version'] in (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('calculation_paths')) is not dict
                or type(data['calculation_paths'].get('schema_version')) is not int
                or data['calculation_paths']['schema_version'] != 1
                or data['calculation_paths'].get('analyzer_version') != 'calculation-paths-1'))
            or (data['schema_version'] not in (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'output_context' in data)
            or (data['schema_version'] in (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('output_context')) is not dict
                or type(data['output_context'].get('schema_version')) is not int
                or data['output_context']['schema_version'] != 1
                or data['output_context'].get('analyzer_version') != 'output-context-1'))
            or (data['schema_version'] not in (18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'stateful_objects' in data)
            or (data['schema_version'] in (18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('stateful_objects')) is not dict
                or type(data['stateful_objects'].get('schema_version')) is not int
                or data['stateful_objects']['schema_version'] != 1
                or data['stateful_objects'].get('analyzer_version') != 'stateful-objects-1'))
            or (data['schema_version'] not in (19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'sfc_conditions' in data)
            or (data['schema_version'] in (19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('sfc_conditions')) is not dict
                or type(data['sfc_conditions'].get('schema_version')) is not int
                or data['sfc_conditions']['schema_version'] != 1
                or data['sfc_conditions'].get('analyzer_version') != 'sfc-conditions-1'))
            or (data['schema_version'] not in (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'sfc_context' in data)
            or (data['schema_version'] in (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('sfc_context')) is not dict
                or type(data['sfc_context'].get('schema_version')) is not int
                or data['sfc_context']['schema_version'] != 1
                or data['sfc_context'].get('analyzer_version') != 'sfc-context-1'))
            or (data['schema_version'] not in (21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'execution_context' in data)
            or (data['schema_version'] in (21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('execution_context')) is not dict
                or type(data['execution_context'].get('schema_version')) is not int
                or data['execution_context']['schema_version'] != (3 if data['schema_version'] in (33, 34, 35) else 2 if data['schema_version'] == 32 else 1)
                or data['execution_context'].get('analyzer_version') != ('execution-context-3' if data['schema_version'] in (33, 34, 35) else 'execution-context-2' if data['schema_version'] == 32 else 'execution-context-1')))
            or (data['schema_version'] not in (22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'signal_context' in data)
            or (data['schema_version'] in (22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('signal_context')) is not dict
                or type(data['signal_context'].get('schema_version')) is not int
                or data['signal_context']['schema_version'] != (5 if data['schema_version'] in (28, 29, 30, 31, 32, 33, 34, 35) else 4 if data['schema_version'] == 27 else 3 if data['schema_version'] in (25, 26) else 2 if data['schema_version'] == 24 else 1)
                or data['signal_context'].get('analyzer_version') != ('signal-context-5' if data['schema_version'] in (28, 29, 30, 31, 32, 33, 34, 35) else 'signal-context-4' if data['schema_version'] == 27 else 'signal-context-3' if data['schema_version'] in (25, 26) else 'signal-context-2' if data['schema_version'] == 24 else 'signal-context-1')))
            or (data['schema_version'] not in (23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'file_operations' in data)
            or (data['schema_version'] in (23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('file_operations')) is not dict
                or type(data['file_operations'].get('schema_version')) is not int
                or data['file_operations']['schema_version'] != 1
                or data['file_operations'].get('analyzer_version') != 'file-operations-1'))
            or (data['schema_version'] not in (26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and 'alarm_evidence' in data)
            or (data['schema_version'] in (26, 27, 28, 29, 30, 31, 32, 33, 34, 35) and (type(data.get('alarm_evidence')) is not dict
                or type(data['alarm_evidence'].get('schema_version')) is not int
                or data['alarm_evidence']['schema_version'] != 1
                or data['alarm_evidence'].get('analyzer_version') != 'alarm-evidence-1'))
            or (data['schema_version'] not in (29, 30, 31, 32, 33, 34, 35) and 'engineering_assemblies' in data)
            or (data['schema_version'] in (29, 30, 31, 32, 33, 34, 35) and (type(data.get('engineering_assemblies')) is not dict
                or type(data['engineering_assemblies'].get('schema_version')) is not int
                or data['engineering_assemblies']['schema_version'] != (3 if data['schema_version'] == 35 else 2 if data['schema_version'] in (30, 31, 32, 33, 34, 35) else 1)
                or data['engineering_assemblies'].get('analyzer_version') != ('engineering-assemblies-3' if data['schema_version'] == 35 else 'engineering-assemblies-2' if data['schema_version'] in (30, 31, 32, 33, 34, 35) else 'engineering-assemblies-1')))
            or (data['schema_version'] not in (34, 35) and 'rack_backing_context' in data)
            or (data['schema_version'] in (34, 35) and (type(data.get('rack_backing_context')) is not dict
                or type(data['rack_backing_context'].get('schema_version')) is not int
                or data['rack_backing_context']['schema_version'] != 1
                or data['rack_backing_context'].get('analyzer_version') != 'rack-backing-context-1'))
            or (data['schema_version'] not in (30, 31, 32, 33, 34, 35) and 'communication_context' in data)
            or (data['schema_version'] in (30, 31, 32, 33, 34, 35) and (type(data.get('communication_context')) is not dict
                or type(data['communication_context'].get('schema_version')) is not int
                or data['communication_context']['schema_version'] != (3 if data['schema_version'] in (32, 33, 34, 35) else 2 if data['schema_version'] in (31, 32, 33, 34, 35) else 1)
                or data['communication_context'].get('analyzer_version') != ('communication-context-3' if data['schema_version'] in (32, 33, 34, 35) else 'communication-context-2' if data['schema_version'] == 31 else 'communication-context-1')))
            or any(type(data.get(key)) is not dict
                   for key in ('snapshot', 'inventory', 'references', 'sfc', 'statistics'))
            or any(type(data.get(key)) is not list for key in ('patterns', 'findings'))):
        raise ReviewHtmlError('Engineering review data is not supported.')
    # Validate and bound the original canonical document before omitting any
    # presentation-only metadata. A smaller distribution view must not permit
    # an oversized or malformed canonical source document to pass the boundary.
    if debug:
        return _encode_payload(data)
    _encode_payload(data, retain=False)
    return _encode_payload(_presentation_data(data))


_PROVIDER_ROOTS = (
    'inventory', 'references', 'sfc', 'access', 'tag_data', 'pid', 'pid_members',
    'calculations', 'rung_analysis', 'relationships', 'conditions',
    'binding_context', 'custom_instruction_context', 'indexed_access',
    'sfr_context', 'aoi_body_context', 'pid_connections', 'calculation_paths',
    'output_context', 'stateful_objects', 'sfc_conditions', 'sfc_context',
    'execution_context', 'signal_context', 'file_operations', 'alarm_evidence',
    'communication_context', 'rack_backing_context', 'engineering_assemblies',
)
_IMPLEMENTATION_METADATA = frozenset({
    'report_version', 'parser_version', 'analyzer_version', 'catalog_version',
    'tool_revision',
})


def _presentation_data(data: dict[str, Any]) -> dict[str, Any]:
    # Project only known envelopes and the explicit candidate rule fields below.
    # Never recurse through source attributes, comments or values: similar keys are
    # engineering evidence, not application metadata. Schema discriminators and
    # source identity stay available to navigation and feedback references.
    projected = {key: value for key, value in data.items()
                 if key not in _IMPLEMENTATION_METADATA}
    for name in _PROVIDER_ROOTS:
        if name in data:
            projected[name] = {key: value for key, value in data[name].items()
                               if key not in _IMPLEMENTATION_METADATA}
    rung_analysis = projected.get('rung_analysis')
    if type(rung_analysis) is dict and type(rung_analysis.get('candidates')) is list:
        # Rule identifiers describe this application's implementation. The
        # candidate ID, source rung, reason, evidence and review status remain
        # unchanged; no similarly named authored source attribute is touched.
        rung_analysis['candidates'] = [
            {key: value for key, value in candidate.items()
             if key not in {'rule_id', 'rule_version'}}
            if type(candidate) is dict else candidate
            for candidate in rung_analysis['candidates']
        ]
    return projected


def _encode_payload(data: dict[str, Any], *, retain: bool = True) -> str:
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
                if retain:
                    output.write(escaped)
        return output.getvalue()
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        if isinstance(exc, ReviewHtmlError):
            raise
        raise ReviewHtmlError('Engineering review data could not be rendered.') from None


def _hash(value: str) -> str:
    return base64.b64encode(hashlib.sha256(value.encode('utf-8')).digest()).decode('ascii')


def _review_assets(data: dict, *, debug: bool = False, workspace: bool = False,
                   run_id: str | None = None, rung_qualification: dict | None = None) -> tuple[str, str]:
    """Bundle the same trusted ladder renderer used by the editable workspace.

    Presentation identity stays outside the canonical evidence payload. Only the
    hosting workspace supplies a saved-run identity; standalone reports cannot
    request source values or open backend help windows.
    """
    if run_id is not None and (not workspace or type(run_id) is not str
                              or not re.fullmatch(r'[^\x00-\x20\x7f]{1,240}', run_id)):
        raise ReviewHtmlError('The saved analysis identity is invalid.')
    qualification = rung_qualification if rung_qualification is not None else {}
    rungs = data['inventory'].get('rungs', [])
    if (type(rungs) is not list or any(type(row) is not dict or type(row.get('id')) is not str
                                     or not re.fullmatch(r'[^\x00-\x20\x7f]{1,240}', row['id'])
                                     for row in rungs)):
        raise ReviewHtmlError('The ladder source identities are invalid.')
    rung_ids = {row['id'] for row in rungs}
    if len(rung_ids) != len(rungs):
        raise ReviewHtmlError('The ladder source identities are invalid.')
    if (type(qualification) is not dict or any(type(key) is not str or key not in rung_ids
                                             or type(value) is not bool
                                             for key, value in qualification.items())):
        raise ReviewHtmlError('The ladder source qualification is invalid.')
    context = json.dumps({'runId': run_id, 'qualifiedRungs': sorted(
        key for key, value in qualification.items() if value)}, ensure_ascii=True,
        separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    assets = Path(__file__).with_name('review_assets')
    shared = Path(__file__).with_name('workspace_assets')
    try:
        css = '\n'.join((shared / name).read_text(encoding='utf-8') for name in (
            'source-colors.css', 'ladder-diagram.css', 'instruction-help.css'))
        css += '\n' + (assets / 'report.css').read_text(encoding='utf-8')
        scripts = [f"const REVIEW_DEBUG = {'true' if debug else 'false'};",
                   f"const REVIEW_LADDER = Object.freeze({context});"]
        if workspace:
            scripts.append('const WORKSPACE_REVIEW = true;')
        scripts.extend((shared / name).read_text(encoding='utf-8') for name in (
            'source-colors.js', 'rung-explanation.js', 'instruction-help-content.js',
            'variable-help-content.js', 'instruction-help.js', 'ladder-diagram.js'))
        scripts.extend((assets / name).read_text(encoding='utf-8') for name in (
            'theme.js', 'review_guide.js', 'language.js', 'report.js'))
        return css, '\n'.join(scripts)
    except (OSError, UnicodeError):
        raise ReviewHtmlError('Engineering review resources are unavailable.') from None


def render_review_html(data: dict[str, Any], *, debug: bool = False,
                       source: bytes | None = None) -> str:
    """Render private evidence, with implementation metadata only on request."""
    if type(debug) is not bool:
        raise ReviewHtmlError('Engineering review display mode is not supported.')
    payload = _payload(data, debug=debug)
    qualification = None
    if source is not None:
        from .workspace_classification import _qualify_source
        try:
            if type(source) is not bytes:
                raise ValueError
            qualification = _qualify_source(source, data['inventory'])[1]
        except (ValueError, TypeError, KeyError):
            raise ReviewHtmlError('The ladder source does not match the review snapshot.') from None
    css, script = _review_assets(data, debug=debug, rung_qualification=qualification)
    policy = ("default-src 'none'; "
              f"script-src 'sha256-{_hash(script)}'; style-src 'sha256-{_hash(css)}'; "
              "connect-src 'none'; img-src 'none'; font-src 'none'; object-src 'none'; "
              "frame-src 'none'; base-uri 'none'; form-action 'none'")
    page = _render_template(policy, css, script, payload)
    _, html_limit = _limits(data['schema_version'])
    if len(page.encode('utf-8')) > html_limit:
        raise ReviewHtmlSizeLimitError('Engineering review exceeds the report size limit.')
    return page


def _render_template(policy: str, css: str, script: str, payload: str, language: str = '') -> str:
    """Substitute template slots once; source text may literally name a slot."""
    values = {'__POLICY__': policy, '__CSS__': css, '__APP__': script,
              '__PAYLOAD__': payload, '__LANGUAGE__': language}
    return re.sub('|'.join(values), lambda match: values[match.group()], _TEMPLATE)


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
<div class="topbar-actions"><span class="topbar-badge" title="Source evidence is not editable. Save engineering decisions in the workspace.">Read only · Source evidence</span><div id="report-language"></div>
<button id="theme-toggle" class="theme-toggle" type="button" hidden>Dark mode · Switch to light</button></div></header>
<main id="main" tabindex="-1"><div id="page-heading"></div>
<div id="toolbar"></div><div id="content"></div></main>
<footer>Captured source evidence. Effects, safety behavior and engineering meaning require review.</footer>
</div></div><noscript><p class="noscript">Enable JavaScript to navigate this offline report. The private JSON artifact in the same run contains the underlying evidence.</p></noscript>
<script type="application/json" id="review-data">__PAYLOAD__</script>
__LANGUAGE__
<script>__APP__</script></body></html>'''
