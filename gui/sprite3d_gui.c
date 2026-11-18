/* sprite3d.exe: the window in front of sprite3d.py (a 3D model from a 2D sprite). Plain C, Win32 + GDI+ (both part
   of Windows), nothing to install. Built the way the base kit's window is (O:\bases\gui\bbb_kit.c): one file, the
   whole window painted by this file into one off-screen picture, no standard controls, Python started hidden.

   What it does: you open a sprite (a PNG with a clear background, the object upright), or drop one on the window.
   The model is made at once and again whenever you change something on the left: how the depth is made (Shaped,
   Flat, Round), what the sprite is (for the parts guess), how thick, the edge's colour. The middle shows the model;
   drag it sideways, or use the arrow keys, to turn it. On the right: the original (if you give one), the sprite and
   the parts picture the model was made from. The files (.obj, .mtl, texture, parts picture, sheet) are in one folder.

   How it talks to Python: it starts  python -u sprite3d.py SPRITE --json ...  hidden and reads its output. Every line
   is one JSON record with an "ev" field (parts, mesh, obj, view, sheet, done, error), so nothing is guessed from
   printed text. Python sits in a job object: closing the window ends it.

   Where things are: the exe sits beside sprite3d.py (or one folder below it, in gui\). Python: SPRITE3D_PYTHON if
   set, else O:\appsnotonc\pixelup\.venv\Scripts\python.exe, else python on the PATH. Results: out\<sprite's name>\
   beside sprite3d.py. Settings: out\sprite3d_gui.ini.
   Keys: Ctrl+O open, Left / Right turn, Enter make again, D details, ? or F1 help, Esc closes a page.
   Build: gui\build.cmd.   Test (no clicks, window off screen): --selftest <shot.bmp> <sprite.png> makes the model,
   writes the window's picture, a second one of the help page, and <shot.bmp>.txt with what happened. */
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>
#include <commdlg.h>
#include <objbase.h>
#include <gdiplus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <math.h>

#define WM_LINE (WM_APP + 1)
#define WM_ENDED (WM_APP + 2)
#define C_BG 0xFF15171Cu
#define C_SIDE 0xFF1B1E25u
#define C_CARD 0xFF252932u
#define C_CARDH 0xFF2D323Du
#define C_LINE 0xFF373C49u
#define C_TEXT 0xFFE9EBEFu
#define C_DIM 0xFF98A1B0u
#define C_ACC 0xFF1FB8A6u
#define C_ACCH 0xFF3ACFBDu
#define C_ONACC 0xFF06211Du
#define C_GOLD 0xFFE2B33Cu
enum { SIDE_W = 300, HEAD_H = 74, FOOT_H = 58, NV = 12, MAXLOG = 200 };
enum { H_NONE, H_OPEN, H_PARTS, H_PARTSX, H_ORIG, H_ORIGX, H_METHOD, H_KIND, H_THICK, H_SIDES, H_OUTL, H_TURN, H_GO, H_FOLDER, H_DETAILS, H_HELP, H_PREV, H_NEXT, H_VIEW,
       H_HANDLE, H_DETAIL, H_POLY, H_PEDIT, H_PREG, H_PNEW, H_PDEL, H_PGUESS, H_PLABEL, H_PSHAPE, H_PTAPER, H_PSTEP, H_PMODE, H_CANVAS, H_BRUSH, H_BSIZE, H_PCLEAR };

typedef struct { RECT r; int kind, idx; } Hit;
static Hit hits[240]; static int nhit, hovK, hovI = -1;
static WCHAR *logv[MAXLOG]; static int nlog;
static HWND hMain; static double SC = 1.0; static HFONT fTitle, fLabel, fUI, fSmall, fBig, fBtn, fMono;
static WCHAR tool[MAX_PATH], py[MAX_PATH], sprite[MAX_PATH], parts[MAX_PATH], orig[MAX_PATH], outDir[MAX_PATH], objFile[MAX_PATH];
static WCHAR head[200], sub[400], facts[300], partsNote[120];
static GpImage *views[NV], *imSprite, *imParts, *imOrig, *imGone;
static int curView, gotViews, busy, dirty, anim, showDetails, showHelp, problems, madeOnce;
static int selMethod, selKind, selThick = 2, selSides, selOutl, selTurn;
static int dragging, dragX, dragView;
static HANDLE hJob;
static int selftest; static WCHAR stShot[MAX_PATH]; static RECT savedR; static int savedMax;

static const char *METHODL[] = { "Shaped", "Flat", "Round", "Turned" }, *METHODV[] = { "shaped", "slab", "round", "turned" };
static const char *KINDL[] = { "Auto", "Sword", "Axe", "Mace" }, *KINDV[] = { "auto", "sword", "axe", "mace" };
static const char *THICK[] = { "0.5", "1", "1.5", "2", "2.5", "3" };
static const char *SIDESL[] = { "Inner colour", "Outline" }, *SIDESV[] = { "inner", "outline" };
static const char *OUTLL[] = { "Sharp", "Seam", "Wrapped" }, *OUTLV[] = { "sharp", "flat", "wrap" };
static const char *TURNL[] = { "Upright", "90", "180", "270" }; static const int TURNV[] = { 0, 90, 180, 270 };
static const char *HANDLEL[] = { "Coloured middle", "With outline" }, *HANDLEV[] = { "inner", "full" };
static int selHandle, selDetail = 2, selPoly;
static const char *POLYL[] = { "Few (low poly)", "Many (per pixel)" }, *POLYV[] = { "lowpoly", "pixels" };
static const char *DETAILL[] = { "1x (pixels)", "2x", "4x", "8x" }; static const int DETAILV[] = { 1, 2, 4, 8 };
/* drawing on the sprite: one value a sprite pixel, in the sprite file's own orientation: -1 as made (not painted),
   0 cut away, 1..255 a grey: the thickness times grey / 128. Saved as out\NAME\NAME_paint.png, given as --paint */
static const char *BRUSHL[] = { "Thinner", "Thicker", "Cut away", "Keep", "As made" }, *BSIZEL[] = { "1", "2", "3" };
static short *pv; static unsigned char *sal, *pdone; static int pw, ph, paintMode, brush, bsize, stroking, hasPaint;
static int canX, canY, canW, canH; static double canS; static WCHAR paintFile[MAX_PATH], drawnNote[200];
/* the parts (regions.py): rg holds each sprite pixel's part (file orientation), -1 none; prt each part's label, shape
   and settings. The window's own parts are saved as out\NAME\NAME_myparts.png + .txt and given as --parts */
typedef struct { int col[3]; char label[16], shape[12], taper[8]; double depth, offset, tamount, bevel; int sides; } Part;
#define MAXP 16
static Part prt[MAXP]; static int nprt, psel, hasParts, saveGuess; static short *rg; static WCHAR myParts[MAX_PATH];
static const char *LABELV[14] = { "blade", "handle", "grip", "guard", "head", "gem", "pommel", "body", "lid", "neck", "base", "rim", "strap", "other" };
static const char *LABELL[14] = { "Blade", "Handle", "Grip", "Guard", "Head", "Gem", "Pommel", "Body", "Lid", "Neck", "Base", "Rim", "Strap", "Other" };
static const char *LSHAPE[14] = { "blade", "roundbar", "roundbar", "plate", "plate", "dome", "ball", "plate", "plate", "lathe", "lathe", "plate", "card", "plate" };
static const double LBEVEL[14] = { 1, 1, 1, 0.6, 1.5, 1, 1, 1, 0.6, 1, 1, 0.4, 1, 1 }, LDEPTH[14] = { 1, 1, 1, 1, 1, 0.8, 1, 1, 1, 1, 1, 1, 1, 1 };
static const char *SHAPEV[8] = { "roundbar", "lathe", "ball", "blade", "plate", "box", "dome", "card" };
static const char *SHAPEL[8] = { "Round bar", "Lathe", "Ball", "Blade", "Plate", "Box", "Dome", "Card" };
static const char *TAPERV[5] = { "none", "up", "down", "left", "right" }, *TAPERL[5] = { "None", "Up", "Down", "Left", "Right" };
static const int PAL[16][3] = { {0,0,255}, {0,255,0}, {255,255,0}, {0,255,255}, {255,128,0}, {255,0,255}, {128,64,255}, {0,160,80},
                                {255,200,128}, {128,255,200}, {64,128,255}, {200,255,0}, {0,128,160}, {255,160,255}, {160,96,0}, {96,255,96} };
static int stStage;
static int parts_read(const WCHAR *png, int turned); static void parts_save(void); static void parts_changed(void);

static int S(double x) { return (int)(x * SC + 0.5); }
static void redraw(void) { InvalidateRect(hMain, NULL, FALSE); }
static void logw(const WCHAR *t) {
    if (nlog == MAXLOG) { free(logv[0]); memmove(logv, logv + 1, (MAXLOG - 1) * sizeof *logv); nlog--; }
    logv[nlog++] = _wcsdup(t);
}

/* ---------- JSON: one flat record per line ---------- */
static const WCHAR *jfind(const WCHAR *s, const WCHAR *key) {
    WCHAR pat[48]; const WCHAR *p; swprintf(pat, 48, L"\"%ls\":", key); p = wcsstr(s, pat);
    if (!p) return NULL;
    p += wcslen(pat); while (*p == L' ') p++;
    return p;
}
static int jstr(const WCHAR *s, const WCHAR *key, WCHAR *out, int cap) {
    const WCHAR *p = jfind(s, key); int n = 0; out[0] = 0;
    if (!p || *p != L'"') return 0;
    for (p++; *p && *p != L'"' && n < cap - 1; p++) {
        if (*p == L'\\' && p[1]) {
            p++;
            if (*p == L'u' && p[1] && p[2] && p[3] && p[4]) { WCHAR h[5] = { p[1], p[2], p[3], p[4], 0 }; out[n++] = (WCHAR)wcstol(h, NULL, 16); p += 4; }
            else out[n++] = *p == L'n' ? L' ' : *p == L't' ? L' ' : *p;
        } else out[n++] = *p;
    }
    out[n] = 0; return 1;
}
static double jnum(const WCHAR *s, const WCHAR *key) { const WCHAR *p = jfind(s, key); return p ? wcstod(p, NULL) : 0; }
static int jtrue(const WCHAR *s, const WCHAR *key) { const WCHAR *p = jfind(s, key); return p && !wcsncmp(p, L"true", 4); }

/* ---------- pictures: read into memory, so the file is never held (Python writes it again on the next run) ---------- */
static GpImage *load_img(const WCHAR *path) {
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    DWORD n, got = 0; HGLOBAL g; IStream *st = NULL; GpImage *im = NULL; GpBitmap *copy = NULL; void *p; UINT w = 0, h = 0;
    if (f == INVALID_HANDLE_VALUE) return NULL;
    n = GetFileSize(f, NULL); g = GlobalAlloc(GMEM_MOVEABLE, n ? n : 1); p = GlobalLock(g); ReadFile(f, p, n, &got, NULL); GlobalUnlock(g); CloseHandle(f);
    if (CreateStreamOnHGlobal(g, TRUE, &st) != S_OK) { GlobalFree(g); return NULL; }
    if (GdipLoadImageFromStream(st, &im) == Ok && im) {
        GdipGetImageWidth(im, &w); GdipGetImageHeight(im, &h);
        if (w && h) GdipCloneBitmapAreaI(0, 0, (INT)w, (INT)h, PixelFormat32bppARGB, (GpBitmap *)im, &copy);
        GdipDisposeImage(im);
    }
    st->lpVtbl->Release(st);
    return (GpImage *)copy;
}
static void drop_img(GpImage **im) { if (*im) GdipDisposeImage(*im); *im = NULL; }

/* ---------- running Python hidden ---------- */
typedef struct { HANDLE rd, proc; } Run;
static DWORD WINAPI reader(LPVOID p) {
    Run *r = (Run *)p; char *buf = (char *)malloc(8192), *line = (char *)malloc(16384); int ll = 0; DWORD got, code = 0, i;
    while (ReadFile(r->rd, buf, 8192, &got, NULL) && got) {
        for (i = 0; i < got; i++) {
            char c = buf[i];
            if (c == '\n') {
                WCHAR *w; int n;
                if (ll && line[ll - 1] == '\r') ll--;
                line[ll] = 0; n = MultiByteToWideChar(CP_UTF8, 0, line, -1, NULL, 0); w = (WCHAR *)malloc((n + 1) * sizeof(WCHAR));
                MultiByteToWideChar(CP_UTF8, 0, line, -1, w, n); PostMessageW(hMain, WM_LINE, 0, (LPARAM)w); ll = 0;
            } else if (ll < 16382) line[ll++] = c;
        }
    }
    WaitForSingleObject(r->proc, 5000); GetExitCodeProcess(r->proc, &code);
    CloseHandle(r->rd); CloseHandle(r->proc); PostMessageW(hMain, WM_ENDED, 0, code); free(buf); free(line); free(r); return 0;
}
static int run(const WCHAR *cmd) {
    SECURITY_ATTRIBUTES sa = { sizeof sa, NULL, TRUE }; HANDLE rd, wr, nul; STARTUPINFOW si; PROCESS_INFORMATION pi; static WCHAR c[7000], b[7100]; Run *r;
    static WCHAR env[] = L"PYTHONUNBUFFERED"; (void)env;
    if (!CreatePipe(&rd, &wr, &sa, 1 << 16)) return 0;
    SetHandleInformation(rd, HANDLE_FLAG_INHERIT, 0);
    nul = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
    memset(&si, 0, sizeof si); si.cb = sizeof si; si.dwFlags = STARTF_USESTDHANDLES; si.hStdOutput = wr; si.hStdError = wr; si.hStdInput = nul;
    wcsncpy(c, cmd, 6999); c[6999] = 0; swprintf(b, 7100, L"> %ls", c); logw(b);
    SetEnvironmentVariableW(L"PYTHONUNBUFFERED", L"1"); SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8"); SetEnvironmentVariableW(L"PYTHONWARNINGS", L"ignore");
    if (!CreateProcessW(NULL, c, NULL, NULL, TRUE, CREATE_NO_WINDOW | CREATE_SUSPENDED, NULL, tool, &si, &pi)) {
        wcscpy(head, L"Python could not be started"); swprintf(sub, 400, L"Windows error %lu. Looked for %ls", GetLastError(), py); logw(sub);
        CloseHandle(rd); CloseHandle(wr); CloseHandle(nul); return 0;
    }
    if (hJob) AssignProcessToJobObject(hJob, pi.hProcess);
    ResumeThread(pi.hThread); CloseHandle(pi.hThread); CloseHandle(wr); CloseHandle(nul);
    r = (Run *)malloc(sizeof *r); r->rd = rd; r->proc = pi.hProcess;
    CloseHandle(CreateThread(NULL, 0, reader, r, 0, NULL));
    busy = 1; anim = 0; SetTimer(hMain, 1, 60, NULL); return 1;
}

static const WCHAR *leaf(const WCHAR *p) { const WCHAR *a = wcsrchr(p, L'\\'), *b = wcsrchr(p, L'/'); if (b > a) a = b; return a ? a + 1 : p; }
static void base_name(const WCHAR *p, WCHAR *out, int cap) { WCHAR *dot; wcsncpy(out, leaf(p), cap - 1); out[cap - 1] = 0; dot = wcsrchr(out, L'.'); if (dot) *dot = 0; }
static int exists(const WCHAR *p) { return GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES; }

/* the model made (again): every setting as sprite3d.py's switches, twelve pictures round it */
static void make(void) {
    static WCHAR cmd[6800]; WCHAR name[120]; int i, n;
    if (!sprite[0]) return;
    if (busy) { dirty = 1; return; }
    dirty = 0; problems = 0; gotViews = 0; drawnNote[0] = 0; drop_img(&imGone); objFile[0] = 0; facts[0] = 0; partsNote[0] = 0;
    base_name(sprite, name, 120);
    swprintf(outDir, MAX_PATH, L"%ls\\out\\%ls", tool, name);
    n = swprintf(cmd, 6800, L"\"%ls\" -u \"%ls\\sprite3d.py\" \"%ls\" --json --px 14 --out \"%ls\" --name \"%ls\" --method %hs --kind %hs --thickness %hs --sides %hs --outline %hs --turn %d --handle %hs --detail %d --mesh %hs",
                 py, tool, sprite, outDir, name, METHODV[selMethod], KINDV[selKind], THICK[selThick], SIDESV[selSides], OUTLV[selOutl], TURNV[selTurn], HANDLEV[selHandle], DETAILV[selDetail], POLYV[selPoly]);
    if (hasPaint && paintFile[0]) n += swprintf(cmd + n, 6800 - n, L" --paint \"%ls\"", paintFile);
    if (hasParts && selMethod == 0) n += swprintf(cmd + n, 6800 - n, L" --parts \"%ls\"", myParts);
    if (orig[0]) n += swprintf(cmd + n, 6800 - n, L" --original \"%ls\"", orig);
    for (i = 0; i < NV; i++) n += swprintf(cmd + n, 6800 - n, L" --view %d 0 \"%ls\\%ls_view_%03d.png\"", i * 360 / NV, outDir, name, i * 360 / NV);
    CreateDirectoryW(outDir, NULL);
    if (run(cmd)) { swprintf(head, 200, L"Making the model of %ls", leaf(sprite)); wcscpy(sub, L"The parts, the mesh and its check, then twelve pictures round it."); }
    redraw();
}
/* the sprite as shown: turned the way it is made (clockwise) */
static void load_sprite_img(void) {
    static const RotateFlipType rt[4] = { RotateNoneFlipNone, Rotate90FlipNone, Rotate180FlipNone, Rotate270FlipNone };
    drop_img(&imSprite); imSprite = load_img(sprite);
    if (imSprite && selTurn) GdipImageRotateFlip(imSprite, rt[selTurn]);
}
/* ---------- drawing on the sprite ---------- */
static int paint_read(const WCHAR *f) {          /* an earlier drawing of the same size into pv; 1 if one was read */
    GpImage *im; UINT w = 0, h = 0; int x, y, any = 0; ARGB c;
    if (!exists(f) || !(im = load_img(f))) return 0;
    GdipGetImageWidth(im, &w); GdipGetImageHeight(im, &h);
    if ((int)w == pw && (int)h == ph)
        for (y = 0; y < ph; y++) for (x = 0; x < pw; x++) {
            GdipBitmapGetPixel((GpBitmap *)im, x, y, &c);
            pv[y * pw + x] = (c >> 24) && sal[y * pw + x] ? (short)((((c >> 16) & 255) + ((c >> 8) & 255) + (c & 255)) / 3) : -1;
            any |= pv[y * pw + x] >= 0;
        }
    GdipDisposeImage(im); return any;
}
static void paint_reset(void) {
    GpImage *im = load_img(sprite); UINT w = 0, h = 0; int x, y; ARGB c; WCHAR nm[120], d[MAX_PATH], beside[MAX_PATH], *dot;
    free(pv); free(sal); free(pdone); pv = NULL; sal = pdone = NULL; pw = ph = 0; hasPaint = 0; paintFile[0] = 0;
    if (!im) return;
    GdipGetImageWidth(im, &w); GdipGetImageHeight(im, &h);
    if (w && h && w <= 1024 && h <= 1024) {
        pw = (int)w; ph = (int)h; pv = (short *)malloc(sizeof(short) * pw * ph); sal = (unsigned char *)malloc(pw * ph); pdone = (unsigned char *)calloc(pw * ph, 1);
        for (y = 0; y < ph; y++) for (x = 0; x < pw; x++) { GdipBitmapGetPixel((GpBitmap *)im, x, y, &c); sal[y * pw + x] = (c >> 24) != 0; pv[y * pw + x] = -1; }
    }
    GdipDisposeImage(im);
    if (!pw) return;
    base_name(sprite, nm, 120);
    swprintf(d, MAX_PATH, L"%ls\\out", tool); CreateDirectoryW(d, NULL); swprintf(d, MAX_PATH, L"%ls\\out\\%ls", tool, nm); CreateDirectoryW(d, NULL);
    swprintf(paintFile, MAX_PATH, L"%ls\\%ls_paint.png", d, nm);
    /* an earlier drawing: the one this window saved, else NAME_paint.png beside the sprite */
    wcsncpy(beside, sprite, MAX_PATH - 1); beside[MAX_PATH - 1] = 0; dot = wcsrchr(beside, L'.');
    if (dot && wcslen(beside) < MAX_PATH - 12) wcscpy(dot, L"_paint.png"); else beside[0] = 0;
    free(rg); rg = (short *)malloc(sizeof(short) * pw * ph); for (x = 0; x < pw * ph; x++) rg[x] = -1;
    nprt = 0; psel = 0; hasParts = 0;
    swprintf(myParts, MAX_PATH, L"%ls\\%ls_myparts.png", d, nm);
    if (selftest) { swprintf(paintFile, MAX_PATH, L"%ls.paint.png", stShot); swprintf(myParts, MAX_PATH, L"%ls.parts.png", stShot); return; }          /* (a test never reads or writes the real drawings) */
    /* the parts: the window's own from before, else NAME_parts.png beside the sprite; otherwise the guess comes from the tool */
    { WCHAR bp[MAX_PATH]; wcsncpy(bp, sprite, MAX_PATH - 1); bp[MAX_PATH - 1] = 0; dot = wcsrchr(bp, L'.');
      if (parts_read(myParts, 0)) hasParts = 1;
      else if (dot && wcslen(bp) < MAX_PATH - 12) { wcscpy(dot, L"_parts.png"); if (parts_read(bp, 0)) { hasParts = 1; parts_save(); } } }
    hasPaint = paint_read(paintFile) || (beside[0] && paint_read(beside));
}
static void paint_save(void) {
    GpBitmap *b = NULL; int x, y, v; CLSID png;
    if (!pw || !paintFile[0]) return;
    hasPaint = 0;
    GdipCreateBitmapFromScan0(pw, ph, 0, PixelFormat32bppARGB, NULL, &b);
    if (!b) return;
    for (y = 0; y < ph; y++) for (x = 0; x < pw; x++) {
        v = pv[y * pw + x];
        GdipBitmapSetPixel(b, x, y, v >= 0 ? 0xFF000000u | ((ARGB)v << 16) | ((ARGB)v << 8) | (ARGB)v : 0);
        hasPaint |= v >= 0;
    }
    CLSIDFromString(L"{557CF406-1A04-11D3-9A73-0000F81EF32E}", &png);
    GdipSaveImageToFile((GpImage *)b, paintFile, &png, NULL); GdipDisposeImage((GpImage *)b);
}
/* a pixel of the picture as shown (turned) -> the sprite file's own pixel */
static int to_file(int dx, int dy, int *fx, int *fy) {
    int dw = selTurn & 1 ? ph : pw, dh = selTurn & 1 ? pw : ph;
    if (dx < 0 || dy < 0 || dx >= dw || dy >= dh) return 0;
    switch (selTurn) {
    case 0: *fx = dx; *fy = dy; break;
    case 1: *fx = dy; *fy = ph - 1 - dx; break;
    case 2: *fx = pw - 1 - dx; *fy = ph - 1 - dy; break;
    default: *fx = pw - 1 - dy; *fy = dx; break;
    }
    return 1;
}
static void paint_at(int mx, int my) {          /* the brush, once a stroke on each pixel */
    int cx, cy, i, j, fx, fy, b = stroking == 2 ? 4 : brush, r0 = bsize == 2 ? -1 : 0, r1 = bsize == 0 ? 0 : 1, cur; short *p;
    if (!pv || canS <= 0 || mx < canX || my < canY) return;
    cx = (int)((mx - canX) / canS); cy = (int)((my - canY) / canS);
    if (paintMode == 2) {          /* the parts: the chosen part painted in; the right button picks the part under it */
        if (stroking == 2) { if (to_file(cx, cy, &fx, &fy) && rg[fy * pw + fx] >= 0) psel = rg[fy * pw + fx]; redraw(); return; }
        for (j = r0; j <= r1; j++) for (i = r0; i <= r1; i++)
            if (to_file(cx + i, cy + j, &fx, &fy) && sal[fy * pw + fx] && nprt) rg[fy * pw + fx] = (short)psel;
        redraw(); return;
    }
    for (j = r0; j <= r1; j++) for (i = r0; i <= r1; i++) {
        if (!to_file(cx + i, cy + j, &fx, &fy) || !sal[fy * pw + fx] || pdone[fy * pw + fx]) continue;
        pdone[fy * pw + fx] = 1; p = &pv[fy * pw + fx]; cur = *p < 8 ? 128 : *p;
        if (b == 0) *p = (short)(cur * 0.7 < 16 ? 16 : cur * 0.7);
        else if (b == 1) *p = (short)(cur * 1.4 + 1 > 255 ? 255 : cur * 1.4 + 1);
        else if (b == 2) *p = 0;
        else if (b == 3) *p = 128;
        else *p = -1;
    }
    redraw();
}
static void stroke_end(void) {
    if (!stroking) return;
    if (paintMode == 2) { int was = stroking; stroking = 0; ReleaseCapture(); if (was == 1) parts_changed(); return; }
    stroking = 0; ReleaseCapture(); if (pdone) memset(pdone, 0, pw * ph); paint_save(); make();
}
/* ---------- the parts ---------- */
static int label_index(const char *l) { int i; for (i = 0; i < 14; i++) if (!strcmp(LABELV[i], l)) return i; return 13; }
static int shape_index(const char *v) { int i; for (i = 0; i < 8; i++) if (!strcmp(SHAPEV[i], v)) return i; return 4; }
static int taper_index(const char *v) { int i; for (i = 0; i < 5; i++) if (!strcmp(TAPERV[i], v)) return i; return 0; }
static void part_default(Part *p, int li, const int *col) {
    memset(p, 0, sizeof *p); p->col[0] = col[0]; p->col[1] = col[1]; p->col[2] = col[2];
    strcpy(p->label, LABELV[li]); strcpy(p->shape, LSHAPE[li]); strcpy(p->taper, "none");
    p->depth = LDEPTH[li]; p->bevel = LBEVEL[li]; p->offset = 0; p->tamount = 0;
    p->sides = (!strcmp(p->shape, "lathe") || !strcmp(p->shape, "ball")) ? 8 : 6;
}
static void part_from_line(Part *p, const WCHAR *l) {
    WCHAR v[40]; const WCHAR *c = wcsstr(l, L"\"colour\": [");
    static const int none[3] = { 0, 0, 255 };
    part_default(p, 13, none);
    if (c) { WCHAR *e; c += 11; p->col[0] = (int)wcstol(c, &e, 10); c = e + 1; p->col[1] = (int)wcstol(c, &e, 10); c = e + 1; p->col[2] = (int)wcstol(c, &e, 10); }
    if (jstr(l, L"label", v, 40)) snprintf(p->label, 16, "%ls", v);
    if (jstr(l, L"shape", v, 40)) snprintf(p->shape, 12, "%ls", v);
    if (jstr(l, L"taper", v, 40)) snprintf(p->taper, 8, "%ls", v);
    if (jfind(l, L"depth")) p->depth = jnum(l, L"depth");
    if (jfind(l, L"offset")) p->offset = jnum(l, L"offset");
    if (jfind(l, L"taper_amount")) p->tamount = jnum(l, L"taper_amount");
    if (jfind(l, L"bevel")) p->bevel = jnum(l, L"bevel");
    if (jfind(l, L"sides")) p->sides = (int)jnum(l, L"sides");
}
/* a parts picture (and its .txt; the six old colours without one) into rg and prt. turned: the picture is as the
   model is made (Python's own, after --turn); else in the sprite file's orientation. Parts with no pixel are left out */
static int parts_read(const WCHAR *png, int turned) {
    GpImage *im; UINT w = 0, h = 0; int x, y, k, j, dw, dh, fx, fy, nn = 0, cnt[MAXP], map[MAXP]; ARGB c; WCHAR tp[MAX_PATH], *dot; FILE *f; char line[1200];
    static Part np[MAXP];
    static const int old[6][3] = { {0,0,255}, {0,255,0}, {255,255,0}, {0,255,255}, {255,128,0}, {255,0,255} };
    if (!pv || !rg || !exists(png) || !(im = load_img(png))) return 0;
    wcsncpy(tp, png, MAX_PATH - 1); tp[MAX_PATH - 1] = 0; dot = wcsrchr(tp, L'.'); if (dot) wcscpy(dot, L".txt");
    f = _wfopen(tp, L"r");
    if (f) {
        while (nn < MAXP && fgets(line, sizeof line, f)) { WCHAR wl[1200]; if (!strchr(line, '{')) continue; MultiByteToWideChar(CP_UTF8, 0, line, -1, wl, 1200); part_from_line(&np[nn++], wl); }
        fclose(f);
    } else for (k = 0; k < 6; k++) part_default(&np[nn++], k, old[k]);
    GdipGetImageWidth(im, &w); GdipGetImageHeight(im, &h);
    dw = selTurn & 1 ? ph : pw; dh = selTurn & 1 ? pw : ph;
    if (turned ? ((int)w != dw || (int)h != dh) : ((int)w != pw || (int)h != ph)) { GdipDisposeImage(im); return 0; }
    for (k = 0; k < pw * ph; k++) rg[k] = -1;
    memset(cnt, 0, sizeof cnt);
    for (y = 0; y < (int)h; y++) for (x = 0; x < (int)w; x++) {
        GdipBitmapGetPixel((GpBitmap *)im, x, y, &c);
        if (!(c >> 24)) continue;
        if (turned) { if (!to_file(x, y, &fx, &fy)) continue; } else { fx = x; fy = y; }
        if (!sal[fy * pw + fx]) continue;
        for (k = 0; k < nn; k++) if (np[k].col[0] == (int)((c >> 16) & 255) && np[k].col[1] == (int)((c >> 8) & 255) && np[k].col[2] == (int)(c & 255)) { rg[fy * pw + fx] = (short)k; cnt[k]++; break; }
    }
    GdipDisposeImage(im);
    for (k = 0, j = 0; k < nn; k++) { map[k] = cnt[k] ? j : -1; if (cnt[k]) prt[j++] = np[k]; }
    if (!j) return 0;
    for (k = 0; k < pw * ph; k++) if (rg[k] >= 0) rg[k] = (short)map[rg[k]];
    nprt = j; if (psel >= nprt) psel = 0;
    return 1;
}
static void parts_save(void) {
    GpBitmap *b = NULL; int x, y, k; CLSID png; WCHAR t[MAX_PATH], *dot; FILE *f;
    if (!pw || !rg || !myParts[0] || !nprt) return;
    GdipCreateBitmapFromScan0(pw, ph, 0, PixelFormat32bppARGB, NULL, &b);
    if (!b) return;
    for (y = 0; y < ph; y++) for (x = 0; x < pw; x++) {
        k = rg[y * pw + x];
        GdipBitmapSetPixel(b, x, y, k >= 0 && k < nprt ? 0xFF000000u | ((ARGB)prt[k].col[0] << 16) | ((ARGB)prt[k].col[1] << 8) | (ARGB)prt[k].col[2] : 0);
    }
    CLSIDFromString(L"{557CF406-1A04-11D3-9A73-0000F81EF32E}", &png);
    GdipSaveImageToFile((GpImage *)b, myParts, &png, NULL); GdipDisposeImage((GpImage *)b);
    wcscpy(t, myParts); dot = wcsrchr(t, L'.'); if (dot) wcscpy(dot, L".txt");
    f = _wfopen(t, L"w");
    if (f) {
        for (k = 0; k < nprt; k++) fprintf(f, "{\"colour\": [%d, %d, %d], \"label\": \"%s\", \"shape\": \"%s\", \"depth\": %g, \"offset\": %g, \"taper\": \"%s\", \"taper_amount\": %g, \"bevel\": %g, \"sides\": %d}\n",
                                           prt[k].col[0], prt[k].col[1], prt[k].col[2], prt[k].label, prt[k].shape, prt[k].depth, prt[k].offset, prt[k].taper, prt[k].tamount, prt[k].bevel, prt[k].sides);
        fclose(f);
    }
    hasParts = 1;
}
static void part_new(void) {
    int c, k, used;
    if (nprt >= MAXP) return;
    for (c = 0; c < 16; c++) { used = 0; for (k = 0; k < nprt; k++) used |= prt[k].col[0] == PAL[c][0] && prt[k].col[1] == PAL[c][1] && prt[k].col[2] == PAL[c][2]; if (!used) break; }
    part_default(&prt[nprt], 13, PAL[c < 16 ? c : 0]); psel = nprt++;
}
static void part_delete(void) {
    int k;
    if (nprt <= 1) return;
    for (k = 0; k < pw * ph; k++) { if (rg[k] == psel) rg[k] = -1; else if (rg[k] > psel) rg[k]--; }
    memmove(&prt[psel], &prt[psel + 1], (nprt - psel - 1) * sizeof(Part)); nprt--;
    if (psel >= nprt) psel = nprt - 1;
}
static void parts_changed(void) { parts_save(); make(); }

static void set_sprite(const WCHAR *p) {
    WCHAR guess[MAX_PATH], nm[120]; int i;
    wcsncpy(sprite, p, MAX_PATH - 1); load_sprite_img(); paint_reset();
    if (selftest == 2 && pv) {          /* the self-test's drawing: the lower third thinner, the top row cut away */
        int x, y, top = -1;
        for (y = 0; y < ph && top < 0; y++) for (x = 0; x < pw; x++) if (sal[y * pw + x]) { top = y; break; }
        for (y = 0; y < ph; y++) for (x = 0; x < pw; x++) if (sal[y * pw + x]) { if (y >= ph * 2 / 3) pv[y * pw + x] = 64; else if (y == top) pv[y * pw + x] = 0; }
        paint_save(); paintMode = 1;
    }
    for (i = 0; i < NV; i++) drop_img(&views[i]);
    drop_img(&imParts); curView = 0; madeOnce = 0;
    parts[0] = 0;                                   /* a parts picture beside the sprite (NAME_parts.png) is taken by itself */
    wcsncpy(guess, sprite, MAX_PATH - 1); { WCHAR *dot = wcsrchr(guess, L'.'); if (dot && wcslen(guess) < MAX_PATH - 12) { wcscpy(dot, L"_parts.png"); if (exists(guess)) wcscpy(parts, guess); } }
    base_name(sprite, nm, 120);
    if (!imSprite) { wcscpy(head, L"That picture could not be opened"); swprintf(sub, 400, L"%ls", sprite); redraw(); return; }
    make();
}
static void on_line(const WCHAR *t) {
    WCHAR ev[24], path[MAX_PATH]; int i;
    if (t[0] != L'{' || !jstr(t, L"ev", ev, 24)) { if (t[0]) logw(t); return; }          /* not a record: something Python itself said (an error); kept for Details */
    logw(t);
    if (!wcscmp(ev, L"error")) { jstr(t, L"text", sub, 400); wcscpy(head, L"That did not work"); problems = 1; redraw(); return; }
    if (!wcscmp(ev, L"parts")) {
        WCHAR k[48]; jstr(t, L"kind", k, 48);
        if (!wcsncmp(k, L"guessed as ", 11)) memmove(k, k + 11, (wcslen(k + 11) + 1) * sizeof(WCHAR));
        if (jstr(t, L"img", path, MAX_PATH)) {
            drop_img(&imParts); imParts = load_img(path);
            if (!hasParts && selMethod == 0) { parts_read(path, 1); if (saveGuess) { saveGuess = 0; parts_save(); } }
        }
        if (jtrue(t, L"guessed")) swprintf(partsNote, 120, L"guessed as %ls", k[0] ? k : L"?"); else wcscpy(partsNote, L"from your parts picture");
        redraw(); return;
    }
    if (!wcscmp(ev, L"mesh")) {
        WCHAR pr[200]; jstr(t, L"problem", pr, 200); problems = (int)jnum(t, L"nproblems");
        if ((int)jnum(t, L"pixels") == 0)
            swprintf(facts, 300, L"%d triangles (low poly)   |   %.0f wide, %.0f tall, %.1f thick (sprite pixels)   |   %ls", (int)jnum(t, L"faces"),
                     jnum(t, L"wide"), jnum(t, L"tall"), jnum(t, L"thick"), problems ? pr : L"every part closed: sound");
        else swprintf(facts, 300, L"%d faces from %d pixels   |   %.0f wide, %.0f tall, %.1f thick (sprite pixels)   |   %ls", (int)jnum(t, L"faces"), (int)jnum(t, L"pixels"),
                 jnum(t, L"wide"), jnum(t, L"tall"), jnum(t, L"thick"), problems ? pr : L"closed all round: sound");
        redraw(); return;
    }
    if (!wcscmp(ev, L"paint")) {
        drop_img(&imGone); if (jstr(t, L"img", path, MAX_PATH)) imGone = load_img(path);
        swprintf(drawnNote, 200, L"%d cut away (%d of them handle outline), %d thinner, %d thicker", (int)jnum(t, L"cut") + (int)jnum(t, L"trimmed"), (int)jnum(t, L"trimmed"), (int)jnum(t, L"thinner"), (int)jnum(t, L"thicker"));
        return;
    }
    if (!wcscmp(ev, L"obj")) { jstr(t, L"file", objFile, MAX_PATH); return; }
    if (!wcscmp(ev, L"view")) {
        i = ((int)(jnum(t, L"yaw") * NV / 360.0 + 0.5)) % NV;
        if (jstr(t, L"img", path, MAX_PATH)) { drop_img(&views[i]); views[i] = load_img(path); gotViews++; }
        swprintf(head, 200, L"Making the model: picture %d of %d", gotViews, NV); redraw(); return;
    }
}
static void capture(const WCHAR *path);
static void on_ended(DWORD code) {
    busy = 0; KillTimer(hMain, 1);
    if (dirty) { make(); return; }                  /* something was changed while it ran: once more, with what is set now */
    if (gotViews) {
        madeOnce = 1;
        if (problems) { wcscpy(head, L"Made, but the check found a problem"); wcscpy(sub, L"See the line under the model, or press Details."); }
        else { wcscpy(head, L"The model is ready"); wcscpy(sub, L"Drag it sideways or use the arrow keys to turn it. Change anything on the left and it is made again. Open folder shows the files."); }
    } else if (wcscmp(head, L"That did not work")) { wcscpy(head, L"No model came back"); swprintf(sub, 400, L"Python ended with code %lu. Press Details to see what it said.", code); }
    redraw();
    if (selftest == 3 && stStage == 0 && nprt) {          /* the parts test: the first part deeper and thinning down, a new gem part in the middle */
        int x, y, cx = pw / 2, cy = ph / 3;
        stStage = 1; paintMode = 2;
        prt[0].depth = 1.5; strcpy(prt[0].taper, "down"); prt[0].tamount = 0.5;
        part_new(); { int col[3]; memcpy(col, prt[psel].col, sizeof col); part_default(&prt[psel], 5, col); }
        for (y = cy - 1; y <= cy + 1; y++) for (x = cx - 1; x <= cx + 1; x++) if (x >= 0 && y >= 0 && x < pw && y < ph && sal[y * pw + x]) rg[y * pw + x] = (short)psel;
        parts_changed(); return;
    }
    if (selftest) {
        WCHAR q[MAX_PATH]; FILE *f; int i, n = 0;
        for (i = 0; i < NV; i++) n += views[i] != NULL;
        hovK = H_NONE; curView = 2; capture(stShot);
        showHelp = 1; swprintf(q, MAX_PATH, L"%ls.help.bmp", stShot); capture(q);
        swprintf(q, MAX_PATH, L"%ls.txt", stShot); f = _wfopen(q, L"w");
        if (f) { fprintf(f, "exit_code %lu\nviews %d\nproblems %d\nsprite_shown %d\nparts_shown %d\nobj %ls\nobj_there %d\nfacts %ls\npainted %d\npaint_file_there %d\ndrawn %ls\nparts %d\nparts_yours %d\n", code, n, problems, imSprite != NULL, imParts != NULL, objFile, exists(objFile), facts,
                       hasPaint, exists(paintFile), drawnNote, nprt, hasParts);
                 for (i = 0; i < nprt; i++) fprintf(f, "part %d %s %s depth %g taper %s %g\n", i + 1, prt[i].label, prt[i].shape, prt[i].depth, prt[i].taper, prt[i].tamount);
                 fclose(f); }
        PostQuitMessage(0);
    }
}

/* ---------- drawing ---------- */
static GpGraphics *G; static HDC DC;
static void rr(double x, double y, double w, double h, double r, ARGB fill, ARGB line, double lw) {
    GpPath *p; double d = r * 2;
    if (d > w) d = w;
    if (d > h) d = h;
    GdipCreatePath(FillModeAlternate, &p);
    GdipAddPathArc(p, (REAL)x, (REAL)y, (REAL)d, (REAL)d, 180, 90); GdipAddPathArc(p, (REAL)(x + w - d), (REAL)y, (REAL)d, (REAL)d, 270, 90);
    GdipAddPathArc(p, (REAL)(x + w - d), (REAL)(y + h - d), (REAL)d, (REAL)d, 0, 90); GdipAddPathArc(p, (REAL)x, (REAL)(y + h - d), (REAL)d, (REAL)d, 90, 90); GdipClosePathFigure(p);
    if (fill) { GpSolidFill *b; GdipCreateSolidFill(fill, &b); GdipFillPath(G, (GpBrush *)b, p); GdipDeleteBrush((GpBrush *)b); }
    if (line) { GpPen *pn; GdipCreatePen1(line, (REAL)lw, UnitPixel, &pn); GdipDrawPath(G, pn, p); GdipDeletePen(pn); }
    GdipDeletePath(p);
}
static void fillrect(int x, int y, int w, int h, ARGB c) { GpSolidFill *b; GdipCreateSolidFill(c, &b); GdipFillRectangleI(G, (GpBrush *)b, x, y, w, h); GdipDeleteBrush((GpBrush *)b); }
static void txt(const WCHAR *s, int x, int y, int w, int h, HFONT f, ARGB c, UINT fl) {
    RECT r = { x, y, x + w, y + h }; GdipFlush(G, FlushIntentionSync);
    SelectObject(DC, f); SetTextColor(DC, RGB((c >> 16) & 255, (c >> 8) & 255, c & 255)); DrawTextW(DC, s, -1, &r, fl | DT_NOPREFIX);
}
static void txta(const char *s, int x, int y, int w, int h, HFONT f, ARGB c, UINT fl) { WCHAR b[200]; swprintf(b, 200, L"%hs", s); txt(b, x, y, w, h, f, c, fl); }
static void hit(int x, int y, int w, int h, int kind, int idx) { if (nhit < 240) { SetRect(&hits[nhit].r, x, y, x + w, y + h); hits[nhit].kind = kind; hits[nhit].idx = idx; nhit++; } }
static int hov(int kind, int idx) { return hovK == kind && hovI == idx; }
static void chip(const char *label, int x, int y, int w, int h, int on, int kind, int idx) {
    rr(x, y, w, h, S(6), on ? C_ACC : hov(kind, idx) ? C_CARDH : C_CARD, on ? 0 : C_LINE, 1);
    txta(label, x, y, w, h, fUI, on ? C_ONACC : C_TEXT, DT_CENTER | DT_VCENTER | DT_SINGLELINE); hit(x, y, w, h, kind, idx);
}
static void chips(const WCHAR *label, const char **items, int n, int cols, int sel, int kind, int *y) {
    int x0 = S(16), wAll = S(SIDE_W - 32), gap = S(4), ch = S(26), cw = (wAll - (cols - 1) * gap) / cols, i;
    txt(label, x0, *y, wAll, S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE); *y += S(20);
    for (i = 0; i < n; i++) chip(items[i], x0 + (i % cols) * (cw + gap), *y + (i / cols) * (ch + gap), cw, ch, i == sel, kind, i);
    *y += ((n + cols - 1) / cols) * (ch + gap) + S(8);
}
/* style: 0 quiet, 1 the main button (teal), 2 gold outline */
static void button(const WCHAR *label, int x, int y, int w, int h, int style, int kind, int idx) {
    int hv = hov(kind, idx);
    if (style == 1) rr(x, y, w, h, S(8), hv ? C_ACCH : C_ACC, 0, 0);
    else if (style == 2) rr(x, y, w, h, S(8), hv ? C_CARDH : C_CARD, C_GOLD, S(2));
    else rr(x, y, w, h, S(8), hv ? C_CARDH : C_CARD, C_LINE, 1);
    txt(label, x, y, w, h, style == 1 ? fBtn : fUI, style == 1 ? C_ONACC : style == 2 ? C_GOLD : C_TEXT, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS);
    hit(x, y, w, h, kind, idx);
}
/* a picture fitted into a box; crisp: each of its pixels a whole block (pixel art is never smoothed) */
static void image_fit(GpImage *im, double x, double y, double w, double h) {
    UINT iw = 1, ih = 1; double s, dw, dh; GdipGetImageWidth(im, &iw); GdipGetImageHeight(im, &ih);
    s = w / iw < h / ih ? w / iw : h / ih;
    if (s > 1) s = floor(s);
    dw = iw * s; dh = ih * s; GdipDrawImageRect(G, im, (REAL)floor(x + (w - dw) / 2), (REAL)floor(y + (h - dh) / 2), (REAL)dw, (REAL)dh);
}
static void thumb(const WCHAR *label, const WCHAR *note, GpImage *im, int x, int y, int w, int h) {
    rr(x, y, w, h, S(10), C_CARD, C_LINE, 1);
    txt(label, x + S(10), y + S(6), w - S(20), S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE);
    if (im) image_fit(im, x + S(10), y + S(28), w - S(20), h - S(28) - (note && note[0] ? S(26) : S(10)));
    else txt(L"none", x, y + S(28), w, h - S(38), fSmall, 0xFF5F6775u, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    if (note && note[0]) txt(note, x + S(8), y + h - S(24), w - S(16), S(18), fSmall, C_DIM, DT_CENTER | DT_SINGLELINE | DT_END_ELLIPSIS);
}
static const WCHAR *HELP[] = {
    L"What this makes", L"A 3D model (.obj with its texture) from one flat sprite. Every face keeps one sprite pixel's own colour: nothing is blended, no colour is added.",
    L"The sprite", L"A PNG with a clear background, the object standing upright: tip up, grip down. Open it with the button or Ctrl+O, or drop the file on the window.",
    L"Depth: Shaped", L"By part (Sprite is: what the parts guess takes it for). A blade becomes a ridge, a shaft or grip round, an axe or mace head a plate with a bevelled edge, a guard a block, a gem a dome.",
    L"Depth: Flat / Round / Turned", L"Flat: a plate, every pixel the same thickness. Round: thicker toward the middle, like a pillow. Turned: every row a circle as wide as the row, as if made on a lathe; for bottles, candles, goblets, gems and wands.",
    L"The parts picture", L"The guess is saved as NAME_parts.png + NAME_parts.txt; a parts picture made elsewhere (its colours, and a .txt saying what each is) is opened with Parts picture.",
    L"Thickness", L"The greatest half-thickness, in sprite pixels. 1.5 gives a model about 3 pixels thick at its thickest. A blade is never more than 60% of the handle's thickness and an axe or mace head 85%, as on a real weapon.",
    L"Outline", L"What becomes of the sprite's dark outline. Sharp: it is not drawn; it takes the colour beside it and the shape runs down to a sharp edge, so blades are sharp and handles round. Seam: kept as a thin dark rim round the model. Wrapped: it follows the shape up its sides. With Seam or Wrapped, Edge colour picks the sides' colour.",
    L"Turn the sprite", L"Turns the sprite clockwise before the model is made, for a sprite drawn lying down or upside down: the model is built tip up, grip down. A parts picture is turned the same way.",
    L"Handle width", L"Coloured middle: a shaft or grip is as wide as its coloured pixels, as the handle looks in the sprite; its dark outline is left off the model. With outline: as wide as colour and outline together (thicker). Only with the Sharp outline.",
    L"Polygons", L"Few (the default): each part one simple shape, a handle a six-sided prism of 20 triangles, a blade a diamond section, a head or guard a bevelled plate with a sharp edge; a whole weapon about 100 to 200 triangles. The colours come from the texture (the sprite, enlarged smooth, laid on front and back; nearest pixel). Many: a block of model for every pixel, thousands of faces; then Detail (1x to 8x) sets how fine.",
    L"Draw on it", L"Paint pixels thinner (blue) or thicker (gold), cut them away, keep them, or back to as made (right button). Saved as out\\NAME\\NAME_paint.png.",
    L"Edit parts", L"Split the sprite into parts and say what each is: paint pixels into the chosen part; the right button picks a part. Each part has a label (Blade, Handle, Gem...), a shape (Round bar, Lathe, Ball, Blade, Plate, Box, Dome, Card) and its own depth, toward you / away, bevel, sides and taper. Guess again starts over. Saved as out\\NAME\\NAME_myparts.png + .txt.",
    L"Turning it", L"Drag the model sideways, click its left or right half, or use the Left and Right arrow keys. Twelve views, 30 degrees apart.",
    L"The files", L"Open folder shows them: NAME.obj, NAME.mtl and NAME_tex.png (the model), NAME_parts.png, NAME_sheet.png. Every model is checked closed (each edge shared by two faces); the line under the model says so.",
    L"Keys", L"Ctrl+O open.  Left / Right turn.  Enter make again.  D details (what Python said).  ? or F1 this page.  Esc closes it." };

static void paint(HDC out, int W, int H) {
    HBITMAP bm, obm; int y, i, mx, mw, vy, vh, tw, vw, x; WCHAR b[400];
    DC = CreateCompatibleDC(out); bm = CreateCompatibleBitmap(out, W, H); obm = (HBITMAP)SelectObject(DC, bm); SetBkMode(DC, TRANSPARENT);
    GdipCreateFromHDC(DC, &G); GdipSetSmoothingMode(G, SmoothingModeAntiAlias); GdipSetInterpolationMode(G, InterpolationModeNearestNeighbor); GdipSetPixelOffsetMode(G, PixelOffsetModeHalf);
    nhit = 0;
    fillrect(0, 0, W, H, C_BG); fillrect(0, 0, S(SIDE_W), H, C_SIDE); fillrect(S(SIDE_W), 0, 1, H, C_LINE);
    /* ---- the left: what to make ---- */
    txt(L"Sprite to 3D", S(16), S(14), S(SIDE_W - 32), S(30), fTitle, C_TEXT, DT_LEFT | DT_SINGLELINE);
    txt(L"a 3D model from a flat picture", S(16), S(44), S(SIDE_W - 32), S(18), fSmall, C_DIM, DT_LEFT | DT_SINGLELINE);
    y = S(78);
    button(sprite[0] ? L"Open another sprite..." : L"Open a sprite...", S(16), y, S(SIDE_W - 32), S(34), sprite[0] ? 0 : 1, H_OPEN, 0); y += S(38);
    txt(sprite[0] ? leaf(sprite) : L"a PNG with a clear background; or drop one here", S(16), y, S(SIDE_W - 32), S(18), fSmall, sprite[0] ? C_ACC : C_DIM, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS); y += S(28);
    chips(L"Depth", METHODL, 4, 4, selMethod, H_METHOD, &y);
    if (selMethod == 0) chips(L"Sprite is (for the parts guess)", KINDL, 4, 4, selKind, H_KIND, &y);
    chips(L"Thickness (sprite pixels)", THICK, 6, 6, selThick, H_THICK, &y);
    chips(L"Outline", OUTLL, 3, 3, selOutl, H_OUTL, &y);
    chips(L"Turn the sprite (degrees, clockwise)", TURNL, 4, 4, selTurn, H_TURN, &y);
    chips(L"Handle width", HANDLEL, 2, 2, selHandle, H_HANDLE, &y);
    chips(L"Polygons", POLYL, 2, 2, selPoly, H_POLY, &y);
    if (selPoly == 1) chips(L"Detail (finer than the sprite's pixels)", DETAILL, 4, 4, selDetail, H_DETAIL, &y);
    if (selOutl != 0) chips(L"Edge colour", SIDESL, 2, 2, selSides, H_SIDES, &y);          /* (with Sharp the outline takes the colour beside it anyway) */
    txt(L"Optional pictures", S(16), y, S(SIDE_W - 32), S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE); y += S(20);
    tw = (S(SIDE_W - 32) - S(4)) / 2;
    button(hasParts ? L"Parts: guess again" : L"Parts picture...", S(16), y, tw, S(28), 0, hasParts ? H_PARTSX : H_PARTS, 0);
    button(orig[0] ? L"Original: clear" : L"Original...", S(16) + tw + S(4), y, tw, S(28), 0, orig[0] ? H_ORIGX : H_ORIG, 0); y += S(32);
    txt(hasParts ? L"parts: yours (Edit parts)" : L"parts: guessed", S(16), y, tw, S(18), fSmall, hasParts ? C_ACC : C_DIM, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    txt(orig[0] ? leaf(orig) : L"original: none", S(16) + tw + S(4), y, tw, S(18), fSmall, orig[0] ? C_ACC : C_DIM, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    y = H - S(96);
    button(L"Make it again", S(16), y, S(SIDE_W - 32), S(36), sprite[0] && !busy ? 1 : 0, H_GO, 0); y += S(44);
    tw = (S(SIDE_W - 32) - S(8)) / 3;
    button(L"Open folder", S(16), y, tw, S(30), madeOnce ? 2 : 0, H_FOLDER, 0); button(L"Details", S(16) + tw + S(4), y, tw, S(30), 0, H_DETAILS, 0); button(L"Help", S(16) + 2 * (tw + S(4)), y, tw, S(30), 0, H_HELP, 0);
    /* ---- the head: what is happening ---- */
    mx = S(SIDE_W) + S(20); mw = W - mx - S(20);
    txt(head, mx, S(12), mw, S(30), fBig, C_TEXT, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    txt(sub, mx, S(42), mw, S(20), fUI, C_DIM, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    fillrect(S(SIDE_W) + 1, S(HEAD_H) - 2, W - S(SIDE_W), 2, C_LINE);
    if (busy) fillrect(S(SIDE_W) + 1, S(HEAD_H) - 2, (int)((W - S(SIDE_W)) * (gotViews + 1.0) / (NV + 1.0)), 2, C_ACC);
    /* ---- the middle: the model, and what it was made from ---- */
    vy = S(HEAD_H) + S(16); vh = H - vy - S(FOOT_H) - S(8); tw = S(190); vw = mw - tw - S(16);
    if (vw < S(120) || paintMode == 2) vw = mw, tw = 0;
    rr(mx, vy, vw, vh, S(12), C_CARD, dragging ? C_ACC : paintMode ? C_GOLD : C_LINE, dragging || paintMode ? S(2) : 1);
    if (paintMode == 2 && pv && imSprite && rg) {          /* the parts: the sprite large in its parts' colours, the chosen part's settings beside it */
        int dw = selTurn & 1 ? ph : pw, dh = selTurn & 1 ? pw : ph, PW = S(340), ax, ay, px, py, fx, fy, k, sx0, sy, cw4, ch = S(24), g = S(3);
        WCHAR b2[120];
        ax = vw - PW - S(40); ay = vh - S(100);
        canS = floor(ax / (double)dw < ay / (double)dh ? ax / (double)dw : ay / (double)dh); if (canS < 1) canS = 1;
        canW = (int)(dw * canS); canH = (int)(dh * canS); canX = mx + S(14) + (ax - canW) / 2; canY = vy + S(44) + (ay - canH) / 2;
        txt(L"Parts: paint pixels into the chosen part (left button); the right button picks the part under it. Choose what each part is and its shape on the right.",
            mx + S(14), vy + S(10), vw - S(28), S(20), fUI, C_GOLD, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
        fillrect(canX, canY, canW, canH, 0xFF101216u);
        GdipDrawImageRect(G, imSprite, (REAL)canX, (REAL)canY, (REAL)canW, (REAL)canH);
        for (py = 0; py < dh; py++) for (px = 0; px < dw; px++) {
            int x0 = canX + (int)(px * canS), y0 = canY + (int)(py * canS), sz = (int)canS;
            if (!to_file(px, py, &fx, &fy) || !sal[fy * pw + fx]) continue;
            k = rg[fy * pw + fx];
            if (k < 0 || k >= nprt) continue;
            fillrect(x0, y0, sz, sz, ((ARGB)(k == psel ? 150 : 60) << 24) | ((ARGB)prt[k].col[0] << 16) | ((ARGB)prt[k].col[1] << 8) | (ARGB)prt[k].col[2]);
            if (k == psel && sz >= 6) rr(x0 + 1, y0 + 1, sz - 2, sz - 2, 1, 0, 0xC0FFFFFFu, 1);
        }
        if (canS >= 6) { for (px = 0; px <= dw; px++) fillrect(canX + (int)(px * canS), canY, 1, canH, 0x28FFFFFFu); for (py = 0; py <= dh; py++) fillrect(canX, canY + (int)(py * canS), canW, 1, 0x28FFFFFFu); }
        hit(canX, canY, canW, canH, H_CANVAS, 0);
        txt(L"size", mx + S(14), vy + vh - S(44), S(34), S(32), fSmall, C_DIM, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
        for (i = 0; i < 3; i++) chip(BSIZEL[i], mx + S(48) + i * S(36), vy + vh - S(44), S(32), S(32), bsize == i, H_BSIZE, i);
        button(L"See the model", mx + S(14) + ax - S(120), vy + vh - S(44), S(120), S(32), 2, H_PMODE, 0);
        /* the panel: the parts, then the chosen part's settings */
        sx0 = mx + vw - PW - S(12); sy = vy + S(40); cw4 = (PW - 3 * g) / 4;
        fillrect(sx0 - S(10), vy + S(36), 1, vh - S(48), C_LINE);
        txt(L"Parts", sx0, sy, PW, S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE); sy += S(18);
        for (k = 0; k < nprt; k++) {
            int cx0 = sx0 + (k % 3) * ((PW - 2 * g) / 3 + g), cy0 = sy + (k / 3) * (ch + g), w3 = (PW - 2 * g) / 3;
            snprintf((char *)b2, 60, "%d %s", k + 1, prt[k].label);
            chip((const char *)b2, cx0, cy0, w3, ch, k == psel, H_PREG, k);
            fillrect(cx0 + S(5), cy0 + ch / 2 - S(5), S(10), S(10), 0xFF000000u | ((ARGB)prt[k].col[0] << 16) | ((ARGB)prt[k].col[1] << 8) | (ARGB)prt[k].col[2]);
        }
        sy += ((nprt + 2) / 3) * (ch + g) + S(4);
        { int w3 = (PW - 2 * g) / 3;
          button(L"+ New part", sx0, sy, w3, ch, 0, H_PNEW, 0); button(L"Delete part", sx0 + w3 + g, sy, w3, ch, 0, H_PDEL, 0); button(L"Guess again", sx0 + 2 * (w3 + g), sy, w3, ch, 0, H_PGUESS, 0); }
        sy += ch + S(8);
        if (nprt) {
            Part *pp = &prt[psel]; int li = label_index(pp->label), si = shape_index(pp->shape), ti = taper_index(pp->taper);
            static const char *SN[5] = { "Depth (times its own)", "Toward you / away (pixels)", "Bevel (pixels)", "Sides (round shapes)", "Taper amount" };
            double vals[5]; vals[0] = pp->depth; vals[1] = pp->offset; vals[2] = pp->bevel; vals[3] = pp->sides; vals[4] = pp->tamount;
            txt(L"What it is", sx0, sy, PW, S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE); sy += S(18);
            for (k = 0; k < 14; k++) chip(LABELL[k], sx0 + (k % 4) * (cw4 + g), sy + (k / 4) * (ch + g), cw4, ch, k == li, H_PLABEL, k);
            sy += 4 * (ch + g) + S(4);
            txt(L"Shape", sx0, sy, PW, S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE); sy += S(18);
            for (k = 0; k < 8; k++) chip(SHAPEL[k], sx0 + (k % 4) * (cw4 + g), sy + (k / 4) * (ch + g), cw4, ch, k == si, H_PSHAPE, k);
            sy += 2 * (ch + g) + S(4);
            txt(L"Thins toward", sx0, sy, PW, S(18), fLabel, C_DIM, DT_LEFT | DT_SINGLELINE); sy += S(18);
            { int w5 = (PW - 4 * g) / 5; for (k = 0; k < 5; k++) chip(TAPERL[k], sx0 + k * (w5 + g), sy, w5, ch, k == ti, H_PTAPER, k); }
            sy += ch + S(6);
            for (k = 0; k < 5; k++) {
                WCHAR vs[32];
                if (k == 3) swprintf(vs, 32, L"%d", pp->sides); else swprintf(vs, 32, L"%.2f", vals[k]);
                txta(SN[k], sx0, sy, PW - S(130), ch, fSmall, C_DIM, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                button(L"-", sx0 + PW - S(124), sy, S(34), ch, 0, H_PSTEP, k * 2);
                txt(vs, sx0 + PW - S(88), sy, S(52), ch, fUI, C_TEXT, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
                button(L"+", sx0 + PW - S(34), sy, S(34), ch, 0, H_PSTEP, k * 2 + 1);
                sy += ch + g;
            }
        }
    } else if (paintMode == 1 && pv && imSprite) {          /* drawing on the sprite: the sprite large, what is drawn over it */
        int dw = selTurn & 1 ? ph : pw, dh = selTurn & 1 ? pw : ph, ax = vw - S(24), ay = vh - S(144), px, py, fx, fy, v, bw, gx;
        canS = floor(ax / (double)dw < ay / (double)dh ? ax / (double)dw : ay / (double)dh); if (canS < 1) canS = 1;
        canW = (int)(dw * canS); canH = (int)(dh * canS); canX = mx + (vw - canW) / 2; canY = vy + S(44) + (ay - canH) / 2;
        txt(L"Draw on the sprite: left button paints with the brush below, right button puts a pixel back as made. The model is made again when you let go.",
            mx + S(14), vy + S(10), vw - S(28), S(20), fUI, C_GOLD, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
        fillrect(canX, canY, canW, canH, 0xFF101216u);
        GdipDrawImageRect(G, imSprite, (REAL)canX, (REAL)canY, (REAL)canW, (REAL)canH);
        if (imGone) {          /* what the model leaves off by itself (the handle's outline): dimmed navy */
            UINT gw = 0, gh = 0; GdipGetImageWidth(imGone, &gw); GdipGetImageHeight(imGone, &gh);
            if ((int)gw == dw && (int)gh == dh) GdipDrawImageRect(G, imGone, (REAL)canX, (REAL)canY, (REAL)canW, (REAL)canH);
        }
        for (py = 0; py < dh; py++) for (px = 0; px < dw; px++) {
            int x0 = canX + (int)(px * canS), y0 = canY + (int)(py * canS), s = (int)canS;
            if (!to_file(px, py, &fx, &fy) || !sal[fy * pw + fx]) continue;
            v = pv[fy * pw + fx];
            if (v < 0) continue;
            if (v < 8) { fillrect(x0, y0, s, s, 0xE015171Cu); fillrect(x0 + s / 3, y0 + s / 3, s - 2 * (s / 3), s - 2 * (s / 3), C_GOLD); }       /* cut away */
            else if (v < 124) fillrect(x0, y0, s, s, ((ARGB)(60 + (128 - v) * 1.4) << 24) | 0x2A6CF0u);                                         /* thinner: blue */
            else if (v > 132) fillrect(x0, y0, s, s, ((ARGB)(60 + (v - 128) * 1.2) << 24) | 0xE2B33Cu);                                         /* thicker: gold */
            else { rr(x0 + 1, y0 + 1, s - 2, s - 2, 1, 0, C_ACC, S(2)); }                                                                       /* keep: teal frame */
        }
        if (canS >= 6) { for (px = 0; px <= dw; px++) fillrect(canX + (int)(px * canS), canY, 1, canH, 0x28FFFFFFu); for (py = 0; py <= dh; py++) fillrect(canX, canY + (int)(py * canS), canW, 1, 0x28FFFFFFu); }
        hit(canX, canY, canW, canH, H_CANVAS, 0);
        bw = S(84); gx = mx + S(14);
        for (i = 0; i < 5; i++) chip(BRUSHL[i], gx + i * (bw + S(4)), vy + vh - S(84), bw, S(32), brush == i, H_BRUSH, i);
        gx = mx + S(14);
        txt(L"size", gx, vy + vh - S(44), S(34), S(32), fSmall, C_DIM, DT_LEFT | DT_VCENTER | DT_SINGLELINE); gx += S(34);
        for (i = 0; i < 3; i++) chip(BSIZEL[i], gx + i * S(36), vy + vh - S(44), S(32), S(32), bsize == i, H_BSIZE, i);
        gx += 3 * S(36) + S(10);
        button(L"Clear all", gx, vy + vh - S(44), S(90), S(32), 0, H_PCLEAR, 0);
        button(L"See the model", mx + vw - S(134), vy + vh - S(44), S(120), S(32), 2, H_PMODE, 0);
    } else if (views[curView]) image_fit(views[curView], mx + S(12), vy + S(12), vw - S(24), vh - S(64));
    else if (busy) { ARGB a = (ARGB)(40 + (int)(30 * (0.5 + 0.5 * sin(anim * 0.18)))); rr(mx + vw / 2.0 - S(60), vy + vh / 2.0 - S(90), S(120), S(180), S(14), (a << 24) | 0xFFFFFF, 0, 0); }
    else txt(sprite[0] ? L"no picture of this side yet" : L"Open a sprite to begin", mx, vy, vw, vh - S(52), fBig, 0xFF5F6775u, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    if (!(paintMode && pv && imSprite)) {
        if (pv) button(L"Edit parts", mx + vw - S(268), vy + vh - S(44), S(96), S(32), 2, H_PEDIT, 0);
        hit(mx + S(12), vy + S(12), vw - S(24), vh - S(64), H_VIEW, 0);
        x = mx + vw / 2;
        if (pv && x + S(118) > mx + vw - S(276)) x = mx + S(14) + S(118);   /* keep the turn buttons clear of Edit parts */
        button(L"<", x - S(118), vy + vh - S(44), S(40), S(32), 0, H_PREV, 0); button(L">", x + S(78), vy + vh - S(44), S(40), S(32), 0, H_NEXT, 0);
        swprintf(b, 400, curView == 0 ? L"the front" : curView == NV / 2 ? L"the back" : curView == NV / 4 || curView == 3 * NV / 4 ? L"edge-on (%d)" : L"turned %d", curView * 360 / NV);
        txt(b, x - S(76), vy + vh - S(44), S(152), S(32), fUI, C_TEXT, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        if (pv) button(hasPaint ? L"Draw on it (drawn)" : L"Draw on it", mx + vw - S(164), vy + vh - S(44), S(150), S(32), 2, H_PMODE, 1);
    }
    if (tw) {
        int tx = mx + vw + S(16), th = (vh - 2 * S(10)) / 3;
        thumb(L"Original", orig[0] ? L"" : L"(optional)", imOrig, tx, vy, tw, th);
        thumb(L"Sprite", L"", imSprite, tx, vy + th + S(10), tw, th);
        thumb(L"Parts", selMethod == 0 ? partsNote : L"not used by this depth", selMethod == 0 ? imParts : NULL, tx, vy + 2 * (th + S(10)), tw, th);
    }
    /* ---- the foot: the model's facts ---- */
    txt(facts[0] ? facts : L"", mx, H - S(FOOT_H), mw, S(22), fUI, problems ? C_GOLD : C_ACC, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    txt(objFile[0] ? objFile : L"", mx, H - S(FOOT_H) + S(24), mw, S(20), fSmall, C_DIM, DT_LEFT | DT_SINGLELINE | DT_PATH_ELLIPSIS);
    if (showDetails) {          /* what Python said, newest last */
        int n = (vh - S(40)) / S(16), k0 = nlog > n ? nlog - n : 0;
        rr(mx, vy, mw, vh, S(12), 0xF015171Cu, C_LINE, 1); txt(L"Details: what the tool said (D closes)", mx + S(14), vy + S(10), mw - S(28), S(20), fLabel, C_GOLD, DT_LEFT | DT_SINGLELINE);
        for (i = k0; i < nlog; i++) txt(logv[i], mx + S(14), vy + S(34) + (i - k0) * S(16), mw - S(28), S(16), fMono, C_DIM, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    }
    if (showHelp) {
        int hx = S(SIDE_W) + S(30), hw = W - hx - S(30), hy = S(24), hh = H - S(48), n = (int)(sizeof HELP / sizeof HELP[0]) / 2, row = (hh - S(60)) / n, lw = S(170);
        rr(hx, hy, hw, hh, S(14), 0xFF1B1E25u, C_GOLD, S(2)); txt(L"Help", hx + S(20), hy + S(12), hw - S(40), S(30), fBig, C_GOLD, DT_LEFT | DT_SINGLELINE);
        (void)row;
        {          /* two columns, each row as tall as its text */
            int colw = (hw - S(60)) / 2, half = (n + 1) / 2, cx0;
            lw = S(112);
            for (i = 0; i < n; i++) {
                RECT c = { 0, 0, colw - lw, 0 };
                if (i == 0 || i == half) y = hy + S(52);
                cx0 = hx + S(20) + (i < half ? 0 : colw + S(20));
                SelectObject(DC, fSmall); DrawTextW(DC, HELP[2 * i + 1], -1, &c, DT_LEFT | DT_WORDBREAK | DT_CALCRECT | DT_NOPREFIX);
                txt(HELP[2 * i], cx0, y, lw - S(8), c.bottom + S(4), fLabel, C_ACC, DT_LEFT | DT_WORDBREAK);
                txt(HELP[2 * i + 1], cx0 + lw, y, colw - lw, c.bottom + S(4), fSmall, C_TEXT, DT_LEFT | DT_WORDBREAK);
                y += c.bottom + S(10);
            }
        }
    }
    GdipFlush(G, FlushIntentionSync); GdipDeleteGraphics(G); BitBlt(out, 0, 0, W, H, DC, 0, 0, SRCCOPY); SelectObject(DC, obm); DeleteObject(bm); DeleteDC(DC);
}
/* the window's picture into a BMP file, painted by paint() itself (a window off screen has no picture to copy) */
static void capture(const WCHAR *path) {
    RECT r; int w, h; BITMAPINFO bi; void *bits; HDC sdc = GetDC(NULL), dc = CreateCompatibleDC(sdc); HBITMAP bm; HGDIOBJ o; FILE *f; BITMAPFILEHEADER fh;
    GetClientRect(hMain, &r); w = r.right; h = r.bottom;
    memset(&bi, 0, sizeof bi); bi.bmiHeader.biSize = sizeof bi.bmiHeader; bi.bmiHeader.biWidth = w; bi.bmiHeader.biHeight = h; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    bm = CreateDIBSection(sdc, &bi, DIB_RGB_COLORS, &bits, NULL, 0); o = SelectObject(dc, bm); paint(dc, w, h); GdiFlush();
    f = _wfopen(path, L"wb");
    if (f) { memset(&fh, 0, sizeof fh); fh.bfType = 0x4D42; fh.bfOffBits = sizeof fh + sizeof bi.bmiHeader; fh.bfSize = fh.bfOffBits + (DWORD)w * h * 4;
             fwrite(&fh, sizeof fh, 1, f); fwrite(&bi.bmiHeader, sizeof bi.bmiHeader, 1, f); fwrite(bits, 4, (size_t)w * h, f); fclose(f); }
    SelectObject(dc, o); DeleteObject(bm); DeleteDC(dc); ReleaseDC(NULL, sdc);
}

static void make_fonts(void) {
    HFONT *fs[7] = { &fTitle, &fLabel, &fUI, &fSmall, &fBig, &fBtn, &fMono }; int px[7] = { 24, 13, 14, 12, 21, 15, 12 }, wt[7] = { 700, 600, 400, 400, 600, 700, 400 }, i;
    for (i = 0; i < 7; i++) { if (*fs[i]) DeleteObject(*fs[i]); *fs[i] = CreateFontW(-S(px[i]), 0, 0, 0, wt[i], 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, i == 6 ? L"Consolas" : L"Segoe UI"); }
}
/* what was chosen and where the window was: out\sprite3d_gui.ini */
static void settings(int save) {
    WCHAR p[MAX_PATH], v[16]; int *vals[11] = { &selMethod, &selKind, &selThick, &selSides, &selOutl, &selTurn, &selHandle, &brush, &bsize, &selDetail, &selPoly }, lim[11] = { 4, 4, 6, 2, 3, 4, 2, 5, 3, 4, 2 }, i;
    const WCHAR *keys[11] = { L"method", L"kind", L"thickness", L"sides", L"outline", L"turn", L"handle", L"brush", L"brush_size", L"detail", L"polygons" };
    if (selftest) return;
    swprintf(p, MAX_PATH, L"%ls\\out", tool); CreateDirectoryW(p, NULL); swprintf(p, MAX_PATH, L"%ls\\out\\sprite3d_gui.ini", tool);
    for (i = 0; i < 11; i++) {
        if (save) { swprintf(v, 16, L"%d", *vals[i]); WritePrivateProfileStringW(L"window", keys[i], v, p); }
        else { int x = (int)GetPrivateProfileIntW(L"window", keys[i], *vals[i], p); if (x >= 0 && x < lim[i]) *vals[i] = x; }
    }
    if (save) {
        WINDOWPLACEMENT wp; LONG *e[4]; const WCHAR *k[4] = { L"left", L"top", L"right", L"bottom" };
        wp.length = sizeof wp; GetWindowPlacement(hMain, &wp); e[0] = &wp.rcNormalPosition.left; e[1] = &wp.rcNormalPosition.top; e[2] = &wp.rcNormalPosition.right; e[3] = &wp.rcNormalPosition.bottom;
        for (i = 0; i < 4; i++) { swprintf(v, 16, L"%ld", *e[i]); WritePrivateProfileStringW(L"window", k[i], v, p); }
        WritePrivateProfileStringW(L"window", L"maximized", wp.showCmd == SW_SHOWMAXIMIZED ? L"1" : L"0", p);
        WritePrivateProfileStringW(L"window", L"sprite", sprite, p); WritePrivateProfileStringW(L"window", L"original", orig, p);
    } else {
        savedR.left = (int)GetPrivateProfileIntW(L"window", L"left", 0, p); savedR.top = (int)GetPrivateProfileIntW(L"window", L"top", 0, p);
        savedR.right = (int)GetPrivateProfileIntW(L"window", L"right", 0, p); savedR.bottom = (int)GetPrivateProfileIntW(L"window", L"bottom", 0, p);
        savedMax = (int)GetPrivateProfileIntW(L"window", L"maximized", 0, p);
        GetPrivateProfileStringW(L"window", L"sprite", L"", sprite, MAX_PATH, p); GetPrivateProfileStringW(L"window", L"original", L"", orig, MAX_PATH, p);
        if (sprite[0] && !exists(sprite)) sprite[0] = 0;
        if (orig[0] && !exists(orig)) orig[0] = 0;
    }
}
static int pick_png(const WCHAR *title, WCHAR *out) {
    OPENFILENAMEW o; WCHAR f[MAX_PATH] = L"";
    memset(&o, 0, sizeof o); o.lStructSize = sizeof o; o.hwndOwner = hMain; o.lpstrFilter = L"PNG pictures\0*.png\0All files\0*.*\0"; o.lpstrFile = f; o.nMaxFile = MAX_PATH; o.lpstrTitle = title;
    o.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY | OFN_NOCHANGEDIR;
    if (!GetOpenFileNameW(&o)) return 0;
    wcscpy(out, f); return 1;
}
static int clickY;
static void turn(int d) { curView = ((curView + d) % NV + NV) % NV; redraw(); }
static void click(int kind, int idx, int x) {
    WCHAR f[MAX_PATH];
    if (showHelp) { showHelp = 0; redraw(); return; }
    switch (kind) {
    case H_OPEN: if (pick_png(L"The sprite: a PNG with a clear background, the object upright", f)) set_sprite(f); break;
    case H_PARTS: if (pick_png(L"A parts picture: the sprite painted in its parts' colours (a .txt beside it gives what each is)", f) && parts_read(f, 0)) { selMethod = 0; parts_changed(); } break;
    case H_PARTSX: case H_PGUESS: hasParts = 0; saveGuess = 1; selMethod = 0; make(); break;
    case H_PEDIT: paintMode = paintMode == 2 ? 0 : 2; if (paintMode == 2 && selMethod != 0) { selMethod = 0; make(); } break;
    case H_PREG: psel = idx; break;
    case H_PNEW: part_new(); parts_save(); break;
    case H_PDEL: part_delete(); parts_changed(); break;
    case H_PLABEL: if (nprt) { int col[3]; memcpy(col, prt[psel].col, sizeof col); part_default(&prt[psel], idx, col); parts_changed(); } break;
    case H_PSHAPE: if (nprt) { strcpy(prt[psel].shape, SHAPEV[idx]); if (idx == 1 || idx == 2) prt[psel].sides = prt[psel].sides < 8 ? 8 : prt[psel].sides; parts_changed(); } break;
    case H_PTAPER: if (nprt) { strcpy(prt[psel].taper, TAPERV[idx]); if (idx && prt[psel].tamount <= 0) prt[psel].tamount = 0.5; parts_changed(); } break;
    case H_PSTEP: if (nprt) {
        Part *pp = &prt[psel]; int k = idx / 2, up = idx & 1; double d = up ? 1 : -1;
        if (k == 0) { pp->depth += 0.25 * d; if (pp->depth < 0.25) pp->depth = 0.25; if (pp->depth > 4) pp->depth = 4; }
        else if (k == 1) { pp->offset += 0.5 * d; if (pp->offset < -6) pp->offset = -6; if (pp->offset > 6) pp->offset = 6; }
        else if (k == 2) { pp->bevel += 0.25 * d; if (pp->bevel < 0) pp->bevel = 0; if (pp->bevel > 4) pp->bevel = 4; }
        else if (k == 3) { pp->sides += up ? 1 : -1; if (pp->sides < 3) pp->sides = 3; if (pp->sides > 16) pp->sides = 16; }
        else { pp->tamount += 0.25 * d; if (pp->tamount < 0) pp->tamount = 0; if (pp->tamount > 1) pp->tamount = 1; }
        parts_changed(); } break;
    case H_ORIG: if (pick_png(L"The original sprite (only shown beside the others)", f)) { wcscpy(orig, f); drop_img(&imOrig); imOrig = load_img(orig); make(); } break;
    case H_ORIGX: orig[0] = 0; drop_img(&imOrig); make(); break;
    case H_METHOD: selMethod = idx; make(); break;
    case H_KIND: selKind = idx; make(); break;
    case H_THICK: selThick = idx; make(); break;
    case H_SIDES: selSides = idx; make(); break;
    case H_OUTL: selOutl = idx; make(); break;
    case H_TURN: selTurn = idx; if (sprite[0]) load_sprite_img(); make(); break;
    case H_HANDLE: selHandle = idx; make(); break;
    case H_DETAIL: selDetail = idx; make(); break;
    case H_POLY: selPoly = idx; make(); break;
    case H_PMODE: paintMode = paintMode ? 0 : 1; break;
    case H_BRUSH: brush = idx; break;
    case H_BSIZE: bsize = idx; break;
    case H_PCLEAR: if (pv) { int k; for (k = 0; k < pw * ph; k++) pv[k] = -1; paint_save(); make(); } break;
    case H_CANVAS: stroking = 1; SetCapture(hMain); paint_at(x, clickY); return;
    case H_GO: make(); break;
    case H_FOLDER: if (outDir[0]) ShellExecuteW(hMain, L"open", outDir, NULL, NULL, SW_SHOWNORMAL); break;
    case H_DETAILS: showDetails = !showDetails; break;
    case H_HELP: showHelp = 1; break;
    case H_PREV: turn(-1); break;
    case H_NEXT: turn(1); break;
    case H_VIEW: dragging = 1; dragX = x; dragView = curView; SetCapture(hMain); break;
    }
    settings(1); redraw();
}
static LRESULT CALLBACK proc(HWND h, UINT m, WPARAM w, LPARAM l) {
    int i;
    switch (m) {
    case WM_LINE: on_line((WCHAR *)l); free((void *)l); return 0;
    case WM_ENDED: on_ended((DWORD)l); return 0;
    case WM_TIMER: anim++; if (busy) redraw(); return 0;
    case WM_ERASEBKGND: return 1;
    case WM_PAINT: { PAINTSTRUCT ps; RECT r; HDC dc = BeginPaint(h, &ps); GetClientRect(h, &r); if (r.right > 0 && r.bottom > 0) paint(dc, r.right, r.bottom); EndPaint(h, &ps); return 0; }
    case WM_GETMINMAXINFO: ((MINMAXINFO *)l)->ptMinTrackSize.x = S(900); ((MINMAXINFO *)l)->ptMinTrackSize.y = S(640); return 0;
    case 0x02E0: { RECT *r = (RECT *)l; SC = HIWORD(w) / 96.0; make_fonts(); SetWindowPos(h, NULL, r->left, r->top, r->right - r->left, r->bottom - r->top, SWP_NOZORDER | SWP_NOACTIVATE); redraw(); return 0; }          /* WM_DPICHANGED */
    case WM_MOUSEMOVE: {
        POINT p = { GET_X_LPARAM(l), GET_Y_LPARAM(l) }; int k = H_NONE, ix = -1;
        if (dragging) { int v = ((dragView + (p.x - dragX) / S(26)) % NV + NV) % NV; if (v != curView) { curView = v; redraw(); } return 0; }
        if (stroking) { paint_at(p.x, p.y); return 0; }
        for (i = nhit - 1; i >= 0; i--) if (PtInRect(&hits[i].r, p)) { k = hits[i].kind; ix = hits[i].idx; break; }
        if (k != hovK || ix != hovI) { hovK = k; hovI = ix; redraw(); }
        return 0; }
    case WM_LBUTTONDOWN: {
        POINT p = { GET_X_LPARAM(l), GET_Y_LPARAM(l) };
        if (showHelp) { showHelp = 0; redraw(); return 0; }
        clickY = p.y;
        for (i = nhit - 1; i >= 0; i--) if (PtInRect(&hits[i].r, p)) { click(hits[i].kind, hits[i].idx, p.x); break; }
        return 0; }
    case WM_RBUTTONDOWN: {          /* on the drawing: put pixels back as made */
        POINT p = { GET_X_LPARAM(l), GET_Y_LPARAM(l) };
        for (i = nhit - 1; i >= 0; i--) if (hits[i].kind == H_CANVAS && PtInRect(&hits[i].r, p)) { stroking = 2; SetCapture(hMain); paint_at(p.x, p.y); if (paintMode == 2) { stroking = 0; ReleaseCapture(); } break; }
        return 0; }
    case WM_RBUTTONUP: stroke_end(); return 0;
    case WM_CAPTURECHANGED: if (stroking && (HWND)l != h) stroke_end(); return 0;
    case WM_LBUTTONUP:
        if (stroking) { stroke_end(); return 0; }
        if (dragging) {          /* a click without a drag: the left half turns one way, the right half the other */
            int x = GET_X_LPARAM(l); dragging = 0; ReleaseCapture();
            if (abs(x - dragX) < S(6)) { for (i = 0; i < nhit; i++) if (hits[i].kind == H_VIEW) turn(x < (hits[i].r.left + hits[i].r.right) / 2 ? -1 : 1); }
            redraw();
        }
        return 0;
    case WM_SETCURSOR: if (LOWORD(l) == HTCLIENT) { SetCursor(LoadCursorW(NULL, hovK == H_VIEW || dragging ? IDC_SIZEWE : hovK == H_CANVAS || stroking ? IDC_CROSS : hovK != H_NONE ? IDC_HAND : IDC_ARROW)); return 1; } break;
    case WM_DROPFILES: {
        WCHAR f[MAX_PATH]; HDROP d = (HDROP)w; size_t n;
        if (DragQueryFileW(d, 0, f, MAX_PATH)) { n = wcslen(f); if (n > 10 && !_wcsicmp(f + n - 10, L"_parts.png") && sprite[0]) { wcscpy(parts, f); selMethod = 0; make(); } else set_sprite(f); }
        DragFinish(d); settings(1); return 0; }
    case WM_KEYDOWN:
        if (w == VK_ESCAPE) { if (showHelp) showHelp = 0; else if (showDetails) showDetails = 0; redraw(); }
        else if (w == VK_F1) { showHelp = !showHelp; redraw(); }
        else if (showHelp) { showHelp = 0; redraw(); }
        else if (w == VK_LEFT) turn(-1);
        else if (w == VK_RIGHT) turn(1);
        else if (w == VK_RETURN) make();
        else if (w == 'D') { showDetails = !showDetails; redraw(); }
        else if (w == 'O' && GetKeyState(VK_CONTROL) < 0) click(H_OPEN, 0, 0);
        return 0;
    case WM_CHAR: if (w == L'?') { showHelp = 1; redraw(); } return 0;
    case WM_CLOSE: settings(1); DestroyWindow(h); return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(h, m, w, l);
}

int WINAPI WinMain(HINSTANCE hi, HINSTANCE hp, LPSTR cmdA, int show) {
    WNDCLASSW wc; MSG msg; RECT wa; WCHAR t[MAX_PATH], *sl; int cw = 1180, chh = 780, argc = 0; JOBOBJECT_EXTENDED_LIMIT_INFORMATION ji; DWORD ex = 0; BOOL dark = TRUE;
    GdiplusStartupInput gin = { 1, NULL, FALSE, FALSE }; ULONG_PTR gtok; HMODULE u32 = GetModuleHandleW(L"user32.dll"), dwm; HDC sdc; WCHAR **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    WCHAR first[MAX_PATH] = L"";
    (void)hp; (void)cmdA;
    /* where sprite3d.py is: beside the exe, or one folder up (the exe in gui\) */
    GetModuleFileNameW(NULL, tool, MAX_PATH); sl = wcsrchr(tool, L'\\'); if (sl) *sl = 0;
    swprintf(t, MAX_PATH, L"%ls\\sprite3d.py", tool);
    if (!exists(t)) { sl = wcsrchr(tool, L'\\'); if (sl) { *sl = 0; swprintf(t, MAX_PATH, L"%ls\\sprite3d.py", tool); if (!exists(t)) *sl = L'\\'; } }
    if (GetEnvironmentVariableW(L"SPRITE3D_TOOL", t, MAX_PATH)) wcscpy(tool, t);
    if (!GetEnvironmentVariableW(L"SPRITE3D_PYTHON", py, MAX_PATH)) { wcscpy(py, L"O:\\appsnotonc\\pixelup\\.venv\\Scripts\\python.exe"); if (!exists(py)) wcscpy(py, L"python"); }
    if (argc >= 3 && !wcscmp(argv[1], L"--selftest")) { selftest = 1; wcsncpy(stShot, argv[2], MAX_PATH - 1); if (argc >= 4) wcsncpy(first, argv[3], MAX_PATH - 1); if (argc >= 5 && !wcscmp(argv[4], L"paint")) selftest = 2; if (argc >= 5 && !wcscmp(argv[4], L"parts")) selftest = 3; }
    else if (argc >= 2) wcsncpy(first, argv[1], MAX_PATH - 1);
    hJob = CreateJobObjectW(NULL, NULL);
    if (hJob) { memset(&ji, 0, sizeof ji); ji.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, &ji, sizeof ji); }
    { typedef BOOL(WINAPI *F)(HANDLE); F fn = (F)(void *)GetProcAddress(u32, "SetProcessDpiAwarenessContext"); if (!fn || !fn((HANDLE)-4)) SetProcessDPIAware(); }
    CoInitialize(NULL); GdiplusStartup(&gtok, &gin, NULL);
    sdc = GetDC(NULL); SC = GetDeviceCaps(sdc, LOGPIXELSX) / 96.0; ReleaseDC(NULL, sdc);
    if (selftest) SC = 1.0;
    make_fonts();
    wcscpy(head, L"Open a sprite to begin"); wcscpy(sub, L"A PNG with a clear background, the object standing upright. Press ? for help.");
    settings(0);
    memset(&wc, 0, sizeof wc); wc.lpfnWndProc = proc; wc.hInstance = hi; wc.lpszClassName = L"sprite3d_gui"; wc.hCursor = LoadCursorW(NULL, IDC_ARROW); wc.hIcon = LoadIconW(NULL, IDI_APPLICATION);
    RegisterClassW(&wc);
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &wa, 0);
    if (selftest) ex = WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW;
    hMain = CreateWindowExW(ex, L"sprite3d_gui", L"Sprite to 3D", WS_OVERLAPPEDWINDOW, selftest ? -8000 : wa.left + (wa.right - wa.left - S(cw)) / 2, selftest ? -8000 : wa.top + (wa.bottom - wa.top - S(chh)) / 2,
                            S(cw), S(chh), NULL, NULL, hi, NULL);
    dwm = LoadLibraryW(L"dwmapi.dll");
    if (dwm) { typedef HRESULT(WINAPI *D)(HWND, DWORD, LPCVOID, DWORD); D fn = (D)(void *)GetProcAddress(dwm, "DwmSetWindowAttribute"); if (fn && fn(hMain, 20, &dark, sizeof dark) != S_OK) fn(hMain, 19, &dark, sizeof dark); }
    DragAcceptFiles(hMain, TRUE);
    if (!selftest && savedR.right - savedR.left > 300 && savedR.bottom - savedR.top > 300) {
        WINDOWPLACEMENT wp; memset(&wp, 0, sizeof wp); wp.length = sizeof wp; wp.rcNormalPosition = savedR; wp.showCmd = savedMax ? SW_SHOWMAXIMIZED : SW_SHOWNORMAL; SetWindowPlacement(hMain, &wp);
    } else ShowWindow(hMain, selftest ? SW_SHOWNOACTIVATE : show);
    if (first[0]) { orig[0] = 0; set_sprite(first); }
    else if (sprite[0]) { if (orig[0]) imOrig = load_img(orig); set_sprite(_wcsdup(sprite)); }
    if (selftest && !busy) { capture(stShot); return 2; }
    while (GetMessageW(&msg, NULL, 0, 0) > 0) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    if (hJob) CloseHandle(hJob);
    GdiplusShutdown(gtok);
    return 0;
}
