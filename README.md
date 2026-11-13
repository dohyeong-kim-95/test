# Tiny Timer

A Windows timer that is always on top and counts down or up. It is a single standalone `timer.exe` of **864 bytes**.

## Usage
- Type a time in the input box (default `5`): `5` = 5 min, `5:30` = 5 min 30 s, `1:00:00` = 1 h
- `▼` (or Enter): count down. When it reaches 0 it beeps and stops.
- `▲`: count up from 0
- `║`: pause / resume
- Esc or the X button: quit
- The window always stays on top.

## How the size is reduced
- The whole thing is written in hand-coded x86 assembly (`timer.asm`, nasm `-f bin`). No linker, no C runtime.
- The UI is an in-memory dialog template, so there is no window class or message loop.
- PE header and import table are written by hand: 1 section, 4-byte alignment, headers overlapped (e_lfanew=4).
- DLL and function name strings are stored in unused PE header fields. Import hints overlap the end of the previous string.
- The trailing state variables (zero at load) double as the import descriptor terminator.
- An import name string that is no longer needed after load is reused as the text buffer.
- Only one user32 messaging import: `SendDlgItemMessageA` does WM_SETFONT / WM_SETTEXT / WM_GETTEXT.
- Closing calls `ExitProcess` straight from the dialog procedure (no `EndDialog`).
- IAT and state are addressed from a base register (`[ebx+disp8]`) to shorten instructions.
- Pause/resume is a single expression: `V = now - V` (start time <-> elapsed time).

## Build
Requires `nasm`.
```
./build.sh
```
