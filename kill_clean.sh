#!/bin/bash
#kill every whe.py windows/proc
kill -KILL `ps | egrep "whe.py|bas.py|net.py|base.py|controller.py" | tr -s " " | cut -d " " -f2`

kill -KILL `ps | grep tee | tr -s " " | cut -d " " -f2`

kill -KILL `ps aux | grep "cat /tmp/out" | grep -v grep | tr -s ' ' | cut -d' ' -f2`

\rm -f /tmp/in* /tmp/out* /tmp/fifo* in* out* f* -v
