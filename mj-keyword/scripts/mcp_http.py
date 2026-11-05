#!/usr/bin/env python3
"""极简 MCP Streamable-HTTP 客户端：从 antigravity 的 mcp_config.json 读服务器地址和请求头（凭证不打印），调用工具。"""
import json, os, sys, urllib.request

CONFIG = os.path.expanduser(os.environ.get("MJK_MCP_CONFIG", "~/.gemini/config/mcp_config.json"))

class MCP:
    def __init__(self, server):
        cfg = json.load(open(CONFIG))
        cfg = cfg.get("mcpServers", cfg)[server]
        self.url = cfg["serverUrl"]
        self.headers = {"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"}
        self.headers.update(cfg.get("headers", {}))
        self.sid = None
        self._id = 0
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "mj-keyword", "version": "2"}})
        self._rpc("notifications/initialized", None, notify=True)

    def _rpc(self, method, params, notify=False, timeout=90):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            self._id += 1
            body["id"] = self._id
        h = dict(self.headers)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, json.dumps(body).encode(), h, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            self.sid = r.headers.get("Mcp-Session-Id") or self.sid
            raw = r.read().decode("utf-8", "ignore")
        if notify or not raw.strip():
            return None
        if raw.lstrip().startswith("{"):
            msg = json.loads(raw)
        else:  # SSE：取最后一条带 id 的 data
            msg = None
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        m = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if m.get("id") == body.get("id"):
                        msg = m
        if msg is None:
            raise RuntimeError(f"{method}: 无法解析返回")
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg["result"]

    def list_tools(self):
        return self._rpc("tools/list", {})["tools"]

    def call(self, name, args):
        """返回工具结果里的文本内容（通常是 JSON 字符串），解析成对象；解析失败返回原文。"""
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        if res.get("isError"):
            raise RuntimeError(f"{name} 报错: {json.dumps(res.get('content'), ensure_ascii=False)[:300]}")
        if "structuredContent" in res and res["structuredContent"]:
            return res["structuredContent"]
        txt = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        try:
            return json.loads(txt)
        except ValueError:
            return txt

if __name__ == "__main__":
    m = MCP(sys.argv[1])
    for t in m.list_tools():
        if len(sys.argv) < 3 or t["name"] == sys.argv[2]:
            print(t["name"])
            if len(sys.argv) >= 3:
                print(json.dumps(t.get("inputSchema"), ensure_ascii=False)[:3000])
