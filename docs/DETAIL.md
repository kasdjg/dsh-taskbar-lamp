# 任务栏小灯

Windows 任务栏上的一只像素鲸鱼加一个实时数字。数字就是此刻正在干活的 dsh 会话数。

- 插件在 dsh 启动时把灯拉起来，dsh 退出时把它关掉。
- 有会话在等你（问你选哪个，或者要权限）时，数字变红并闪动。
- 数字变多时向上翻牌，变少时向下翻牌。
- 有会话在跑时，鲸鱼会慢慢吐泡泡。
- 子代理不算独立任务，它们算在派它们出去的那个会话里。

## 它读什么

只读 dsh 自己写在 `%USERPROFILE%\.dsh\sessions\<工作区>\<会话>\session.v4.jsonl.zstd` 下的会话文件：

- 有 `turn/start` 没有对应的 `turn/end`，说明这个会话在跑；
- 有没答复的 `ask_user_question` 工具调用，或者 `approval/asked` 没有 `approval/decided`，说明有弹窗在等你。

不外传任何数据，也不改任何 dsh 设置。

## 环境要求

灯本体是打包在 `lamp/` 里的一个小 Python 程序，需要：

- Windows 10 或 11；
- Python 3.10 以上，并装有 `pillow`、`pystray`、`zstandard`。

插件按这个顺序找解释器：配置里的 `pythonPath`、环境变量 `DSH_LAMP_PYTHON`、`D:\develop\python313\pythonw.exe` 与 `C:\Python313\pythonw.exe`、`PATH` 里的 `pythonw`。进程如果在三秒内退出，插件会记一条警告，写明可能缺哪个包。

## 怎么用

- 按住图案可以沿任务栏拖动，纵向只能在任务栏那一条里挪，位置会记住。
- 打开和关闭就在插件页本身：启用它就有，停用它就没。

## 限制

- 只在 Windows 上工作，其他平台会记一条跳过日志。
- 灯只在 dsh 运行期间存在，dsh 关掉就没了。
- 只告诉你“有东西在等你”，不告诉你是哪个项目。

---

# Taskbar lamp

A small pixel whale plus a live number on the Windows taskbar. The number is how many dsh sessions are working right now.

- The plugin starts the lamp when dsh starts and stops it when dsh exits.
- When a session is waiting for you (a question dialog, or an approval prompt), the number turns red and blinks.
- The number rolls up when work appears and down when it finishes.
- The whale blows slow bubbles while at least one session is working.
- Subagents are not counted as separate tasks; they count toward the session that started them.

## What it reads

Only the session files dsh already writes under `%USERPROFILE%\.dsh\sessions\<workspace>\<session>\session.v4.jsonl.zstd`:

- a `turn/start` without a matching `turn/end` means that session is working;
- an unanswered `ask_user_question` tool call, or an `approval/asked` without `approval/decided`, means a dialog is waiting for you.

Nothing is sent anywhere, and no dsh setting is changed.

## Requirements

The lamp itself is a small Python program bundled in `lamp/`. It needs:

- Windows 10 or 11;
- Python 3.10 or newer with `pillow`, `pystray` and `zstandard`.

The plugin looks for the interpreter through the `pythonPath` option, `DSH_LAMP_PYTHON`, `D:\develop\python313\pythonw.exe` and `C:\Python313\pythonw.exe`, then `pythonw` on `PATH`. If the process exits within three seconds, the plugin logs a warning naming the likely missing package.

## Using the lamp

- Drag it along the taskbar; it remembers where you put it and only moves vertically inside the taskbar strip.
- Turning it on and off is the plugin itself: enable it and the lamp appears, disable it and the lamp goes away.

## Limits

- Windows only; other platforms log that the plugin is skipped.
- The lamp lives as long as dsh does.
- It tells you *that* something is waiting, not which project.
