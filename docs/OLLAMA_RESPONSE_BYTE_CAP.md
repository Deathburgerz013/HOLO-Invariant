# Shared Ollama response byte cap

The shared `request_local_ollama_json` adapter previously called `read()`
without a size. It now requests at most 1,048,577 bytes from the response:
a 1,048,576-byte envelope limit plus one overflow-detection byte. Oversized
responses raise `LocalOllamaAdapterError` before decoding or JSON parsing.
An envelope exactly at the limit can still pass the existing JSON checks.
The response context closes on success, overflow, parsing failure, or read error.

This is an intentional compatibility restriction: callers returning larger
envelopes now receive an explicit error. Injected response objects must support
the standard `read(size)` interface. The handoff recorder's in-memory wrapper
supports that interface; its existing tighter capture cap stays in place.
No retained run file is rewritten and receipt fields are unchanged.

Tests use small limits and a stream that records the requested size. They cover
below-limit, exact-limit, overflow, rejection before parsing, context closure,
the production read size, and existing parse/read error behavior. They do not
allocate a huge payload or demonstrate an OOM attack.

This cap bounds the raw bytes requested by this adapter from a compliant
response reader. It does not cap server generation, all process memory, JSON
nesting, elapsed time, or an injected reader that ignores its size argument.
It does not establish model correctness, authenticated emission, or authority.
Token budgets and broader parser/resource controls remain separate work.
