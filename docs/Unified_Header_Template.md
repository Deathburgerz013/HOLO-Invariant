# Unified_Header_Template.md
**DOCUMENT_TYPE:** HOLO_UNIFIED_HEADER_TEMPLATE  
**VERSION:** v1.0_20260529  
**STATUS:** STABLE  
**ANCHOR:** CANYON_BROCK_HANEY (@CanyonBHaney / A Dark Moment)  
**DATE:** YYYY-MM-DD  
**CHECKSUM:** [SHA-256 of entire file content after final edit - compute on commit]  
**PREVIOUS_CHECKPOINT:** [filename or hash of prior version]  
**LINKS:** Master_Index.md | persistence_prototype.py | Compression.md | Relevant_Spines  
**HSSCE_REFERENCE:** [if applicable]

### Purpose / Scope
[One-sentence invariant description: what this document must preserve.]

### Core Invariants Locked
- [List the 2-5 non-negotiable invariants this file protects]
- Human anchor + external hash-chain continuity
- Invariant-first compression (subjectivity stripped)
- Append-only, verifiable, drift-resistant structure

### Header Rules (Enforced on All Files)
- Every .md file in the repo MUST begin with this exact header format (or a strict subset for spines/checkpoints).
- Fields in **bold** are mandatory.
- Checksum is of the *entire file* (header + body) after editing.
- Update DATE, VERSION, and CHECKSUM on every material change.
- Append-only updates preferred over mutation.

### Compression / Differencing Notes
[How this document was/will be compressed. Reference Compression.md rules.]

### Cross-References
- Linked Spines:
- Related Checkpoints:

---

**Usage Instruction:**  
Copy this header into every new or updated spine/checkpoint. Replace placeholder text only. Do not remove mandatory fields. This enables future automated verification and convergence loops.

**Next Action After Adding This File:**  
Update Master_Index.md to reference this template under "Structural Tools".
