"""Transport failures must not become misleading project-error responses."""
from __future__ import annotations

import io
import json
import base64
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from plc_workbench.project_store import ProjectError
from plc_workbench.workspace import WorkspaceHandler


DISCONNECTS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)


class ResponseStream:
    """Exercise the real HTTP header writer and body writer deterministically."""

    def __init__(self, *, fail_on: int | None = None, error: OSError | None = None):
        self.attempts: list[bytes] = []
        self.fail_on = fail_on
        self.error = error

    def write(self, value: bytes) -> int:
        self.attempts.append(value)
        if len(self.attempts) == self.fail_on:
            assert self.error is not None
            raise self.error
        return len(value)


class WorkspaceDisconnectTests(unittest.TestCase):
    def handler(self, path: str, *, method: str = 'GET',
                stream: ResponseStream | None = None) -> WorkspaceHandler:
        # Skip the network accept loop but use the actual handler, route, JSON
        # serializer and BaseHTTPRequestHandler response-header implementation.
        handler = object.__new__(WorkspaceHandler)
        workspace = Mock()
        digest = base64.b64encode(hashlib.sha256(b'').digest()).decode('ascii')
        policy = (f"default-src 'none'; script-src 'sha256-{digest}'; style-src 'sha256-{digest}'; "
                  "connect-src 'self'; img-src 'none'; font-src 'none'; object-src 'none'; "
                  "frame-src 'none'; base-uri 'none'; form-action 'none'")
        workspace.report.return_value = (f'<html><meta http-equiv="Content-Security-Policy" '
                                         f'content="{policy}">Invented report</html>').encode()
        workspace.state.return_value = {'revision': 2}
        workspace.mutate.return_value = {'revision': 2}
        handler.server = SimpleNamespace(workspace=workspace, token='synthetic-session',
                                         origin='http://127.0.0.1:12345')
        handler.command = method
        handler.path = path
        handler.requestline = f'{method} {path} HTTP/1.1'
        handler.request_version = 'HTTP/1.1'
        handler.close_connection = False
        body = json.dumps({'command': {'type': 'synthetic'}, 'expected_revision': 1}).encode()
        handler.headers = {'Host': '127.0.0.1:12345',
                           'Content-Type': 'application/json',
                           'Content-Length': str(len(body)),
                           'X-Workspace-Token': 'synthetic-session'}
        handler.rfile = io.BytesIO(body)
        handler.wfile = stream if stream is not None else ResponseStream()
        return handler

    def test_raw_report_mode_remains_opaque_and_blocks_connections(self) -> None:
        handler = self.handler('/raw-not-a-route')
        handler._send(200, b'<html><script>untrusted()</script></html>', 'text/html', report=True)
        headers = handler.wfile.attempts[0].decode()
        self.assertIn("sandbox allow-scripts;", headers)
        self.assertIn("connect-src 'none'", headers)
        self.assertNotIn('allow-same-origin', headers)
        self.assertNotIn('allow-popups', headers)

    def test_trusted_report_mode_rejects_missing_or_unsafe_policy_before_headers(self) -> None:
        handler = self.handler('/analysis')
        for data in (b'<html>Untrusted</html>',
                     b'<meta http-equiv="Content-Security-Policy" content="script-src *; connect-src *">'):
            with self.subTest(data=data), self.assertRaises(ProjectError):
                handler._send(200, data, 'text/html', report=True, trusted_report=True)
            self.assertEqual(handler.wfile.attempts, [])

    def test_report_disconnect_during_headers_or_body_never_writes_a_second_response(self) -> None:
        for error_type in DISCONNECTS:
            for fail_on in (1, 2):
                with self.subTest(error=error_type.__name__, fail_on=fail_on):
                    stream = ResponseStream(fail_on=fail_on, error=error_type('synthetic disconnect'))
                    handler = self.handler('/analysis', stream=stream)
                    handler.do_GET()
                    self.assertTrue(handler.close_connection)
                    self.assertEqual(len(stream.attempts), fail_on)
                    self.assertTrue(stream.attempts[0].startswith(b'HTTP/1.0 200 '))
                    self.assertNotIn(b'500', b''.join(stream.attempts))
                    handler.server.workspace.report.assert_called_once_with(None)

    def test_post_response_disconnect_does_not_retry_or_undo_an_applied_change(self) -> None:
        for error_type in DISCONNECTS:
            for fail_on in (1, 2):
                with self.subTest(error=error_type.__name__, fail_on=fail_on):
                    stream = ResponseStream(fail_on=fail_on, error=error_type('synthetic disconnect'))
                    handler = self.handler('/api/mutate', method='POST', stream=stream)
                    handler.do_POST()
                    self.assertTrue(handler.close_connection)
                    self.assertEqual(len(stream.attempts), fail_on)
                    self.assertTrue(stream.attempts[0].startswith(b'HTTP/1.0 200 '))
                    handler.server.workspace.mutate.assert_called_once_with(
                        {'type': 'synthetic'}, 1, author='Reviewer')

    def test_post_body_disconnect_makes_no_change_or_error_response(self) -> None:
        for error_type in DISCONNECTS:
            with self.subTest(error=error_type.__name__):
                handler = self.handler('/api/mutate', method='POST')
                handler.rfile = Mock()
                handler.rfile.read.side_effect = error_type('synthetic disconnect')
                handler.do_POST()
                self.assertTrue(handler.close_connection)
                self.assertEqual(handler.wfile.attempts, [])
                handler.server.workspace.mutate.assert_not_called()
                handler.server.workspace.state.assert_not_called()

    def test_project_read_oserrors_still_produce_a_controlled_500(self) -> None:
        # Even connection-shaped errors from storage are not mistaken for a
        # browser disconnect: only actual transport reads/writes are suppressed.
        for error_type in (OSError, PermissionError, FileNotFoundError, ConnectionAbortedError, TimeoutError):
            with self.subTest(error=error_type.__name__):
                handler = self.handler('/analysis')
                handler.server.workspace.report.side_effect = error_type('private-source-path')
                handler.do_GET()
                self.assertTrue(handler.wfile.attempts[0].startswith(b'HTTP/1.0 500 '))
                body = json.loads(handler.wfile.attempts[1])
                self.assertIn('Could not read the project.', body['error'])
                self.assertNotIn('private-source-path', body['error'])

    def test_project_write_oserror_still_produces_a_controlled_500(self) -> None:
        handler = self.handler('/api/mutate', method='POST')
        handler.server.workspace.mutate.side_effect = PermissionError('private-source-path')
        handler.do_POST()
        self.assertTrue(handler.wfile.attempts[0].startswith(b'HTTP/1.0 500 '))
        body = json.loads(handler.wfile.attempts[1])
        self.assertIn('Could not save the project.', body['error'])
        self.assertNotIn('private-source-path', body['error'])

    def test_disconnect_while_delivering_a_project_error_does_not_escape(self) -> None:
        for fail_on in (1, 2):
            with self.subTest(fail_on=fail_on):
                stream = ResponseStream(fail_on=fail_on, error=ConnectionAbortedError('synthetic disconnect'))
                handler = self.handler('/analysis', stream=stream)
                handler.server.workspace.report.side_effect = PermissionError('private-source-path')
                handler.do_GET()
                self.assertTrue(handler.close_connection)
                self.assertEqual(len(stream.attempts), fail_on)
                self.assertTrue(stream.attempts[0].startswith(b'HTTP/1.0 500 '))

    def test_unrelated_send_oserror_is_not_silenced(self) -> None:
        handler = self.handler('/analysis', stream=ResponseStream(fail_on=1, error=OSError('unexpected failure')))
        with self.assertRaisesRegex(OSError, 'unexpected failure'):
            handler._send(200, b'Invented report', 'text/plain')


if __name__ == '__main__':
    unittest.main()
