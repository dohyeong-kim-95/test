; Tiny always-on-top timer (countdown / count-up) for Windows. nasm -f bin.
bits 32
B equ 0x400000
org B
    db 'MZ',0,0
    db 'PE',0,0
    dw 0x14c, 1
n_u32: db 'user32.dll',0,0
    dw 0x70, 0x103
    dw 0x10b
h_MessageBeep: dw 0
    db 'MessageBeep',0
    dd entry - B
h_SetTimer equ $ - 2
    db 'SetTimer'
    dd B
    dd 4, 4
    dw 4, 0, 0, 0, 4, 0
    dd 0
    dd end - B
    dd hdr_end - B
    dd 0
    dw 2, 0
    dd 0x100000, 0x1000, 0x100000, 0x1000, 0
    dd 2
    dd 0, 0
    dd idt - B, 60
    db '.text',0,0,0
    dd end - hdr_end, hdr_end - B, end - hdr_end, hdr_end - B
h_ExitProcess equ $ - 2          ; hint = high word of PointerToRawData
    db 'ExitProcess',0           ; PointerToRelocations/Linenumbers/counts (unused in images)
    dd 0xE0000060
hdr_end:

; ---------------- dialog template (dword aligned here: 0xB0) ----------------
tmpl:
    dd 0x00CA0840, 8
    dw 5, 0, 0, 126, 39, 0, 0
    dw 'T', 0, 8, __utf16__('Arial'), 0
%macro item 8
    align 4, db 0
    dd 0x50000000 | %1, 0
    dw %2, %3, %4, %5, %6, 0xFFFF, %7
    dw %8, 0, 0
%endmacro
%macro item0 7                   ; no text
    align 4, db 0
    dd 0x50000000 | %1, 0
    dw %2, %3, %4, %5, %6, 0xFFFF, %7
    dw 0, 0
%endmacro
    item0 0x01,      0,  0, 126, 24, 10, 0x82
    item 0x00810000, 2, 25,  28, 12, 11, 0x81, '5'
    item 0x00010001,32, 25,  30, 12,  1, 0x80, 0x25BC
    item 0x00010000,63, 25,  30, 12,  3, 0x80, 0x25B2
    item 0x00010000,94, 25,  30, 12,  4, 0x80, 0x2551

; ---------------- code ----------------
%define I(x) [ebx + x - BUF]
init:                            ; eax = 0
    push proc                    ; SetTimer callback = proc, so WM_TIMER's lParam is the tick count
    push 100
    push ebp                     ; id (any nonzero)
    push ebp
    push eax                     ; WM_SETFONT lParam
    push eax                     ; face (default)
    push 0x20                    ; FF_SWISS
    times 7 push eax
    mov ah, 3
    push eax                     ; weight 768 (bold)
    cdq
    times 3 push edx
    push -40                     ; height
    call I(CreateFontA)
    push eax
    push 0x30                    ; WM_SETFONT
    push 10
    push ebp
    call I(SendDlgItemMessageA)
    call I(SetTimer)             ; args pushed above
    jmp proc.zero                     ; show 00:00:00, return TRUE

; INT_PTR CALLBACK proc(h, msg, w, l)
proc:
    xor eax, eax
    pushad                       ; saved-eax slot = return value = 0
    mov ebx, BUF
    lea esi, [esp+36]
    lodsd
    xchg eax, ebp                ; h
    lodsd                        ; msg
    sub ax, 0x110                ; WM_INITDIALOG
    jz init
    dec eax                      ; WM_COMMAND
    jz command
    dec eax
    dec eax                      ; WM_TIMER
    jnz done
    lodsd
    lodsd                        ; lParam = tick count (we are the TIMERPROC)
    mov I(NOW), eax
    cmp byte I(RUN), 0
    je done
    sub eax, I(V)                ; up: elapsed ms; down: -(remaining ms)
    cmp byte I(MODE), 1
    jne show
    neg eax
    jg .left
    push 0x30                    ; MB_ICONEXCLAMATION
    call I(MessageBeep)
.zero:
    xor eax, eax
    mov I(RUN), al               ; finished
.left:
    add eax, 999                 ; round up for countdown
show:                            ; eax = ms -> "h:mm:ss"
    xor edx, edx
    mov ecx, 1000
    div ecx
    push 60
    pop ecx
    cdq
    div ecx
    push edx                     ; s
    cdq
    div ecx
    push edx                     ; m
    push eax                     ; h
    lea eax, I(fmt)
    push eax
    push ebx                     ; BUF
    call I(wsprintfA)
    add esp, 20
    push ebx
    push eax                     ; wParam unused
    push 0x0C                    ; WM_SETTEXT
    push 10
    push ebp
    call I(SendDlgItemMessageA)
    inc byte [esp+28]            ; return TRUE
done:
    popad
    ret 16

command:
    lodsd                        ; wParam: id (1 down/Enter, 2 close, 3 up, 4 pause)
    cmp al, 4
    ja done
    je pause
    cmp al, 2
    je close
    mov I(MODE), eax             ; MODE = id, RUN = 0
    ja .set                      ; up: start from "elapsed = 3 ms"
    mov esi, ebx                 ; BUF
    push ebx
    push 16
    push 0x0D                    ; WM_GETTEXT
    push 11
    push ebp
    call I(SendDlgItemMessageA)  ; eax = len (< 256)
    xor ecx, ecx                 ; t
    cdq                          ; cur (negated)
    mov edi, 60000               ; ms per unit of last field
.l: lodsb
    sub al, '0'
    jb .end
    cmp al, 10                   ; ':'
    je .colon
    imul edx, edx, 10
    sub edx, eax
    jmp .l
.colon:
    add ecx, edx
    imul ecx, ecx, 60
    cdq
    mov di, 1000
    jmp .l
.end:
    lea eax, [ecx + edx]
    imul eax, edi                ; -(target ms)
.set:
    mov I(V), eax                ; as if paused at this elapsed value
pause:                           ; V = now - V toggles start-time <-> elapsed
    mov eax, I(NOW)              ; tick of the last WM_TIMER (<= 100 ms old)
    sub eax, I(V)
    mov I(V), eax
    not byte I(RUN)
    jmp done

entry:
    mov ebx, BUF
    xor eax, eax
    push eax
    push proc
    push eax
    push tmpl
    push eax
    call I(DialogBoxIndirectParamW)
close:
    call I(ExitProcess)

; ---------------- imports ----------------
n_k32: db 'kernel32.dll',0
n_g32: db 'gdi32.dll',0
%macro hn 1
h_%1 equ $ - 2
    db %str(%1), 0
%endmacro
    hn CreateFontA
    hn wsprintfA
    hn DialogBoxIndirectParamW
    times ($$ - $ - 13 - 20) & 3 db 0   ; so that the IAT is dword aligned
fmt: db '%u:%02u:%02u',0
BUF equ $                        ; ebx points here; reused as text buffer after load (20 bytes)
    hn SendDlgItemMessageA
%macro imp 1
%1: dd h_%1 - B
%endmacro
iat_k32:
    imp ExitProcess
    dd 0
iat_g32:
    imp CreateFontA
    dd 0
iat_u32:
    imp DialogBoxIndirectParamW
    imp SetTimer
    imp MessageBeep
    imp wsprintfA
    imp SendDlgItemMessageA      ; list terminated by idt's first dword (0)
idt:
    dd 0, 0, 0, n_k32 - B, iat_k32 - B
    dd 0, 0, 0, n_u32 - B, iat_u32 - B
    dd 0, 0, 0, n_g32 - B, iat_g32 - B
; state: zero at load, so it also serves as the null import descriptor (20 bytes)
V:      dd 0                     ; running: start tick (down: end tick); paused: elapsed (down: -remaining)
MODE:   db 0                     ; 1 = countdown
RUN:    db 0
        dw 0
NOW:    dd 0                     ; last tick count seen
        times 8 db 0
end:
