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
from .review_html import _encode_payload, _hash, _limits, _presentation_data, _render_template


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


def read_report_data(original: bytes, inventory: dict) -> dict:
    """Read only the inert, source-bound payload from a saved analysis report.

    Some analysis providers are saved inside this payload rather than separate
    JSON artifacts. Callers can reuse those results without executing imported
    scripts, translating source code or rerunning the parser.
    """
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
        # Validate the optional provider envelopes used by the trusted report
        # view, while returning the captured payload unchanged to the caller.
        _presentation_data(data)
        return data
    except (UnicodeError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError('Could not read the saved report evidence. The project source remains available.') from exc


def refresh_report(original: bytes, inventory: dict, *, translations: dict | None = None,
                   language: str = 'original', catalog: dict | None = None) -> bytes:
    """Return a source-bound, current read-only view of saved evidence."""
    try:
        data = read_report_data(original, inventory)
        if language not in {'original', 'english', 'both'}:
            raise ProjectError('The report language must be original, English or both.')
        payload = _encode_payload(_presentation_data(data))
        overlay = _language_overlay(data, translations, language, catalog)
        assets = Path(__file__).with_name('review_assets')
        css = (assets / 'report.css').read_text(encoding='utf-8')
        script = 'const REVIEW_DEBUG = false; const WORKSPACE_REVIEW = true;\n' + '\n'.join(
            (assets / name).read_text(encoding='utf-8')
            for name in ('theme.js', 'review_guide.js', 'language.js', 'report.js')
        )
        policy = ("default-src 'none'; "
                  f"script-src 'sha256-{_hash(script)}'; style-src 'sha256-{_hash(css)}'; "
                  "connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'")
        rendered = _render_template(policy, css, script, payload, overlay).encode('utf-8')
        if len(rendered) > _limits(data['schema_version'])[1]:
            raise ProjectError('The refreshed evidence report exceeds its display size limit.')
        return rendered
    except (UnicodeError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError('Could not display the saved report evidence. The project source remains available.') from exc


def _language_overlay(data: dict, translations: dict | None, language: str,
                      catalog: dict | None) -> str:
    """Keep derived wording out of the canonical evidence payload and script."""
    if translations is None and catalog is None and language == 'original':
        return ''
    if translations is not None and not isinstance(translations, dict):
        raise ProjectError('The English reading layer is invalid.')
    entries: list[dict] = []
    if catalog is not None:
        if not isinstance(catalog, dict) or catalog.get('snapshot_id') != data['snapshot']['id']:
            raise ProjectError('The English reading layer belongs to a different source snapshot.')
        entries = catalog.get('entries', [])
        if not isinstance(entries, list) or any(
            not isinstance(e, dict) or not all(isinstance(e.get(key), str) for key in ('id', 'locator', 'kind', 'original'))
            for e in entries
        ):
            raise ProjectError('The English annotation catalogue is invalid.')
    allowed = {e['original'] for e in entries}
    allowed.update(e.get('description') for e in data['inventory'].get('entities', []))
    allowed.update(e.get('comment') for e in data['inventory'].get('rungs', []))
    allowed.update(e.get('direct_text') for e in data['sfc'].get('elements', [])
                   if e.get('kind') in {'description', 'text_box', 'text_box_text'})
    allowed.update(e.get('raw_text') for e in data.get('sfc_conditions', {}).get('comments', []))
    rows = []
    for original, translated in (translations or {}).items():
        if not isinstance(original, str) or original not in allowed or not isinstance(translated, dict):
            continue
        text = translated.get('text')
        ready = translated.get('status') == 'translated' and translated.get('failed') is not True and isinstance(text, str)
        rows.append({'original': original, 'text': text if ready else '',
                     'status': 'translated' if ready else 'unavailable'})
    overlay = {'schema_version': data['schema_version'], 'snapshot_id': data['snapshot']['id'],
               'language': language, 'translations': rows, 'entries': entries,
               'coverage': catalog.get('coverage', {}) if catalog else {},
               'limitations': catalog.get('limitations', []) if catalog else []}
    encoded = _encode_payload(overlay)
    # Hidden inert text, not a third script block: legacy report readers still
    # see the original evidence script followed by the trusted application.
    return f'<div id="review-language-data" hidden>{encoded}</div>'
