# Hand-made PE32 header + import table. Image base 0x400000, file offset == RVA.
# Unused header fields hold DLL name strings to save bytes.
.set B, 0x400000
.section .hdr,"dr"
    .ascii "MZ\0\0"
    .ascii "PE\0\0"                    # e_lfanew = 4 (overlaps SectionAlignment)
    .short 0x14c, 1                    # i386, 1 section
n_u32: .ascii "user32.dll\0\0"         # TimeDateStamp/PointerToSymbolTable/NumberOfSymbols (unused)
    .short 0x70, 0x103                 # opt hdr size, RELOCS_STRIPPED|EXEC|32BIT
    .short 0x10b                       # PE32
h_MessageBeep: .short 0                # linker version (unused) = hint
    .ascii "MessageBeep\0"             # SizeOfCode/InitializedData/UninitializedData (unused)
    .long _entry - B                   # AddressOfEntryPoint
    .ascii "SetTimer"                  # BaseOfCode/BaseOfData (unused); hint = entry high word,
.set h_SetTimer, . - 10                #   NUL = low byte of ImageBase
    .long B                            # ImageBase
    .long 4, 4                         # Section/FileAlignment (0x3C = e_lfanew)
    .short 4, 0, 0, 0, 4, 0            # OS / image / subsystem versions
    .long 0                            # Win32VersionValue
    .long __end - B                    # SizeOfImage
    .long __hdr_end - B                # SizeOfHeaders
    .long 0                            # CheckSum
    .short 2, 0                        # GUI subsystem, DllCharacteristics
    .long 0x100000, 0x1000, 0x100000, 0x1000, 0
    .long 2                            # NumberOfRvaAndSizes
    .long 0, 0                         # export dir
    .long idt - B, 40                  # import dir
    .ascii ".text\0\0\0"
    .long __sec_size, __hdr_end - B, __sec_size, __hdr_end - B
    .long 0, 0, 0
    .long 0xE0000060                   # code|data|RWX

# Import table. Hint words overlap the tail of the previous name (hint is only a lookup guess).
# Must be placed last before .bss: the zero .bss bytes act as the null descriptor terminator.
.section .idt,"dr"
.macro imp f, n
    .globl __imp__\f
__imp__\f: .long h_\n - B
.endm
iat_k32:
    imp GetTickCount@0, GetTickCount
    imp ExitProcess@4, ExitProcess
    .long 0
iat_g32:
    imp CreateFontA@56, CreateFontA
    .long 0
iat_u32:
    imp DialogBoxIndirectParamW@20, DialogBoxIndirectParamW
    imp EndDialog@8, EndDialog
    imp SetTimer@16, SetTimer
    imp SetDlgItemTextA@12, SetDlgItemTextA
    imp GetDlgItemTextA@16, GetDlgItemTextA
    imp MessageBeep@4, MessageBeep
    imp wsprintfA, wsprintfA
    imp SendDlgItemMessageA@20, SendDlgItemMessageA
    .long 0
# Hint/name entries: the 2-byte hint overlaps the tail of the previous string
# (the hint is only a lookup guess; the loader falls back to a name search).
n_k32: .asciz "kernel32.dll"
n_g32: .asciz "gdi32.dll"
.irp f, GetTickCount, ExitProcess, DialogBoxIndirectParamW, EndDialog, SetDlgItemTextA, GetDlgItemTextA, wsprintfA, SendDlgItemMessageA, CreateFontA
.set h_\f, . - 2
    .asciz "\f"
.endr
    .p2align 2
# Import descriptors. Placed last before .bss: the zeroed .bss acts as the null terminator.
idt:
    .long 0, 0, 0, n_k32 - B, iat_k32 - B
    .long 0, 0, 0, n_u32 - B, iat_u32 - B
    .long 0, 0, 0, n_g32 - B, iat_g32 - B
