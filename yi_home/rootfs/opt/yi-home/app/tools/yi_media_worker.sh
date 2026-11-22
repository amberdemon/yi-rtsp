#!/bin/sh
# The prepared worker writes binary media to fd 3. Keep vendor printf output
# out of both the media pipe and logs; native stage diagnostics remain on fd 2.
exec 3>&1
exec 1>/dev/null
exec "$@"
