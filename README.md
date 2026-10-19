# alexa-plus-mcp

Alexa+ MCP server for the Amazon Developer Hackathon 2026

## What this is not

This repository contains no code from the Zealous Mirror ecosystem. That is not
an assurance, it is a gate: `tools/selftest_no_ecosystem_code.py` hashes every
file here against every text file in the private repositories with whitespace
normalised, so a reindented copy is still caught. It also refuses to pass
unless it can first prove it can see those repositories, because a search that
found nothing because it looked nowhere is the failure it exists to prevent.

Run it:

    bash tools/gate_cycle.sh

## Licence

Not chosen yet. See `LICENSE`. This has to be settled before the first public
push.
