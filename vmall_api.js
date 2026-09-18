// vmall 库存监听助手
// 原理: 华为商城 WAF 校验客户端指纹, 模拟请求会被拒(50017)。
//       本脚本用无头浏览器加载商品页, 监听页面自身发出的 querySkuInventoryV2 库存响应(权威实时数据)。
// 用法: node vmall_api.js <商品页URL> [等待毫秒, 默认15000]
// 输出: 单行 JSON { "inventory": {"skuCode": 数量, ...} }
// 依赖: playwright-core + 本机 Edge(自动探测) 或 playwright 安装的 Chromium
const { chromium } = require("playwright-core");
const fs = require("fs");

const CANDIDATE_EDGE = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
];

(async () => {
  const [prdUrl, waitMsArg] = process.argv.slice(2);
  const waitMs = Number(waitMsArg) || 15000;
  const exe = CANDIDATE_EDGE.find((p) => fs.existsSync(p));
  const launchOpts = exe
    ? { executablePath: exe, headless: true }
    : { headless: true };

  const browser = await chromium.launch(launchOpts);
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    locale: "zh-CN",
  });

  const inventory = {};
  let resolveDone;
  const done = new Promise((res) => (resolveDone = res));
  page.on("response", async (resp) => {
    try {
      if (!/querySkuInventoryV2/.test(resp.url())) return;
      const d = await resp.json();
      for (const it of d.inventoryReqVOs || [])
        inventory[it.skuCode] = it.inventoryQty;
      if (Object.keys(inventory).length && resolveDone) resolveDone(true);
    } catch (e) {}
  });

  try {
    await page.goto(prdUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  } catch (e) {
    console.log(JSON.stringify({ error: "NAV:" + String(e).slice(0, 120) }));
    await browser.close();
    process.exit(0);
  }
  // 抓到库存响应就立刻返回(通常 5-10 秒), 抓不到则等满 waitMs
  await Promise.race([done, page.waitForTimeout(waitMs)]);
  await page.waitForTimeout(1000);
  console.log(JSON.stringify({ inventory }));
  await browser.close();
})();
