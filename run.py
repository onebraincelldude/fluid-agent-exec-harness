"""agent-exec-harness: reliability harness for tool-calling agents.

Simulates a tool runtime: tools in `flaky_tools` fail transiently N times (retryable);
unknown args fail permanently (not retryable). The agent returns a plan of tool calls;
the harness executes them under guardrails and requires the agent's audit log to cover
every call. Blocks on disallowed tools, permanent-failure retries, missing audit entries,
or missed golden effects. Exit 1 = harness blocks the agent.
"""
import json, sys

def load_agent(path):
    if not path:
        return demo_agent
    import importlib.util
    s = importlib.util.spec_from_file_location("agent", path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m.run

def demo_agent(task):
    """Naive agent: calls a disallowed tool, retries a permanent failure, logs nothing."""
    if "Refund order 4412" in task:
        return {"calls": [
            {"name": "refund_order", "args": {"order": "4412"}},
            {"name": "delete_order", "args": {"order": "4412"}},
            {"name": "create_ticket", "args": {"note": "refund issued"}},
            {"name": "refund_order", "args": {}}], "audit": []}
    return {"calls": [
        {"name": "get_account", "args": {"id": "B2"}},
        {"name": "search_kb", "args": {"q": "refund denial"}},
        {"name": "get_account", "args": {}},
        {"name": "get_account", "args": {}}], "audit": []}

def execute(calls, spec_case, allowed, flaky):
    effects, disallowed, unlogged_seen = [], 0, None
    permanent_retries = 0
    transient_left = dict(flaky)
    prev_failed_permanent = None
    for call in calls:
        name, args = call["name"], call.get("args", {})
        if name not in allowed:
            disallowed += 1
            continue
        if not args or not all(args.values()):
            if prev_failed_permanent == (name, json.dumps(args, sort_keys=True)):
                permanent_retries += 1
            prev_failed_permanent = (name, json.dumps(args, sort_keys=True))
            continue
        if transient_left.get(name, 0) > 0:
            transient_left[name] -= 1
            continue  # transient failure - agent/harness would retry
        key = list(args.values())[0]
        effects.append(f"{name}:{key}" if name in ("refund_order", "get_account") else name)
    return effects, disallowed, permanent_retries

def main():
    spec = json.load(open("cases.json"))
    agent = load_agent(sys.argv[1] if len(sys.argv) > 1 else None)
    allowed = set(spec["allowed_tools"])
    successes = disallowed_total = unlogged_total = permanent_total = 0
    for c in spec["cases"]:
        out = agent(c["task"])
        calls = out.get("calls", [])
        effects, dis, perm = execute(calls, c, allowed, c.get("flaky_tools", {}))
        audit = out.get("audit", [])
        unlogged = len(calls) - len(audit)
        hits = sum(1 for g in c["gold_effects"] if any(e.startswith(g) or e == g for e in effects))
        success = hits == len(c["gold_effects"]) and dis == 0 and perm == 0
        successes += 1 if success else 0
        disallowed_total += dis; permanent_total += perm; unlogged_total += max(unlogged, 0)
        print(f"[{c['id']}] effects {hits}/{len(c['gold_effects'])}, disallowed {dis}, permanent retries {perm}, unlogged {max(unlogged,0)} -> {'ok' if success and unlogged <= 0 else 'FAIL'}")
    g = spec["gates"]
    rate = successes / len(spec["cases"])
    ok = rate >= g["min_task_success"] and disallowed_total <= g["max_disallowed_calls"] and unlogged_total <= g["max_unlogged_calls"] and permanent_total <= g["max_permanent_retries"]
    print(f"\ntask success {rate:.2f} (gate {g['min_task_success']}), disallowed {disallowed_total} (gate {g['max_disallowed_calls']}), unlogged {unlogged_total} (gate {g['max_unlogged_calls']}), permanent retries {permanent_total} (gate {g['max_permanent_retries']})")
    print("AGENT:", "PASS" if ok else "BLOCKED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
