"""Publish local validated bundles as GitHub Release assets, never as Git blobs.

Default is a local preflight. --publish uploads; --verify-only checks existing
releases. Credentials come from normal gh environment or Git Credential Manager
and remain in process memory. Existing uploaded assets are never overwritten.
"""

import argparse
from datetime import datetime, UTC
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import quote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = "Eureka375/DocLens"
API = f"repos/{REPO}"
REPORT = ROOT / "docs/validation/github-releases/upload-results.json"
# Early binary archives do not have a verified one-to-one source snapshot.
VERSIONS = [
    ("t01", "archive-t01", "48af8f9", True),
    ("v0.2.0", "archive-v0.2.0", "48af8f9", False),
    ("v0.2.1", "archive-v0.2.1", "48af8f9", False),
    ("v0.3.0", "v0.3.0", "138c0e7", False),
    ("v0.3.1", "v0.3.1", "54657c0", False),
    ("v0.4.0", "v0.4.0", "f150bcd", False),
    ("v0.4.1", "v0.4.1", "0fc0f6d", False),
    ("v0.4.2", "v0.4.2", "97806eb", False),
    ("v0.5.0", "v0.5.0", "a775e01", False),
    ("v0.5.1", "v0.5.1", "adda58e", False),
]


def log(event, **data):
    print(json.dumps({"event": event, **data}, ensure_ascii=True), flush=True)


def save_report(rows):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps({"repository": REPO, "checked_at_utc": datetime.now(UTC).isoformat(),
                                     "versions": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def preflight():
    rows = []
    for version, tag, commit, prerelease in VERSIONS:
        folder = ROOT / "releases" / version
        archives = list(folder.glob("*.zip"))
        if len(archives) != 1:
            raise RuntimeError(f"Expected one top-level release ZIP: {version}")
        path = archives[0]
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"ZIP CRC failed: {version}")
            for name in archive.namelist():
                if Path(name).name.lower() in {"ai-settings.bin", ".env", "credentials.json", "api-key.txt", "api_key.txt"}:
                    raise RuntimeError(f"Unexpected credential-like file in {version}; inspect locally")
        checksum = path.with_suffix(".zip.sha256")
        if checksum.exists():
            if checksum.read_text(encoding="utf-8-sig").split()[0].lower() != digest:
                raise RuntimeError(f"Checksum mismatch: {version}")
        else:
            checksum.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        # GitHub strips non-ASCII characters from uploaded asset names. Keep
        # the original local bundle, and give the downloaded ZIP a matching
        # ASCII checksum filename and checksum entry.
        asset_name = re.sub(r"[^A-Za-z0-9._-]", "", path.name)
        remote_checksum = folder / (asset_name + ".sha256")
        if remote_checksum != checksum:
            remote_checksum.write_text(f"{digest}  {asset_name}\n", encoding="ascii")
        sha = subprocess.check_output(["git", "rev-parse", commit], cwd=ROOT, text=True).strip()
        archived = tag.startswith("archive-")
        notes_path = ROOT / "build/github-release-notes" / f"{tag}.md"
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        readme = folder / "README.md"
        notes = readme.read_text(encoding="utf-8-sig") if readme.exists() else f"# DocLens {version}\n\n历史Windows便携包。\n"
        # Relative links in repository README files need an absolute target on Releases.
        def rewrite(match):
            label, target = match.groups()
            if target.startswith(("https:", "http:", "#", "mailto:")):
                return match.group()
            try:
                relative = (folder / target).resolve().relative_to(ROOT).as_posix()
            except ValueError:
                return label
            return f"{label}(https://github.com/{REPO}/blob/{sha}/{quote(relative, safe='/')})"
        notes = re.sub(r"(\[[^\]]*\])\(([^)]+)\)", rewrite, notes)
        if archived:
            notes += ("\n\n**历史二进制归档**：未追溯到可与此包一一对应的完整源码快照。"
                      "归档标签指向仓库初始化提交，仅作为下载入口，不代表可用该提交重建本包。"
                      "T01为一次性技术原型，不是正式产品。\n")
        notes += (f"\n\n下载附件：`{asset_name}`，完整解压后运行，保留依赖目录。\n"
                  f"\nSHA-256：`{digest}`。同时提供校验文件。\n"
                  "\n本次按本地原包上传，已核对ZIP完整性和摘要，未重新构建或重新验收历史版本功能。\n")
        notes_path.write_text(notes, encoding="utf-8")
        rows.append({"version": version, "tag": tag, "target_sha": sha, "historical_archive": archived,
                     "prerelease": prerelease, "local_file": path.relative_to(ROOT).as_posix(),
                     "asset_name": asset_name, "checksum_file": remote_checksum.relative_to(ROOT).as_posix(),
                     "bytes": path.stat().st_size, "sha256": digest, "zip_crc_verified": True,
                     "status": "preflight_passed"})
        log("preflight", version=version, bytes=path.stat().st_size)
    return rows


class GitHub:
    def __init__(self):
        self.gh = shutil.which("gh") or "C:/Program Files/GitHub CLI/gh.exe"
        self.env = dict(os.environ)
        self.env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
        self.token = self.env.get("GH_TOKEN") or self.env.get("GITHUB_TOKEN")
        if not self.token:
            credentials = subprocess.run(["git", "-c", "credential.interactive=never", "credential", "fill"],
                input="protocol=https\nhost=github.com\npath=Eureka375/DocLens.git\n\n", text=True,
                capture_output=True, env=self.env, cwd=ROOT, timeout=30)
            values = dict(line.split("=", 1) for line in credentials.stdout.splitlines() if "=" in line)
            self.token = values.get("password")
        if not self.token:
            raise RuntimeError("No existing noninteractive GitHub credential available")
        self.env["GH_TOKEN"] = self.token

    def run(self, *args, missing_ok=False, timeout=120):
        result = subprocess.run([self.gh, *args], cwd=ROOT, env=self.env, capture_output=True,
                                text=True, encoding="utf-8", timeout=timeout)
        if result.returncode:
            if missing_ok and "HTTP 404" in result.stderr:
                return None
            raise RuntimeError(result.stderr.replace(self.token, "[REDACTED]")[:1800])
        return result.stdout

    def api(self, path, missing_ok=False):
        result = self.run("api", path, missing_ok=missing_ok)
        return json.loads(result) if result is not None else None

    def release(self, tag):
        release = self.api(f"{API}/releases/tags/{quote(tag, safe='')}", missing_ok=True)
        if release is not None:
            return release
        # Drafts can exist before their tag is published; the tag endpoint
        # returns 404, while the authenticated release collection contains them.
        return next((r for r in self.api(f"{API}/releases?per_page=100") if r["tag_name"] == tag), None)


def check_asset(asset, path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if asset.get("state") != "uploaded" or asset["size"] != path.stat().st_size:
        raise RuntimeError(f"Remote asset is incomplete: {path.name}")
    if asset.get("digest") != "sha256:" + digest:
        raise RuntimeError(f"Remote SHA-256 does not match or is unavailable: {path.name}")
    return {"name": asset["name"], "bytes": asset["size"], "sha256": digest,
            "download_url": asset["browser_download_url"], "remote_digest_verified": True}


def publish(github, row, verify_only=False):
    tag = row["tag"]
    release = github.release(tag)
    if release is None:
        if verify_only:
            raise RuntimeError(f"Release missing: {tag}")
        args = ["release", "create", tag, "--repo", REPO, "--target", row["target_sha"],
                "--title", f"DocLens {row['version']} Windows" + (" (历史归档)" if row["historical_archive"] else ""),
                "--notes-file", str(ROOT / "build/github-release-notes" / f"{tag}.md"), "--draft", "--latest=false"]
        if row["prerelease"]:
            args.append("--prerelease")
        github.run(*args)
        release = github.release(tag)
    files = [(ROOT / row["local_file"], row["asset_name"]),
             (ROOT / row["checksum_file"], Path(row["checksum_file"]).name)]
    verified = []
    for path, asset_name in files:
        assets = github.api(f"{API}/releases/{release['id']}/assets?per_page=100")
        asset = next((a for a in assets if a["name"] == asset_name), None)
        if asset is None and not verify_only:
            log("upload_start", version=row["version"], asset=path.name, bytes=path.stat().st_size)
            github.run("release", "upload", tag, str(path), "--repo", REPO, timeout=1800)
            assets = github.api(f"{API}/releases/{release['id']}/assets?per_page=100")
            asset = next((a for a in assets if a["name"] == asset_name), None)
        if asset is None:
            raise RuntimeError(f"Asset missing: {path.name}")
        verified.append(check_asset(asset, path))
    if release["draft"]:
        if verify_only:
            raise RuntimeError(f"Release is still draft: {tag}")
        github.run("release", "edit", tag, "--repo", REPO, "--draft=false",
                   "--latest=" + ("true" if tag == "v0.5.1" else "false"))
    release = github.release(tag)
    if release["draft"]:
        raise RuntimeError(f"Release not published: {tag}")
    reference = github.api(f"{API}/git/ref/tags/{quote(tag, safe='')}")
    if reference["object"]["type"] != "commit" or reference["object"]["sha"] != row["target_sha"]:
        raise RuntimeError(f"Tag source mismatch: {tag}")
    row.update(status="published_verified", release_url=release["html_url"], release_id=release["id"], assets=verified)
    log("published_verified", version=row["version"], url=release["html_url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--publish", action="store_true")
    modes.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    rows = preflight()
    save_report(rows)
    if not (args.publish or args.verify_only):
        return
    github = GitHub()
    for row in rows:
        try:
            publish(github, row, args.verify_only)
        except Exception as exc:
            row.update(status="error", error=str(exc).replace(github.token, "[REDACTED]"))
            save_report(rows)
            raise
        save_report(rows)


if __name__ == "__main__":
    main()
