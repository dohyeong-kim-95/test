/* Tiny always-on-top timer (always topmost): countdown / count-up. Win32 dialog, no CRT. */
#include <windows.h>

static DWORD t0, acc, target;          /* ms */
static int running, down;

static void show(HWND h, DWORD ms)
{
    char b[12];
    DWORD s = down ? (ms + 999) / 1000 : ms / 1000;
    wsprintfA(b, "%02u:%02u:%02u", s / 3600, s / 60 % 60, s % 60);
    SetDlgItemTextA(h, 10, b);
}

static INT_PTR CALLBACK proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    DWORD el, t = 0, cur = 0, colon = 0;
    char b[16], *p = b;
    if (m == WM_INITDIALOG) {
        SendDlgItemMessageA(h, 10, WM_SETFONT,
            (WPARAM)CreateFontA(-40, 0, 0, 0, FW_BOLD, 0, 0, 0, 0, 0, 0, 0, FF_SWISS, 0), 0);
        SetTimer(h, 1, 100, 0);
        return 1;
    }
    if (m == WM_TIMER && running) {
        el = acc + GetTickCount() - t0;
        if (down) {
            if (el >= target) { running = 0; el = target; MessageBeep(MB_ICONEXCLAMATION); }
            el = target - el;
        }
        show(h, el);
    }
    if (m == WM_COMMAND)
        switch (LOWORD(w)) {
        case IDCANCEL:                      /* close / Esc */
            EndDialog(h, 0);
            break;
        case IDOK: case 3:                  /* Down(Enter) / Up : (re)start */
            down = LOWORD(w) == IDOK;
            /* "90" = 90 min, "5:30" = 5m30s, "1:00:00" = 1h */
            GetDlgItemTextA(h, 11, b, sizeof b);
            for (; *p; p++)
                if (*p == ':') { t = (t + cur) * 60; cur = 0; colon = 1; }
                else cur = cur * 10 + *p - '0';
            t += cur;
            target = (colon ? t : t * 60) * 1000;
            acc = 0; t0 = GetTickCount(); running = 1;
            show(h, down ? target : 0);
            break;
        case 4:                             /* Pause / Resume */
            if (running) acc += GetTickCount() - t0;
            else t0 = GetTickCount();
            running ^= 1;
            break;
        }
    return 0;
}

/* In-memory dialog template (items must be DWORD aligned). */
#define S(x) (WS_CHILD | WS_VISIBLE | (x))
#define LO(d) (WORD)(d), (WORD)((d) >> 16)
static const WORD tmpl[] __attribute__((aligned(4))) = {
    LO(WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | DS_SETFONT | DS_CENTER), LO(WS_EX_TOPMOST),
    5, 0, 0, 126, 39,  0, 0, 'T','i','m','e','r',0,  8, 'A','r','i','a','l',0,
    /* item: style, exstyle, x, y, cx, cy, id, 0xFFFF, class atom, text, 0(extra), [pad] */
    LO(S(SS_CENTER)), 0, 0,  0, 0, 126, 24, 10, 0xFFFF, 0x82, '0','0',':','0','0',':','0','0',0, 0, 0,
    LO(S(WS_BORDER | WS_TABSTOP)), 0, 0,  2, 25, 28, 12, 11, 0xFFFF, 0x81, '5',':','0','0',0, 0, 0,
    LO(S(BS_DEFPUSHBUTTON | WS_TABSTOP)), 0, 0,  32, 25, 30, 12, IDOK, 0xFFFF, 0x80, 0x25BC,0, 0,
    LO(S(WS_TABSTOP)), 0, 0,  63, 25, 30, 12, 3, 0xFFFF, 0x80, 0x25B2,0, 0,
    LO(S(WS_TABSTOP)), 0, 0,  94, 25, 30, 12, 4, 0xFFFF, 0x80, 'I','I',0, 0, 0,
};

void entry(void)
{
    DialogBoxIndirectParamW(0, (LPCDLGTEMPLATEW)tmpl, 0, proc, 0);
    ExitProcess(0);
}
