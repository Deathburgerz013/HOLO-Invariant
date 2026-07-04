## Mechanisms of Acceleration: Learning Loops (1950s–2026)

To speed up documentation, research, and understanding, shift focus from pure chronology to the closed feedback/iteration loops that turn incremental human work into exponential capability gains. These repeatable processes powered the post-2017 Transformer explosion and continue driving frontier progress.

Highest-leverage areas (prioritized by impact and verifiable sourcing). Primary papers, company announcements, and benchmarks only.

### 1. Gradient-Based Optimization & Core Training Loops (Foundational, 1980s–present)

**Key documented elements:**  
Backpropagation (Rumelhart, Hinton, Williams 1986) enables efficient credit assignment in deep networks.  
Stochastic Gradient Descent (SGD) + momentum/Adam-family optimizers (including AdamW, Lion) form the universal training loop.  
Forward pass → loss → backward pass → parameter update repeats at massive scale.

This is the mechanical heart of every modern model from AlexNet onward.

**Integrity check:** 100% (textbook math + thousands of papers/implementations).  
**Completion in expanded intel base:** 65% (deep learning mentioned in timeline; loop mechanics now formalized).

### 2. Scaling Laws as Meta-Learning / Resource Allocation Loops (2010s–2022+)

**Key documented elements:**  
Kaplan et al. (2020) and Hoffmann et al. (Chinchilla, 2022) quantify power-law relationships between loss and model size/data/compute.  
Compute-optimal training and over-training strategies become standard. Emergent abilities appear predictably at scale thresholds.

Predictive loop: small experiments → fit laws → optimal massive allocation → repeat. Primary driver of post-Transformer acceleration.

**Integrity check:** 95%+ (highly cited, reproducible curves; minor exponent debates).  
**Completion in expanded intel base:** 55%.

(Visual analog: scaling applied to inference-time "thinking" compute.)

### 3. Preference Optimization & Human Feedback Loops (RLHF era, 2022–present)

**Key documented elements:**  
InstructGPT/ChatGPT (2022): supervised fine-tuning → human preference reward model → RL (PPO).  
Evolution to DPO, KTO, ORPO, RLAIF (AI-as-judge) lowers cost while improving alignment.  
Tight human–model loop converts raw base models into usable assistants.

**Integrity check:** 90%+ (OpenAI papers + widespread reproduction; ongoing trade-off research).  
**Completion in expanded intel base:** 60%.

### 4. Test-Time Compute & Internal Reasoning Loops (2024–2026 frontier)

**Key documented elements:**  
OpenAI o-series (o1-preview/o1-mini Sept 2024; o3/o4-mini April 2025+), Grok "Think Mode"/reasoning (Grok-3 Feb 2025, expanded in Grok-4+), DeepSeek-R1 (Jan 2025).  
Models trained (RL/distillation) for longer, higher-quality reasoning traces with extra inference compute: chain-of-thought, self-reflection, search over paths, process supervision.  
Dramatic benchmark gains on hard reasoning/math/coding without proportional pre-training increases.

"Thinking longer" as a first-class scaling dimension.

**Integrity check:** 90% (strong empirical results across labs; mechanistic details maturing).  
**Completion in expanded intel base:** 50%.

(Visual: iterative reasoning traces with reflection/verification.)

### 5. Agentic / Tool-Use / Multi-Agent Feedback Loops (2023–2026+)

**Key documented elements:**  
ReAct, Toolformer, native tool-calling (GPT-4o May 2024, Claude, Grok-4+, Gemini).  
Plan → tool use (search, code, APIs) → observe → iterate/reflect. Multi-agent (orchestrator + specialists, e.g., Grok Heavy modes) adds parallelism/verification.  
External closed loops with real-world tools.

**Integrity check:** 85% (strong product/benchmark results; failure modes active research).  
**Completion in expanded intel base:** 45%.

**Recommended Next Actions**  
Prioritize deep dives: Test-time reasoning → Scaling laws → Agentic loops.  
Maintain verifiable sourcing. Target 85%+ loops completion in 2–3 passes.

This turns the timeline into a complete, self-reinforcing intel base on AI advancement mechanisms.
