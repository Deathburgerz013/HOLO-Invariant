import timeit

def sum_integers(n: int) -> int:
    total = 0
    for i in range(n):  # Monomorphic for specialization
        total += i
    return total

# Benchmark
time = timeit.timeit(lambda: sum_integers(1000000), number=10)
print(f"Benchmark result: {time:.6f} seconds")