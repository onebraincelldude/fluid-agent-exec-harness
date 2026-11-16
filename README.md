# agent-exec-harness
Execution reliability harness for tool-calling agents. Runs a task suite with guardrails
(only allow-listed tools, argument validation), retries transient tool failures with
backoff while never retrying permanent ones, requires an audit log entry per tool call,
and scores task completion against golden outcomes. Gates in `cases.json`; any agent
callable via `python run.py my_agent.py` (exposing `run(task)`). `python run.py` runs the
naive demo agent, which the harness blocks.
