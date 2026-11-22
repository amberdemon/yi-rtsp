#!/bin/sh
# Patched worker emits media to fd 3; library stdout and stderr are diagnostics.
exec 3>&1
exec 1>&2
exec qemu-aarch64 "$@"
