# Crazy Stock | 量化策略复现与转换

[English](#english) | [中文](#中文)

---

## 中文

### 📊 项目简介

本仓库专注于在 **PTrade（国金量化交易平台）** 上复现和转换来自 **JoinQuant（聚宽）** 的各类量化交易策略。

### 🎯 主要目标

- 收集和整理聚宽平台的优质量化策略
- 将聚宽策略代码转换为PTrade兼容格式
- 提供完整的API转换文档和工具
- 帮助量化交易者实现策略跨平台迁移

### 📁 项目结构

```
crazy-stock/
├── joinquant/                    # 聚宽原始策略
│   ├── 2024年度精选策略上/         # 2024年度精选策略（上）
│   ├── 2024年度精选策略下/         # 2024年度精选策略（下）
│   ├── 2025年度精选策略/           # 2025年度精选策略
│   └── 聚宽策略2026/              # 2026年策略集合
│
├── ptrade/                       # PTrade转换后策略
│   ├── collect/                   # 收集的PTrade策略
│   │   ├── 五福3.4.py             # ETF套利策略
│   │   └── 小市值策略.py           # 小市值选股策略
│   └── convert/                   # 转换后的策略
│       └── 三驾马车策略.py         # 多策略组合
│
└── .claude/skills/               # Claude Code技能
    └── jq2ptrade/                 # 聚宽转PTrade转换工具
        ├── SKILL.md               # 转换规则文档
        ├── README.md              # 使用说明
        └── reference/             # API参考文档
            ├── JoinQuant_API_Documentation.md
            ├── Ptrade_API_Documentation.md
            └── JoinQuant_vs_PTrade_API_Comparison.md
```

### 🔧 核心转换规则

| 聚宽 | PTrade | 说明 |
|------|--------|------|
| `.XSHG` | `.SS` | 上海交易所代码 |
| `.XSHE` | `.SZ` | 深圳交易所代码 |
| `get_price(count=N)` | `get_history(N, ...)` | 历史数据获取 |
| `context.portfolio.positions[code]` | `get_position(code)` | 持仓查询 |
| `LimitPrice(price)` | `limit_price=price` | 限价单语法 |
| `print()` | `log.info()` | 日志输出 |

### 🚀 快速开始

1. **浏览策略**: 在 `joinquant/` 目录查看原始聚宽策略
2. **查看转换**: 在 `ptrade/` 目录查看转换后的PTrade策略
3. **使用工具**: 使用 `.claude/skills/jq2ptrade/` 中的转换工具

### 📖 策略类型

本仓库包含多种类型的量化策略：

- 📈 **选股策略**: 小市值、多因子、价值投资等
- 🔄 **轮动策略**: ETF轮动、行业轮动、板块轮动等
- 📊 **择时策略**: 动量择时、均线择时、波动率择时等
- ⚖️ **组合策略**: 风险平价、全天候、多策略组合等
- 🤖 **机器学习**: 因子挖掘、预测模型、智能选股等

### 📝 注意事项

1. PTrade必须调用 `set_universe()` 设置股票池
2. PTrade成交量必须为100的整数倍（1手=100股）
3. PTrade为内网环境，无法安装第三方库
4. 部分聚宽API在PTrade中不存在，需要替代实现

### 📄 许可证

MIT License

---

## English

### 📊 Project Overview

This repository focuses on reproducing and converting quantitative trading strategies from **JoinQuant (聚宽)** to **PTrade (国金量化交易平台)**.

### 🎯 Main Objectives

- Collect and organize high-quality strategies from JoinQuant platform
- Convert JoinQuant strategy code to PTrade-compatible format
- Provide comprehensive API conversion documentation and tools
- Help quantitative traders achieve cross-platform strategy migration

### 📁 Project Structure

```
crazy-stock/
├── joinquant/                    # Original JoinQuant strategies
│   ├── 2024年度精选策略上/         # 2024 Featured Strategies (Part 1)
│   ├── 2024年度精选策略下/         # 2024 Featured Strategies (Part 2)
│   ├── 2025年度精选策略/           # 2025 Featured Strategies
│   └── 聚宽策略2026/              # 2026 Strategy Collection
│
├── ptrade/                       # Converted PTrade strategies
│   ├── collect/                   # Collected PTrade strategies
│   │   ├── 五福3.4.py             # ETF arbitrage strategy
│   │   └── 小市值策略.py           # Small-cap stock selection
│   └── convert/                   # Converted strategies
│       └── 三驾马车策略.py         # Multi-strategy portfolio
│
└── .claude/skills/               # Claude Code skills
    └── jq2ptrade/                 # JoinQuant to PTrade converter
        ├── SKILL.md               # Conversion rules
        ├── README.md              # Usage guide
        └── reference/             # API reference docs
            ├── JoinQuant_API_Documentation.md
            ├── Ptrade_API_Documentation.md
            └── JoinQuant_vs_PTrade_API_Comparison.md
```

### 🔧 Core Conversion Rules

| JoinQuant | PTrade | Description |
|-----------|--------|-------------|
| `.XSHG` | `.SS` | Shanghai exchange code |
| `.XSHE` | `.SZ` | Shenzhen exchange code |
| `get_price(count=N)` | `get_history(N, ...)` | Historical data retrieval |
| `context.portfolio.positions[code]` | `get_position(code)` | Position query |
| `LimitPrice(price)` | `limit_price=price` | Limit order syntax |
| `print()` | `log.info()` | Log output |

### 🚀 Quick Start

1. **Browse Strategies**: Check original JoinQuant strategies in `joinquant/`
2. **View Conversions**: See converted PTrade strategies in `ptrade/`
3. **Use Tools**: Utilize conversion tools in `.claude/skills/jq2ptrade/`

### 📖 Strategy Types

This repository includes various types of quantitative strategies:

- 📈 **Stock Selection**: Small-cap, multi-factor, value investing, etc.
- 🔄 **Rotation**: ETF rotation, sector rotation, industry rotation, etc.
- 📊 **Market Timing**: Momentum timing, MA timing, volatility timing, etc.
- ⚖️ **Portfolio**: Risk parity, all-weather, multi-strategy portfolio, etc.
- 🤖 **Machine Learning**: Factor mining, prediction models, intelligent selection, etc.

### 📝 Notes

1. PTrade requires `set_universe()` to set stock pool
2. PTrade volume must be multiples of 100 (1 lot = 100 shares)
3. PTrade runs in isolated network, cannot install third-party libraries
4. Some JoinQuant APIs don't exist in PTrade, need alternative implementations

### 📄 License

MIT License

---

> 🔄 **JoinQuant to PTrade Converter** - Making strategy migration easier
