#!/bin/sh
# Run terminal fault cases independently; status and serial markers must agree.
set -eu
QEMU=${QEMU:-qemu-system-i386}
run_case() {
    image=$1
    expected_status=$2
    log=$3
    set +e
    # QEMU may include caller-supplied flags; intentional word splitting.
    timeout 10s $QEMU -accel tcg -m 32M -kernel "$image" -display none \
        -serial stdio -monitor none -no-reboot -nic none \
        -device isa-debug-exit,iobase=0xf4,iosize=4 > "$log" 2>&1
    status=$?
    set -e
    cat "$log"
    test "$status" -eq "$expected_status"
    grep -qx 'PASS two tasks yield resume exit reuse' "$log"
}
run_case build/core.elf 33 build/serial.log
! grep -q '^FAULT ' build/serial.log
test "$(grep -c '^PASS ' build/serial.log)" -eq 2
for case_id in 1 2 3; do
    log="build/fault-$case_id.log"
    run_case "build/fault-$case_id.elf" 37 "$log"
    test "$(grep -c '^PASS ' "$log")" -eq 3
    grep -qx 'PASS expected exception frame' "$log"
    case "$case_id" in
        1) vector=00000000; error=00000000; symbol=fault_divide_instruction ;;
        2) vector=00000006; error=00000000; symbol=fault_invalid_instruction ;;
        3) vector=0000000d; error=00000018; symbol=fault_gp_instruction ;;
    esac
    address=$(nm "build/fault-$case_id.elf" | awk -v name="$symbol" '$3 == name {print $1}')
    test -n "$address"
    test "$(grep -c '^FAULT ' "$log")" -eq 1
    grep -Eq "^FAULT vector=0x$vector error=0x$error eip=0x$address cs=0x00000008 eflags=0x[0-9a-f]{8}$" "$log"
done
# Corruption must take the actual panic path, never expected-fault success.
for case_id in 1 2 3 4 5 6; do
    log="build/stack-$case_id.log"
    run_case "build/stack-$case_id.elf" 35 "$log"
    case "$case_id" in
        1|5|6) reason='task stack guard' ;;
        2|3) reason='task stack pointer bounds' ;;
        4) reason='task stack pointer alignment' ;;
    esac
    grep -qx "FAIL: $reason" "$log"
    test "$(grep -c '^FAIL:' "$log")" -eq 1
    test "$(grep -c '^PASS ' "$log")" -eq 2
    ! grep -q '^FAULT ' "$log"
    ! grep -q 'corrupt task resumed\|corrupt task accepted' "$log"
    if test "$case_id" -ge 5; then
        grep -qx 'FIXTURE corrupt running task guard' "$log"
    else
        ! grep -q '^FIXTURE ' "$log"
    fi
done
