"""Live config-service -> secret-free per-customer snapshot.

`cust sync` fetches through the hosted Fuse MCP (the server holds the config-service keys; this
process only needs the bearer token Claude Code already uses), projects every record through an
allowlist, diffs against the previous snapshot and writes `Customers/<ID>/config.snapshot.yaml`.

The config API returns SNAP passwords, SFTP private keys, API keys and webhook secrets. Nothing
here copies a field by default: the `project_*` functions name what is kept, and `assert_no_secrets`
refuses to write a snapshot containing any secret value seen in the raw payload.
"""

import datetime as dt
import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import yaml

MCP_ENVS = {"prod": "production", "dev": "staging"}  # the MCP's "staging" is the dev deployment
SECRET_KEY = re.compile(r"(key|secret|password|token|credential|private|auth)", re.I)
CHANGE_LOG_LIMIT = 40
SNAPSHOT_FILE = "config.snapshot.yaml"


# ---------------------------------------------------------------- fetch

class FuseConfig:
    """config-service reads through the hosted Fuse MCP's `config-read` tool."""

    def __init__(self, url, token):
        self.url = url
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "cust-sync", "version": "1"}}})

    @classmethod
    def from_claude_config(cls, path=None):
        cfg = json.loads(Path(path or Path.home() / ".claude.json").read_text())

        def find(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "mcpServers" and isinstance(v, dict) and "fuse" in v:
                        return v["fuse"]
                    hit = find(v)
                    if hit:
                        return hit
            return None

        server = find(cfg)
        if not server or "Authorization" not in (server.get("headers") or {}):
            raise RuntimeError("no hosted fuse MCP with an Authorization header in ~/.claude.json")
        return cls(server["url"], server["headers"]["Authorization"])

    def _rpc(self, body):
        req = urllib.request.Request(self.url, json.dumps(body).encode(), self.headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode()

    def read(self, env, path):
        out = self._rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "config-read", "arguments": {"environment": MCP_ENVS[env], "path": path}}})
        line = next(l for l in out.splitlines() if l.startswith("data:"))
        result = json.loads(line[5:])["result"]
        if result.get("isError"):
            raise RuntimeError(result["content"][0]["text"][:200])
        reply = json.loads(result["content"][0]["text"])
        if reply.get("status") != 200:
            raise RuntimeError("%s %s -> %s" % (env, path, reply.get("status")))
        return reply["body"]

    def listing(self, env, path, page=100):
        rows, offset = [], 0
        while True:
            body = self.read(env, "%s?count=%d&offset=%d" % (path, page, offset))
            rows += body["data"]
            offset += len(body["data"])
            if not body["data"] or offset >= body.get("total", offset):
                return rows


# ---------------------------------------------------------------- project (allowlist)

def _short_hash(value):
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha:" + hashlib.sha256(blob.encode()).hexdigest()[:8]


def _host(url):
    return urlparse(url).netloc if isinstance(url, str) and url else None


def _clean(d):
    return {k: v for k, v in d.items() if v is not None and v != [] and v != {}}


def project_connector(summary, detail):
    cfg = detail.get("config") or {}
    use_cases = {}
    for key, value in detail.items():
        if isinstance(value, dict) and "useCase" in value:
            use_cases[key] = _clean({
                "status": value.get("status"),
                "rules": _count_rules(value.get("config") or {}),
                "mapping": _short_hash(value.get("config")),
            })
    conditions = (cfg.get("retrievalConditions") or {}).get("salesOrder")
    return _clean({
        "id": detail.get("connectorId") or summary.get("connectorId"),
        "storefrontId": detail.get("storefrontId"),
        "name": detail.get("friendlyName") or summary.get("friendlyName"),
        "type": cfg.get("type") or summary.get("type"),
        "status": summary.get("status"),
        "confirmationsEnabled": detail.get("confirmationsEnabled"),
        "stockAdjustmentsEnabled": cfg.get("stockAdjustmentsEnabled"),
        "outboundTagsEnabled": cfg.get("outboundTagsEnabled"),
        "egressFiletype": cfg.get("egressFiletype"),
        "host": cfg.get("host"),
        "store": (cfg.get("instance") or {}).get("storeName"),
        "webhookHost": _host(cfg.get("webhookUrl")),
        "retrievalConditions": [
            _clean({k: c.get(k) for k in ("field", "operator", "type", "value")})
            for c in conditions
        ] if conditions else None,
        "useCases": use_cases,
    })


def _count_rules(config):
    rules = config.get("rules")
    if isinstance(rules, list):
        return len(rules)
    if isinstance(rules, dict):
        return sum(len(v) for v in rules.values() if isinstance(v, list))
    return None


def project_backend(backend):
    cfg = (backend or {}).get("config") or {}
    return _clean({
        "type": cfg.get("type"),
        "host": cfg.get("host"),
        "broadcastConfirmations": cfg.get("broadcastConfirmations"),
    })


def secret_values(node, acc=None):
    """Every string a secret-named key holds, anywhere in a raw payload."""
    acc = set() if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and v and k != "key" and SECRET_KEY.search(k):
                acc.add(v)
            else:
                secret_values(v, acc)
    elif isinstance(node, list):
        for v in node:
            secret_values(v, acc)
    return acc


def assert_no_secrets(projected, secrets):
    blob = json.dumps(projected, default=str)
    leaked = [s for s in secrets if len(s) >= 6 and s in blob]
    if leaked:
        raise RuntimeError("refusing to write a snapshot containing %d secret value(s)" % len(leaked))


def fetch_environment(client, env):
    """{businessId: env block} for one environment, plus every secret value seen."""
    businesses = client.listing(env, "/api/v1/business")
    summaries = client.listing(env, "/api/v1/connectors")
    backends = client.listing(env, "/api/v1/backend")
    with ThreadPoolExecutor(6) as pool:
        details = list(pool.map(
            lambda s: client.read(env, "/api/v1/connectors/" + s["connectorId"]), summaries))
    secrets = secret_values(backends) | secret_values(details)

    blocks = {}
    for b in businesses:
        blocks[b["businessId"]] = {
            "friendlyName": b.get("friendlyName"),
            "storefronts": [_clean({"id": s.get("storefrontId"), "name": s.get("friendlyName")})
                            for s in b.get("storefronts") or []],
            "connectors": [],
        }
    for summary, detail in zip(summaries, details):
        bid = detail.get("businessId") or summary.get("businessId")
        if bid in blocks:
            blocks[bid]["connectors"].append(project_connector(summary, detail))
    for backend in backends:
        bid = (backend.get("config") or {}).get("businessId")
        if bid in blocks:
            blocks[bid]["backend"] = project_backend(backend)
    for block in blocks.values():
        block["connectors"].sort(key=lambda c: (c.get("type") or "", c.get("name") or ""))
        block["storefronts"].sort(key=lambda s: s.get("name") or "")
    return blocks, secrets


# ---------------------------------------------------------------- diff

def _scalars(connector):
    out = {k: v for k, v in connector.items() if k not in ("id", "useCases", "retrievalConditions")}
    out["retrievalConditions"] = connector.get("retrievalConditions")
    for uc, info in (connector.get("useCases") or {}).items():
        out["mapping:" + uc] = info.get("mapping")
        out["status:" + uc] = info.get("status")
    return out


def diff_environment(env, old, new, today):
    """Change entries between two env blocks. A first sight (old is None) is a baseline, not a change."""
    changes = []

    def log(subject, summary):
        changes.append({"at": today, "env": env, "subject": subject, "summary": summary})

    if old is None:
        return changes
    if new is None:
        log("business", "no longer present in %s" % env)
        return changes
    old_sf = {s["id"]: s for s in old.get("storefronts", [])}
    new_sf = {s["id"]: s for s in new.get("storefronts", [])}
    for sid in new_sf.keys() - old_sf.keys():
        log("storefront", "added %s" % new_sf[sid].get("name"))
    for sid in old_sf.keys() - new_sf.keys():
        log("storefront", "removed %s" % old_sf[sid].get("name"))

    old_c = {c["id"]: c for c in old.get("connectors", [])}
    new_c = {c["id"]: c for c in new.get("connectors", [])}
    for cid in new_c.keys() - old_c.keys():
        log(new_c[cid].get("name", cid), "connector added (%s)" % new_c[cid].get("type"))
    for cid in old_c.keys() - new_c.keys():
        log(old_c[cid].get("name", cid), "connector removed")
    for cid in new_c.keys() & old_c.keys():
        a, b = _scalars(old_c[cid]), _scalars(new_c[cid])
        for field in sorted(a.keys() | b.keys()):
            if a.get(field) != b.get(field):
                if field.startswith("mapping:"):
                    log(new_c[cid]["name"], "%s mapping changed" % field.split(":", 1)[1])
                else:
                    log(new_c[cid]["name"], "%s: %s -> %s" % (field, a.get(field), b.get(field)))
    if old.get("backend") != new.get("backend"):
        log("backend", "%s -> %s" % (old.get("backend"), new.get("backend")))
    return changes


# ---------------------------------------------------------------- assemble + write

def load_snapshot(folder):
    f = Path(folder) / SNAPSHOT_FILE
    return (yaml.safe_load(f.read_text()) or {}) if f.exists() else {}


def build_snapshots(fetched, previous, today, now):
    """({businessId: snapshot}, {businessId: [change entries made by this run]}). `fetched` is {env: {businessId: block}}."""
    ids = sorted({bid for blocks in fetched.values() for bid in blocks})
    out, fresh = {}, {}
    for bid in ids:
        prev = previous.get(bid) or {}
        envs, changes, made = {}, list(prev.get("changes") or []), []
        for env, blocks in fetched.items():
            block = blocks.get(bid)
            if block is not None:
                envs[env] = {k: v for k, v in block.items() if k != "friendlyName"}
            old = (prev.get("environments") or {}).get(env)
            entries = diff_environment(env, old, block and envs.get(env), today)
            if prev and old is None and block is not None:
                entries.append({"at": today, "env": env, "subject": "business", "summary": "now present in %s" % env})
            made += entries
            changes = entries + changes
        name = next((b[bid]["friendlyName"] for b in fetched.values() if bid in b), bid)
        out[bid] = {
            "businessId": bid,
            "friendlyName": name,
            "synced": now,
            "environments": envs,
            "changes": changes[:CHANGE_LOG_LIMIT],
        }
        fresh[bid] = made
    return out, fresh


def write_snapshot(folder, snapshot):
    Path(folder).mkdir(parents=True, exist_ok=True)
    header = ("# Generated by `cust sync` from live config-service. Do not edit.\n"
              "# Secret-free by construction: allowlisted fields only.\n")
    (Path(folder) / SNAPSHOT_FILE).write_text(
        header + yaml.safe_dump(snapshot, sort_keys=False, default_flow_style=False, width=100))


def customer_kind(snapshot):
    prod = (snapshot.get("environments") or {}).get("prod")
    return "customer" if prod and prod.get("connectors") else "fixture"


def today_iso():
    return dt.date.today().isoformat()


# ---------------------------------------------------------------- generated stub

GENERATED = "config-snapshot"
INGRESS = {"sftp": ("sftp-connector", "SFTP drop"), "shopify": ("shopify-connector", "Shopify store"),
           "rest": ("fapi", "REST client"), "api": ("fapi", "REST client")}


def _label(use_cases):
    return ", ".join(use_cases) if use_cases else "no mappings"


def render_stub(snapshot, today):
    """overview.md for a business with no hand-written narrative. Present-tense config only."""
    bid, name = snapshot["businessId"], snapshot["friendlyName"]
    envs = snapshot.get("environments") or {}
    env = "prod" if "prod" in envs else "dev"
    block = envs.get(env) or {}
    connectors = block.get("connectors") or []
    types = sorted({c.get("type") or "unknown" for c in connectors})
    backend = block.get("backend") or {}
    where = "production" if env == "prod" else "dev only"

    if connectors:
        bluf = "%s has %d %s connector%s in %s%s. No narrative has been captured; this page is generated from live config." % (
            name, len(connectors), "/".join(types), "" if len(connectors) == 1 else "s", where,
            (" and lands in a %s backend" % backend["type"]) if backend.get("type") else "")
    else:
        bluf = "%s exists in config-service (%s) with no connectors. No narrative has been captured." % (name, where)

    lines = ["---", "tags: [customer, %s]" % bid, "verified: '%s'" % today,
             "verified_against: cust sync (config-service)", "generated: %s" % GENERATED,
             "title: %s — overview" % name.replace(":", " -"),
             "thesis: %s" % json.dumps(bluf), "confidence: high", "---",
             "# %s — overview" % name, "",
             "```orient-bluf", json.dumps({"v": 1, "bluf": bluf, "confidence": "high", "action": "none"}), "```", ""]

    if connectors:
        nodes, edges = [], []
        for i, t in enumerate(types):
            svc, source = INGRESS.get(t, (None, "%s source" % t))
            nodes.append({"id": "s%d" % i, "label": "%s %s" % (name, source) if len(types) > 1 else name,
                          "sub": source, "kind": "external"})
            if svc:
                nodes.append({"id": "i%d" % i, "label": svc, "kind": "service", "service": svc, "ev": [1]})
                edges += [{"from": "s%d" % i, "to": "i%d" % i}, {"from": "i%d" % i, "to": "pipe"}]
            else:
                edges.append({"from": "s%d" % i, "to": "pipe"})
        nodes.append({"id": "pipe", "label": "Fuse core pipeline", "sub": "collector, dedupe-service, snap-adapter", "kind": "external"})
        edges.append({"from": "pipe", "to": "wms"})
        nodes.append({"id": "wms", "label": (backend.get("type") or "WMS").upper(),
                      "sub": backend.get("host"), "kind": "external", "ev": [1]})
        lines += ["## Integration shape", "", "```orient-flow",
                  json.dumps({"v": 1, "title": "%s: channels in" % name, "nodes": nodes, "edges": edges}), "```", ""]

    def pairs(e):
        return {(c.get("type"), u) for c in (e or {}).get("connectors") or [] for u in (c.get("useCases") or {})}

    mirrors = "prod" in envs and "dev" in envs and pairs(envs["prod"]) == pairs(envs["dev"])
    for env_key, label in (("prod", "Production"), ("dev", "Dev")):
        eb = envs.get(env_key)
        if not eb or not eb.get("connectors"):
            continue
        if env_key == "dev" and mirrors:
            lines += ["## Dev connectors", "", "Dev maps the same use cases per channel as production.", ""]
            continue
        lines += ["## %s connectors" % label, "",
                  "| Connector | Type | Use cases | Confirmations | Mappings |", "| --- | --- | --- | --- | --- |"]
        for c in eb["connectors"]:
            ucs = list((c.get("useCases") or {}).keys())
            lines.append("| %s | %s | %s | %s | %d |" % (
                c.get("name"), c.get("type"), _label(ucs),
                "on" if c.get("confirmationsEnabled") else "off", len(ucs)))
        lines.append("")

    lines += ["## Evidence", "", "```orient-evidence",
              json.dumps({"v": 1, "items": [{"id": 1, "kind": "log",
                                             "ref": "cust sync -> config-service (%s), %s" % (env, today),
                                             "note": "connectors, use cases, confirmation flags and backend type, read live"}]}),
              "```", ""]
    return "\n".join(lines)


def render_report(fresh, snapshots, previous, narrative, problems=()):
    """Digest-ready markdown for what this run changed. `narrative` is the set of businessIds with hand-written docs."""
    prev_times = sorted(p["synced"] for p in previous.values() if p.get("synced"))
    since = "since %s" % prev_times[0] if prev_times else "baseline run, nothing to compare"
    prod = [(b, c) for b, cs in fresh.items() for c in cs if c["env"] == "prod"]
    dev = {}
    for b, cs in fresh.items():
        n = sum(1 for c in cs if c["env"] == "dev")
        if n:
            dev[b] = n
    n_prod = sum(1 for s in snapshots.values() if "prod" in s["environments"])
    lines = ["Synced %d businesses (%d in prod, %d dev only), %s: **%d prod change%s**, %d dev change%s."
             % (len(snapshots), n_prod, len(snapshots) - n_prod, since, len(prod), "" if len(prod) == 1 else "s",
                sum(dev.values()), "" if sum(dev.values()) == 1 else "s"), ""]
    if prod:
        lines += ["**Production changes**", "", "| Business | Subject | Change |", "| --- | --- | --- |"]
        for b, c in sorted(prod, key=lambda x: x[0]):
            lines.append("| [[Customers/%s/overview\\|%s]] | %s | %s |" % (b, b, c["subject"], c["summary"]))
        lines.append("")
        stale = sorted({b for b, _ in prod if b in narrative})
        if stale:
            lines += ["**Narrative may be stale** (hand-written docs exist; run `customer-sync`): %s" % ", ".join(stale), ""]
    if dev:
        lines += ["**Dev changes** (by business): %s" % ", ".join("%s (%d)" % kv for kv in sorted(dev.items())), ""]
    if problems:
        lines += ["**Could not process:** %s" % ", ".join(problems), ""]
    return "\n".join(lines).rstrip() + "\n"
