from holosim import UnifiedOperator

print("🚀 Testing UnifiedOperator...")

op = UnifiedOperator("test_memory.jsonl")

result = op.converge_and_append(
    "This is the first human-verified convergence using the UnifiedOperator.",
    human_confirmation=False
)

print("\n✅ Success! Full result:")
print(result)

# Optional: show the whole chain
print("\n📜 Full chain replay:")
op.replay_convergences()