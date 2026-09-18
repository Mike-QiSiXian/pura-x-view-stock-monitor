#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pura X View 官方线上渠道补货监控工具
=====================================

功能:
  1. 轮询监控京东(skuId 库存 API)和任意商品页(关键词判定)的库存状态
  2. 检测到 "无货 -> 有货" 变化时立即:
     - 本机蜂鸣报警 + Windows 弹窗
     - 自动用默认浏览器打开商品下单页(你手动完成最后一步点击, 约 10 秒)
     - 可选: Server酱推送到手机微信 / 自定义 webhook(钉钉/企微机器人)

用法:
  python monitor.py                 # 按 config.json 持续监控 (Ctrl+C 退出)
  python monitor.py --once          # 只检查一轮后退出 (适合调试或挂系统计划任务)
  python monitor.py --test-alert    # 测试报警链路(蜂鸣+弹窗+开页面+推送), 不查库存
  python monitor.py --config xx.json

首次使用:
  1. pip install requests
  2. 编辑 config.json:
     - 京东目标: 把 skuId 换成真实值。方法: 京东搜索商品 -> 打开商品详情页,
       地址栏 https://item.jd.com/100xxxxxxxx.html 中的数字就是 skuId
       (注意区分自营店和第三方店, 店铺名在商品页标题下方)
     - 华为商城目标: 在 vmall.com 搜索 "Pura X View", 选中 12+256 版本后
       复制地址栏链接填入 url 字段
     - area 字段是京东收货地址编码, 默认北京; 其他地区可改
       (格式: 1_72_4137_0, 段含义 省_市_区县_街道)
  3. (可选) 注册 https://sct.ftqq.com 获取 SendKey 填入, 实现手机微信推送
  4. python monitor.py 挂机运行

设计边界(重要):
  - 本工具只做 "监控 + 提醒 + 秒开下单页", 不保存任何账号密码、
    不做自动登录、不代替你点击下单/支付。
    原因: 华为商城和京东对脚本自动下单有强风控(滑块/人脸验证),
    自动提交订单不仅成功率低, 还可能导致账号被限制购买。
  - 检测间隔自带随机抖动, 请勿把 interval_seconds 调到 5 秒以下,
    请求过于频繁会触发平台风控封 IP。
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("缺少 requests 库, 请先执行: pip install requests")

try:
    import winsound  # Windows 专用
except ImportError:
    winsound = None

BASE_DIR = Path(__file__).resolve().parent
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TIMEOUT = 15

# 京东 StockState 含义(以 c0.3.cn/stock 接口返回为准, 平台可能调整):
IN_STOCK_STATES = {33, 39, 40}   # 现货 / 配货中(通常可下单)
OUT_STOCK_STATES = {34, 36}      # 无货 / 采购中
STATE_NAME = {33: "现货", 34: "无货", 36: "采购中", 39: "有货", 40: "可配货"}


def log(msg, log_file=None):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    if log_file:
        try:
            p = BASE_DIR / log_file
            # 单文件超过 5MB 时轮转, 避免长时间运行把磁盘写满
            if p.exists() and p.stat().st_size > 5 * 1024 * 1024:
                p.replace(p.with_suffix(".old.log"))
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


# ---------------------------------------------------------------- 检查器

def check_jd(target, session):
    """京东库存检查: c0.3.cn/stock 接口, 返回 (状态, 详情, 打开用的URL)"""
    sku = str(target.get("skuId", "")).strip()
    if not sku.isdigit():
        return "未配置", "skuId 未填写或不是数字, 跳过", ""
    area = target.get("area", "1_72_4137_0")
    url = f"https://c0.3.cn/stock?skuId={sku}&area={area}&extraParam=%7B%22originid%22%3A%221%22%7D&fqsp=0"
    open_url = target.get("open_url") or f"https://item.jd.com/{sku}.html"
    try:
        r = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        stock = data.get("stock", {})
        state = int(stock.get("StockState", -1))
        name = stock.get("StockStateName") or STATE_NAME.get(state, f"未知({state})")
        status = "有货" if state in IN_STOCK_STATES else (
            "无货" if state in OUT_STOCK_STATES else "未知")
        return status, f"京东库存状态: {name} (code={state})", open_url
    except Exception as e:
        return "错误", f"京东接口请求失败: {e}", open_url


def check_url(target, session):
    """通用页面关键词检查: 返回 (状态, 详情, 打开用的URL)"""
    url = str(target.get("url", "")).strip()
    if not url.startswith("http") or "替换" in url:
        return "未配置", "url 未填写, 跳过", ""
    in_markers = target.get("in_stock_markers", ["立即购买", "加入购物车", "现货"])
    out_markers = target.get("out_stock_markers", ["到货通知", "缺货", "已售罄", "售完", "暂无货"])
    try:
        r = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.encoding = r.apparent_encoding or "utf-8"
        text = r.text
        # 优先判无货: 页面同时含两类词时, 缺货提示更可信
        if any(m in text for m in out_markers):
            return "无货", "页面包含缺货关键词", url
        if any(m in text for m in in_markers):
            return "有货", "页面包含可购买关键词", url
        return "未知", "页面无法判定(可能是JS动态渲染, 建议换用京东skuId目标或确认标记词)", url
    except Exception as e:
        return "错误", f"页面请求失败: {e}", url


def check_vmall(target, session):
    """华为商城检查: 无头浏览器加载商品页, 监听页面自身的 querySkuInventoryV2 库存响应。
    (模拟请求会被 WAF 以 50017 拒绝, 只能让真实页面自己去取)"""
    import subprocess
    prd_url = str(target.get("prd_url", "")).strip()
    if not prd_url.startswith("http") or "替换" in prd_url:
        return "未配置", "prd_url 未填写, 跳过", ""
    node = target.get("node_path", "node")
    # 配置里的 node 路径不存在时(如云端 Linux)回退到 PATH 里的 node
    if node != "node" and not os.path.isfile(node):
        node = "node"
    helper = str(BASE_DIR / target.get("helper_script", "vmall_api.js"))
    env = dict(os.environ)
    nm = str(target.get("node_modules_path", "")).strip()
    if nm:
        sep = ";" if os.name == "nt" else ":"
        env["NODE_PATH"] = nm if not env.get("NODE_PATH") else env["NODE_PATH"] + sep + nm
    try:
        r = subprocess.run(
            [node, helper, prd_url, str(int(target.get("wait_ms", 12000)))],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace", env=env, cwd=str(BASE_DIR),
        )
        lines = [l for l in (r.stdout or "").strip().splitlines() if l.strip()]
        data = json.loads(lines[-1]) if lines else {}
        if "error" in data:
            return "错误", f"页面加载失败: {data['error']}", prd_url
        inv = data.get("inventory", {})
        if not inv:
            return "错误", "未捕获到库存响应(页面结构可能变化)", prd_url
        watch = [c for c in target.get("sku_codes", []) if c] or list(inv.keys())
        avail = {c: inv[c] for c in watch if int(inv.get(c, 0)) > 0}
        status = "有货" if avail else "无货"
        detail = f"监控 {len(watch)} 个SKU, 有货: " + (", ".join(f"{c}×{q}" for c, q in avail.items()) or "无")
        open_url = target.get("open_url") or prd_url
        return status, detail, open_url
    except subprocess.TimeoutExpired:
        return "错误", "浏览器加载超时", prd_url
    except Exception as e:
        return "错误", f"vmall 检查失败: {e}", prd_url


def check_target(target, session):
    t = target.get("type", "url")
    if t == "jd":
        return check_jd(target, session)
    if t == "vmall":
        return check_vmall(target, session)
    return check_url(target, session)


# ---------------------------------------------------------------- 报警

def alert(target_name, detail, open_url, notify_cfg):
    log(f"*** 库存变动: {target_name} -> 有货! {detail} ***")
    if winsound:
        try:
            for _ in range(3):
                winsound.Beep(1300, 400)
                time.sleep(0.15)
        except Exception:
            pass
    if notify_cfg.get("toast", True):
        try:
            ps = ("Add-Type -AssemblyName System.Windows.Forms; "
                  f"[System.Windows.Forms.MessageBox]::Show("
                  f"'{target_name} 补货啦! {detail}', '补货提醒', 0, 48)")
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps])
        except Exception as e:
            log(f"弹窗失败: {e}")
    if notify_cfg.get("open_browser", True) and open_url:
        try:
            webbrowser.open(open_url)
        except Exception as e:
            log(f"打开浏览器失败: {e}")
    # 环境变量优先于配置文件(GitHub Actions Secrets 走环境变量, 避免密钥入库)
    key = (os.environ.get("SERVERCHAN_SENDKEY")
           or notify_cfg.get("serverchan_sendkey") or "").strip()
    if key:
        try:
            requests.post(f"https://sctapi.ftqq.com/{key}.send",
                          data={"title": f"补货提醒: {target_name}",
                                "desp": f"{detail}\n\n[点此下单]({open_url})"},
                          timeout=TIMEOUT)
        except Exception as e:
            log(f"ServerChan 推送失败: {e}")
    hook = (os.environ.get("WEBHOOK_URL")
            or notify_cfg.get("webhook_url") or "").strip()
    if hook:
        try:
            requests.post(hook,
                          json={"msgtype": "text",
                                "text": {"content": f"补货提醒: {target_name} {detail} {open_url}"}},
                          timeout=TIMEOUT)
        except Exception as e:
            log(f"webhook 推送失败: {e}")


def test_alert(cfg):
    log("触发测试报警(蜂鸣+弹窗+开配置中第一个已配置目标的页面+推送)")
    t = next((x for x in cfg["targets"] if x.get("type") == "jd"
              and str(x.get("skuId", "")).strip().isdigit())
             or next((x for x in cfg["targets"]), None), None)
    open_url = (t and (t.get("open_url") or t.get("url"))) or "https://www.vmall.com"
    alert("【测试】补货监控", "这是一条测试报警, 收到说明链路正常", open_url,
          cfg.get("notify", {}))
    log("测试报警已发送, 如蜂鸣/弹窗/浏览器/手机推送有任何一项没收到, 检查对应配置")


# ---------------------------------------------------------------- 主流程

def load_config(path):
    p = Path(path)
    if not p.exists():
        default = {
            "interval_seconds": 60,
            "jitter_ratio": 0.25,
            "log_file": "stock_monitor.log",
            "state_file": "stock_state.json",
            "notify": {
                "beep": True, "toast": True, "open_browser": True,
                "serverchan_sendkey": "", "webhook_url": ""
            },
            "targets": [
                {
                    "name": "京东自营 Pura X View 12+256 (示例, 请替换skuId)",
                    "type": "jd",
                    "skuId": "100000000000",
                    "area": "1_72_4137_0",
                    "open_url": ""
                },
                {
                    "name": "华为商城 Pura X View 12+256 (示例, 请替换url)",
                    "type": "url",
                    "url": "https://www.vmall.com/product/comdetail/index.html?prdId=替换&sbomCode=替换",
                    "in_stock_markers": ["立即购买", "加入购物车", "现货"],
                    "out_stock_markers": ["到货通知", "缺货", "已售罄", "售完", "暂无货"]
                }
            ]
        }
        p.write_text(json.dumps(default, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"已生成默认配置 {p.resolve()}, 请编辑后重新运行。")
        sys.exit(0)
    return json.loads(p.read_text(encoding="utf-8"))


def load_state(path):
    p = BASE_DIR / path
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path, state):
    (BASE_DIR / path).write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


def run_once(cfg, state):
    session = requests.Session()
    changed = False
    for t in cfg["targets"]:
        name = t.get("name", "未命名目标")
        if not t.get("enabled", True):
            continue
        status, detail, open_url = check_target(t, session)
        prev = state.get(name, {}).get("status")
        log(f"{name}: {status} ({detail})")
        state[name] = {"status": status, "detail": detail,
                       "time": datetime.now().isoformat(timespec="seconds")}
        if status == "有货" and prev != "有货":
            alert(name, detail, open_url, cfg.get("notify", {}))
            changed = True
        time.sleep(random.uniform(1.5, 3.5))  # 目标间间隔, 降低风控风险
    save_state(cfg.get("state_file", "stock_state.json"), state)
    return changed


def main():
    ap = argparse.ArgumentParser(description="Pura X View 补货监控")
    ap.add_argument("--config", default=str(BASE_DIR / "config.json"))
    ap.add_argument("--once", action="store_true", help="只检查一轮后退出")
    ap.add_argument("--test-alert", action="store_true", help="测试报警链路")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.test_alert:
        test_alert(cfg)
        return

    state = load_state(cfg.get("state_file", "stock_state.json"))
    interval = max(20, int(cfg.get("interval_seconds", 60)))
    jitter = float(cfg.get("jitter_ratio", 0.25))
    active = [t for t in cfg["targets"] if t.get("enabled", True)]
    log(f"监控启动: {len(active)} 个目标生效(共 {len(cfg['targets'])} 个), "
        f"间隔约 {interval} 秒 (Ctrl+C 退出)")
    log("提示: 状态从 无货->有货 时才会触发报警, 首次检测即有货也会报警")
    log(f"日志文件: {BASE_DIR / cfg.get('log_file', 'stock_monitor.log')}")

    if args.once:
        run_once(cfg, state)
        return

    # 写 PID 文件, 供 stop_monitor.cmd 精确停止本进程
    pid_file = BASE_DIR / "monitor.pid"
    try:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass

    while True:
        try:
            t0 = time.time()
            run_once(cfg, state)
            cost = time.time() - t0
            log(f"本轮耗时 {cost:.1f} 秒, 下次检查约 {int(interval * (1 - jitter))}-"
                f"{int(interval * (1 + jitter))} 秒后")
            time.sleep(interval * random.uniform(1 - jitter, 1 + jitter))
        except KeyboardInterrupt:
            log("已手动退出")
            break
        except Exception as e:
            log(f"本轮异常(将在下轮重试): {e}")
            time.sleep(interval)

    try:
        pid_file.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    main()
