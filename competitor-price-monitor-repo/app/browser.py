"""浏览器侧公共部分: 专用 Chrome 的启动、礼貌的取页(限速 + 拦截页识别)。
专用 Chrome 使用独立资料夹(~/chrome-price-profile)，开放本机调试端口 9222，Playwright 通过 CDP 连接，不影响你平时的 Chrome。"""
import os, pathlib, platform, random, re, shutil, subprocess, time, urllib.request
from urllib.parse import urlparse

PORT = 9222
SITES = {"EURO": "https://www.euro.com.pl/", "OleOle": "https://www.oleole.pl/", "MEX": "https://www.mediaexpert.pl/"}

class Blocked(Exception): pass

def chrome_up():
    try: urllib.request.urlopen(f"http://localhost:{PORT}/json/version", timeout=2); return True
    except Exception: return False

def chrome_exe():
    s, cands = platform.system(), []
    if s == "Darwin": cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    elif s == "Windows":
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base: cands.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
        cands.append(os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"))
    else: cands = [shutil.which(x) or "" for x in ("google-chrome", "chromium", "chromium-browser")]
    return next((c for c in cands if c and os.path.exists(c)), None)

def start_chrome(settle=30):
    """打开专用 Chrome。已经开着就什么也不做；刚启动的多等 settle 秒，避免第一批页面超时。"""
    if chrome_up(): return True
    exe = chrome_exe()
    if not exe: print("找不到 Chrome。请安装 Google Chrome，或手动用 --remote-debugging-port=9222 启动它。"); return False
    profile = pathlib.Path.home() / "chrome-price-profile"
    print("正在打开专用 Chrome(请保持它开着，不要关)...")
    subprocess.Popen([exe, f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}", "--no-first-run", "https://www.euro.com.pl/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if chrome_up(): time.sleep(settle); return True
        time.sleep(2)
    print("专用 Chrome 没有在 60 秒内准备好。"); return False

def fetch(page, url):
    """打开一个页面并返回 HTML。每页间隔 8–14 秒；超时重试一次；识别拦截页(Lockdown / Lock / Blokada / 被送回首页)并抛 Blocked。"""
    for attempt in (1, 2):
        try: page.goto(url, wait_until="domcontentloaded", timeout=60000); break
        except Exception as ex:
            if type(ex).__name__ != "TimeoutError" or attempt == 2: raise
            time.sleep(20)
    page.wait_for_timeout(3500)
    html = page.content()
    if "Access Denied" in html[:3000] or re.search(r"<title>[^<]*(lockdown|access denied|forbidden|\block\b|blokad)", html[:6000], re.I): raise Blocked(url)
    if urlparse(page.url).path in ("", "/") and urlparse(url).path not in ("", "/"): raise Blocked("被重定向回首页: " + url)   # 软拦截
    time.sleep(random.uniform(8.0, 14.0))
    return html
