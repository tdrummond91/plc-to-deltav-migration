"""Bounded, atomic installation checks with tiny independent test archives."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from plc_workbench import setup_translation as setup


def archive(path: Path, extra: dict[str, bytes] | None = None) -> str:
    with zipfile.ZipFile(path, "w") as output:
        for name in setup.REQUIRED_FILES:
            content = json.dumps({"from_code": "fr", "to_code": "en", "package_version": "1.9"}).encode() if name == "metadata.json" else b"independently synthetic"
            output.writestr(f"{setup.PACKAGE_ROOT}/{name}", content)
        for name, content in (extra or {}).items():
            # ZipInfo normally normalizes Windows separators while writing.
            # Override after construction to exercise an externally made ZIP.
            info = zipfile.ZipInfo(name)
            info.filename = name
            info.orig_filename = name
            output.writestr(info, content)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SetupTranslationTests(unittest.TestCase):
    def test_exact_files_and_license_installed_without_segmentation_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.argosmodel"
            digest = archive(package, {f"{setup.PACKAGE_ROOT}/stanza/resources.json": b"unused"})
            target = root / "model"
            with patch.object(setup, "PACKAGE_SHA256", digest), patch("urllib.request.urlopen", side_effect=AssertionError("No network")):
                setup.install_package(package, target)
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}, {*setup.REQUIRED_FILES, "installation.json"})
            self.assertEqual(json.loads((target / "installation.json").read_text())["package_sha256"], digest)

    def test_bad_hash_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.argosmodel"
            archive(package)
            with self.assertRaisesRegex(ValueError, "pinned"):
                setup.install_package(package, root / "model")
            self.assertFalse((root / "model").exists())

    def test_paths_and_duplicates_are_rejected_without_partial_install(self):
        for dangerous in ("../escape", f"{setup.PACKAGE_ROOT}/../../escape", "C:/escape", f"{setup.PACKAGE_ROOT}/model\\escape", f"{setup.PACKAGE_ROOT}/README.md"):
            with self.subTest(dangerous=dangerous), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                package = root / "test.argosmodel"
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    digest = archive(package, {dangerous: b"bad"})
                with patch.object(setup, "PACKAGE_SHA256", digest), self.assertRaises(ValueError):
                    setup.install_package(package, root / "model")
                self.assertFalse((root / "model").exists())
                self.assertEqual(list(root.glob(".translation-install-*")), [])

    def test_existing_target_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.argosmodel"
            digest = archive(package)
            target = root / "model"
            target.mkdir()
            sentinel = target / "keep.txt"
            sentinel.write_text("keep")
            with patch.object(setup, "PACKAGE_SHA256", digest), self.assertRaisesRegex(ValueError, "already exists"):
                setup.install_package(package, target)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_package_size_bound_precedes_hash_and_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.argosmodel"
            archive(package)
            with patch.object(setup, "MAX_PACKAGE_BYTES", 1), self.assertRaisesRegex(ValueError, "too large"):
                setup.install_package(package, root / "model")

    def test_cli_local_package_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.argosmodel"
            digest = archive(package)
            with patch.object(setup, "PACKAGE_SHA256", digest), patch.object(setup, "DEFAULT_MODEL_DIR", root / "model"), patch.object(setup, "download_package", side_effect=AssertionError("No network")), patch.object(setup, "Engine") as constructor:
                constructor.return_value.translate.return_value = {"text": "The pump must not start.", "status": "translated"}
                self.assertEqual(setup.main(["--package", str(package)]), 0)
                constructor.assert_called_once_with(root / "model")

    def test_cli_does_not_offer_unused_custom_model_location(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            setup.main(["--model-dir", "unused-folder"])
        self.assertEqual(failure.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
