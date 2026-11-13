#!/bin/sh
set -e
P=i686-w64-mingw32-
clang --target=i686-w64-mingw32 -Oz -c -fno-asynchronous-unwind-tables -fno-ident -fno-stack-protector -fno-builtin timer.c -o timer.o
${P}as pe.s -o pe.o
${P}ld -T link.ld --image-base=0x100000 --disable-reloc-section -o img.pe pe.o timer.o
${P}objcopy -O binary -j .img img.pe timer.exe
rm -f img.pe *.o
ls -l timer.exe
