#ifndef CORE_TRAPS_H
#define CORE_TRAPS_H
#include <stdint.h>
#include <stddef.h>

/* Same-privilege ring-0 frame: pushal, normalized vector/error, CPU frame.
 * saved_esp is pushal's pre-push value, not a privilege-transition stack.
 * There is no user ESP/SS tail in this experiment.
 */
typedef struct {
    uint32_t edi, esi, ebp, saved_esp, ebx, edx, ecx, eax;
    uint32_t vector, error, eip, cs, eflags;
} trap_frame_t;
_Static_assert(sizeof(trap_frame_t) == 52, "trap frame size");
_Static_assert(offsetof(trap_frame_t, vector) == 32, "vector offset");
_Static_assert(offsetof(trap_frame_t, error) == 36, "error offset");
_Static_assert(offsetof(trap_frame_t, eip) == 40, "instruction offset");
_Static_assert(offsetof(trap_frame_t, cs) == 44, "selector offset");
_Static_assert(offsetof(trap_frame_t, eflags) == 48, "flags offset");
void traps_init(void);
__attribute__((noreturn)) void core_exception(const trap_frame_t *frame);
void fault_divide(void);
void fault_invalid(void);
void fault_general_protection(void);
extern const uint8_t fault_divide_instruction[];
extern const uint8_t fault_invalid_instruction[];
extern const uint8_t fault_gp_instruction[];
#endif
