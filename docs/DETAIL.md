# Taskbar lamp

A small pixel whale plus a live number on the Windows taskbar. The number is how many dsh sessions are working right now.

- The plugin starts the lamp when dsh starts and stops it when dsh exits.
- When a session is waiting for you (a question dialog, or an approval prompt), the number turns red and blinks.
- When the number grows, it rolls upward; when it shrinks, it rolls down.
- While at least one session is working, the whale blows two slowly rising bubbles.

## What it reads

Only the session files dsh already writes under `%USERPROFILE%\.dsh\sessions\<workspace>\<session>\session.v4.jsonl.zstd`:

- a `turn/start` without a matching `turn/end` means that session is working;
- an unanswered `ask_user_question` tool call, or an `approval/asked` without `approval/decided`, means a dialog is waiting for you.

Nothing is sent anywhere, and no dsh setting is changed.

## Requirements

The lamp itself is a small Python program bundled in `lamp/`. It needs:

- Python 3.10 or newer on Windows, with `pillow`, `pystray` and `zstandard`;
- a Windows 11 taskbar (it also runs on Windows 10, the placement is less tidy).

The plugin looks for the interpreter in this order:

1. the `pythonPath` option in the plugin configuration;
2. the `DSH_LAMP_PYTHON` environment variable;
3. `D:\develop\python313\pythonw.exe` and `C:\Python313\pythonw.exe`;
4. `pythonw` on `PATH`.

If the process exits within three seconds, the plugin logs a warning naming the missing Python packages.

## Using the lamp

- Drag the whale left or right; it remembers where you put it. Vertically it can only move inside the taskbar strip.
- Right-click it for refresh, light/dark toggle, hide, and quit.
- A small dot appears in the notification area as well; its menu shows and hides the lamp.

## Limits

- Windows only. On other platforms the plugin logs that it is skipped.
- The lamp only lives while dsh does. Closing dsh removes it from the taskbar.
- It cannot tell you *which* project is waiting, only that something is.
