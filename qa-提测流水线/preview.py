#!/usr/bin/env python3
"""本地预览服务器 —— 仅用于在本机浏览器里看 Kit（含 md 查看器）。

用法：在 kit 目录下运行
    python3 preview.py           # 默认 http://0.0.0.0:8090
    python3 preview.py 8099      # 指定端口

它相比 `python3 -m http.server` 只多做一件事：给 .md / .html 等文本文件
显式带上 charset=utf-8，这样即使直接打开裸 .md 也不会中文乱码。

注意：发到 GitHub 时用不到这个脚本。GitHub 网页会原生渲染 .md；
要把 HTML 演示页做成站点，用 GitHub Pages（静态托管，无需运行任何服务）。
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class UTF8Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".md": "text/markdown; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    handler = partial(UTF8Handler)
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"预览服务：http://0.0.0.0:{port}/  （Ctrl+C 停止）")
        print(f"文档查看器：http://<本机IP>:{port}/查看.html")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
