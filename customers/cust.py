#!/usr/bin/env python3
"""Customers — deterministic state/context helper for the customer-* skills.

Everything this owns lives in the Obsidian vault, one folder per business. Unlike
Waypoint (git-anchored, one folder per repo), a customer isn't a repo — there is no
commit history to diff staleness against. Freshness here is a `last_synced` date
stamped by `customer-sync` after it reconciles captured facts against live
config-service state; this script only tracks *when*, not *what changed* — the diff
itself is the sync skill's job (it has live MCP config-service access this script
does not).
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
import os

import yaml

VAULT = Path(os.environ.get("CUSTOMERS_VAULT", Path.home() / "Documents/obsidian"))
CUST = VAULT / "Customers"
NON_DOC_FILES = {"ledger.md", "customer.yaml"}
STALE_AFTER_DAYS = 30
TODAY = dt.date.today().isoformat()


def die(msg, code=1):
    print("cust: %s" % msg, file=sys.stderr)
    sys.exit(code)


FM = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)


def read_fm(path: Path):
    if not path.exists():
        return {}, ""
    text = path.read_text()
    m = FM.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    return data, m.group(2)


def write_fm(path: Path, data: dict, body: str):
    fm = yaml.safe_dump(data, sort_keys=False, default_flow_style=False).strip()
    path.write_text("---\n%s\n---\n%s" % (fm, body.lstrip("\n")))


def normalize(business_id: str) -> str:
    return (business_id or "").strip().upper()


def days_since(iso_date: str):
    if not iso_date:
        return None
    try:
        d = dt.date.fromisoformat(iso_date)
    except ValueError:
        return None
    return (dt.date.today() - d).days


def load_customer_yaml(d: Path):
    f = d / "customer.yaml"
    if not f.exists():
        return {}
    return yaml.safe_load(f.read_text()) or {}


def save_customer_yaml(d: Path, data: dict):
    (d / "customer.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    )


def ledger_recent(d: Path, n=5):
    f = d / "ledger.md"
    if not f.exists():
        return []
    lines = f.read_text().splitlines()
    out = []
    for i, l in enumerate(lines):
        if not l.startswith("## "):
            continue
        title = next((x.strip() for x in lines[i + 1:i + 4] if x.strip()), "")
        out.append("%s — %s" % (l[3:].strip(), title[:90]))
        if len(out) == n:
            break
    return out


# ------------------------------------------------------------------- commands

def locate(business_id):
    bid = normalize(business_id)
    if not bid:
        die("a business id is required")
    d = CUST / bid
    return {"businessId": bid, "vault": str(d), "onboarded": (d / "customer.yaml").exists()}


def cmd_locate(a):
    print(json.dumps(locate(a.business_id), indent=2))


def cmd_init(a):
    bid = normalize(a.business_id)
    d = CUST / bid
    d.mkdir(parents=True, exist_ok=True)
    cy = d / "customer.yaml"
    if not cy.exists():
        save_customer_yaml(d, {
            "businessId": bid,
            "friendlyName": a.friendly_name or bid,
            "environment": a.environment or "production",
            "connectors": [],
            "wms": [],
            "created": TODAY,
            "last_synced": None,
        })
    led = d / "ledger.md"
    if not led.exists():
        led.write_text(
            "---\ntags: [customer, ledger]\n---\n# %s — customer ledger\n\n"
            "Agent-facing. Newest first. Incidents, config decisions, and the reasoning\n"
            "behind them. Not a diary, not a support log — what a future agent needs before\n"
            "touching this customer's config again.\n\n" % bid
        )
    print("initialised %s" % d)


def cmd_context(a):
    info = locate(a.business_id)
    d = Path(info["vault"])
    print("business: %s | vault: %s | onboarded: %s"
          % (info["businessId"], d, "yes" if info["onboarded"] else "NO"))
    if not info["onboarded"]:
        print("\n!! not onboarded — ask the user whether to run customer-onboard before proceeding")
        return

    meta = load_customer_yaml(d)
    print("\n--- customer.yaml ---")
    print(yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip())

    ls = meta.get("last_synced")
    ds = days_since(ls) if ls else None
    if ds is None:
        print("\n!! never synced — run customer-sync before trusting captured config facts")
    elif ds > STALE_AFTER_DAYS:
        print("\n!! last synced %d days ago (>%d) — re-run customer-sync before trusting captured config facts"
              % (ds, STALE_AFTER_DAYS))
    else:
        print("\nsynced %d day(s) ago — within freshness window" % ds)

    docs = [f for f in sorted(d.glob("*.md")) if f.name not in NON_DOC_FILES]
    if docs:
        print("\n--- docs ---")
        for f in docs:
            fm, _ = read_fm(f)
            print("  %-18s verified %s" % (f.name, fm.get("verified", "unverified")))

    led = ledger_recent(d)
    if led:
        print("\n--- ledger (last %d — never read the whole file) ---" % len(led))
        for h in led:
            print("  %s" % h)


def cmd_list(a):
    if not CUST.is_dir():
        die("no %s yet — nothing onboarded" % CUST)
    rows = []
    for p in sorted(CUST.iterdir()):
        if not p.is_dir():
            continue
        meta = load_customer_yaml(p)
        ls = meta.get("last_synced")
        ds = days_since(ls) if ls else None
        flag = "NEVER SYNCED" if ds is None else ("STALE:%dd" % ds if ds > STALE_AFTER_DAYS else "ok")
        connectors = meta.get("connectors") or []
        rows.append({
            "businessId": p.name,
            "friendlyName": meta.get("friendlyName", p.name),
            "connectors": len(connectors),
            "wms": ",".join(meta.get("wms") or []) or "-",
            "flag": flag,
        })
    if not rows:
        print("(no customers onboarded yet)")
        return
    for r in rows:
        print("%-14s %-32s connectors=%-3d wms=%-10s sync=%s"
              % (r["businessId"], r["friendlyName"][:32], r["connectors"], r["wms"], r["flag"]))


def cmd_ledger(a):
    info = locate(a.business_id)
    d = Path(info["vault"])
    if not info["onboarded"]:
        cmd_init(argparse.Namespace(business_id=info["businessId"], friendly_name=None, environment=None))
    led = d / "ledger.md"
    body = a.body if a.body else sys.stdin.read()
    head = "## %s — %s" % (a.date or TODAY, a.title or "note")
    entry = "%s\n\n%s\n" % (head, body.strip())
    text = led.read_text()
    parts = text.split("\n## ", 1)
    if len(parts) == 2:
        led.write_text("%s\n\n%s\n## %s" % (parts[0].rstrip(), entry, parts[1]))
    else:
        led.write_text("%s\n\n%s" % (text.rstrip(), entry))
    print("appended to %s: %s" % (led, head))


def cmd_synced(a):
    info = locate(a.business_id)
    if not info["onboarded"]:
        die("%s is not onboarded — run customer-onboard first" % info["businessId"])
    d = Path(info["vault"])
    meta = load_customer_yaml(d)
    meta["last_synced"] = TODAY
    save_customer_yaml(d, meta)
    print("stamped last_synced=%s for %s" % (TODAY, info["businessId"]))


def cmd_sync(a):
    """Live config-service -> config.snapshot.yaml per business; stub overview for the un-narrated."""
    sys.path.insert(0, str(Path(__file__).parent))
    import config_snapshot as cs

    real_stdout = sys.stdout
    if a.report:
        sys.stdout = sys.stderr  # progress lines must not leak into the digest section

    client = cs.FuseConfig.from_claude_config()
    envs = [e for e in ("prod", "dev") if not a.env or a.env == e]
    fetched, secrets = {}, set()
    for env in envs:
        fetched[env], seen = cs.fetch_environment(client, env)
        secrets |= seen
        print("%-4s %d businesses, %d connectors" % (
            env, len(fetched[env]), sum(len(b["connectors"]) for b in fetched[env].values())))

    wanted = {normalize(x) for x in a.only} if a.only else None
    previous = {p.name: cs.load_snapshot(p) for p in CUST.iterdir() if p.is_dir()} if CUST.is_dir() else {}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    snapshots, fresh = cs.build_snapshots(fetched, previous, TODAY, now)
    changed = created = stubs = 0
    for bid, snap in snapshots.items():
        if wanted and bid not in wanted:
            continue
        cs.assert_no_secrets(snap, secrets)
        d = CUST / bid
        new_changes = len(snap["changes"]) - len((previous.get(bid) or {}).get("changes") or [])
        changed += 1 if new_changes > 0 else 0
        if a.dry_run:
            continue
        cs.write_snapshot(d, snap)
        meta = load_customer_yaml(d)
        if not meta:
            created += 1
            cmd_init(argparse.Namespace(business_id=bid, friendly_name=snap["friendlyName"], environment=None))
            meta = load_customer_yaml(d)
        if "kind" not in meta:
            meta["kind"] = cs.customer_kind(snap)
            save_customer_yaml(d, meta)
        ov = d / "overview.md"
        if not ov.exists() or "generated: %s" % cs.GENERATED in ov.read_text()[:400]:
            ov.write_text(cs.render_stub(snap, TODAY))
            stubs += 1
    summary = ("%s%d snapshots, %d with changes, %d new customer folders, %d generated overviews"
               % ("(dry run) " if a.dry_run else "", len(wanted or snapshots), changed, created, stubs))
    if a.report:
        narrative = {p.name for p in CUST.iterdir() if p.is_dir()
                     and any((p / f).exists() for f in ("known-context.md", "architecture.md"))}
        sys.stdout = real_stdout
        print(cs.render_report(fresh, snapshots, previous, narrative))
    else:
        print(summary)


def cmd_index(a):
    if not CUST.is_dir():
        die("no %s yet" % CUST)
    lines = ["---", "tags: [customers]", "---", "# Customers", "",
             "One folder per business (keyed by config-service `businessId`). Inside each:", "",
             "- `customer.yaml` — cheap orientation index (not documentation)",
             "- `config.snapshot.yaml` — generated by `cust sync` from live config-service, secret-free; do not edit",
             "- `overview.md` — who they are, channels/integrations, business facts",
             "- `architecture.md` — integration diagram: upstream systems → channel(s) → connector(s) → WMS(es)",
             "- `known-context.md` — config quirks, gotchas, decisions and why, `## Captured Config`, `## Unknowns`",
             "- `ledger.md` — agent-facing record of incidents and config decisions, newest first", "",
             "Fuse MCP (config-service) is implementation truth. This vault is *why it's set that*",
             "*way* and what broke because of it. Regenerate this page with `cust index`.", "",
             "| Business | Friendly name | Connectors | WMS | Last synced |",
             "| --- | --- | --- | --- | --- |"]
    for p in sorted(CUST.iterdir()):
        if not p.is_dir():
            continue
        meta = load_customer_yaml(p)
        snap = (yaml.safe_load((p / "config.snapshot.yaml").read_text()) or {}) if (p / "config.snapshot.yaml").exists() else {}
        env = (snap.get("environments") or {}).get("prod") or (snap.get("environments") or {}).get("dev") or {}
        connectors = len(env.get("connectors") or meta.get("connectors") or [])
        wms = ((env.get("backend") or {}).get("type") or "").upper() or ", ".join(meta.get("wms") or []) or "?"
        ls = meta.get("last_synced") or "never"
        lines.append("| [[Customers/%s/overview\\|%s]] | %s | %d | %s | %s |"
                     % (p.name, p.name, meta.get("friendlyName", p.name), connectors, wms, ls))
    (CUST / "index.md").write_text("\n".join(lines) + "\n")
    print("wrote %s" % (CUST / "index.md"))


def main():
    ap = argparse.ArgumentParser(prog="cust", description="Fuse Customers vault helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("locate", help="resolve a business id to its vault folder")
    p.add_argument("business_id")
    p.set_defaults(fn=cmd_locate)

    p = sub.add_parser("init", help="create the vault folder, index and ledger")
    p.add_argument("business_id")
    p.add_argument("--friendly-name")
    p.add_argument("--environment")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("context", help="the orientation bundle: index, sync freshness, ledger")
    p.add_argument("business_id")
    p.set_defaults(fn=cmd_context)

    p = sub.add_parser("list", help="every onboarded customer, one line each, sync freshness flagged")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("ledger", help="prepend an entry (agent-facing record)")
    p.add_argument("business_id")
    p.add_argument("--title", required=True)
    p.add_argument("--date")
    p.add_argument("--body", help="entry body; omit to read stdin")
    p.set_defaults(fn=cmd_ledger)

    p = sub.add_parser("synced", help="stamp last_synced=today after customer-sync reconciles drift")
    p.add_argument("business_id")
    p.set_defaults(fn=cmd_synced)

    p = sub.add_parser("sync", help="snapshot live config-service state for every business (secret-free)")
    p.add_argument("--env", choices=["prod", "dev"])
    p.add_argument("--only", nargs="+", metavar="BUSINESS_ID")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report", action="store_true", help="print digest-ready markdown of what this run changed")
    p.set_defaults(fn=cmd_sync)

    p = sub.add_parser("index", help="regenerate Customers/index.md")
    p.set_defaults(fn=cmd_index)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
