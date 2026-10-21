"""Explicit one-time download/install of the pinned public translation model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request
import zipfile

from .local_translation_engine import (
    DEFAULT_MODEL_DIR, Engine, MODEL_ID, PACKAGE_SHA256, PACKAGE_URL,
    REQUIRED_FILES,
)

MAX_PACKAGE_BYTES = 90 * 1024 * 1024
MAX_EXTRACTED_BYTES = 110 * 1024 * 1024
PACKAGE_ROOT = "translate-fr_en-1_9"


def download_package(destination: Path) -> None:
    """Only setup contacts the public model host. No source text is accepted."""
    request = urllib.request.Request(PACKAGE_URL, headers={"User-Agent": "Mozilla/5.0 PLC-Workbench-Model-Setup/1.0", "Accept": "application/zip"})
    total = 0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        if not response.geturl().startswith("https://"):
            raise ValueError("The model download did not remain on HTTPS.")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_PACKAGE_BYTES:
                raise ValueError("The model download exceeded its expected size limit.")
            output.write(chunk)


def install_package(package: Path, model_dir: Path) -> None:
    """Validate first, extract only known model files, then publish atomically."""
    package, model_dir = Path(package), Path(model_dir)
    if package.stat().st_size > MAX_PACKAGE_BYTES:
        raise ValueError("The model package is too large.")
    with package.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != PACKAGE_SHA256:
            raise ValueError("The model package does not match the pinned French-to-English model.")
    if model_dir.exists() or model_dir.is_symlink():
        raise ValueError("The model folder already exists and was kept intact.")
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".translation-install-", dir=model_dir.parent) as temporary:
        staging = Path(temporary) / "fr-en"
        staging.mkdir()
        manifest = {"model_id": MODEL_ID, "package_sha256": PACKAGE_SHA256, "files": {}}
        with zipfile.ZipFile(package) as archive:
            members: dict[str, zipfile.ZipInfo] = {}
            total = 0
            for member in archive.infolist():
                name = PurePosixPath(member.filename)
                if (name.is_absolute() or ".." in name.parts or "\\" in member.orig_filename
                        or ":" in member.filename or stat.S_ISLNK(member.external_attr >> 16)):
                    raise ValueError("The model archive contains an unsafe path.")
                if not name.parts or name.parts[0] != PACKAGE_ROOT:
                    raise ValueError("The model archive has an unexpected root.")
                relative = "/".join(name.parts[1:])
                if relative in REQUIRED_FILES:
                    if relative in members:
                        raise ValueError("The model archive contains duplicate files.")
                    total += member.file_size
                    members[relative] = member
            if set(members) != set(REQUIRED_FILES) or total > MAX_EXTRACTED_BYTES:
                raise ValueError("The model archive is incomplete or too large.")
            for relative, member in members.items():
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                with destination.open("rb") as source:
                    manifest["files"][relative] = {"size": destination.stat().st_size, "sha256": hashlib.file_digest(source, "sha256").hexdigest()}
        metadata = json.loads((staging / "metadata.json").read_text(encoding="utf-8"))
        if metadata.get("from_code") != "fr" or metadata.get("to_code") != "en" or metadata.get("package_version") != "1.9":
            raise ValueError("The model metadata is not the pinned French-to-English pair.")
        (staging / "installation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        staging.rename(model_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install an optional local French-to-English reading aid. Only public model files are downloaded; comments never leave this computer.")
    parser.add_argument("--package", type=Path, help="Install a previously downloaded .argosmodel without network access")
    args = parser.parse_args(argv)
    try:
        if not DEFAULT_MODEL_DIR.exists():
            if args.package:
                install_package(args.package, DEFAULT_MODEL_DIR)
            else:
                print("Downloading the public French-to-English model (about 67 MB). No project data is sent.")
                with tempfile.TemporaryDirectory(prefix="plc-translation-") as temporary:
                    package = Path(temporary) / "fr-en.argosmodel"
                    download_package(package)
                    install_package(package, DEFAULT_MODEL_DIR)
        engine = Engine(DEFAULT_MODEL_DIR)
        sample = engine.translate("La pompe ne doit pas démarrer.")
        if sample["status"] != "translated":
            raise RuntimeError("The local model did not pass its built-in reading check.")
        print("Local translation is ready. Reopen the workbench, then choose English translation.")
        print("Original comments remain unchanged. Translations are saved locally for reuse.")
        return 0
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
        print("Translation setup could not finish. Check the network/package and local translation dependencies. Existing model files were kept intact.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
