# HoloChain - Tamper-Evident Append-Only Memory

Core tool for Holo/Sim Systems Continuity Engine.  
Provides cryptographically verifiable, append-only storage that survives resets and works for everyone.

## Quick Start

```python
from holosim.holo_chain import HoloChain

# Initialize (creates the file automatically)
chain = HoloChain("my_memory.jsonl")

# Append data
chain.append("Plain text entry from Canyon")
chain.append({"key": "value", "user": "Canyon", "note": "Structured data"})

# Verify and load
loaded = chain.load_and_verify()
print(f"Total entries: {len(loaded)}")

python holo_chain.py append "Your message here"
python holo_chain.py verify