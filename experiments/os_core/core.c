/* Bounded cooperative OS experiment, conceived by Canyon Brock Haney.
 * Grok supplied the initial proposal; GPT supplied this correction.
 * Single CPU, ring 0, interrupts disabled. No isolation or device drivers.
 */
#include <stdint.h>
#include <stddef.h>
#include "traps.h"

#ifndef CORE_FAULT_CASE
#define CORE_FAULT_CASE 0
#endif
#if CORE_FAULT_CASE < 0 || CORE_FAULT_CASE > 3
#error Unsupported fault case
#endif

#ifndef CORE_STACK_CASE
#define CORE_STACK_CASE 0
#endif
#if CORE_STACK_CASE < 0 || CORE_STACK_CASE > 6
#error Unsupported stack case
#endif
#if CORE_STACK_CASE && CORE_FAULT_CASE
#error Fixtures must be separate images
#endif

#define STACK_GUARD_SIZE 16
#define STACK_GUARD_BYTE 0xa5
#define SWITCH_FRAME_SIZE (5 * sizeof(uint32_t))
#define MAX_TASKS 8
#define STACK_SIZE 4096
#define HEAP_SIZE (64 * 1024)

typedef enum { UNUSED, READY, RUNNING } task_state_t;
typedef struct {
    task_state_t state;
    uint32_t *sp;
    void (*entry)(void *);
    void *arg;
} task_t;

static task_t tasks[MAX_TASKS];
static uint8_t stacks[MAX_TASKS][STACK_SIZE] __attribute__((aligned(16)));
static uint8_t heap[HEAP_SIZE] __attribute__((aligned(16)));
static size_t heap_off;
static uint32_t *scheduler_sp;
static int current = -1;
static unsigned cursor;
extern void core_switch(uint32_t **old_sp, uint32_t *new_sp);

static inline void outb(uint16_t port, uint8_t value) {
    __asm__ volatile("outb %0, %1" : : "a"(value), "Nd"(port));
}
static inline uint8_t inb(uint16_t port) {
    uint8_t value;
    __asm__ volatile("inb %1, %0" : "=a"(value) : "Nd"(port));
    return value;
}
static void serial_init(void) {
    outb(0x3f9, 0); outb(0x3fb, 0x80);
    outb(0x3f8, 1); outb(0x3f9, 0);
    outb(0x3fb, 3); outb(0x3fa, 0xc7); outb(0x3fc, 0x0b);
}
static void print(const char *s) {
    while (*s) {
        while (!(inb(0x3fd) & 0x20)) {}
        outb(0x3f8, (uint8_t)*s++);
    }
}
static __attribute__((noreturn)) void finish(unsigned code) {
    __asm__ volatile("outl %0, %1" : : "a"(code), "Nd"((uint16_t)0xf4));
    for (;;) __asm__ volatile("cli; hlt");
}
static __attribute__((noreturn)) void panic(const char *reason) {
    print("FAIL: "); print(reason); print("\n"); finish(0x11);
}
static void require(int condition, const char *reason) {
    if (!condition) panic(reason);
}

static void print_hex(uint32_t value) {
    static const char digits[] = "0123456789abcdef";
    char text[11] = "0x00000000";
    for (unsigned i = 0; i < 8; ++i)
        text[2 + i] = digits[(value >> (28 - 4 * i)) & 15];
    print(text);
}

__attribute__((noreturn)) void core_exception(const trap_frame_t *frame) {
    print("FAULT vector="); print_hex(frame->vector);
    print(" error="); print_hex(frame->error);
    print(" eip="); print_hex(frame->eip);
    print(" cs="); print_hex(frame->cs);
    print(" eflags="); print_hex(frame->eflags);
    print("\n");
#if CORE_FAULT_CASE != 0
    const uint32_t expected_vector = CORE_FAULT_CASE == 1 ? 0 :
                                     CORE_FAULT_CASE == 2 ? 6 : 13;
    const uint32_t expected_error = CORE_FAULT_CASE == 3 ? 0x18 : 0;
    const uint32_t expected_eip = (uint32_t)(CORE_FAULT_CASE == 1 ?
        fault_divide_instruction : CORE_FAULT_CASE == 2 ?
        fault_invalid_instruction : fault_gp_instruction);
    require(current >= 0 && tasks[current].state == RUNNING, "fault task context");
    require(frame->vector == expected_vector, "exception vector");
    require(frame->error == expected_error, "exception error code");
    require(frame->eip == expected_eip, "exception instruction address");
    require(frame->cs == 0x08 && !(frame->eflags & 0x200), "exception context");
    print("PASS expected exception frame\n");
    /* Distinguish expected-fault completion from ordinary demo success. */
    finish(0x12);
#else
    panic("unhandled CPU exception");
#endif
}

/* Zero and oversized requests fail without altering the allocation cursor. */
static void *core_alloc(size_t n) {
    if (!n || n > sizeof(heap) - heap_off) return NULL;
    size_t aligned = (n + (size_t)15) & ~(size_t)15;
    if (aligned > sizeof(heap) - heap_off) return NULL;
    void *p = heap + heap_off;
    heap_off += aligned;
    return p;
}

/* Integer bounds checks never dereference an unvalidated saved pointer.
 * The bottom marker detects writes to these bytes, not arbitrary overflow.
 */
static void check_task_stack(unsigned id) {
    uintptr_t low = (uintptr_t)stacks[id] + STACK_GUARD_SIZE;
    uintptr_t high = (uintptr_t)stacks[id] + STACK_SIZE;
    uintptr_t saved = (uintptr_t)tasks[id].sp;
    require(saved >= low && saved <= high - SWITCH_FRAME_SIZE,
            "task stack pointer bounds");
    require((saved & (sizeof(uint32_t) - 1)) == 0,
            "task stack pointer alignment");
    for (unsigned n = 0; n < STACK_GUARD_SIZE; ++n)
        require(stacks[id][n] == STACK_GUARD_BYTE, "task stack guard");
}

static void core_yield(void) {
    require(current >= 0 && tasks[current].state == RUNNING, "yield context");
    tasks[current].state = READY;
    core_switch(&tasks[current].sp, scheduler_sp);
}
static __attribute__((noreturn)) void task_exit(void) {
    tasks[current].state = UNUSED;
    core_switch(&tasks[current].sp, scheduler_sp);
    panic("returned to exited task");
}
static __attribute__((noreturn)) void task_trampoline(void) {
    tasks[current].entry(tasks[current].arg);
    task_exit();
}
static __attribute__((noreturn)) void unexpected_return(void) {
    panic("trampoline returned");
}
static int core_spawn(void (*entry)(void *), void *arg) {
    if (!entry) return -1;
    for (unsigned i = 0; i < MAX_TASKS; ++i) {
        if (tasks[i].state != UNUSED) continue;
        for (unsigned n = 0; n < STACK_GUARD_SIZE; ++n)
            stacks[i][n] = STACK_GUARD_BYTE;
        uint32_t *sp = (uint32_t *)(stacks[i] + STACK_SIZE);
        /* ret enters trampoline with esp == 12 mod 16, as a C call does. */
        *--sp = (uint32_t)unexpected_return;
        *--sp = (uint32_t)task_trampoline;
        *--sp = 0; /* ebp */
        *--sp = 0; /* ebx */
        *--sp = 0; /* esi */
        *--sp = 0; /* edi */
        tasks[i].sp = sp;
        tasks[i].entry = entry;
        tasks[i].arg = arg;
        tasks[i].state = READY;
        return (int)i;
    }
    return -1;
}
/* Return to boot/idle context after each yield or task exit. */
static int core_schedule(void) {
    for (unsigned n = 0; n < MAX_TASKS; ++n) {
        unsigned i = (cursor + n) % MAX_TASKS;
        if (tasks[i].state != READY) continue;
        check_task_stack(i);
        cursor = (i + 1) % MAX_TASKS;
        current = (int)i;
        tasks[i].state = RUNNING;
        core_switch(&scheduler_sp, tasks[i].sp);
        check_task_stack(i);
        current = -1;
        return 1;
    }
    return 0;
}

static unsigned completed;
static unsigned steps[2];
static unsigned order[6], order_len;
static void simple_task(void *arg) {
    (void)arg;
    ++completed;
}
static void demo_task(void *arg) {
    unsigned id = (unsigned)(uintptr_t)arg;
    volatile unsigned sentinel = 0xcafe0000u + id;
    for (unsigned i = 0; i < 3; ++i) {
        require(sentinel == 0xcafe0000u + id, "stack continuity");
        require(order_len < 6, "order bound");
        order[order_len++] = id;
        ++steps[id];
        print(id ? "B yield\n" : "A yield\n");
        core_yield();
    }
    ++completed;
    print(id ? "B exit\n" : "A exit\n");
}
#if CORE_FAULT_CASE != 0
static void deliberate_fault_task(void *arg) {
    (void)arg;
#if CORE_FAULT_CASE == 1
    fault_divide();
#elif CORE_FAULT_CASE == 2
    fault_invalid();
#else
    fault_general_protection();
#endif
    panic("fault instruction returned");
}
#endif

#if CORE_STACK_CASE != 0
static void stack_fixture_task(void *arg) {
    (void)arg;
#if CORE_STACK_CASE <= 4
    panic("corrupt task resumed");
#else
    print("FIXTURE corrupt running task guard\n");
    stacks[current][0] ^= 1;
#if CORE_STACK_CASE == 5
    core_yield();
    panic("corrupt task resumed");
#endif
    /* Case 6 returns through the ordinary task exit path. */
#endif
}
static __attribute__((noreturn)) void run_stack_fixture(void) {
    int id = core_spawn(stack_fixture_task, NULL);
    require(id >= 0, "stack fixture spawn");
#if CORE_STACK_CASE == 1
    stacks[id][0] ^= 1;
#elif CORE_STACK_CASE == 2
    tasks[id].sp = (uint32_t *)(stacks[id] + STACK_GUARD_SIZE - 4);
#elif CORE_STACK_CASE == 3
    tasks[id].sp = (uint32_t *)(stacks[id] + STACK_SIZE - 16);
#elif CORE_STACK_CASE == 4
    tasks[id].sp = (uint32_t *)(stacks[id] + STACK_SIZE - 25);
#endif
    core_schedule();
    panic("corrupt task accepted");
}
#endif

void kmain(uint32_t magic, uint32_t info) {
    (void)info;
    serial_init();
    require(magic == 0x2badb002, "multiboot magic");
    traps_init();
    print("BOOT protected-mode cooperative core\n");
    require(!core_schedule(), "empty scheduler");
    require(core_spawn(NULL, NULL) == -1, "null entry");
    require(core_alloc(0) == NULL, "zero allocation");
    require(core_alloc((size_t)-1) == NULL, "oversized allocation");
    require(heap_off == 0, "failed allocation mutation");
    require(((uintptr_t)core_alloc(1) & 15) == 0, "heap alignment");
    require(core_alloc(HEAP_SIZE - 16) != NULL, "exact allocation");
    require(core_alloc(1) == NULL, "heap full");
    for (unsigned i = 0; i < MAX_TASKS; ++i)
        require(core_spawn(simple_task, NULL) == (int)i, "spawn capacity");
    require(core_spawn(simple_task, NULL) == -1, "full task table");
    unsigned dispatches = 0;
    while (core_schedule()) require(++dispatches <= MAX_TASKS, "exit progress");
    require(completed == MAX_TASKS, "all tasks exited");
    print("PASS idle allocator capacity exit\n");
    completed = 0;
    /* Retired stack markers must be reset when a slot is reused. */
    stacks[0][0] = 0;
    stacks[1][STACK_GUARD_SIZE - 1] = 0;
    require(core_spawn(demo_task, (void *)0) == 0, "slot reuse A");
    require(core_spawn(demo_task, (void *)1) == 1, "slot reuse B");
    dispatches = 0;
    while (core_schedule()) require(++dispatches <= 8, "yield progress");
    require(completed == 2 && steps[0] == 3 && steps[1] == 3, "task results");
    require(order_len == 6, "trace length");
    for (unsigned i = 0; i < 6; ++i) require(order[i] == i % 2, "round robin");
    require(!core_schedule(), "idle after exit");
    print("PASS two tasks yield resume exit reuse\n");
#if CORE_STACK_CASE != 0
    run_stack_fixture();
#elif CORE_FAULT_CASE != 0
    require(core_spawn(deliberate_fault_task, NULL) >= 0, "fault task spawn");
    core_schedule();
    panic("fault task returned to scheduler");
#else
    finish(0x10);
#endif
}
