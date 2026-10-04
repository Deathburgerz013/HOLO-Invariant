/* i386 SysV cooperative call boundary: edi, esi, ebx, ebp, return PC.
 * No interrupt frame; caller-saved registers belong to the C call ABI.
 * Interrupts remain disabled throughout this first experiment.
 */
.section .text
.global core_switch
.type core_switch,@function
core_switch:
    mov 4(%esp), %eax
    mov 8(%esp), %edx
    push %ebp
    push %ebx
    push %esi
    push %edi
    mov %esp, (%eax)
    mov %edx, %esp
    pop %edi
    pop %esi
    pop %ebx
    pop %ebp
    ret
.size core_switch, .-core_switch
.section .note.GNU-stack,"",@progbits
