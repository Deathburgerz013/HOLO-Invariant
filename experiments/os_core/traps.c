#include "traps.h"

typedef struct __attribute__((packed)) {
    uint16_t offset_low, selector;
    uint8_t reserved, attributes;
    uint16_t offset_high;
} idt_gate_t;
typedef struct __attribute__((packed)) {
    uint16_t limit;
    uint32_t base;
} idt_pointer_t;
_Static_assert(sizeof(idt_gate_t) == 8, "i386 IDT gate size");
_Static_assert(sizeof(idt_pointer_t) == 6, "i386 IDTR size");
static idt_gate_t idt[256] __attribute__((aligned(16)));
extern void (*const exception_stubs[32])(void);

void traps_init(void) {
    /* BSS leaves IRQ/unimplemented gates absent; maskable IRQs stay disabled. */
    for (unsigned i = 0; i < 32; ++i) {
        uint32_t address = (uint32_t)exception_stubs[i];
        idt[i].offset_low = (uint16_t)address;
        idt[i].selector = 0x08;
        idt[i].reserved = 0;
        idt[i].attributes = 0x8e; /* present, DPL 0, 32-bit interrupt gate */
        idt[i].offset_high = (uint16_t)(address >> 16);
    }
    const idt_pointer_t pointer = {
        .limit = sizeof(idt) - 1, .base = (uint32_t)idt,
    };
    __asm__ volatile("lidt %0" : : "m"(pointer) : "memory");
}
