SECTIONS
{
  . = 0x400000;
  .img : {
    *(.hdr) . = ALIGN(4); __hdr_end = .;
    *(.text) *(.text$*) *(.rdata) *(.rdata$*) *(.data) *(.idt) *(.bss) *(COMMON)
    . = ALIGN(4); __end = .;
  }
  __sec_size = __end - __hdr_end;
  /DISCARD/ : { *(*) }
}
