# dsh-taskbar-lamp

A small pixel whale on your Windows taskbar that tells you how many DeepSeek Harness (dsh) sessions are working right now.

![The lamp beside the taskbar clock](docs/images/taskbar-zoom.png)

![The whole taskbar](docs/images/taskbar.png)

- **Live count** — every running dsh session counts one.
- **Red and blinking** — a session is waiting for you: a question dialog, or an approval prompt.
- **Rolling digits** — the number rolls up when work appears and down when it finishes.
- **Bubbles** — the whale blows two slow bubbles while at least one session is working.
- **Remembers where you put it** — drag it along the taskbar, vertically inside the taskbar strip only.

It reads nothing but the session files dsh already writes under `%USERPROFILE%\.dsh\sessions\`. Nothing leaves your machine.

## Install

```sh
dsh plugin add dsh-taskbar-lamp
```

The plugin starts the lamp with dsh and stops it when dsh exits.

## Requirements

- Windows 10 or 11 (Windows 11 looks tidiest).
- Python 3.10+ with `pillow`, `pystray` and `zstandard`:
  ```sh
  python -m pip install pillow pystray zstandard
  ```
- The plugin finds the interpreter through the `pythonPath` option, the `DSH_LAMP_PYTHON` environment variable, `D:\develop\python313\pythonw.exe` / `C:\Python313\pythonw.exe`, or `pythonw` on `PATH`.

## Configuration

```yaml
- id: taskbar-lamp
  name: 'dsh-taskbar-lamp'
  config:
    pythonPath: 'C:\Python313\pythonw.exe'
```

## Limits

- Windows only.
- The lamp lives as long as dsh does.
- It tells you *that* something is waiting, not which project.

## 中文说明

在 Windows 任务栏上放一只像素鲸鱼和实时数字，数字就是此刻正在干活的 dsh 会话数。有弹窗等你确认时数字变红并闪动；任务数增减时数字上下翻牌；有活在跑时鲸鱼会吐泡泡。

只读 `%USERPROFILE%\.dsh\sessions\` 下 dsh 自己写的会话文件，不外传任何东西。

需要本机有 Python 3.10+ 以及 `pillow`、`pystray`、`zstandard` 三个包。插件会随 dsh 启动和退出。

## License

MIT
