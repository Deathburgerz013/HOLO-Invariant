# Cooperative protected-mode core experiment

Author / operator: Canyon Brock Haney. Grok supplied the initial OS proposal;
GPT supplied the corrected implementation. Base: HOLO-Invariant `ac43ede`.

This isolated experiment boots a Multiboot v1 ELF directly in QEMU, dispatches
C tasks through a separate assembly switch, resumes them after cooperative
yields, and returns exited tasks to the scheduler. It is a first boot milestone,
not a complete OS or an extension of HOLO's operational authority.

## Build and check

Use Linux or WSL with GNU Make, GCC capable of freestanding `-m32` compilation,
GNU binutils (`ld` with `elf_i386` support and `nm`), GNU timeout, Python 3,
and QEMU system x86. No 32-bit libc
is linked. On Ubuntu these tools are provided by `build-essential` and
`qemu-system-x86` and `python3`.

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
PASS block wake idle stale handle reuse
```

The check runs thirteen separate images: ordinary demo, divide error (#DE),
invalid opcode (#UD), general protection (#GP), six stack-corruption cases,
two blocking misuse cases, and an interactive serial-console image.
Every image first runs the
existing allocator and scheduler checks. Fault variants then spawn a task which
executes the deliberate fault instruction.

The demo requires debug-exit status 33 and three PASS lines. Each expected fault
requires status 37, four PASS lines, and one FAULT report. Panic uses status 35.
Stack-corruption and blocking misuse cases require status 35 and the specific
diagnostic, with no
additional PASS or FAULT report. They use the real panic path.
`check.sh` independently compares the printed EIP to the ELF symbol read by
`nm`, as well as vector, error, and code selector. Each QEMU run has a ten-second
timeout. Reset, timeout, missing markers, malformed reports, and unexpected
exit codes fail the check. QEMU uses software emulation, 32 MiB RAM, no NIC,
and no disk; it does not boot the host. The console session has a separate
ten-second process deadline and a 64 KiB captured-output limit.

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
preemption, paging, userspace isolation, network queue, NIC
driver, persistence, or physical-hardware boot has been implemented. A task that never yields can monopolize the CPU;
stack corruption is checked only at scheduler boundaries as described below.
QEMU's test timeout is external to the kernel.
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


## Task stack integrity contract

This extension is based on `ce98b14`. The bottom 16 bytes of each 4096-byte
task stack hold a marker, leaving 4080 bytes for task execution. Spawn resets
those bytes on every slot reuse. The ordinary demo deliberately damages two
retired markers before reuse and then exercises normal yield/resume/exit.

Before switching to a READY task, the scheduler checks its saved pointer using
integer addresses: it must lie between the first byte after the marker and
stack-top minus 20 bytes, inclusive, and be aligned to a four-byte word.
Twenty bytes account for the four restored registers and return PC consumed
by `core_switch`. Fresh stacks additionally include the trampoline return
address. The checker does not dereference the saved pointer. It verifies all
16 marker bytes before resuming and repeats both checks on the scheduler stack
after yield or exit returns, before clearing `current` or reusing the slot.

Six deliberate fixtures run after the ordinary demo: damaged marker before
resume; pointer below the usable range; pointer too near the top for the
switch frame; misaligned pointer; running-task marker damage followed by
yield; and running-task marker damage followed by exit. Each must panic with
the designated bounds, alignment, or marker diagnostic. The first four must
never enter the damaged task; the yield case must never resume it. Cases five
and six also require a marker proving the task ran before damaging its stack.

These are trusted-code diagnostics, not memory protection or overflow
prevention. A write that skips the marker, a corrupted return address inside
an otherwise valid frame, or a task that never returns to the scheduler can
escape these checks. A broken live task stack may fail before it can switch
back. The scheduler/boot stack is not guarded by this task-only checker.
There is no paging, guard page, alternate fault stack, repair, or isolation.

Development validation: ten QEMU 8.2.2 images passed at both `-O0` and `-O2`
(20 boots), retaining all three CPU exception fixtures. Removing the
pre-dispatch check in a disposable copy was rejected with `corrupt task
resumed`; removing the post-return check was rejected with `corrupt task
accepted`. These observations concern explicit fixture writes, not natural
stack exhaustion or hardware protection. Classification remains PARTIAL.

The same development checkout's Python suite reported `3461 passed in 22.89s`.
The updated map validated 5169 nonempty lines with zero rail violations.
GitHub CI for this extension has not yet run; Windows results are pending.


## Cooperative block/wake contract

This extension is based on `9baecd9`. A RUNNING task calls `core_block`, becomes
BLOCKED, saves its cooperative context, and returns control to the scheduler.
The scheduler still dispatches only READY slots. With every live task BLOCKED,
it returns zero to its caller without changing those tasks or their saved
pointers. This is an idle observation, not successful task completion.

`core_spawn` keeps its existing slot-number result. `core_handle` snapshots the
slot and its nonzero 32-bit generation; invalid or UNUSED slots produce an
invalid handle. Each successful spawn increments the generation. A slot whose
generation reaches UINT32_MAX can run its last incarnation, then is permanently
retired from spawn, reducing capacity rather than allowing identity wraparound.
The demo moves an unused counter to MAX-1 to exercise that bound without
billions of spawns. Handles are internal task identity, not authorization.

`core_wake` accepts only a matching handle for a BLOCKED task, validates its
saved stack, then makes it READY. It returns zero on success and -1 for an
invalid slot, zero/mismatched generation, or non-BLOCKED state, with no mutation
on those rejected requests. Matching handles with damaged stacks use the
existing terminal panic path. READY, RUNNING, exited, and stale incarnations
cannot be woken. A successful wake can come from the scheduler caller or
another trusted task. Exit still retires the task incarnation normally.

The demo checks two tasks becoming blocked, unchanged all-blocked idle,
rejection of malformed and mismatched handles, an unrelated READY task running
past blocked slots, duplicate wake rejection, repeated block/wake/yield/exit,
local stack continuity, wake from another task, and stale wake rejection while
a replacement task occupies the same slot. Stack checks apply after blocking
returns to the scheduler and before subsequent dispatch, as for yield/exit.
A third PASS marker reports this lifecycle in every boot image.

Two additional terminal fixtures check a blocked stack marker corrupted before
wake and `core_block` called from scheduler context. The shell check requires
the exact panic diagnostic, three existing PASS markers, and no FAULT report;
corruption acceptance or invalid blocking acceptance must fail.

All calls remain single-CPU, ring 0, with interrupts disabled. There is no event
queue, pending wake storage, IRQ wakeup, timeout, cancellation, synchronization,
or preemption. A wake arriving before a task blocks is rejected, not buffered.
The caller must arrange ordering and explicitly dispatch after waking. A task
that never yields/blocks/exits can still monopolize the CPU, and a blocked task
can wait forever. Handles do not prevent trusted tasks from modifying kernel
memory. Existing terminal-fault and task-stack limits remain. Classification
is PARTIAL OS experiment.

Development validation: twelve QEMU 8.2.2 images passed at both `-O0` and `-O2`
(24 boots). Disposable mutations making block leave a task READY, ignoring
handle generation, omitting wake's READY transition, and skipping wake's stack
check were rejected. Python reported `3461 passed in 23.48s`; the map validated
5188 nonempty lines with zero rail violations. These are development
observations; GitHub CI and operator Windows checks for this extension are
pending. Physical hardware remains untested.


## Polled serial console contract

This extension is based on `da4d2e1`. The ordinary twelve boot images keep their
existing terminal behavior. A separate console image first runs the same three
lifecycle demos, then prints `CONSOLE ready` and polls COM1 input. To interact
from a Linux/WSL terminal:

```sh
make -C experiments/os_core console
```

Type `help`, `status`, or `quit`, ending the line with CR or LF. Commands are
case-sensitive and exact; extra spaces or arguments are unknown commands.
Empty lines are ignored, so CRLF executes a command once. There is no echo,
backspace editing, history, escape processing, or arbitrary command execution.
`quit` prints `CONSOLE bye` and uses debug-exit status 33 in QEMU. The interactive Make
target accepts that exit code and rejects other emulator exits; `make check`
adds the command-response validation.

`status` reports counts of READY, RUNNING, BLOCKED, UNUSED, and retired slots.
Retired slots are a subset of UNUSED slots, not a fifth task state. The initial
console status is `ready=0 running=0 blocked=0 unused=8 retired=1` because the
preceding generation-exhaustion demo deliberately retires one slot. This is a
snapshot of this demo's task table, not host state, memory safety, or authority.

`console.c` holds a 32-byte line buffer and accepts at most 31 printable ASCII
bytes before a delimiter. Matching uses explicit lengths, not an unterminated
C-string scan. An oversized line or a nonprintable byte enters discard mode;
the parser stops storing bytes, drains through CR/LF, emits one error, resets,
and accepts a later line. The first rejection reason is retained. UART receive
error flags also invalidate the current line, but hardware error injection is
not covered by these observations. Prefixes and rejected suffixes cannot run
commands. A line without a delimiter remains pending without buffer growth
past the cap. Input-state storage is fixed; no heap allocation occurs.

The console checks for one received byte per scheduler iteration. With no
input it continues cooperative dispatch. It does not enable interrupts, invoke
preemption, dispatch commands from an IRQ, or sleep on input. A task that never
returns can still starve the console; UART overruns and unpaced bursts are not
prevented. Serial output still assumes an available UART and may wait forever.
No disk, network, program loading, permissions, host actions, or recovery is
added. Physical keyboards and hardware serial ports remain unverified.

`check_console.py` drives QEMU serial pipes on Linux/WSL with paced input. It
waits for the ready marker, then compares exact responses for help/status,
fragmented input without premature execution, CR/LF and blank lines, unknown
commands, case and whitespace rejection, exactly 31 bytes, overlength lines
including valid command suffixes, discard recovery, NUL/tab/non-ASCII bytes,
and quit. It requires the existing three PASS markers, no fault/panic, and exit
33. Exact captured serial bytes are retained in `build/console.log`, including
on failure. The automated console test uses only Python's standard library.

Classification remains PARTIAL OS experiment. This console is a bounded
interaction path inside the emulator, not a general shell or new authority.

Development validation: thirteen QEMU 8.2.2 images passed at each of `-O0` and
`-O2` (26 boots). Three parser mutations in disposable copies were rejected:
a wrong line-length boundary, acceptance of invalid bytes, and failure to reset
discard state. Python reported `3461 passed in 31.18s`; the map validated 5208
nonempty lines with zero rail violations. Interactive-target exit handling
accepted a simulated status 33 and rejected simulated status 35; those two
checks were shell checks, not emulator boots. GitHub CI and operator Windows
results for this extension are pending.
