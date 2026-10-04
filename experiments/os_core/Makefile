CC = gcc
LD = ld
QEMU = qemu-system-i386
OPT ?= -O2
CFLAGS = -m32 $(OPT) -std=c11 -ffreestanding -fno-pie -fno-pic -fno-stack-protector -fno-asynchronous-unwind-tables -fno-builtin -mno-sse -mno-mmx -msoft-float -Wall -Wextra -Werror
COMMON = build/boot.o build/switch.o build/traps.o build/trap-table.o
OBJECTS = $(COMMON) build/core.o
STACK_IMAGES = $(foreach n,1 2 3 4 5 6,build/stack-$(n).elf)
FAULT_IMAGES = build/fault-1.elf build/fault-2.elf build/fault-3.elf

.PHONY: all check clean
all: build/core.elf
build:
	mkdir -p build
build/%.o: %.S | build
	$(CC) $(CFLAGS) -c $< -o $@
build/trap-table.o: traps.c traps.h | build
	$(CC) $(CFLAGS) -c $< -o $@
build/core.o: core.c traps.h | build
	$(CC) $(CFLAGS) -c $< -o $@
build/core.elf: $(OBJECTS) linker.ld
	$(LD) -m elf_i386 -T linker.ld -o $@ $(OBJECTS)
build/fault-%.o: core.c traps.h | build
	$(CC) $(CFLAGS) -DCORE_FAULT_CASE=$* -c $< -o $@
build/fault-%.elf: $(COMMON) build/fault-%.o linker.ld
	$(LD) -m elf_i386 -T linker.ld -o $@ $(COMMON) build/fault-$*.o
build/stack-%.o: core.c traps.h | build
	$(CC) $(CFLAGS) -DCORE_STACK_CASE=$* -c $< -o $@
build/stack-%.elf: $(COMMON) build/stack-%.o linker.ld
	$(LD) -m elf_i386 -T linker.ld -o $@ $(COMMON) build/stack-$*.o
check: build/core.elf $(FAULT_IMAGES) $(STACK_IMAGES)
	@QEMU="$(QEMU)" sh check.sh
clean:
	rm -rf build
