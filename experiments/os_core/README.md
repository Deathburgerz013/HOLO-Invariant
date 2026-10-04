# Cooperative protected-mode core experiment

Author / operator: Canyon Brock Haney. Grok supplied the initial OS proposal;
GPT supplied the corrected implementation. Base: HOLO-Invariant `ac43ede`.

This isolated experiment boots a Multiboot v1 ELF directly in QEMU, dispatches
C tasks through a separate assembly switch, resumes them after cooperative
yields, and returns exited tasks to the scheduler. It is a first boot milestone,
not a complete OS or an extension of HOLO's operational authority.

## Build and check

Use Linux or WSL with GNU Make, GCC capable of freestanding `-m32` compilation,
GNU ld with `elf_i386` support, GNU timeout, and QEMU system x86. No 32-bit libc
is linked. On Ubuntu these tools are provided by `build-essential` and
`qemu-system-x86`.

```sh
make -C experiments/os_core check
```

Successful serial output ends with:

```text
BOOT protected-mode cooperative core
PASS idle allocator capacity exit
A yield
B yield
A yield
B yield
A yield
B yield
A exit
B exit
PASS two tasks yield resume exit reuse
```

The check requires QEMU debug-exit status 33, both PASS lines, and completion
within ten seconds. Panic exits with status 35. Reset, timeout, missing success
markers, and unexpected exit codes fail the check. QEMU uses software emulation,
32 MiB RAM, no NIC, and no disk; it does not boot the host.

To exercise both compiler layouts:

```sh
make -C experiments/os_core clean
make -C experiments/os_core check OPT=-O0
make -C experiments/os_core clean
make -C experiments/os_core check OPT=-O2
```

## Exact switch contract

At a cooperative C call boundary, `core_switch` saves i386 SysV callee-saved
`ebp`, `ebx`, `esi`, and `edi` plus the return address already on the stack.
It stores the old stack pointer, loads the new pointer, restores those four
registers, and uses `ret`. Fresh stacks contain that same layout and a synthetic
return address into the trampoline. Trampoline entry has `esp` congruent to 12
modulo 16, as after a C call with a 16-byte aligned caller stack.

This is not an interrupt frame and never uses `iret`. The bootstrap disables
interrupts and clears the direction flag. A task must preserve those conditions.
The assembly boundary avoids replacing a compiler-managed stack in inline C.

Scheduler and tasks have separate stacks. Task return marks the slot unused
and switches back to the scheduler. Static task stacks can be reused without
consuming the bump heap. An empty or exhausted ready set returns to the boot
context without accessing a negative task index.

The aligned bump allocator rejects zero, oversized, and exhausted requests
before advancing its cursor. It does not free memory.

## Observed boundaries and limits

The boot checks cover empty scheduling, null task entry rejection, allocator
alignment and exhaustion, eight task slots, capacity rejection, clean exit,
slot reuse, round-robin order, local stack continuity, and repeated yield/resume.
The demo checks its own progress bounds; these are not isolation boundaries
against arbitrary code. All tasks are trusted, single-CPU ring-0 code.

No IDT/trap handling, timer IRQ, preemption, paging, userspace isolation,
blocking/wakeup, network queue, NIC driver, persistence, or physical-hardware
boot has been implemented. A task that never yields can monopolize the CPU;
a stack overflow is not caught. QEMU's test timeout is external to the kernel.
Serial port availability and the Multiboot loader are environmental assumptions.

Linux GCC/QEMU observations do not establish Windows-native build support,
physical-machine safety, consciousness, AI execution authority, or a general
self-correcting OS. Classification: PARTIAL OS experiment.

## Retained development observation

On the Linux development checkout based on `ac43ede`, GCC builds with `-O0`
and `-O2` each booted in QEMU 8.2.2 and produced both PASS markers with exit
status 33. Two deliberate mutations in disposable copies were rejected:
marking an exited task READY, and removing allocation rounding.

The same checkout's HOLO suite reported `3461 passed in 19.61s`; this is an
observation for this development environment, not a replacement for other
platforms' retained results. The updated implementation map passed rail
validation with 5133 checked nonempty lines and zero violations. GitHub's new
workflow has not run yet; physical hardware remains untested.
