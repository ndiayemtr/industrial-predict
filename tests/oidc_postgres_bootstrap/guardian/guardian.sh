#!/bin/sh
# Idle-only PID 1 foundation. No activation protocol or bootstrap dispatcher.
set -u

if [ "$#" -ne 0 ]; then
    printf '%s\n' 'OIDC guardian arguments rejected' >&2
    exit 78
fi

idle_pid=''
stop_guardian() {
    trap '' TERM INT
    if [ -n "$idle_pid" ]; then
        kill -TERM "$idle_pid" 2>/dev/null || :
        wait "$idle_pid" 2>/dev/null || :
    fi
    exit 0
}

trap stop_guardian TERM INT
trap '' HUP QUIT USR1 USR2
/usr/bin/sleep infinity &
idle_pid=$!
wait "$idle_pid" 2>/dev/null
printf '%s\n' 'OIDC guardian idle process ended' >&2
exit 70
