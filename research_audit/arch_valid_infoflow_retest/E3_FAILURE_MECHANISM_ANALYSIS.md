# E3 — Info-flow difference analysis (VALID runs only)

Buckets on the diagnostic 24 (gold compared; all runs VALID_RUN):

| Bucket | n | IDs |
|--------|---|-----|
| Both correct | 12 | — |
| **A** Direct✓ Initial✗ | **1** | `lvbench_1634` |
| **B** Initial✓ Direct✗ | **7** | `1885, 3030, 4167, 4182, 5137, 542, 730` |
| **C** Both✗ | **4** | `13, 22, 255, 3229` |

Below: **observational** notes from tool traces. Correct/incorrect alone does not prove a unique mechanism.

## A — Direct only (`lvbench_1634`, reasoning)

- Initial **did** use vision: transcript + overview + 2× inspect; **48** Qwen frames; DeepSeek×5.  
- Observations discuss interview timing / post-interview context; final answer **B** vs gold **C** (Direct **C**).  
- Plausible reading: **evidence acquired but answerer/routing erred**, not “zero vision”. Cannot assert missing frames without frame-level gold.

## B — Initial only (7)

Common pattern: Initial gets **non-empty successful** overview/scan/inspect text; Direct 32-frame VQA picks a wrong letter.

Examples:

- `lvbench_1885` (event understanding): single overview, 32 frames, answer A=gold; Direct B.  
- `lvbench_3030` (event understanding): heavy search (96 frames, multi scan/inspect); answer D=gold; Direct B.  
- `lvbench_4167` (summarization): overview-only, D=gold; Direct B.

**Observable:** adaptive search + DeepSeek synthesis can beat uniform 32-frame Direct on event/summary items in this set.  
**Not proven:** that Direct “never saw” the cue—only that end-to-end Direct failed while Initial succeeded with successful tool returns.

Event-understanding type: Initial 3/4, Direct **0/4** — strongest type-level signal; still small-n.

## C — Both wrong (4)

- `lvbench_13` (temporal grounding): Initial inspect-only (8 frames) → D; Direct → D; gold C. Shared wrong letter.  
- `lvbench_3229` (summarization): Initial scan (16 frames) → C; Direct → B; gold D. Different wrong answers.

These look like **hard / under-specified retrieval**, not env breakage. Limited RSI “fix Initial→Direct” upside here (oracle only +1 over Initial).

## Mechanism summary (cautious)

1. Env-fixed Initial is **not** vision-starved on discordant items in A/B (tools return text; meters > 0).  
2. Dominant gap vs Direct is **B** (Initial wins), not A — opposite of the invalid Phase D narrative.  
3. Residual errors are mostly **C** plus one **A** (possible answerer misuse).  
4. Perfect I/D selector adds only **+1** over always-Initial → weak case that “missing Direct path” is the binding bottleneck on this set.
