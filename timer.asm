; Tiny always-on-top timer (countdown / count-up) for Windows. nasm -f bin.
; Whole image = file (file offset == RVA), base 0x400000, one RWX section.
bits 32
B equ 0x400000
org B

; ---------------- PE header (unused fields hold import strings) ----------------
    db 'MZ',0,0
    db 'PE',0,0                  ; e_lfanew = 4 (dword at 0x3C = SectionAlignment)
    dw 0x14c, 1                  ; i386, 1 section
n_u32: db 'user32.dll',0,0       ; TimeDateStamp/PointerToSymbolTable/NumberOfSymbols
    dw 0x70, 0x103               ; SizeOfOptionalHeader, RELOCS_STRIPPED|EXEC|32BIT
    dw 0x10b                     ; PE32
h_MessageBeep: dw 0              ; linker version (unused) = hint
    db 'MessageBeep',0           ; SizeOfCode/InitializedData/UninitializedData
    dd entry - B                 ; AddressOfEntryPoint (high word = hint of SetTimer)
h_SetTimer equ $ - 2
    db 'SetTimer'                ; BaseOfCode/BaseOfData; NUL = low byte of ImageBase
    dd B                         ; ImageBase
    dd 4, 4                      ; Section/FileAlignment
    dw 4, 0, 0, 0, 4, 0          ; OS / image / subsystem versions
    dd 0                         ; Win32VersionValue
    dd end - B                   ; SizeOfImage
    dd hdr_end - B               ; SizeOfHeaders
    dd 0                         ; CheckSum
    dw 2, 0                      ; GUI, DllCharacteristics
    dd 0x100000, 0x1000, 0x100000, 0x1000, 0
    dd 2                         ; NumberOfRvaAndSizes
    dd 0, 0                      ; export
    dd idt - B, 60               ; import
    db '.text',0,0,0
    dd end - hdr_end, hdr_end - B, end - hdr_end, hdr_end - B, 0, 0, 0
    dd 0xE0000060                ; code|data|RWX
hdr_end:

; ---------------- code ----------------
%define I(x) [ebx + x - idt]     ; IAT slot / state via base register
entry:
    mov ebx, idt
    xor eax, eax
    push eax
    push proc
    push eax
    push tmpl
    push eax
    call I(DialogBoxIndirectParamW)
    push eax
    call I(ExitProcess)

; INT_PTR CALLBACK proc(h, msg, w, l)
proc:
    pushad
    mov ebx, idt
    mov ebp, [esp+36]            ; h
    mov eax, [esp+40]            ; msg
    sub eax, 0x110               ; WM_INITDIALOG
    jz init
    dec eax                      ; WM_COMMAND
    jz command
    dec eax
    dec eax                      ; WM_TIMER
    jnz done
    cmp byte I(RUN), 0
    je done
tick:
    call I(GetTickCount)
    sub eax, I(V)                ; elapsed ms
    cmp byte I(DOWN), 0
    je show
    mov ecx, I(TARGET)
    sub ecx, eax                 ; remaining
    ja .left
    mov byte I(RUN), 0           ; finished
    push 0x30                    ; MB_ICONEXCLAMATION
    call I(MessageBeep)
    xor ecx, ecx
.left:
    lea eax, [ecx + 999]         ; round up for countdown
show:                            ; eax = ms -> "h:mm:ss"
    xor edx, edx
    mov ecx, 1000
    div ecx
    push 60
    pop ecx
    xor edx, edx
    div ecx
    push edx                     ; s
    xor edx, edx
    div ecx
    push edx                     ; m
    push eax                     ; h
    push fmt
    lea esi, I(BUF)
    push esi
    call I(wsprintfA)
    add esp, 20
    push esi
    push 10
    push ebp
    call I(SetDlgItemTextA)
done:
    popad
    xor eax, eax
    ret 16

init:
    xor ecx, ecx
    push ecx                     ; face (default)
    push 0x20                    ; FF_SWISS
    times 7 push ecx
    push 700                     ; FW_BOLD
    times 3 push ecx
    push -40                     ; height
    call I(CreateFontA)
    push 0
    push eax
    push 0x30                    ; WM_SETFONT
    push 10
    push ebp
    call I(SendDlgItemMessageA)
    push 0
    push 100
    push 1
    push ebp
    call I(SetTimer)
    popad
    push 1
    pop eax
    ret 16

command:
    mov eax, [esp+44]            ; id in al
    cmp al, 4
    ja done
    je pause
    cmp al, 2
    je close
    ; 1 = down (Enter), 3 = up: parse "m", "m:ss", "h:mm:ss"
    cmp al, 1
    sete I(DOWN)
    push 16
    lea esi, I(BUF)
    push esi
    push 11
    push ebp
    call I(GetDlgItemTextA)
    xor eax, eax
    xor ecx, ecx                 ; t
    cdq                          ; cur
    mov edi, 60000               ; ms per unit of last field
.l: lodsb
    sub al, '0'
    jb .end
    cmp al, 10                   ; ':'
    je .colon
    imul edx, edx, 10
    add edx, eax
    jmp .l
.colon:
    add ecx, edx
    imul ecx, ecx, 60
    cdq
    mov edi, 1000
    jmp .l
.end:
    lea eax, [ecx + edx]
    imul eax, edi
    mov I(TARGET), eax
    mov byte I(RUN), 1
    call I(GetTickCount)
    mov I(V), eax
    jmp tick

pause:                           ; V = now - V toggles start-time <-> elapsed
    call I(GetTickCount)
    sub eax, I(V)
    mov I(V), eax
    xor byte I(RUN), 1
    jmp done

close:
    push 0
    push ebp
    call I(EndDialog)
    jmp done

; ---------------- data ----------------
fmt: db '%02u:%02u:%02u',0

align 4, db 0
tmpl:
    dd 0x00CA0840, 8             ; CAPTION|SYSMENU|MINIMIZEBOX|DS_SETFONT|DS_CENTER, EX_TOPMOST
    dw 5, 0, 0, 126, 39, 0, 0
    dw 0, 8, __utf16__('Arial'), 0             ; no title
%macro item 8                    ; style x y cx cy id class text
    align 4, db 0
    dd 0x50000000 | %1, 0
    dw %2, %3, %4, %5, %6, 0xFFFF, %7
    dw %8, 0, 0
%endmacro
    item 0x01,       0,  0, 126, 24, 10, 0x82, __utf16__('00:00:00')
    item 0x00810000, 2, 25,  28, 12, 11, 0x81, __utf16__('5:00')
    item 0x00010001,32, 25,  30, 12,  1, 0x80, 0x25BC
    item 0x00010000,63, 25,  30, 12,  3, 0x80, 0x25B2
    item 0x00010000,94, 25,  30, 12,  4, 0x80, __utf16__('II')

; ---------------- imports ----------------
; hint/name entries: the 2-byte hint overlaps the previous string's tail (hint is only a guess)
n_k32: db 'kernel32.dll',0
n_g32: db 'gdi32.dll',0
%macro hn 1
h_%1 equ $ - 2
    db %str(%1), 0
%endmacro
    hn GetTickCount
    hn ExitProcess
    hn CreateFontA
    hn EndDialog
    hn SetDlgItemTextA
    hn GetDlgItemTextA
    hn wsprintfA
    hn SendDlgItemMessageA
BUF equ $                        ; reused as text buffer after load (24 bytes)
    hn DialogBoxIndirectParamW
align 4, db 0
%macro imp 1
%1: dd h_%1 - B
%endmacro
iat_k32:
    imp GetTickCount
    imp ExitProcess
    dd 0
iat_g32:
    imp CreateFontA
    dd 0
iat_u32:
    imp DialogBoxIndirectParamW
    imp EndDialog
    imp SetTimer
    imp SetDlgItemTextA
    imp GetDlgItemTextA
    imp MessageBeep
    imp wsprintfA
    imp SendDlgItemMessageA
    dd 0
idt:
    dd 0, 0, 0, n_k32 - B, iat_k32 - B
    dd 0, 0, 0, n_u32 - B, iat_u32 - B
    dd 0, 0, 0, n_g32 - B, iat_g32 - B
; state: zero at load, so it also serves as the null import descriptor (20 bytes)
V:      dd 0                     ; running: start tick; paused: elapsed ms
TARGET: dd 0
RUN:    db 0
DOWN:   db 0
        times 10 db 0
end:
