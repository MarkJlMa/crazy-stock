---
name: jq2ptrade
description: |
  聚宽(JQData)策略转PTrade策略转换工具。将聚宽平台的量化策略代码转换为PTrade平台兼容代码。
  触发关键词：聚宽转ptrade、jq转ptrade、转换策略、joinquant转ptrade、jq2ptrade
metadata:
  openclaw:
    emoji: "🔄"
---

# 聚宽转PTrade策略转换 Skill

## 概述

本Skill用于将聚宽(JQData)平台的量化策略代码转换为PTrade平台兼容代码。

**参考文档**（位于 `reference/` 目录）：
- 聚宽API文档：`reference/JoinQuant_API_Documentation.md`
- PTrade API文档：`reference/Ptrade_API_Documentation.md`
- API对比文档：`reference/JoinQuant_vs_PTrade_API_Comparison.md`

---

## 一、核心转换规则

### 1.1 股票代码格式转换

| 聚宽格式 | PTrade格式 | 说明 |
|---------|-----------|------|
| `.XSHG` | `.SS` | 上海交易所 |
| `.XSHE` | `.SZ` | 深圳交易所 |

**转换函数**：
```python
def convert_code_jq_to_ptrade(code):
    """聚宽代码转PTrade代码"""
    if isinstance(code, str):
        return code.replace('.XSHG', '.SS').replace('.XSHE', '.SZ')
    elif isinstance(code, list):
        return [c.replace('.XSHG', '.SS').replace('.XSHE', '.SZ') for c in code]
    return code
```

### 1.2 策略框架转换

| 聚宽 | PTrade | 说明 |
|------|--------|------|
| `initialize(context)` | `initialize(context)` | 相同 |
| `handle_data(context, data)` | `handle_data(context, data)` | 相同 |
| `before_trading_start(context)` | `before_trading_start(context, data)` | PTrade多data参数 |
| `after_trading_end(context)` | `after_trading_end(context, data)` | PTrade多data参数 |
| `tick_data`不支持 | `tick_data(context, data)` | PTrade特有 |

**必须添加**：
```python
def initialize(context):
    set_universe(g.security)  # PTrade必须设置股票池
```

### 1.3 数据获取函数转换

| 聚宽函数 | PTrade函数 | 说明 |
|---------|-----------|------|
| `get_price(security, count=N, frequency='daily')` | `get_history(N, '1d', field, security_list=security)` | 获取最近N条 |
| `get_price(security, start_date, end_date)` | `get_price(security, start_date, end_date)` | 日期范围获取 |
| `attribute_history(security, count, unit, fields)` | `get_history(count, unit, field, security_list=security)` | 历史数据 |
| `history(count, unit, field, security_list)` | `get_history(count, unit, field, security_list)` | 历史数据 |
| `get_all_securities(['stock'])` | `get_Ashares()` | 获取A股列表 |
| `get_index_stocks(index)` | `get_index_stocks(index)` | 指数成分股（需转换代码格式） |
| `get_trade_days(start, end)` | `get_trade_days(start, end)` | 交易日列表 |
| `get_fundamentals(query)` | `get_fundamentals(security, table, field)` | 财务数据（语法不同） |

**frequency/unit参数转换**：

| 聚宽 | PTrade |
|------|--------|
| `'daily'` / `'1d'` | `'1d'` |
| `'minute'` / `'1m'` | `'1m'` |
| `'5m'` | `'5m'` |
| `'weekly'` / `'1w'` | `'1w'` |
| `'monthly'` / `'1M'` | `'mo'` |

### 1.4 持仓访问转换

| 聚宽方式 | PTrade方式 |
|---------|-----------|
| `context.portfolio.positions['code']` | `get_position('code')` |
| `position.total_amount` | `position.amount` |
| `position.closeable_amount` | `position.enable_amount` |
| `position.avg_cost` | `position.cost_basis` |
| `position.security` | `position.sid` |
| `context.portfolio.available_cash` | `context.portfolio.cash` |
| `context.portfolio.positions_value` | 需自行计算 |

### 1.5 交易函数转换

| 聚宽语法 | PTrade语法 |
|---------|-----------|
| `order(code, 100)` | `order(code, 100)` |
| `order(code, 100, LimitPrice(10.5))` | `order(code, 100, limit_price=10.5)` |
| `order(code, 100, MarketOrderStyle())` | `order_market(code, 100, market_type=4)` |
| `order_target(code, 0)` | `order_target(code, 0)` |
| `order_value(code, 10000)` | `order_value(code, 10000)` |

**市价单类型**（PTrade）：

| market_type | 说明 |
|-------------|------|
| 1 | 对手方最优价格 |
| 2 | 本方最优价格 |
| 3 | 即时成交剩余撤销 |
| 4 | 最优五档即时成交剩余撤销 |
| 5 | 全额成交或撤销 |

### 1.6 定时任务转换

| 聚宽 | PTrade |
|------|--------|
| `run_daily(func, time='before_open')` | `run_daily(context, func, time='9:10')` |
| `run_daily(func, time='after_close')` | `run_daily(context, func, time='15:30')` |
| `run_daily(func, time='every_bar')` | `handle_data`中处理 |
| `run_weekly(func, weekday, time)` | `run_daily` + 条件判断 |
| `run_monthly(func, monthday, time)` | `run_daily` + 条件判断 |

**时间映射**：

| 聚宽时间表达式 | PTrade时间 |
|---------------|-----------|
| `'before_open'` | `'9:10'` |
| `'open'` | `'9:30'` |
| `'after_close'` | `'15:30'` |
| `'morning'` | `'8:00'` |
| `'night'` | `'20:00'` |

### 1.7 技术指标转换

聚宽需使用talib，PTrade内置指标函数：

```python
# 聚宽方式
import talib
macd, signal, hist = talib.MACD(close.values, fastperiod=12, slowperiod=26, signalperiod=9)

# PTrade方式
macd_data = get_MACD(security, fastperiod=12, slowperiod=26, signalperiod=9)
```

| 指标 | 聚宽(talib) | PTrade内置 |
|------|------------|-----------|
| MACD | `talib.MACD()` | `get_MACD(security)` |
| KDJ | 需自行实现 | `get_KDJ(security)` |
| RSI | `talib.RSI()` | `get_RSI(security)` |
| CCI | `talib.CCI()` | `get_CCI(security)` |

### 1.8 日志输出转换

| 聚宽 | PTrade |
|------|--------|
| `print('信息')` | `log.info('信息')` |
| `log.info('信息')` | `log.info('信息')` |
| `log.warn('警告')` | `log.warn('警告')` |
| `log.error('错误')` | `log.error('错误')` |

### 1.9 设置函数转换

| 聚宽 | PTrade |
|------|--------|
| `set_benchmark('000300.XSHG')` | `set_benchmark('000300.SS')` |
| `set_order_cost(OrderCost(...), type='stock')` | `set_commission(commission_ratio=0.0003, min_commission=5.0)` |
| `set_slippage(FixedSlippage(0.02))` | `set_fixed_slippage(fixedslippage=0.02)` |
| `set_slippage(PriceRelatedSlippage(0.002))` | `set_slippage(slippage=0.002)` |
| `set_option('use_real_price', True)` | PTrade默认使用真实价格 |

### 1.10 全局变量

两者都使用 `g` 作为全局变量对象，用法基本相同。

**注意**：PTrade中 `g` 会自动持久化，但 `__` 开头的变量不会。

---

## 二、完整转换检查清单

转换聚宽策略到PTrade时，必须检查以下项目：

- [ ] **股票代码格式**：`.XSHG` → `.SS`，`.XSHE` → `.SZ`
- [ ] **set_universe**：PTrade必须调用
- [ ] **数据获取函数**：`get_price(count=N)` → `get_history(N, ...)`
- [ ] **数据字段访问**：DataFrame列访问方式可能不同
- [ ] **持仓访问**：`context.portfolio.positions[code]` → `get_position(code)`
- [ ] **持仓属性**：`total_amount` → `amount`，`closeable_amount` → `enable_amount`
- [ ] **账户属性**：`available_cash` → `cash`
- [ ] **限价单语法**：`LimitPrice(price)` → `limit_price=price`
- [ ] **市价单语法**：`MarketOrderStyle()` → `order_market(..., market_type=4)`
- [ ] **日志输出**：`print()` → `log.info()`
- [ ] **定时任务时间**：`before_open` → `'9:10'`，`after_close` → `'15:30'`
- [ ] **定时任务参数**：PTrade需要传入context参数
- [ ] **技术指标**：使用PTrade内置函数或自行实现
- [ ] **财务数据**：`get_fundamentals`语法完全不同

---

## 三、转换示例

### 示例1：双均线策略

#### 转换前（聚宽策略）

```python
# 聚宽双均线策略
def initialize(context):
    g.security = '000001.XSHE'
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    g.short_window = 5
    g.long_window = 20

def handle_data(context, data):
    prices = get_price(g.security, count=g.long_window,
                       frequency='daily', fields='close')['close']

    short_ma = prices[-g.short_window:].mean()
    long_ma = prices[-g.long_window:].mean()

    position = context.portfolio.positions.get(g.security, None)

    if short_ma > long_ma and (position is None or position.total_amount == 0):
        order_value(g.security, context.portfolio.available_cash * 0.95)
        print('买入')
    elif short_ma < long_ma and position and position.total_amount > 0:
        order_target(g.security, 0)
        print('卖出')
```

#### 转换后（PTrade策略）

```python
# PTrade双均线策略
def initialize(context):
    g.security = '000001.SZ'                     # 代码格式转换
    set_universe(g.security)                     # 必须设置股票池
    set_benchmark('000300.SS')                   # 代码格式转换
    g.short_window = 5
    g.long_window = 20

def handle_data(context, data):
    # 数据获取方式转换
    prices = get_history(g.long_window, '1d', 'close', security_list=g.security)

    short_ma = prices['close'][-g.short_window:].mean()
    long_ma = prices['close'][-g.long_window:].mean()

    # 持仓访问方式转换
    position = get_position(g.security)

    if short_ma > long_ma and position.amount == 0:
        order_value(g.security, context.portfolio.cash * 0.95)  # available_cash -> cash
        log.info('买入')                                        # print -> log.info
    elif short_ma < long_ma and position.amount > 0:
        order_target(g.security, 0)
        log.info('卖出')
```

### 示例2：定时任务策略

#### 转换前（聚宽策略）

```python
def initialize(context):
    g.security = '000001.XSHE'
    run_daily(morning_trade, time='before_open')
    run_daily(afternoon_trade, time='after_close')

def morning_trade(context):
    log.info('开盘前执行')

def afternoon_trade(context):
    log.info('收盘后执行')
```

#### 转换后（PTrade策略）

```python
def initialize(context):
    g.security = '000001.SZ'
    set_universe(g.security)                     # 必须设置股票池
    run_daily(context, morning_trade, time='9:10')    # before_open -> '9:10'
    run_daily(context, afternoon_trade, time='15:30') # after_close -> '15:30'

def morning_trade(context):
    log.info('开盘前执行')

def afternoon_trade(context):
    log.info('收盘后执行')
```

### 示例3：限价单策略

#### 转换前（聚宽策略）

```python
def handle_data(context, data):
    price = data['000001.XSHE'].close
    order('000001.XSHE', 100, LimitPrice(price * 1.01))
```

#### 转换后（PTrade策略）

```python
def handle_data(context, data):
    price = data['000001.SZ'].close
    order('000001.SZ', 100, limit_price=price * 1.01)  # LimitPrice -> limit_price
```

### 示例4：多股票策略

#### 转换前（聚宽策略）

```python
def initialize(context):
    g.stocks = ['000001.XSHE', '600000.XSHG']
    set_universe(g.stocks)

def handle_data(context, data):
    for stock in g.stocks:
        position = context.portfolio.positions.get(stock, None)
        if position and position.closeable_amount > 0:
            order_target(stock, 0)
```

#### 转换后（PTrade策略）

```python
def initialize(context):
    g.stocks = ['000001.SZ', '600000.SS']        # 代码格式转换
    set_universe(g.stocks)

def handle_data(context, data):
    for stock in g.stocks:
        position = get_position(stock)            # 持仓访问方式转换
        if position.enable_amount > 0:            # closeable_amount -> enable_amount
            order_target(stock, 0)
```

---

## 四、PTrade特有限制

转换时需要注意PTrade的以下限制：

1. **必须设置股票池**：`set_universe()` 必须调用
2. **volume必须为100的整数倍**（1手=100股）
3. **内网隔离**：无法联网，不能pip安装第三方库
4. **价格精度**：股票0.01，可转债/ETF 0.001
5. **持久化**：全局变量 `g` 自动持久化，`__` 开头的变量不会
6. **废单处理**：废单仍返回order_id，需在回调中检查状态

---

## 五、执行流程

### 转换流程

1. **识别来源**：确认是聚宽策略代码
2. **代码转换**：按转换规则逐一替换
3. **检查清单**：使用转换检查清单验证
4. **生成代码**：输出转换后的PTrade策略
5. **保存策略**：在项目 `ptrade/` 目录下保存

### 转换优先级

1. 股票代码格式转换（最基础）
2. 添加 `set_universe()` 调用（必须）
3. 数据获取函数转换
4. 持仓访问方式转换
5. 交易函数语法转换
6. 定时任务时间格式转换
7. 日志输出方式转换

---

## 六、自动转换脚本

```python
import re

def convert_jq_to_ptrade(code):
    """将聚宽代码转换为PTrade代码"""

    # 1. 股票代码格式转换
    code = code.replace('.XSHG', '.SS')
    code = code.replace('.XSHE', '.SZ')

    # 2. 持仓属性转换
    code = code.replace('.total_amount', '.amount')
    code = code.replace('.closeable_amount', '.enable_amount')
    code = code.replace('.avg_cost', '.cost_basis')
    code = re.sub(r'context\.portfolio\.available_cash', 'context.portfolio.cash', code)

    # 3. 限价单语法转换
    code = re.sub(r'LimitPrice\(([^)]+)\)', r'limit_price=\1', code)
    code = re.sub(r'MarketOrderStyle\(\)', '', code)

    # 4. 日志输出转换
    code = re.sub(r'^(\s*)print\(', r'\1log.info(', code, flags=re.MULTILINE)

    # 5. 定时任务时间转换
    code = code.replace("time='before_open'", "time='9:10'")
    code = code.replace("time='after_close'", "time='15:30'")
    code = code.replace("time='open'", "time='9:30'")

    # 6. 持仓访问方式转换
    # context.portfolio.positions.get(code, None) -> get_position(code)
    code = re.sub(
        r"context\.portfolio\.positions\.get\(['\"]([^'\"]+)['\"],\s*None\)",
        r"get_position('\1')",
        code
    )

    # 7. 检查是否需要添加set_universe
    if 'def initialize(context):' in code and 'set_universe' not in code:
        # 在initialize函数中添加set_universe
        code = re.sub(
            r'(def initialize\(context\):[\s\S]*?)(g\.security\s*=\s*[\'"][^\'"]+[\'"])',
            r'\1\2\n    set_universe(g.security)',
            code
        )

    return code
```

---

## 七、常见问题

### Q1: get_price返回格式不同怎么办？

聚宽的 `get_price` 返回DataFrame或Panel，PTrade的 `get_history` 返回DataFrame。需要调整字段访问方式。

### Q2: 财务数据查询语法完全不同怎么办？

聚宽使用query语法，PTrade使用表名+字段名。需要完全重写财务数据查询逻辑。

### Q3: 技术指标如何处理？

优先使用PTrade内置函数（get_MACD、get_KDJ等），如果没有则使用talib自行实现。

### Q4: 定时任务参数不同怎么办？

PTrade的 `run_daily` 需要传入context参数，聚宽不需要。需要在调用时添加context。

### Q5: 如何处理PTrade没有的函数？

部分聚宽函数在PTrade中不存在，需要用其他方式实现或简化策略逻辑。

---

> 文档版本：1.0
> 更新日期：2026-05-10
