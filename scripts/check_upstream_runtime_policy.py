#!/usr/bin/env python3
"""Check that validated Oracle and DevSpace runtimes match npm's latest tags.

The checker deliberately reports a newly published npm version as drift; it
never installs, promotes, patches, or restarts anything.  The policy records a
validated current release and a separately pinned last-known-good rollback
release.  ``--fixture`` makes the complete registry exchange deterministic for
offline tests and CI reproductions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


POLICY_SCHEMA = "codex.web-gpt.upstream-runtime-policy/v1"
REPORT_SCHEMA = "codex.web-gpt.upstream-runtime-report/v1"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
INTEGRITY_RE = re.compile(r"^sha512-[A-Za-z0-9+/]+={0,2}$")
HTTPS_RE = re.compile(r"^https://", re.IGNORECASE)
ROOT_KEYS = {"schema", "promotion", "runtimes"}
PROMOTION_KEYS = {
    "mode",
    "npm_latest",
    "automatic_promotion",
    "automatic_install",
    "automatic_service_restart",
    "drift_issue_title",
}
RUNTIME_KEYS = {"package", "registry", "current", "last_known_good"}
RELEASE_KEYS = {"version", "integrity", "source"}
LKG_KEYS = {"version", "integrity"}


class PolicyError(ValueError):
    """Policy or registry metadata does not satisfy the closed contract."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyError(f"{label} must be an object")
    return value


def _closed_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise PolicyError(f"{label} keys must be exactly {sorted(expected)}; got {sorted(actual)}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PolicyError(f"{label} must be a non-empty string")
    return value


def _version(value: Any, label: str) -> str:
    text = _string(value, label)
    if not SEMVER_RE.fullmatch(text):
        raise PolicyError(f"{label} must be SemVer")
    return text


def _integrity(value: Any, label: str) -> str:
    text = _string(value, label)
    if not INTEGRITY_RE.fullmatch(text):
        raise PolicyError(f"{label} must be a sha512 npm integrity value")
    return text


def validate_policy(raw: Any) -> dict[str, Any]:
    policy = _object(raw, "policy")
    _closed_keys(policy, ROOT_KEYS, "policy")
    if policy["schema"] != POLICY_SCHEMA:
        raise PolicyError(f"policy.schema must be {POLICY_SCHEMA}")

    promotion = _object(policy["promotion"], "policy.promotion")
    _closed_keys(promotion, PROMOTION_KEYS, "policy.promotion")
    if promotion["mode"] != "newest-validated-stable":
        raise PolicyError("policy.promotion.mode must be newest-validated-stable")
    if promotion["npm_latest"] != "candidate-immediately":
        raise PolicyError("policy.promotion.npm_latest must be candidate-immediately")
    for key in ("automatic_promotion", "automatic_install", "automatic_service_restart"):
        if promotion[key] is not False:
            raise PolicyError(f"policy.promotion.{key} must be false")
    _string(promotion["drift_issue_title"], "policy.promotion.drift_issue_title")

    runtimes = _object(policy["runtimes"], "policy.runtimes")
    if set(runtimes) != {"oracle", "devspace"}:
        raise PolicyError("policy.runtimes must contain exactly oracle and devspace")
    for name, runtime_raw in runtimes.items():
        runtime = _object(runtime_raw, f"policy.runtimes.{name}")
        _closed_keys(runtime, RUNTIME_KEYS, f"policy.runtimes.{name}")
        _string(runtime["package"], f"policy.runtimes.{name}.package")
        registry = _string(runtime["registry"], f"policy.runtimes.{name}.registry")
        if not HTTPS_RE.match(registry):
            raise PolicyError(f"policy.runtimes.{name}.registry must use https")
        current = _object(runtime["current"], f"policy.runtimes.{name}.current")
        _closed_keys(current, RELEASE_KEYS, f"policy.runtimes.{name}.current")
        _version(current["version"], f"policy.runtimes.{name}.current.version")
        _integrity(current["integrity"], f"policy.runtimes.{name}.current.integrity")
        source = _string(current["source"], f"policy.runtimes.{name}.current.source")
        if not HTTPS_RE.match(source):
            raise PolicyError(f"policy.runtimes.{name}.current.source must use https")
        lkg = _object(runtime["last_known_good"], f"policy.runtimes.{name}.last_known_good")
        _closed_keys(lkg, LKG_KEYS, f"policy.runtimes.{name}.last_known_good")
        _version(lkg["version"], f"policy.runtimes.{name}.last_known_good.version")
        _integrity(lkg["integrity"], f"policy.runtimes.{name}.last_known_good.integrity")
        if current["version"] == lkg["version"]:
            raise PolicyError(f"policy.runtimes.{name} current and last_known_good must differ")
    return policy


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot read JSON {path}: {exc}") from exc


def _fixture_metadata(fixture: dict[str, Any], registry: str) -> dict[str, Any]:
    registries = _object(fixture.get("registries"), "fixture.registries")
    return _object(registries.get(registry), f"fixture.registries[{registry!r}]")


def _download_metadata(registry: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(registry, headers={"Accept": "application/json", "User-Agent": "codex-runtime-policy/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _object(json.loads(response.read().decode("utf-8")), f"registry {registry}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        raise PolicyError(f"cannot query registry {registry}: {exc}") from exc


def _registry_release(metadata: dict[str, Any], version: str, label: str) -> dict[str, Any]:
    versions = _object(metadata.get("versions"), "registry.versions")
    release = _object(versions.get(version), f"registry.versions[{version!r}]")
    dist = _object(release.get("dist"), f"registry.versions[{version!r}].dist")
    integrity = _integrity(dist.get("integrity"), f"registry.versions[{version!r}].dist.integrity")
    tarball = _string(dist.get("tarball"), f"registry.versions[{version!r}].dist.tarball")
    if not HTTPS_RE.match(tarball):
        raise PolicyError(f"registry.versions[{version!r}].dist.tarball must use https")
    return {"version": version, "integrity": integrity, "tarball": tarball, "label": label}


def inspect_runtime(name: str, runtime: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    tags = _object(metadata.get("dist-tags"), "registry.dist-tags")
    latest = _version(tags.get("latest"), "registry.dist-tags.latest")
    current = runtime["current"]
    lkg = runtime["last_known_good"]
    current_archive = _registry_release(metadata, current["version"], "current")
    lkg_archive = _registry_release(metadata, lkg["version"], "last_known_good")
    if current_archive["integrity"] != current["integrity"]:
        raise PolicyError(f"{name} current archive integrity does not match the policy")
    if lkg_archive["integrity"] != lkg["integrity"]:
        raise PolicyError(f"{name} last-known-good archive integrity does not match the policy")
    latest_archive = _registry_release(metadata, latest, "latest")
    return {
        "package": runtime["package"],
        "registry": runtime["registry"],
        "current": current_archive,
        "last_known_good": lkg_archive,
        "latest": latest_archive,
        "status": "in-sync" if latest == current["version"] else "drift",
    }


def check(policy: dict[str, Any], fixture: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, runtime in policy["runtimes"].items():
        try:
            metadata = _fixture_metadata(fixture, runtime["registry"]) if fixture is not None else _download_metadata(runtime["registry"], timeout)
            results[name] = inspect_runtime(name, runtime, metadata)
        except PolicyError as exc:
            results[name] = {"package": runtime["package"], "registry": runtime["registry"], "status": "error", "error": str(exc)}
    drifted = sorted(name for name, result in results.items() if result["status"] == "drift")
    errors = sorted(name for name, result in results.items() if result["status"] == "error")
    return {
        "schema": REPORT_SCHEMA,
        "promotion": policy["promotion"],
        "runtimes": results,
        "drifted": drifted,
        "errors": errors,
        "in_sync": not drifted and not errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[1] / "upstream-runtime-policy.json")
    parser.add_argument("--fixture", type=Path, help="Offline registry fixture with {registries: {url: metadata}}.")
    parser.add_argument("--output", type=Path, help="Write the JSON report atomically to this path.")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--allow-drift", action="store_true", help="Return success for drift so a caller can create/update its issue.")
    args = parser.parse_args(argv)
    try:
        policy = validate_policy(_read_json(args.policy))
        fixture = _read_json(args.fixture) if args.fixture else None
        report = check(policy, fixture, args.timeout)
    except PolicyError as exc:
        report = {"schema": REPORT_SCHEMA, "in_sync": False, "drifted": [], "errors": [str(exc)], "runtimes": {}}
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(args.output)
    print(encoded, end="")
    if report.get("errors"):
        return 1
    if report.get("drifted") and not args.allow_drift:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
