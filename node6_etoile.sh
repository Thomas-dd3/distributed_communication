#!/bin/bash

# Création des pipes de la base 1 et du controller 1
mkfifo /tmp/inb0 /tmp/outb0
mkfifo /tmp/inc0 /tmp/outc0

mkfifo /tmp/inb1 /tmp/outb1
mkfifo /tmp/inc1 /tmp/outc1

mkfifo /tmp/inb2 /tmp/outb2
mkfifo /tmp/inc2 /tmp/outc2

mkfifo /tmp/inb3 /tmp/outb3
mkfifo /tmp/inc3 /tmp/outc3

mkfifo /tmp/inb4 /tmp/outb4
mkfifo /tmp/inc4 /tmp/outc4

mkfifo /tmp/inb5 /tmp/outb5
mkfifo /tmp/inc5 /tmp/outc5

# Démarrage des sites
./base.py --whatwho --ident=base_site0 --auto --verbose=0 < /tmp/inb0 > /tmp/outb0 &
./base.py --whatwho --ident=base_site1 --auto --verbose=0 < /tmp/inb1 > /tmp/outb1 &
./base.py --whatwho --ident=base_site2 --auto --verbose=0 < /tmp/inb2 > /tmp/outb2 &
./base.py --whatwho --ident=base_site3 --auto --verbose=0 < /tmp/inb3 > /tmp/outb3 &
./base.py --whatwho --ident=base_site4 --auto --verbose=0 < /tmp/inb4 > /tmp/outb4 &
./base.py --whatwho --ident=base_site5 --auto --verbose=0 < /tmp/inb5 > /tmp/outb5 &

./controller.py --whatwho --ident=controller_site0 --auto --id=0 --total=6 --verbose=0 < /tmp/inc0 > /tmp/outc0 &
./controller.py --whatwho --ident=controller_site1 --auto --id=1 --total=6 --verbose=0 < /tmp/inc1 > /tmp/outc1 &
./controller.py --whatwho --ident=controller_site2 --auto --id=2 --total=6 --verbose=0 < /tmp/inc2 > /tmp/outc2 &
./controller.py --whatwho --ident=controller_site3 --auto --id=3 --total=6 --verbose=0 < /tmp/inc3 > /tmp/outc3 &
./controller.py --whatwho --ident=controller_site4 --auto --id=4 --total=6 --verbose=0 < /tmp/inc4 > /tmp/outc4 &
./controller.py --whatwho --ident=controller_site5 --auto --id=5 --total=6 --verbose=0 < /tmp/inc5 > /tmp/outc5 &


# Waiting for the link creation (security delay)
sleep 1

cat /tmp/outb0 > /tmp/inc0 &
cat /tmp/outb1 > /tmp/inc1 &
cat /tmp/outb2 > /tmp/inc2 &
cat /tmp/outb3 > /tmp/inc3 &
cat /tmp/outb4 > /tmp/inc4 &
cat /tmp/outb5 > /tmp/inc5 &

cat /tmp/outc0 | tee /tmp/inb0 /tmp/inc1 &
cat /tmp/outc1 | tee /tmp/inb1 /tmp/inc0 /tmp/inc2 /tmp/inc4 &
cat /tmp/outc2 | tee /tmp/inb2 /tmp/inc1 /tmp/inc3 /tmp/inc4 &
cat /tmp/outc3 | tee /tmp/inb3 /tmp/inc2 &
cat /tmp/outc4 | tee /tmp/inb4 /tmp/inc1 /tmp/inc2 /tmp/inc5 &
cat /tmp/outc5 | tee /tmp/inb5 /tmp/inc4
