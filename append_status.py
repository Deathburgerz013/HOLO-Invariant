from holosim.core import HoloChain 
chain = HoloChain('holo_memory.jsonl') 
chain.replay(full=False) 
print('--- End ---') 
