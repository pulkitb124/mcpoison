# MCPoison

**Measuring (and defending against) indirect prompt injection in MCP agents.**

AI agents read data from the outside world through tools — documents, tickets, web
pages, database rows. Because a language model can't cleanly separate *its
instructions* from *the data it's reading*, an attacker can hide instructions inside
that data and hijack the agent. This is called **indirect prompt injection**.

MCPoison is a controlled, sandboxed testbed for studying this problem in agents built
on the **Model Context Protocol (MCP)**. It asks three questions:

1. **Where can the poison hide?** We compare two delivery vectors:
   - **Tool output** — instructions hidden in the content a tool returns (the classic vector).
   - **Tool descriptions** — instructions hidden in a tool's metadata that the agent reads
     to decide *how* to use it (an MCP-native vector that is far less studied).
2. **What actually protects the agent?** We run proposed defenses head-to-head and
   measure not just how much they reduce attacks, but how much they hurt the agent's
   ability to do its real job.
3. **What makes it worse?** How susceptibility varies across models, attack phrasing,
   and agent autonomy.

## Status

Early scaffolding. See the process outline below for where this is headed.

## Safety & ethics

All attacks run inside a sandbox against **local canary services** — nothing harmful
happens for real. The goal is to help defenders measure and mitigate a known class of
vulnerability, not to enable attacks.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[analysis,dev]"
cp .env.example .env   # then fill in your API keys
```

## Layout

```
src/mcpoison/     # library code (agent loop, MCP tools, attacks, defenses)
```
