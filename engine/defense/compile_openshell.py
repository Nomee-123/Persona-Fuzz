from __future__ import annotations

import re

import yaml

from .policy_ir import Policy

ROOT_NAMES = {"root", "0"}


def _name(host: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    return value[:48] or "host"


def compile_openshell(policy: Policy) -> str:
    hosts = [h for h in policy.allowed_hosts if not h.startswith("*.") and not h.startswith(".")]
    network_policies = {}
    used: set[str] = set()
    for host in hosts:
        name = _name(host)
        base = name
        i = 2
        while name in used:
            name = f"{base}-{i}"
            i += 1
        used.add(name)
        network_policies[name] = {
            "name": name,
            "endpoints": [
                {
                    "host": host,
                    "port": 443,
                    "protocol": "rest",
                    "access": "read-write",
                    "enforcement": "enforce",
                }
            ],
            "binaries": [{"path": "/usr/bin/python3"}],
        }
    data = {
        "version": 1,
        "filesystem_policy": {
            "include_workdir": True,
            "read_only": ["/usr", "/lib", "/etc"],
            "read_write": ["/sandbox", "/tmp"],
        },
        "landlock": {"compatibility": "best_effort"},
        "process": {"run_as_user": "sandbox", "run_as_group": "sandbox"},
        "network_policies": network_policies,
    }
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def validate_openshell(yaml_text: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(yaml_text)
    except Exception as exc:
        return False, [f"invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return False, ["top level must be a mapping"]
    if data.get("version") != 1:
        errors.append("version must be 1")
    process = data.get("process", {})
    if str(process.get("run_as_user", "")).lower() in ROOT_NAMES:
        errors.append("run_as_user may not be root")
    if str(process.get("run_as_group", "")).lower() in ROOT_NAMES:
        errors.append("run_as_group may not be root")
    for key, pol in (data.get("network_policies") or {}).items():
        for endpoint in pol.get("endpoints", []):
            host = str(endpoint.get("host", ""))
            if host.startswith("*.in") or host.startswith("*.") and host.count(".") <= 1:
                errors.append(f"TLD wildcard host not allowed: {host}")
            if not host:
                errors.append(f"empty host in {key}")
            if int(endpoint.get("port", 0)) <= 0:
                errors.append(f"invalid port in {key}")
    return not errors, errors
