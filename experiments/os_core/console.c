#include "console.h"

static int command_is(const console_input_t *input, const char *word,
                      unsigned length) {
    if (input->used != length) return 0;
    for (unsigned n = 0; n < length; ++n)
        if (input->line[n] != word[n]) return 0;
    return 1;
}
void console_invalidate(console_input_t *input) {
    if (input->discard == CONSOLE_NONE) input->discard = CONSOLE_INVALID;
}
console_result_t console_feed(console_input_t *input, uint8_t byte) {
    if (byte == '\r' || byte == '\n') {
        console_result_t result = input->discard;
        if (result == CONSOLE_NONE && input->used) {
            if (command_is(input, "help", 4)) result = CONSOLE_HELP;
            else if (command_is(input, "status", 6)) result = CONSOLE_STATUS;
            else if (command_is(input, "quit", 4)) result = CONSOLE_QUIT;
            else result = CONSOLE_UNKNOWN;
        }
        input->used = 0;
        input->discard = CONSOLE_NONE;
        return result;
    }
    if (input->discard != CONSOLE_NONE) return CONSOLE_NONE;
    if (byte < 0x20 || byte > 0x7e) {
        console_invalidate(input);
        return CONSOLE_NONE;
    }
    /* Leave one byte unused; no unbounded write or length counter growth. */
    if (input->used >= CONSOLE_LINE_CAPACITY - 1) {
        input->discard = CONSOLE_TOO_LONG;
        return CONSOLE_NONE;
    }
    input->line[input->used++] = (char)byte;
    return CONSOLE_NONE;
}
