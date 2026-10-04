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

.section .text
.global _start
.type _start,@function
_start:
    cli
    cld
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
