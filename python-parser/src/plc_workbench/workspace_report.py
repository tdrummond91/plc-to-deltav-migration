"""Refresh saved report presentation without re-running or rewriting analysis.

Older private reports predate section/source fragment navigation. Extract only
their inert JSON, verify the captured inventory against the imported artifact,
and wrap it in this installation's trusted view assets. Original report bytes
remain in the project. Imported executable HTML is never reused.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path

from .project_store import ProjectError
from .review_html import _TEMPLATE, _encode_payload, _hash, _limits, _presentation_data


class _Payload(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.active = False
        self.count = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attributes = dict(attrs)
        if tag == 'script' and attributes.get('id') == 'review-data':
            if attributes.get('type') != 'application/json':
                raise ProjectError('The saved report does not contain an inert evidence payload.')
            self.count += 1
            self.active = True

    def handle_data(self, data: str) -> None:
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script':
            self.active = False


def refresh_report(original: bytes, inventory: dict) -> bytes:
    """Return a source-bound, current read-only view of saved evidence."""
    try:
        parser = _Payload()
        parser.feed(original.decode('utf-8'))
        if parser.count != 1:
            raise ProjectError('The saved report must contain exactly one evidence payload.')
        data = json.loads(''.join(parser.parts))
        if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
                or not 1 <= data['schema_version'] <= 35
                or any(not isinstance(data.get(key), dict)
                       for key in ('snapshot', 'inventory', 'references', 'sfc', 'statistics'))
                or any(not isinstance(data.get(key), list) for key in ('patterns', 'findings'))):
            raise ProjectError('The saved evidence report uses an unsupported structure.')
        captured = _presentation_data({'inventory': inventory})['inventory']
        report_inventory = _presentation_data({'inventory': data['inventory']})['inventory']
        if data['snapshot'] != inventory['snapshot'] or report_inventory != captured:
            raise ProjectError('The saved report and project inventory disagree; choose a consistent analysis run.')
        payload = _encode_payload(_presentation_data(data))
        assets = Path(__file__).with_name('review_assets')
        css = (assets / 'report.css').read_text(encoding='utf-8')
        script = 'const REVIEW_DEBUG = false; const WORKSPACE_REVIEW = true;\n' + '\n'.join(
            (assets / name).read_text(encoding='utf-8')
            for name in ('theme.js', 'review_guide.js', 'report.js')
        )
        policy = ("default-src 'none'; "
                  f"script-src 'sha256-{_hash(script)}'; style-src 'sha256-{_hash(css)}'; "
                  "connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'")
        rendered = (_TEMPLATE.replace('__POLICY__', policy).replace('__CSS__', css)
                    .replace('__APP__', script).replace('__PAYLOAD__', payload)).encode('utf-8')
        if len(rendered) > _limits(data['schema_version'])[1]:
            raise ProjectError('The refreshed evidence report exceeds its display size limit.')
        return rendered
    except (UnicodeError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError('Could not display the saved report evidence. The project source remains available.') from exc
