# Microbenchmarks

These benchmarks use [pyperf](https://pyperf.readthedocs.io/) to measure small, focused Frappe
framework operations.

## Running

Use a fresh site that has not been altered:

```bash
bench new-site bench.localhost
bench --site bench.localhost set-config allow_tests true
bench --site bench.localhost run-microbenchmarks
```

Running the complete suite can take a long time.

Useful arguments:

- `--filter benchmark_name` runs only benchmarks whose names contain the filter value.
- `--help` shows pyperf's built-in runner options.
- `-p5` runs a quick, rough benchmark with 5 worker processes.
- `-o output.json` stores detailed results for later analysis.

Useful pyperf commands:

- `pyperf compare_to baseline.json changed.json` compares two result files and applies statistical
  significance tests.
- `pyperf timeit` is useful for measuring tiny operations such as setting an attribute on an object.

## Getting Reliable Results

Local development machines are often noisy benchmarking environments. For more stable results:

1. Use a Linux machine.
2. Stop unnecessary running processes.
3. Plug in laptops and avoid benchmarking on battery power.
4. Disable SMT/HyperThreading:

   ```bash
   echo "off" | sudo tee /sys/devices/system/cpu/smt/control
   ```

5. Disable turbo boost. The exact steps depend on the CPU and kernel.
6. Use the `performance` CPU governor.
7. Disable ASLR:

   ```bash
   echo 0 | sudo tee /proc/sys/kernel/randomize_va_space
   ```

These steps should make results much less noisy. For more background, see
<https://ankush.dev/p/reliable-benchmarking>.

## Writing

1. Find the appropriate `bench_{module}.py` file.
2. Add a function with a `bench_` prefix. The function body is the benchmark.
3. Use `NanoBenchmark` instead of a function when measuring very small operations, especially
   operations below 1 ms where Python function-call overhead can distort results.
4. Make sure the benchmark measures the intended path. For example, when benchmarking
   `frappe.get_cached_doc` fetching from Redis, clear or avoid local caches so the benchmark is not
   only measuring local cache access.
