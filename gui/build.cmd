@echo off
rem builds sprite3d.exe (the window in front of sprite3d.py) into the tool's folder, beside sprite3d.py.
rem Needs clang with the MinGW headers: O:\appsnotonc\llvm\env.cmd sets that up on this PC. Close a running sprite3d.exe first.
rem build.cmd NAME builds NAME.exe instead (a trial beside a running one).
setlocal
call O:\appsnotonc\llvm\env.cmd
cd /d "%~dp0"
set OUT=sprite3d
if not "%1"=="" set OUT=%1
O:\appsnotonc\gcc\mingw64\bin\windres.exe sprite3d_gui.rc -O coff -o sprite3d_gui.res || exit /b 1
clang %CLANG_FLAGS% -O2 -Wall -Wextra -mwindows -static -o ..\%OUT%.exe sprite3d_gui.c sprite3d_gui.res -lgdiplus -lgdi32 -luser32 -lshell32 -lcomdlg32 -lole32 -lkernel32 -lm || exit /b 1
echo built ..\%OUT%.exe
