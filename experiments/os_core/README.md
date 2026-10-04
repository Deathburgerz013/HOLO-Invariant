# Cooperative protected-mode core experiment

Author / operator: Canyon Brock Haney. Grok supplied the initial OS proposal;
GPT supplied the corrected implementation. Base: HOLO-Invariant `ac43ede`.

This isolated experiment boots a Multiboot v1 ELF directly in QEMU, dispatches
C tasks through a separate assembly switch, resumes them after cooperative
yields, and returns exited tasks to the scheduler. It is a first boot milestone,
not a complete OS or an extension of HOLO's operational authority.

## Build and check

Use Linux or WSL with GNU Make, GCC capable of freestanding `-m32` compilation,
GNU binutils (`ld` with `elf_i386` support and `nm`), GNU timeout,
and QEMU system x86. No 32-bit libc
is linked. On Ubuntu these tools are provided by `build-essential` and
`qemu-system-x86`.

```sh
make -C experiments/os_core check
```

The ordinary demo serial output is:

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

The check now runs four separate images: ordinary demo, divide error (#DE),
invalid opcode (#UD), and general protection (#GP). Every image first runs the
existing allocator and scheduler checks. Fault variants then spawn a task which
executes the deliberate fault instruction.

The demo requires debug-exit status 33 and two PASS lines. Each expected fault
requires status 37, three PASS lines, and one FAULT report. Panic uses status 35.
`check.sh` independently compares the printed EIP to the ELF symbol read by
`nm`, as well as vector, error, and code selector. Each QEMU run has a ten-second
timeout. Reset, timeout, missing markers, malformed reports, and unexpected
exit codes fail the check. QEMU uses software emulation, 32 MiB RAM, no NIC,
and no disk; it does not boot the host.

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

This is not an interrupt frame and never uses `iret`. The bootstrap installs a private flat GDT, disables
interrupts, and clears the direction flag. A task must preserve those conditions.
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

Terminal exception reporting is implemented as described below. No timer IRQ,
preemption, paging, userspace isolation, blocking/wakeup, network queue, NIC
driver, persistence, or physical-hardware boot has been implemented. A task that never yields can monopolize the CPU;
a stack overflow is not caught. QEMU's test timeout is external to the kernel.
Serial port availability and the Multiboot loader are environmental assumptions.

Linux GCC/QEMU observations do not establish Windows-native build support,
physical-machine safety, consciousness, AI execution authority, or a general
self-correcting OS. Classification: PARTIAL OS experiment.

## Historical first-boot development observation

On the Linux development checkout based on `ac43ede`, GCC builds with `-O0`
and `-O2` each booted in QEMU 8.2.2 and produced both PASS markers with exit
status 33. Two deliberate mutations in disposable copies were rejected:
marking an exited task READY, and removing allocation rounding.

The same checkout's HOLO suite reported `3461 passed in 19.61s`; this is an
observation for this development environment, not a replacement for other
platforms' retained results. The updated implementation map passed rail
validation with 5133 checked nonempty lines and zero violations. GitHub's new
workflow has not run yet; physical hardware remains untested.


## Terminal exception-reporting contract

This extension is based on `fe3f1dd`. The bootstrap installs a three-entry flat
GDT and reloads code/data selectors before C initialization. `traps_init`
installs 32 ring-0 exception entries in a 256-entry IDT; remaining entries stay
absent. Maskable interrupts remain disabled. This prerequisite follows the
[Multiboot machine-state contract](https://www.gnu.org/software/grub/manual/multiboot/html_node/Machine-state.html):
the loader's descriptor table cannot be assumed suitable for segment reloads.
CPU exception-frame semantics follow the
[Intel system programming manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html).

Assembly stubs normalize vector/error before `pushal`. For CPU error-code
vectors 8, 10-14, 17, 21, 29, and 30, the error is supplied by the CPU; other
stubs push a synthetic zero. Software INT into an error-code vector is outside
this contract. The common entry disables interrupts, clears DF, retains the
frame pointer, aligns a separate C-call stack position, and calls the terminal
reporter. The header fixes C offsets with compile-time assertions.

The frame is for same-privilege 32-bit ring-0 entry only: eight pushal words,
vector, error, EIP, CS, and EFLAGS. It does not include a privilege-change ESP/SS
tail. The pushal saved-ESP word is not such a tail. The reporter prints vector,
error, EIP, CS, and EFLAGS; default unexpected exceptions then panic. There is
no return via IRET, resumed faulting task, automatic repair, alternate trap
stack, guarded serial output, double-fault recovery, or stack-overflow recovery.
A corrupted stack or a fault inside the handler may still reset or hang the
machine; the external QEMU timeout remains essential.

In expected-fault images, the reporter additionally requires a RUNNING task,
the exact designated fault instruction, expected vector/error, selector 0x08,
and interrupted IF clear. Expected completion is a fixture result, not a
production recovery policy. No pending timer/device interrupt is enabled.

Observed in the development environment: four QEMU 8.2.2 cases passed at both
`-O0` and `-O2` (eight boots). #DE and #UD reported a zero synthetic error;
#GP reported the invalid selector 0x18. Disposable mutations adding an extra
word to #GP's frame, changing the expected EIP, and raising an unexpected
fault in the ordinary demo were rejected. HOLO's Linux suite reported
`3461 passed in 18.39s`. GitHub CI for this extension has not yet run. Only
these three deliberate faults were exercised; other installed vectors,
physical hardware, and recovery remain unverified. Classification stays PARTIAL.
