/* Terminal CPU-exception entry; never returns through iret.
 * CPU error-code vectors omit the synthetic zero. Never call those entries
 * through software INT: software INT does not supply the CPU error code.
 */
.section .text
.macro EXCEPTION n
.global exception_stub_\n
.type exception_stub_\n,@function
exception_stub_\n:
.if (\n != 8) && (\n != 10) && (\n != 11) && (\n != 12) && (\n != 13) && (\n != 14) && (\n != 17) && (\n != 21) && (\n != 29) && (\n != 30)
    push $0
.endif
    push $\n
    jmp exception_common
.size exception_stub_\n, .-exception_stub_\n
.endm
.irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    EXCEPTION \n
.endr
exception_common:
    cli
    cld
    pushal
    mov %esp, %eax
    /* Preserve frame pointer while aligning the C call independently. */
    and $-16, %esp
    sub $12, %esp
    push %eax
    call core_exception
1:  cli
    hlt
    jmp 1b

.global fault_divide, fault_divide_instruction
.type fault_divide,@function
fault_divide:
    mov $1, %eax
    xor %edx, %edx
    xor %ecx, %ecx
fault_divide_instruction:
    div %ecx
    ret
.size fault_divide, .-fault_divide

.global fault_invalid, fault_invalid_instruction
.type fault_invalid,@function
fault_invalid:
fault_invalid_instruction:
    ud2
    ret
.size fault_invalid, .-fault_invalid

.global fault_general_protection, fault_gp_instruction
.type fault_general_protection,@function
fault_general_protection:
    mov $0x18, %ax /* selector beyond the three-entry GDT */
fault_gp_instruction:
    mov %ax, %ds
    ret
.size fault_general_protection, .-fault_general_protection

.section .rodata
.balign 4
.global exception_stubs
exception_stubs:
.irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    .long exception_stub_\n
.endr
.section .note.GNU-stack,"",@progbits
