/* Multiboot v1 enters 32-bit protected mode with paging disabled. */
.section .multiboot,"a"
.balign 4
.long 0x1badb002
.long 3
.long -(0x1badb002 + 3)

.section .bss
.balign 16
boot_stack:
.skip 16384
boot_stack_top:

.section .rodata
.balign 8
core_gdt:
.quad 0
.quad 0x00cf9a000000ffff /* flat ring-0 code, selector 0x08 */
.quad 0x00cf92000000ffff /* flat ring-0 data, selector 0x10 */
core_gdt_end:
core_gdt_pointer:
.word core_gdt_end - core_gdt - 1
.long core_gdt

.section .text
.global _start
.type _start,@function
_start:
    cli
    cld
    /* Preserve loader magic (eax) and info (ebx); use dx for segments. */
    lgdt core_gdt_pointer
    ljmp $0x08, $core_segments_ready
core_segments_ready:
    mov $0x10, %dx
    mov %dx, %ds
    mov %dx, %es
    mov %dx, %ss
    mov %dx, %fs
    mov %dx, %gs
    mov $boot_stack_top, %esp
    xor %ebp, %ebp
    /* Keep the stack aligned before passing magic and info. */
    sub $8, %esp
    push %ebx
    push %eax
    call kmain
1:  cli
    hlt
    jmp 1b
.size _start, .-_start
.section .note.GNU-stack,"",@progbits
