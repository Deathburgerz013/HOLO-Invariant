import timeit
import sys

def sum_integers(n: int) -> int:
    total = 0
    for i in range(n):
        total += i
    return total

# Benchmark
time_taken = timeit.timeit(lambda: sum_integers(1000000), number=20)
print(f"Benchmark v2 (20 runs): {time_taken:.6f} seconds")

if sys.version_info >= (3, 11):
    print("Python >=3.11: Adaptive interpreter active for monomorphic loops.")
else:
    print(f"Python version {sys.version_info} – specialization gains stronger in 3.11+.")