#!/bin/sh
set -e
nasm -f bin timer.asm -o timer.exe
ls -l timer.exe
