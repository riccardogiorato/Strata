> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Conversation-cache correction, 2026-10-20

The installed Strata 0.2.1 Q2_0 / 128K configuration inherited a disabled
multi-conversation cache. Real alternating 85K–92K requests reused zero
tokens and spent about 124–132 seconds reading each full history.
`before-metrics.json` records budget 0, 17 requests and zero reused tokens.
The installation checks did not test alternating conversations.

Both standing Q2_0 0.2.1 configurations now set an 8192 MiB host-RAM
conversation budget, 2 parked slots, and a 1024-token minimum to avoid
parking tiny side requests. The default physical RAM floor is retained.
The GPU cap, model, context, engine and Turing settings are unchanged.
Original configurations are saved beside this report with `.before` suffixes.
The managed service was restarted immediately after the user explicitly
requested it; in-flight calls were interrupted. It remains enabled at boot.

The live-server A→B→A→B test used separate real-code prompts of 3907 and
3908 tokens. Returning to A reused 3900 tokens and read 28; returning to B
reused 3901 and read 28. Follow-ups took 0.569 and 0.499 seconds, including
restore, prefill and generation. The engine reported two restores, three
parks, no evictions and about 460 MiB retained at the final snapshot.
`alternation.json`, raw responses, `after-metrics.json` and `alternation.log`
retain these measurements. This is a small alternating-session validation,
not a successful 90K-per-conversation test or a guarantee that arbitrary
histories fit. Real sessions each need an initial warm read after restart;
unchanged token prefixes are required for reuse. Cache admissions can still
be skipped when snapshots exceed the budget or physical RAM headroom.

`check-alternation.py` reproduces the live-server test. It sends requests to
the single managed engine; it does not start an additional GPU process.
The earlier idle-boundary watcher was cancelled before the explicit restart.
