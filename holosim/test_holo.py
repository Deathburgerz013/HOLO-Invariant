import sys
sys.path.insert(0, '.')
from holosim.core import HoloChain
import json

hc = HoloChain('test_holo_memory.jsonl')
print('Import successful - HoloChain v', hc.VERSION)

print('\n=== Test 1: Append plain ===')
entry1 = hc.append('Test entry one - plain text for HSSCE')
print(entry1)

print('\n=== Test 2: Append compressed ===')
data = {'invariant': 'continuity', 'date': '2026-06-14', 'spine': 'Holo/Sim'}
entry2 = hc.append(data, compress=True)
print(entry2)

print('\n=== Test 3: Density Stats ===')
print(json.dumps(hc.get_density_stats(), indent=2))

print('\n=== Test 4: Replay ===')
hc.replay(full=False)

print('\n=== Test 5: Current State ===')
print(hc.get_state())

print('\n=== Test 6: Verify ===')
hc.load_and_verify()
print('✅ All tests passed.')