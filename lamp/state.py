"""读取 DSH 会话日志，算出"有几个会话正在干活"和"有没有在等用户确认"。

数据来源：
  %USERPROFILE%\\.dsh\\sessions\\<工作区>\\<会话>\\session.v4.jsonl.zstd
该文件由 DSH 以"一事件一帧"的方式追加压缩，规则：
  turn/start 与 turn/end 配对判断会话是否在跑；
  tool/call(name=ask_user_question) 没有对应 tool/result 表示弹窗在等回答；
  approval/asked 没有对应 approval/decided 表示审批弹窗在等确认。
"""

import io
import json
import os
import time

import zstandard

ROOT = os.path.join(os.path.expanduser("~"), ".dsh", "sessions")
FRAME_MAGIC = b"\x28\xb5\x2f\xfd"
DECOMP = zstandard.ZstdDecompressor()


def _decode_frames(chunk):
    """把一段多帧 zstd 数据解成文本；遇到写了一半的尾帧就停在最后一个完整帧。"""
    starts = []
    pos = chunk.find(FRAME_MAGIC)
    while pos != -1:
        starts.append(pos)
        pos = chunk.find(FRAME_MAGIC, pos + 1)
    if not starts:
        return "", 0
    out = []
    good_until = 0
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(chunk)
        try:
            out.append(DECOMP.decompressobj().decompress(chunk[s:e]).decode("utf-8"))
            good_until = e
        except Exception:
            break
    return "".join(out), good_until


class SessionState:
    __slots__ = ("path", "workspace", "session_id", "offset", "mtime", "size",
                 "open_turns", "calls", "results", "approvals_open", "last_seen", "depth")

    def __init__(self, path, workspace, session_id):
        self.path = path
        self.workspace = workspace
        self.session_id = session_id
        self.offset = 0
        self.mtime = 0.0
        self.size = 0
        self.open_turns = {}
        self.calls = {}
        self.results = set()
        self.approvals_open = {}
        self.last_seen = 0.0
        self.depth = 0

    def _apply(self, ev):
        t = ev.get("type")
        d = ev.get("data") or {}
        if t == "session":
            # 子代理也是独立会话文件，但它们是父会话派出去的，不该单独计数。
            # 注意：session 事件的字段在顶层，不像其他事件套在 data 里。
            try:
                self.depth = int(ev.get("delegationDepth") or 0)
            except Exception:
                self.depth = 0
        elif t == "turn/start":
            self.open_turns[d.get("turn")] = ev.get("time")
            self.last_seen = time.time()
        elif t == "turn/end":
            self.open_turns.pop(d.get("turn"), None)
            self.last_seen = time.time()
        elif t == "tool/call":
            self.calls[d.get("callId")] = (d.get("turn"), d.get("name"))
        elif t == "tool/result":
            msg = d.get("message") or {}
            cid = msg.get("toolCallId") or (msg.get("source") or {}).get("callId") or d.get("toolCallId")
            if cid:
                self.results.add(cid)
        elif t == "approval/asked":
            self.approvals_open[d.get("id")] = d
        elif t == "approval/decided":
            self.approvals_open.pop(d.get("id"), None)

    def refresh(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return False
        if st.st_size == self.size and st.st_mtime == self.mtime:
            return False
        if st.st_size < self.offset:
            # 文件被重写或压缩过，重头再来
            self.offset = 0
            self.open_turns.clear()
            self.calls.clear()
            self.results.clear()
            self.approvals_open.clear()
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            chunk = f.read()
        text, consumed = _decode_frames(chunk)
        self.offset += consumed
        self.size = st.st_size
        self.mtime = st.st_mtime
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                self._apply(json.loads(line))
            except Exception:
                pass
        return True

    @property
    def running(self):
        return bool(self.open_turns)

    def pending(self):
        """返回 (等待回答的问题数, 等待确认的审批数)。只算当前正在跑的那一轮。"""
        if not self.running:
            return 0, 0
        turns = set(self.open_turns)
        q = sum(1 for cid, (turn, name) in self.calls.items()
                if name == "ask_user_question" and turn in turns and cid not in self.results)
        a = len(self.approvals_open)
        return q, a

    @property
    def name(self):
        return self.workspace.strip("-~").replace("-", "\\")


class Monitor:
    def __init__(self, max_idle_seconds=12 * 3600):
        self.sessions = {}
        self.max_idle = max_idle_seconds
        self.last_scan = 0.0

    def _walk(self):
        now = time.time()
        seen = set()
        for ws in os.listdir(ROOT):
            wd = os.path.join(ROOT, ws)
            if not os.path.isdir(wd):
                continue
            for sid in os.listdir(wd):
                p = os.path.join(wd, sid, "session.v4.jsonl.zstd")
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if now - st.st_mtime > self.max_idle:
                    continue
                seen.add(p)
                s = self.sessions.get(p)
                if s is None:
                    s = SessionState(p, ws, sid)
                    self.sessions[p] = s
                if s.refresh():
                    pass
        for p in list(self.sessions):
            if p not in seen:
                self.sessions.pop(p, None)
        self.last_scan = now

    def snapshot(self):
        self._walk()
        running, waiting, total_wait = [], [], 0
        for s in self.sessions.values():
            if s.running and s.depth == 0:
                q, a = s.pending()
                total_wait += q + a
                running.append({"session": s.session_id, "workspace": s.name,
                                "since": min(s.open_turns.values()) if s.open_turns else None,
                                "questions": q, "approvals": a})
                if q or a:
                    waiting.append(running[-1])
        running.sort(key=lambda r: r["since"] or "")
        return {
            "running": len(running),
            "waiting": len(waiting),
            "pending_total": total_wait,
            "items": running,
            "waiting_items": waiting,
            "at": time.time(),
        }


if __name__ == "__main__":
    m = Monitor()
    t = time.time()
    snap = m.snapshot()
    print("scan ms", round((time.time() - t) * 1000, 1))
    print(json.dumps(snap, ensure_ascii=False, indent=1))
