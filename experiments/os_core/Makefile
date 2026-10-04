CC = gcc
LD = ld
QEMU = qemu-system-i386
OPT ?= -O2
CFLAGS = -m32 $(OPT) -std=c11 -ffreestanding -fno-pie -fno-pic -fno-stack-protector -fno-asynchronous-unwind-tables -fno-builtin -mno-sse -mno-mmx -msoft-float -Wall -Wextra -Werror
OBJECTS = build/boot.o build/switch.o build/core.o

.PHONY: all check clean
all: build/core.elf
build:
	mkdir -p build
build/%.o: %.S | build
	$(CC) $(CFLAGS) -c $< -o $@
build/core.o: core.c | build
	$(CC) $(CFLAGS) -c $< -o $@
build/core.elf: $(OBJECTS) linker.ld
	$(LD) -m elf_i386 -T linker.ld -o $@ $(OBJECTS)
check: build/core.elf
	@set +e; timeout 10s $(QEMU) -accel tcg -m 32M -kernel $< -display none -serial stdio -monitor none -no-reboot -nic none -device isa-debug-exit,iobase=0xf4,iosize=4 > build/serial.log 2>&1; status=$$?; cat build/serial.log; test $$status -eq 33 || exit 1; test "$$(grep -c '^PASS ' build/serial.log)" -eq 2 && grep -qx 'PASS two tasks yield resume exit reuse' build/serial.log
clean:
	rm -rf build
