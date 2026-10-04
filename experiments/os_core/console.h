#ifndef CORE_CONSOLE_H
#define CORE_CONSOLE_H
#include <stdint.h>

#define CONSOLE_LINE_CAPACITY 32
typedef enum {
    CONSOLE_NONE, CONSOLE_HELP, CONSOLE_STATUS, CONSOLE_QUIT,
    CONSOLE_UNKNOWN, CONSOLE_TOO_LONG, CONSOLE_INVALID
} console_result_t;
typedef struct {
    char line[CONSOLE_LINE_CAPACITY];
    unsigned used;
    console_result_t discard;
} console_input_t;

/* Initialize to zero; consume one byte. Invalid lines drain to CR or LF. */
console_result_t console_feed(console_input_t *input, uint8_t byte);
void console_invalidate(console_input_t *input);
#endif
