# EnvPath

A local workspace for chat, retained evidence lookup, and exportable drafts.
Author: Canyon Brock Haney. Implementation: Codex.

From the repository directory:

```powershell
python -m holosim.envpath
```

This opens `http://127.0.0.1:8766/`. Stop the server with Ctrl+C in the terminal.
No new runtime packages are required. The selected chain defaults to the
existing `holo_memory.jsonl`; an absent chain stays absent and displays zero
records. EnvPath never seeds, repairs, appends, or overwrites that file.

## Chat

Chat needs an already-running local Ollama service and a tool-capable model.
EnvPath does not install Ollama, download models, or start background services.
Inspect installed models with `ollama list`, then select one explicitly:

```powershell
python -m holosim.envpath --model qwen2.5:7b
```

Ollama requests explicitly use CPU execution (`num_gpu: 0`).

Other options: `--chain-file PATH`, `--port 8766`, `--no-browser`, and
`--ollama http://127.0.0.1:11434/api/chat`. The model endpoint must be HTTP
loopback and cannot redirect. It is a chat transport, separate from HOLO's
existing JSON software-proposal adapter. The default model name is a starting
configuration, not a claim that it is installed or sufficient.

Answers stream into the conversation. Actual tool results appear in the tool
activity panel, including errors. The executable tool allowlist consists of:

- `search_retained`: historical content search, with index and hash references.
- `read_retained`: exact record lookup and explicit correction/revalidation links.
- `prepare_draft`: construct a proposal without writing it to disk or memory.

Some Ollama templates return a tool request as content instead of `tool_calls`.
EnvPath recognizes only a complete JSON object with exactly `name` and
`arguments`, a known tool name, object arguments, and no duplicate keys. It
uses the same dispatcher, limits, and diagnostics. Prose and embedded examples
are never extracted as calls; control JSON is excluded from the final answer.

The model receives no shell, network-search, append, authorization, file-write,
or execution tool. Record content is evidence, not instructions. Generated
answers can still be wrong; inspect their source records and tool results.
Chat doesn't establish truth, current environmental state, or acceptance.

Stop cooperatively cancels between model chunks and before queued tools.
A blocked local socket read can take up to its 180-second timeout to return;
Stop cannot undo work already performed. Only one model turn runs at a time.
Failed and cancelled turns are excluded from subsequent chat history. New chat
clears the browser's bounded conversation and diagnostic view. Nothing is
automatically saved. Existing tool exchanges are shown in diagnostics; past
model context is a bounded user/assistant text history, not persistent memory.

## Evidence and drafts

Search works with Ollama offline. Results retain the original entry and show
links rather than silently replacing it with corrected text. Open a result to
inspect its full decoded content, exact hash, and linked records. A hash match
establishes bounded identity, not truth or permission.

To prepare a correction, open an original record and choose **Use as correction
target**. Write the proposal and choose **Prepare draft**. For a new note, select
**New note**. The resulting JSON binds the draft content, selected source-file
digest, source head, and exact correction target (when applicable). All drafts
remain `PROPOSAL_ONLY`, `accepted: false`, `truth_claimed: false`, with write and
execution authority `NONE`. A draft hash does not approve its contents.

**Download proposal JSON** exports through the browser. It does not append,
correct, or import into HOLO. Review and authorized persistence require the
existing separate workflow; EnvPath does not yet provide that workflow in its
interface. A future importer must revalidate target, current head, and separate
authorization. Do not treat a downloaded proposal as an execution permit.

Evidence is verified through `build_continuity_topology`. Source-file bytes
are checked before and after projection; a change during a model turn prevents
a completed answer. Partial streamed text may already be visible and is marked
incomplete. These checks do not freshly observe the external environment.

Workspace limits: 8 MiB selected chain, 24 KiB per decoded record, 12 search
results (with total count and explicit preview limits), 4 model rounds, 8 tool
calls, 16,000 output characters, and bounded request/history/stream bytes.
These are workspace transport limits, not token-count or memory-allocation
guarantees; underlying HOLO validation occurs before decoded-size checking.

The server binds only to local IPv4 loopback. Host validation, a per-launch
request token, same-origin POST checks, closed request schemas, and an inline
script/style nonce protect the browser interface. Evidence/model text is
rendered with `textContent`, never as executable HTML. This is a local personal
workspace, not a multi-user authenticated service.

## Scope and inspiration

Classification: **PARTIAL** — a usable first workspace over retained HOLO
records. It does not yet integrate arbitrary document archives, authorized
commit UI, web search, audio playback, narration, or autonomous tasks.

The comparison with [Felhaven](https://github.com/Felsyn/felhaven) informed
the separation of chat, tool diagnostics, and display. EnvPath is independently
implemented; no Felhaven code is copied. HOLO remains the owner of evidence
verification and authority boundaries.

Focused verification:

```powershell
python -m pytest -q tests/test_envpath.py
```
