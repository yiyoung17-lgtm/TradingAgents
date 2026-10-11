# 本地 Gemini 版 TradingAgents

已安装在项目独立 `.venv` 中。Python 使用 Codex 随附的 3.12 运行时；若该运行时被移除，需要用 Python 3.11+ 重建虚拟环境。

## 填写密钥

在项目 `.env` 中填写 `GOOGLE_API_KEY`。密钥只保存在本机，不要发到聊天或提交到 Git。环境变量中的值优先于 `.env`。

## 启动

双击 `run-local.command`，或在终端运行：

```bash
cd '/Users/youngyi/Documents/ChatGPT/交易/TradingAgents'
./run-local.command
```

选择股票、分析日期及分析师。本地已配置 Gemini 3.5 Flash Lite、中文报告、研究/风险辩论各一轮、低思考级别。可在 `.env` 修改模型和参数。

先用单只股票及 market,news 分析师验证数据与成本。运行需要能够访问 Google Gemini 和行情数据服务；实际调用消耗 Gemini 额度，免费额度可能遇到限流。

报告保存在 `reports/`，缓存、CLI 偏好和研究记忆保存在 `local-data/`。请通过启动脚本运行，以使用这些本地路径。

检查命令：

```bash
./run-local.command --help
.venv/bin/python -m pip check
```

当前部署使用官方 CLI 手动研究。Gemini API 和长桥真实市场数据已单独验证。

## 数据质量保护与备用源

启动分析前会检查有效行情，以及已选新闻/基本面分析师需要的资料。行情过期、价格无效或新闻窗口无法覆盖时，会退出（状态码 2），记录在 `reports/failed/`，不会继续调用模型生成买卖结论。核心数据在工具调用中失效也会停止。FRED 和预测市场是可选资料，缺失不等于市场中性。

## 长桥数据源（已接入）

`.env` 的以下四项已设为 `longbridge`：

```dotenv
TRADINGAGENTS_VENDOR_CORE_STOCK_APIS=longbridge
TRADINGAGENTS_VENDOR_TECHNICAL_INDICATORS=longbridge
TRADINGAGENTS_VENDOR_FUNDAMENTAL_DATA=longbridge
TRADINGAGENTS_VENDOR_NEWS_DATA=longbridge
```

适配器通过已安装的 `longbridge` CLI 读取数据，复用 CLI 的本地 OAuth 登录。无需把长桥 Token 复制进项目。只调用行情、财报和新闻读取命令。

- 行情、指标和核验快照统一使用常规交易时段、不复权日线，按交易所本地日期处理。K 线按年分段；进程内缓存最多五分钟。
- 财报按长桥 `rpt_date` 报告发布日期过滤，排除分析日期之后的报告；供应商的历史修订版本不保证适合严格回测。
- 新闻仅为最近资讯样本，按 UTC 发布日期过滤，并标记实际覆盖范围，不保证覆盖整个研究窗口。没有窗口内可用新闻就停止；有部分新闻时可分析，但必须保留覆盖限制。
- 公司名称、研究记忆结算的收盘价也使用长桥。内部人交易尚未验证，明确返回不可用；宏观及预测市场仍为可选独立来源。

示例：

```bash
./run-local.command --ticker AAPL --date 2026-10-09 --analysts market,news --save --no-show
```

也可使用 `AAPL.US`、`700.HK`、`600519.SH` 等长桥符号。账户行情权限决定可访问范围。若授权失效，在终端运行 `longbridge auth login` 重新授权。CLI 路径可通过 `TRADINGAGENTS_LONGBRIDGE_CLI` 指定。

2026-10-11 完整 AAPL 示例分析成功保存到 `reports/reports/AAPL_20261011_213847/`，222 项相关测试通过。该目录的 `VALIDATION_NOTES.md` 标记了新闻报告的价格引用与行情快照之间的冲突；完整流程成功并不保证模型结论正确。

宏观资料可选：在 `.env` 添加 `FRED_API_KEY`，申请入口：https://fred.stlouisfed.org/docs/api/api_key.html 。

此前 AAPL_20261011_200122 的报告因核心数据缺失不可用；修复保留了原文件，未改写历史结论。角色提示已要求引用带日期和来源的证据；未提供持仓、资金和验证价格时，不得提出具体股数或仓位。提示约束不等于模型事实验证，正常报告仍需审阅。
