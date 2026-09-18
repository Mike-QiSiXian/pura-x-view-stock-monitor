# Pura X View 补货监控（pura-x-view-stock-monitor）

监控华为商城 **HUAWEI Pura X View 12GB+256GB 零度白（白色，¥5999）** 的库存，
补货时第一时间提醒；同时提供云端检查（电脑关机也能查）。

> 说明：本工具只做「监控 → 提醒 → 秒开下单页」，**不做自动登录、不代替你点击下单/支付**。
> 原因：华为商城对脚本自动下单有强风控（滑块/人脸验证），自动提交不仅成功率低，
> 还可能导致账号被限制购买。

---

## 一、功能

| 能力 | 说明 |
|---|---|
| 本机高频监控 | 每 36~54 秒一轮（45 秒 + 20% 随机抖动防风控），后台无窗口运行 |
| 云端定时检查 | GitHub Actions 每 10 分钟检查一次（由外部定时器 cron-job.org 触发） |
| 五路提醒 | 蜂鸣 + 系统弹窗 + 自动打开下单页 + Server酱(微信) + 自定义 webhook |
| 状态去重 | 只在「无货 → 有货」时提醒，不会反复轰炸 |
| 秒开下单页 | 直接打开已预选「零度白 · 12GB+256GB」的商品页，点「立即购买」即可 |

## 二、原理（为什么必须用无头浏览器）

华为商城 WAF 会校验客户端指纹，直接模拟 HTTP 请求一律返回
`{"info":"不支持当前客户端","resultCode":"50017"}`（改 UA / sec-fetch / Cookie 均无效，
疑似 TLS 指纹校验）。因此改为：用**无头浏览器真实加载商品页**，监听页面自身发出的
`querySkuInventoryV2` 接口响应——这是权威的实时库存数据。

> 京东端不可监控：旧的库存接口 `c0.3.cn/stock` 已下线（域名全球解析失败），新接口需要签名。

## 三、文件说明

| 文件 | 作用 |
|---|---|
| `monitor.py` | 本机监控主程序（轮询、判定、报警、日志、单实例保护） |
| `vmall_api.js` | 无头浏览器监听助手：加载商品页并抓取库存响应，抓到即提前退出 |
| `config.json` | 配置：监控目标、SKU、间隔、提醒开关 |
| `run_monitor.cmd` | 前台运行（可看日志，Ctrl+C 停止） |
| `run_monitor_hidden.cmd` | 后台无窗口运行（推荐，日志写入 `stock_monitor.log`） |
| `stop_monitor.cmd` | 停止全部监控实例 |
| `stock_state.json` | 库存状态，用于跨次运行去重（云端会回写本文件） |
| `SKU颜色对照表.txt` | 颜色/容量 与 SKU 编码的对照（含深链接参数说明） |
| `云端定时器配置说明.txt` | cron-job.org 触发 GitHub Actions 的完整配置步骤 |
| `本地运维备忘.txt` | 本机 git / 沙箱环境踩坑记录与恢复步骤 |
| `.github/workflows/stock-check.yml` | 云端检查工作流（`--once` 单轮检查后退出） |

## 四、SKU 对照（12GB+256GB ¥5999）

| SKU 编码 | 颜色 |
|---|---|
| 2601010634025 | 幻夜黑 |
| **2601010634026** | **零度白（白）← 当前监控目标** |
| 2601010634027 | 跃影红 |
| 2601010634028 | 亚麻灰 |

512GB（¥6999）为 `...029~032`，1TB（¥8499）为 `...033~036`，颜色顺序相同。
国补版为独立编码 `...301~304`（销售方：中邮普泰通信服务有限公司（国补））。

## 五、本机运行

```
# 1) 依赖（首次）
pip install requests
# 无头浏览器：使用本机已安装的 Edge / Chrome（自动探测），无需额外下载
# Node 依赖：playwright-core（见 config.json 的 node_modules_path）

# 2) 后台启动（无窗口）
双击 run_monitor_hidden.cmd

# 3) 查看运行情况
stock_monitor.log       # 每轮结果与耗时

# 4) 停止
双击 stop_monitor.cmd
```

调试用：

```
python monitor.py --once         # 只检查一轮
python monitor.py --test-alert   # 测试提醒链路（蜂鸣/弹窗/开页面/推送）
python monitor.py --force        # 忽略单实例保护强制启动
```

## 六、云端检查

`monitor.py --once` 由 GitHub Actions 执行，库存状态回写 `stock_state.json`，
提醒通过 Server酱推送（SendKey 存在仓库 Secrets：`SERVERCHAN_SENDKEY`，不入库）。

GitHub 对 `schedule` 触发有严重节流（实测被压到约 5 次/天），因此真正的
10 分钟频率由外部定时器 **cron-job.org** 调 GitHub API 触发 `workflow_dispatch`
实现，配置步骤见 `云端定时器配置说明.txt`。

## 七、配置示例（config.json）

```json
{
  "interval_seconds": 45,
  "jitter_ratio": 0.2,
  "targets": [
    {
      "name": "华为商城 Pura X View 12+256 零度白(白色)",
      "type": "vmall",
      "enabled": true,
      "prd_url": "https://item.vmall.com/product/comdetail/index.html?prdId=10086683896486",
      "open_url": "https://item.vmall.com/product/comdetail/index.html?prdId=10086683896486&sbomCode=2601010634026",
      "wait_ms": 12000,
      "sku_codes": ["2601010634026"]
    }
  ]
}
```

> `sbomCode` 参数可让页面直接预选指定颜色与容量（实测有效；`skuId` / `skuCode` 参数无效）。

## 八、常见问题

- **弹 cmd 黑框**：已在 `monitor.py` 中为子进程加 `CREATE_NO_WINDOW` 修复。
- **后台没有日志**：早期版本 `log()` 未落盘导致静默，现已改为模块级 `LOG_FILE`。
- **重复启动**：有单实例保护（`monitor.pid` + 进程存活检测），重复启动会自行退出。
- **git 推送失败（返回 128 且无输出）**：本机沙箱环境下 `git-remote-https.exe` 会崩溃，
  已固化 `git config http.version HTTP/1.1` 规避；详见 `本地运维备忘.txt`。
- **收不到微信提醒**：检查仓库 Secrets 里的 `SERVERCHAN_SENDKEY` 是否有效。

## 九、免责声明

仅用于个人购机时的库存提醒，请遵守商城用户协议，勿用于批量抢购或转售。
