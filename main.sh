#!/bin/bash

if [ $# -eq 0 ]
    then
        echo "Provide the number of node as the first parameters."
    fi

for i in `seq 0 $(($1-1))`;
do
    # Création des pipes de la base 1 et du controller 1
    mkfifo /tmp/inb$i /tmp/outb$i
    mkfifo /tmp/inc$i /tmp/outc$i
done

for i in `seq 0 $(($1-1))`;
do
    # Démarrage des sites
    ./base.py --whatwho --ident=base_site$i --auto --id=$i --total=$1 --verbose=0 < /tmp/inb$i > /tmp/outb$i &

    ./controller.py --whatwho --ident=controller_site$i --auto --id=$i --total=$1 --verbose=0 < /tmp/inc$i > /tmp/outc$i &

done

# Waiting for the link creation (security delay)
sleep 1

for i in `seq 0 $(($1-1))`;
do
    cat /tmp/outb$i > /tmp/inc$i &
    
    if [ $1 -eq 1 ]
    then
        cat /tmp/outc$i > /tmp/inb$i &
        break
    fi
    
    if [ $i -eq 0 ]
    then
        cat /tmp/outc$i | tee /tmp/inb$i /tmp/inc$(($i+1)) &
    elif [ $i -lt $(($1-1)) ]
    then
        cat /tmp/outc$i | tee /tmp/inb$i /tmp/inc$(($i-1)) /tmp/inc$(($i+1)) &
    else
        cat /tmp/outc$i | tee /tmp/inb$i /tmp/inc$(($i-1))
    fi

done