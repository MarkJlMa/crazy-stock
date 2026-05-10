# JoinQuant to PTrade Converter Skill

> OpenClaw Skill — 将聚宽(JQData)策略转换为PTrade策略

---

## 概述

本Skill用于将聚宽(JQData)平台的量化策略代码转换为PTrade平台兼容代码。

## 功能特性

- **自动代码转换**：股票代码格式、函数调用、属性访问等
- **完整转换规则**：覆盖数据获取、交易、持仓、定时任务等
- **转换检查清单**：确保不遗漏任何转换项
- **示例代码**：提供常见策略的转换示例

## 安装

```bash
skillhub install jq2ptrade
```

## 使用方法

**触发关键词**：`聚宽转ptrade`、`jq转ptrade`、`转换策略`、`joinquant转ptrade`、`jq2ptrade`

**示例**：
> "把这个聚宽策略转换成PTrade策略"
> "将以下JoinQuant代码转换为PTrade"
> "聚宽转ptrade，帮我转换这个双均线策略"

## 核心转换规则速查

### 股票代码

| 聚宽 | PTrade |
|------|--------|
| `.XSHG` | `.SS` |
| `.XSHE` | `.SZ` |

### 数据获取

| 聚宽 | PTrade |
|------|--------|
| `get_price(security, count=N)` | `get_history(N, ...)` |
| `attribute_history(...)` | `get_history(...)` |
| `get_all_securities(['stock'])` | `get_Ashares()` |

### 持仓访问

| 聚宽 | PTrade |
|------|--------|
| `context.portfolio.positions[code]` | `get_position(code)` |
| `total_amount` | `amount` |
| `closeable_amount` | `enable_amount` |
| `available_cash` | `cash` |

### 交易函数

| 聚宽 | PTrade |
|------|--------|
| `LimitPrice(10.5)` | `limit_price=10.5` |
| `MarketOrderStyle()` | `order_market(..., market_type=4)` |

### 定时任务

| 聚宽 | PTrade |
|------|--------|
| `time='before_open'` | `time='9:10'` |
| `time='after_close'` | `time='15:30'` |

## 转换检查清单

- [ ] 股票代码格式转换
- [ ] 添加 `set_universe()` 调用
- [ ] 数据获取函数转换
- [ ] 持仓访问方式转换
- [ ] 持仓属性名称转换
- [ ] 限价单语法转换
- [ ] 日志输出方式转换
- [ ] 定时任务时间转换

## 参考文档

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 完整转换规则和示例 |
| `reference/JoinQuant_API_Documentation.md` | 聚宽API文档 |
| `reference/Ptrade_API_Documentation.md` | PTrade API文档 |
| `reference/JoinQuant_vs_PTrade_API_Comparison.md` | API对比文档 |

## 注意事项

1. PTrade **必须**调用 `set_universe()` 设置股票池
2. PTrade volume必须为100的整数倍
3. PTrade无法联网，不能pip安装第三方库
4. PTrade价格精度：股票0.01，可转债/ETF 0.001

---

## License

MIT
