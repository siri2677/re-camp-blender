"""Runtime compatibility shim for InstantMesh's legacy diffusers import.

InstantMesh pins diffusers 0.20.2, whose dynamic pipeline loader imports the
removed ``huggingface_hub.cached_download`` symbol.  The provider process is
isolated with this module as ``sitecustomize`` so the repository and installed
packages are not modified.  The shim only supplies the legacy symbol for raw
community-pipeline URLs; normal Hub downloads continue to use the installed
``huggingface_hub`` implementation.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

try:
    import huggingface_hub as _huggingface_hub
except Exception:  # pragma: no cover - provider startup reports the original error
    _huggingface_hub = None


if _huggingface_hub is not None and not hasattr(_huggingface_hub, "cached_download"):

    def cached_download(
        url: str,
        cache_dir: str | os.PathLike[str] | None = None,
        force_download: bool = False,
        proxies: object | None = None,
        resume_download: bool = False,
        local_files_only: bool = False,
        use_auth_token: str | bool | None = None,
        **_: object,
    ) -> str:
        """Download a legacy raw URL into a deterministic local cache."""

        del proxies, resume_download
        if local_files_only:
            raise FileNotFoundError(f"Local-only cache miss for {url}")

        base_dir = Path(cache_dir or os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        target_dir = base_dir / "compat-cached-download"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / hashlib.sha256(url.encode("utf-8")).hexdigest()
        if force_download or not target.exists():
            request = urllib.request.Request(url)
            if isinstance(use_auth_token, str):
                request.add_header("Authorization", f"Bearer {use_auth_token}")
            with urllib.request.urlopen(request) as response, target.open("wb") as output:
                output.write(response.read())
        return str(target)


    _huggingface_hub.cached_download = cached_download
