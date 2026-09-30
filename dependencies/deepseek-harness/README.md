# DeepSeek Harness integration

Upstream: https://github.com/deepseek-ai/deepseek-harness.git

Pinned source commit: `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`.
The project specifies Node `^22.19.0 || >=24.0.0` and pnpm `11.7.0`.
Install the dependency source and node_modules separately using the steps below.

The included `local-adaptations.patch` adapts file access, DeepSeek message
serialization and tool calls, with corresponding upstream test changes.
The session entry point is `solver_full_workspace/editor/headless.ts` in the
main package. See `LICENSE` in this directory for the upstream license.

Install in a new dependency directory and apply the patch once:

```bash
git clone https://github.com/deepseek-ai/deepseek-harness.git /your/deepseek-harness
git -C /your/deepseek-harness checkout --detach b150a551b8d465e31e418e1b2eaf5e79bbb7d28e
git -C /your/deepseek-harness apply /absolute/path/to/this-package/dependencies/deepseek-harness/local-adaptations.patch
cp /absolute/path/to/this-package/solver_full_workspace/editor/headless.ts /your/deepseek-harness/packages/bundle/headless/src/full-candidate-runner.ts
cd /your/deepseek-harness
pnpm install --frozen-lockfile
pnpm run build:lib:host
```

Use the pinned commit and adaptation files above. The engine runs through the
source workspace's CLI and tsx loader. engine/editor.py generates a profile in
each private session directory. Solver-only execution does not require this Node
dependency; investigation and editing do.
