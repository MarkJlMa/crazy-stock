# 聚宽(JQData) vs PTrade API 对比文档

> 本文档详细对比聚宽量化平台API与PTrade量化平台API的差异，帮助开发者在两个平台间进行策略迁移。

---

## 目录

- [平台概述对比](#平台概述对比)
- [代码格式差异](#代码格式差异)
- [策略框架对比](#策略框架对比)
- [股票代码格式对比](#股票代码格式对比)
- [数据获取函数对比](#数据获取函数对比)
- [交易函数对比](#交易函数对比)
- [持仓与账户信息对比](#持仓与账户信息对比)
- [定时任务对比](#定时任务对比)
- [技术指标对比](#技术指标对比)
- [其他差异](#其他差异)
- [策略迁移指南](#策略迁移指南)

---

## 平台概述对比

| 特性 | 聚宽(JQData) | PTrade |
|------|-------------|--------|
| **部署方式** | 本地/云端 | 券商机房托管 |
| **实盘支持** | 需对接券商 | 直接实盘 |
| **数据源** | JQData数据库 | 券商行情源 |
| **Python版本** | 3.6+ | 3.5/3.11(券商不同) |
| **最小粒度** | 分钟级 | Tick级(3秒) |
| **网络环境** | 可联网 | 内网隔离 |
| **第三方库** | 可pip安装 | 仅内置库 |
| **适用场景** | 研究、回测、模拟 | 实盘交易 |

---

## 代码格式差异

### 全局变量

| 平台 | 全局变量对象 | 示例 |
|------|-------------|------|
| 聚宽 | `g` | `g.security = '000001.XSHE'` |
| PTrade | `g` | `g.security = '000001.SZ'` |

两者都使用 `g` 作为全局变量对象，用法基本相同。

### 日志输出

| 平台 | 日志函数 | 示例 |
|------|---------|------|
| 聚宽 | `print()` / `log.info()` | `print("日志内容")` |
| PTrade | `log.info()` / `log.warn()` / `log.error()` | `log.info("日志内容")` |

---

## 策略框架对比

### 初始化函数

两者框架结构基本相同：

```python
# 聚宽
def initialize(context):
    g.security = '000001.XSHE'
    set_benchmark('000300.XSHG')

# PTrade
def initialize(context):
    g.security = '000001.SZ'
    set_universe(g.security)  # PTrade需要设置股票池
    set_benchmark('000300.SS')
```

**主要差异**：
- PTrade必须调用 `set_universe()` 设置股票池
- 聚宽的 `set_benchmark()` 是可选的

### 盘前函数

| 平台 | 函数名 | 执行时间 |
|------|--------|---------|
| 聚宽 | `before_trading_start(context)` | 每交易日9:00前 |
| PTrade | `before_trading_start(context, data)` | 回测8:30，交易9:10 |

**差异**：
- PTrade多一个 `data` 参数（保留字段，暂无数据）

### 盘中函数

| 平台 | 函数名 | 参数 |
|------|--------|------|
| 聚宽 | `handle_data(context, data)` | context, data |
| PTrade | `handle_data(context, data)` | context, data |

**data对象差异**：

| 特性 | 聚宽 | PTrade |
|------|------|--------|
| 访问方式 | `data[security]` | `data[security]` |
| 属性访问 | `data[security].close` | `data[security].close` 或 `data[security].price` |
| 字典方式 | `data[security]['close']` | 支持 |

### 盘后函数

| 平台 | 函数名 | 执行时间 |
|------|--------|---------|
| 聚宽 | `after_trading_end(context)` | 每交易日15:30后 |
| PTrade | `after_trading_end(context, data)` | 每交易日15:30 |

### Tick级别函数（PTrade特有）

```python
# PTrade支持tick级别交易
def tick_data(context, data):
    # data包含tick、order、transcation
    current_price = eval(data[security]['tick']['bid_grp'][0])[1][0]
    order_tick(security, 100, 1)
```

聚宽不支持tick级别交易。

---

## 股票代码格式对比

### 代码后缀差异

| 市场 | 聚宽格式 | PTrade格式 |
|------|---------|-----------|
| 上海证券交易所 | `.XSHG` | `.SS` |
| 深圳证券交易所 | `.XSHE` | `.SZ` |
| 中金所期货 | `.CCFX` | `.CCFX` |
| 上期所期货 | `.XSGE` | `.XSGE` |
| 大商所期货 | `.XDCE` | `.XDCE` |
| 郑商所期货 | `.XZCE` | `.XZCE` |

### 示例对比

| 标的 | 聚宽代码 | PTrade代码 |
|------|---------|-----------|
| 平安银行 | `000001.XSHE` | `000001.SZ` |
| 恒生电子 | `600570.XSHG` | `600570.SS` |
| 沪深300 | `000300.XSHG` | `000300.SS` |
| 上证50 | `000016.XSHG` | `000016.SS` |

### 代码转换函数

```python
def jq_to_ptrade(code):
    """聚宽代码转PTrade代码"""
    return code.replace('.XSHG', '.SS').replace('.XSHE', '.SZ')

def ptrade_to_jq(code):
    """PTrade代码转聚宽代码"""
    return code.replace('.SS', '.XSHG').replace('.SZ', '.XSHE')
```

---

## 数据获取函数对比

### 获取历史行情

#### 聚宽：`get_price()`

```python
# 聚宽
df = get_price('000001.XSHE', 
               start_date='2020-01-01', 
               end_date='2020-12-31',
               frequency='daily',
               fields=['open', 'close', 'high', 'low', 'volume'])

# 或使用count
df = get_price('000001.XSHE', 
               end_date='2020-12-31',
               count=100,
               frequency='daily')
```

#### PTrade：`get_price()` / `get_history()`

```python
# PTrade - get_price (指定日期范围)
df = get_price('000001.SZ', 
               start_date='20200101',  # 格式不同
               end_date='20201231',
               frequency='1d',          # 频率格式不同
               fields=['open', 'close'])

# PTrade - get_history (最近N条)
df = get_history(100, 
                 frequency='1d', 
                 field='close', 
                 security_list='000001.SZ')
```

### 参数差异对比

| 参数 | 聚宽 | PTrade |
|------|------|--------|
| 日期格式 | 'YYYY-MM-DD' | 'YYYYMMDD' 或 'YYYY-MM-DD' |
| 日线频率 | 'daily' / '1d' | '1d' |
| 分钟频率 | '1m' / '5m' | '1m' / '5m' |
| 周线 | 'weekly' / '1w' | '1w' / 'weekly' |
| 月线 | 'monthly' / '1M' | 'mo' / 'monthly' |
| 复权参数 | `fq='pre'/'post'/'none'` | `fq='pre'/'post'/None` |

### 获取历史数据返回格式

| 场景 | 聚宽 | PTrade |
|------|------|--------|
| 单股票单字段 | DataFrame | DataFrame |
| 单股票多字段 | DataFrame | DataFrame |
| 多股票单字段 | DataFrame (列索引为股票代码) | DataFrame (含code列) |
| 多股票多字段 | DataFrame (多层列索引) | DataFrame (含code列) |

### 获取交易日历

#### 聚宽

```python
# 获取交易日列表
trade_days = get_trade_days(start_date='2020-01-01', 
                            end_date='2020-12-31')

# 获取所有交易日
all_days = get_all_trade_days()

# 判断是否交易日
is_trading = is_trading_day('2020-01-01')
```

#### PTrade

```python
# 获取指定范围交易日
trade_days = get_trade_days(start_date='2020-01-01', 
                             end_date='2020-12-31')

# 获取所有交易日
all_days = get_all_trades_days()

# 获取前后N天交易日
prev_day = get_trading_day(-1)
next_day = get_trading_day(1)
```

### 获取股票列表

#### 聚宽

```python
# 获取所有A股
stocks = get_all_securities(types=['stock'])

# 获取指数成分股
stocks = get_index_stocks('000300.XSHG')

# 获取行业股票
stocks = get_industry_stocks('C27')

# 获取概念股票
stocks = get_concept_stocks('GN287')
```

#### PTrade

```python
# 获取A股列表
stocks = get_Ashares()

# 获取指数成分股
stocks = get_index_stocks('000300.SS')

# 获取行业股票
stocks = get_industry_stocks('A01000.XBHS')
```

### 获取财务数据

#### 聚宽

```python
# 聚宽使用query方式
q = query(valuation.pe_ratio, valuation.pb_ratio
         ).filter(valuation.code == '000001.XSHE')
df = get_fundamentals(q, statDate='2020q1')

# 或使用快捷方式
df = get_fundamentals(query(valuation).filter(valuation.code.in_(['000001.XSHE'])))
```

#### PTrade

```python
# PTrade使用表名和字段名
df = get_fundamentals('000001.SZ', 'balance_statement', 'total_assets')
```

### 获取实时行情

#### 聚宽

```python
# 获取实时行情（需要订阅）
df = get_current_data(['000001.XSHE', '600570.XSHG'])
```

#### PTrade

```python
# 获取行情快照
snapshot = get_snapshot('000001.SZ')

# 获取档位价格
gear_price = get_gear_price('000001.SZ')

# 获取逐笔委托
entrust = get_individual_entrust('000001.SZ')

# 获取逐笔成交
trans = get_individual_transaction('000001.SZ')
```

---

## 交易函数对比

### 按数量下单

#### 聚宽

```python
# 买入100股
order('000001.XSHE', 100)

# 卖出100股
order('000001.XSHE', -100)

# 限价买入
order('000001.XSHE', 100, LimitPrice(10.5))
```

#### PTrade

```python
# 买入100股
order('000001.SZ', 100)

# 卖出100股
order('000001.SZ', -100)

# 限价买入
order('000001.SZ', 100, limit_price=10.5)
```

**差异**：
- 聚宽使用 `LimitPrice()` 对象
- PTrade直接使用 `limit_price` 参数

### 目标数量下单

#### 聚宽

```python
# 调整持仓到1000股
order_target('000001.XSHE', 1000)

# 清仓
order_target('000001.XSHE', 0)
```

#### PTrade

```python
# 调整持仓到1000股
order_target('000001.SZ', 1000)

# 清仓
order_target('000001.SZ', 0)
```

两者用法相同。

### 按价值下单

#### 聚宽

```python
# 买入10000元
order_value('000001.XSHE', 10000)

# 调整持仓市值到10000元
order_target_value('000001.XSHE', 10000)
```

#### PTrade

```python
# 买入10000元
order_value('000001.SZ', 10000)

# 调整持仓市值到10000元
order_target_value('000001.SZ', 10000)
```

两者用法相同。

### 市价单

#### 聚宽

```python
# 聚宽市价单
order('000001.XSHE', 100, MarketOrderStyle())
```

#### PTrade

```python
# PTrade市价单（支持多种类型）
order_market('000001.SZ', 100, market_type=4)  # 最优五档即时成交
```

**PTrade市价类型**：
| market_type | 说明 |
|-------------|------|
| 1 | 对手方最优价格 |
| 2 | 本方最优价格 |
| 3 | 即时成交剩余撤销 |
| 4 | 最优五档即时成交剩余撤销 |
| 5 | 全额成交或撤销 |

### 撤单

#### 聚宽

```python
# 撤销指定订单
cancel_order(order_id)
```

#### PTrade

```python
# 撤销指定订单
cancel_order(order_id)

# 批量撤单
cancel_order_ex([order_id1, order_id2])
```

### 获取订单信息

| 功能 | 聚宽 | PTrade |
|------|------|--------|
| 获取未完成订单 | `get_open_orders()` | `get_open_orders()` |
| 获取所有订单 | `get_orders()` | `get_orders()` |
| 获取指定订单 | `get_order(order_id)` | `get_order(order_id)` |
| 获取当日成交 | `get_trades()` | `get_trades()` |

---

## 持仓与账户信息对比

### 获取持仓

#### 聚宽

```python
# 获取所有持仓
positions = context.portfolio.positions

# 获取指定股票持仓
position = context.portfolio.positions['000001.XSHE']

# 持仓数量
amount = position.total_amount

# 可用数量
available = position.closeable_amount

# 持仓成本
cost = position.avg_cost
```

#### PTrade

```python
# 获取所有持仓
positions = get_all_positions()

# 获取指定股票持仓
position = get_position('000001.SZ')

# 持仓数量
amount = position.amount

# 可用数量
available = position.enable_amount

# 持仓成本
cost = position.cost_basis
```

### 属性名称对比

| 属性 | 聚宽 | PTrade |
|------|------|--------|
| 持仓数量 | `total_amount` | `amount` |
| 可用数量 | `closeable_amount` | `enable_amount` |
| 持仓成本 | `avg_cost` | `cost_basis` |
| 标的代码 | `security` | `sid` |

### 获取账户信息

#### 聚宽

```python
# 总资产
total_value = context.portfolio.total_value

# 可用资金
cash = context.portfolio.available_cash

# 持仓市值
market_value = context.portfolio.positions_value

# 初始资金
starting_cash = context.portfolio.starting_cash
```

#### PTrade

```python
# 总资产
total_value = context.portfolio.total_value

# 可用资金
cash = context.portfolio.cash

# 初始资金
starting_cash = context.portfolio.starting_cash
```

### 属性名称对比

| 属性 | 聚宽 | PTrade |
|------|------|--------|
| 可用资金 | `available_cash` | `cash` |
| 持仓市值 | `positions_value` | - |
| 持仓字典 | `positions` | `positions` |

---

## 定时任务对比

### 聚宽：`run_daily()`

```python
def initialize(context):
    # 每天开盘前执行
    run_daily(before_market_open, time='before_open')
    
    # 每天收盘后执行
    run_daily(after_market_close, time='after_close')
    
    # 指定时间执行
    run_daily(scheduled_func, time='14:30')

def before_market_open(context):
    log.info("开盘前执行")

def after_market_close(context):
    log.info("收盘后执行")
```

### PTrade：`run_daily()` / `run_interval()`

```python
def initialize(context):
    # 指定时间执行
    run_daily(context, scheduled_func, time='14:30')
    
    # 按间隔执行（秒）
    run_interval(context, interval_func, seconds=10)

def scheduled_func(context):
    log.info("定时执行")

def interval_func(context):
    log.info("间隔执行")
```

**差异**：
- 聚宽支持 `time='before_open'` 和 `time='after_close'`
- PTrade需要指定具体时间，如 `'9:30'`
- PTrade支持 `run_interval()` 按秒级间隔执行

---

## 技术指标对比

### 聚宽

聚宽没有内置技术指标函数，需要自己实现或使用第三方库：

```python
# 使用talib
import talib

close = get_price('000001.XSHE', count=100, fields='close')['close']
macd, signal, hist = talib.MACD(close.values)
```

### PTrade

PTrade内置技术指标函数：

```python
# MACD
macd_data = get_MACD('000001.SZ', fastperiod=12, slowperiod=26, signalperiod=9)

# KDJ
kdj_data = get_KDJ('000001.SZ', n=9, m=3, weight=3)

# RSI
rsi_data = get_RSI('000001.SZ', n=14)

# CCI
cci_data = get_CCI('000001.SZ', n=14)
```

---

## 其他差异

### 滑点设置

#### 聚宽

```python
def initialize(context):
    # 固定滑点
    set_slippage(FixedSlippage(0.02))
    
    # 比例滑点
    set_slippage(PriceRelatedSlippage(0.002))
```

#### PTrade

```python
def initialize(context):
    # 固定滑点
    set_fixed_slippage(fixedslippage=0.02)
    
    # 比例滑点
    set_slippage(slippage=0.002)
```

### 佣金设置

#### 聚宽

```python
def initialize(context):
    # 股票佣金
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, 
                             open_commission=0.0003, close_commission=0.0003,
                             close_commission_today=0), type='stock')
```

#### PTrade

```python
def initialize(context):
    # 股票佣金
    set_commission(commission_ratio=0.0003, min_commission=5.0, type='STOCK')
```

### 基准设置

#### 聚宽

```python
def initialize(context):
    set_benchmark('000300.XSHG')  # 沪深300
```

#### PTrade

```python
def initialize(context):
    set_benchmark('000300.SS')  # 沪深300
```

### 底仓设置

#### 聚宽

```python
# 聚宽在回测中通过初始持仓设置
# 需要在回测参数中配置
```

#### PTrade

```python
def initialize(context):
    pos = {
        'sid': '600570.SS',
        'amount': '1000',
        'enable_amount': '600',
        'cost_basis': '55'
    }
    set_yesterday_position([pos])
```

---

## 策略迁移指南

### 1. 股票代码转换

```python
def convert_code_jq_to_ptrade(code):
    """聚宽代码转PTrade代码"""
    return code.replace('.XSHG', '.SS').replace('.XSHE', '.SZ')

def convert_code_ptrade_to_jq(code):
    """PTrade代码转聚宽代码"""
    return code.replace('.SS', '.XSHG').replace('.SZ', '.XSHE')
```

### 2. 日期格式转换

```python
def convert_date_to_ptrade(date_str):
    """日期格式转PTrade格式"""
    # 聚宽: '2020-01-01' -> PTrade: '20200101'
    return date_str.replace('-', '')

def convert_date_to_jq(date_str):
    """日期格式转聚宽格式"""
    # PTrade: '20200101' -> 聚宽: '2020-01-01'
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
```

### 3. 数据获取函数替换

| 聚宽函数 | PTrade替换 |
|---------|-----------|
| `get_price(security, start_date, end_date)` | `get_price(security, start_date, end_date)` |
| `get_price(security, count)` | `get_history(count, security_list=security)` |
| `get_all_securities()` | `get_Ashares()` |
| `get_index_stocks(index)` | `get_index_stocks(index)` |
| `get_trade_days()` | `get_trade_days()` |

### 4. 持仓访问替换

```python
# 聚宽
position = context.portfolio.positions['000001.XSHE']
amount = position.total_amount

# PTrade
position = get_position('000001.SZ')
amount = position.amount
```

### 5. 交易函数替换

```python
# 聚宽限价单
order('000001.XSHE', 100, LimitPrice(10.5))

# PTrade限价单
order('000001.SZ', 100, limit_price=10.5)
```

### 6. 定时任务替换

```python
# 聚宽
run_daily(func, time='before_open')

# PTrade
run_daily(context, func, time='9:10')
```

---

## 完整策略迁移示例

### 聚宽策略

```python
# 聚宽双均线策略
def initialize(context):
    g.security = '000001.XSHE'
    set_benchmark('000300.XSHG')
    g.short_window = 5
    g.long_window = 20

def handle_data(context, data):
    # 获取历史数据
    prices = get_price(g.security, count=g.long_window, 
                       fields='close')['close']
    
    short_ma = prices[-g.short_window:].mean()
    long_ma = prices[-g.long_window:].mean()
    
    position = context.portfolio.positions.get(g.security, None)
    
    if short_ma > long_ma and (position is None or position.total_amount == 0):
        order_value(g.security, context.portfolio.available_cash * 0.95)
        log.info('买入')
    elif short_ma < long_ma and position and position.total_amount > 0:
        order_target(g.security, 0)
        log.info('卖出')
```

### PTrade策略

```python
# PTrade双均线策略
def initialize(context):
    g.security = '000001.SZ'
    set_universe(g.security)
    set_benchmark('000300.SS')
    g.short_window = 5
    g.long_window = 20

def handle_data(context, data):
    # 获取历史数据
    prices = get_history(g.long_window, '1d', 'close', 
                         security_list=g.security)
    
    short_ma = prices['close'][-g.short_window:].mean()
    long_ma = prices['close'][-g.long_window:].mean()
    
    position = get_position(g.security)
    
    if short_ma > long_ma and position.amount == 0:
        order_value(g.security, context.portfolio.cash * 0.95)
        log.info('买入')
    elif short_ma < long_ma and position.amount > 0:
        order_target(g.security, 0)
        log.info('卖出')
```

---

## 总结

### 主要差异点

1. **股票代码格式**：聚宽使用 `.XSHG/.XSHE`，PTrade使用 `.SS/.SZ`
2. **日期格式**：聚宽使用 `'YYYY-MM-DD'`，PTrade支持 `'YYYYMMDD'`
3. **数据获取**：聚宽 `get_price()` 更灵活，PTrade区分 `get_price()` 和 `get_history()`
4. **持仓访问**：聚宽通过 `context.portfolio.positions`，PTrade通过 `get_position()`
5. **限价单**：聚宽使用 `LimitPrice()` 对象，PTrade使用 `limit_price` 参数
6. **技术指标**：聚宽需自行实现，PTrade内置函数
7. **Tick交易**：PTrade支持tick级别，聚宽不支持
8. **定时任务**：聚宽支持 `before_open/after_close`，PTrade需指定具体时间

### 迁移建议

1. 先完成股票代码格式转换
2. 检查数据获取函数的参数格式
3. 修改持仓访问方式
4. 调整限价单语法
5. 测试定时任务执行时间
6. 验证技术指标计算结果

---

> 文档版本：1.0  
> 更新日期：2026-05-10
