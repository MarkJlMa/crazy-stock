# JoinQuant (聚宽) API 文档

> 本文档整理自聚宽量化交易平台官方API文档，用于快速查阅和参考。

---

## 目录

- [概述](#概述)
- [快速入门](#快速入门)
- [策略框架](#策略框架)
- [定时运行函数](#定时运行函数)
- [回测引擎](#回测引擎)
- [订单处理](#订单处理)
- [风险指标](#风险指标)
- [策略设置函数](#策略设置函数)
- [数据获取函数](#数据获取函数)
- [交易函数](#交易函数)
- [融资融券函数](#融资融券函数)
- [期货专用函数](#期货专用函数)
- [其他函数](#其他函数)
- [对象说明](#对象说明)
- [Python库](#python库)
- [策略示例](#策略示例)

---

## 概述

### 平台简介

JoinQuant（聚宽）是一个量化交易平台，提供：

- **回测环境**：基于历史数据验证策略
- **模拟交易**：实盘模拟运行策略
- **研究环境**：数据分析和策略研究

### 数据覆盖

1. **股票数据**：所有A股上市公司2005年以来的行情、市值、财务数据
2. **基金数据**：600+基金行情、净值数据（ETF、LOF、分级基金等）
3. **金融期货**：中金所所有金融期货产品行情
4. **股票指数**：近600种指数行情及成分股数据
5. **行业板块**：按行业、板块选股
6. **概念板块**：按概念板块选股
7. **宏观数据**：全方位宏观数据

### 注意事项

- 所有价格单位是元
- 所有时间是北京时间（UTC+8）
- 时间都是 `datetime.datetime` 对象
- 每日结束时自动撤销所有未完成订单
- 回测和模拟中，每日下单最大数量为10000笔

---

## 快速入门

### 简单策略示例

```python
def initialize(context): 
    # 定义一个全局变量, 保存要操作的股票 
    g.security = '000001.XSHE' 
    # 运行函数 
    run_daily(market_open, time='every_bar') 
 
def market_open(context): 
    if g.security not in context.portfolio.positions: 
        order(g.security, 1000) 
    else: 
        order(g.security, -800) 
```

### 实用策略示例

```python
# 导入聚宽函数库 
import jqdata 
 
# 初始化函数，设定要操作的股票、基准等等 
def initialize(context): 
    # 定义一个全局变量, 保存要操作的股票 
    g.security = '000001.XSHE' 
    # 设定沪深300作为基准 
    set_benchmark('000300.XSHG') 
    # 开启动态复权模式(真实价格) 
    set_option('use_real_price', True) 
    # 运行函数 
    run_daily(market_open, time='every_bar') 
 
# 每个单位时间调用一次 
def market_open(context): 
    security = g.security 
    # 获取股票的收盘价 
    close_data = attribute_history(security, 5, '1d', ['close']) 
    # 取得过去五天的平均价格 
    MA5 = close_data['close'].mean() 
    # 取得上一时间点价格 
    current_price = close_data['close'][-1] 
    # 取得当前的现金 
    cash = context.portfolio.cash 
 
    # 如果上一时间点价格高出五天平均价1%, 则全仓买入 
    if current_price > 1.01*MA5: 
        order_value(security, cash) 
        log.info("Buying %s" % (security)) 
    # 如果上一时间点价格低于五天平均价, 则空仓卖出 
    elif current_price < MA5 and context.portfolio.positions[security].closeable_amount > 0: 
        order_target(security, 0) 
        log.info("Selling %s" % (security)) 
```

---

## 策略框架

### initialize（必须）

初始化方法，在整个回测、模拟实盘中最开始执行一次。

```python
def initialize(context): 
    # g为全局变量 
    g.security = "000001.XSHE"
```

**参数**：
- `context`: Context对象，存放有当前的账户/股票持仓信息

### handle_data（必须）

该函数每个单位时间会调用一次，如果按天回测则每天调用一次，如果按分钟则每分钟调用一次。

```python
def handle_data(context, data): 
    order("000001.XSHE", 100)
```

**参数**：
- `context`: Context对象
- `data`: 字典，key是股票代码，value是SecurityUnitData对象

**注意**：
- data 里面的数据是按需获取的
- data 只在这一个时间点有效，不要存起来到下一个 handle_data 再用
- 要获取回测当天的开盘价/是否停牌/涨跌停价，请使用 `get_current_data`

### before_trading_start（可选）

每天开始交易前被调用一次，启动时间为 9:20。

```python
def before_trading_start(context): 
    log.info(str(context.current_dt))
```

### after_trading_end（可选）

每天结束交易后被调用一次，启动时间为 15:10。

```python
def after_trading_end(context): 
    log.info(str(context.current_dt))
```

### process_initialize（可选）

每次模拟盘/回测进程重启时执行，在 initialize 后执行。

```python
def process_initialize(context): 
    # query 对象不能被 pickle 序列化
    g.__q = query(valuation) 
 
def handle_data(context, data): 
    get_fundamentals(g.__q)
```

### on_strategy_end（可选）

在回测、模拟交易正常结束时被调用。

```python
def on_strategy_end(context): 
    print '回测结束'
```

### after_code_changed（可选）

模拟盘恢复时发现代码已修改，则执行此函数。

```python
def after_code_changed(context): 
    g.stock = '000001.XSHE'
```

---

## 定时运行函数

### run_monthly

```python
run_monthly(func, monthday, time='open', reference_security)
```

按月运行。

**参数**：
- `func`: 一个函数，必须接受context参数
- `monthday`: 每月的第几个交易日，可以是负数
- `time`: 执行时间
- `reference_security`: 时间的参照标的

### run_weekly

```python
run_weekly(func, weekday, time='open', reference_security)
```

按周运行。

### run_daily

```python
run_daily(func, time='open', reference_security)
```

每天内何时运行。

### time 参数说明

| 值 | 说明 |
|---|------|
| 具体时间 | 24小时内任意时间，如"10:00", "01:00" |
| every_bar | 只能在run_daily中调用；按天会在每天开盘时调用一次，按分钟会在每天的每分钟运行 |
| open | 开盘时运行(等同于"9:30") |
| before_open | 早上9:00运行 |
| after_close | 下午15:30运行 |
| morning | 早上8:00运行 |
| night | 晚上20:00运行 |

time 表达式具有 'base +/-offset' 的形式，如：
- 'open-30m' 表示开盘前30分钟
- 'close+1h30m' 表示收盘后一小时三十分钟

### 示例

```python
def weekly(context): 
    print 'weekly %s %s' % (context.current_dt, context.current_dt.isoweekday()) 
 
def monthly(context): 
    print 'monthly %s %s' % (context.current_dt, context.current_dt.month) 
 
def daily(context): 
    print 'daily %s' % context.current_dt 
 
def initialize(context): 
    # 指定每月第一个交易日, 在开盘后一小时10分钟执行 
    run_monthly(monthly, 1, 'open + 1h10m') 
 
    # 指定每天收盘前10分钟运行 
    run_weekly(daily, 'close - 10m') 
 
    # 指定每天收盘后执行 
    run_daily(daily, 'after_close') 
 
    # 指定在每天的10:00运行 
    run_daily(daily, '10:00') 
 
    # 参照股指期货的时间每分钟运行一次
    run_daily(daily, 'every_bar', reference_security='IF1512.CCFX')
```

### unschedule_all

取消所有定时运行。

```python
unschedule_all()
```

---

## 回测引擎

### 回测环境

1. 回测引擎运行在Python 2.7之上
2. 支持所有Python标准库和部分常用第三方库
3. 策略运行在安全隔离的进程中

### 回测过程

1. 准备策略，选择股票池，实现handle_data函数
2. 选定回测开始和结束日期，选择初始资金、调仓间隔
3. 引擎根据股票池和日期取得股票数据，调用handle_data函数
4. 下单后根据实际交易情况处理订单
5. 可调用get_open_orders取得未完成订单，调用cancel_order取消订单
6. 可调用record()函数记录数据，以图表方式显示
7. 可调用log.info/debug/warn/error函数打印日志

### 运行频率

#### 频率：天

当选择天频率时，算法在每根日线Bar都会运行一次，即每天运行一次。

#### 频率：分钟

当选择分钟频率时，算法在每根分钟Bar都会运行一次，即每分钟运行一次。

#### 频率：Tick

当选择Tick频率时，每当新来一个Tick，算法都会被执行一次。
注意：现阶段，Tick频率只有在模拟交易时可以选择。

### 运行时间

| 时间点 | 函数 |
|-------|------|
| 开盘前(9:20) | run_monthly/run_weekly/run_daily中time='before_open'，before_trading_start |
| 盘中 | run_monthly/run_weekly/run_daily在指定交易时间执行，handle_data |
| 收盘后(15:00后半小时内) | run_monthly/run_weekly/run_daily中time='after_close'，after_trading_end |

---

## 订单处理

### 回测模式

#### 市价单

**按天回测**：
- 当"最新价+滑点"在涨跌停范围内，则进行撮合，反之撤销
- 交易价格：开盘价 + 滑点
- 最大成交量：每次下单成交量不会超过该股票当天的总成交量 × order_volume_ratio

**分钟回测**：
- 当"最新价+滑点"在涨跌停范围内，则进行撮合，反之撤销
- 交易价格：上一分钟的最后一个价格 + 滑点

#### 限价单

- 当委托价 > 最新价+滑点，按市价单模式撮合
- 当委托价 <= 最新价+滑点，则挂单，在Bar结束时按照Bar信息进行撮合

### 模拟交易模式

默认开启盘口撮合模式。

#### 使用盘口撮合

**市价单买单**：
- 根据卖单盘口进行撮合
- 优先从卖一档开始撮合，根据成交量算出加权均价

**市价单卖单**：
- 根据买单盘口进行撮合
- 优先从买一档开始撮合

### 滑点

可通过 `set_slippage` 设置滑点参数。

### 交易税费

- 券商手续费：默认万分之三，最少5元
- 印花税：卖方单边征收，默认千分之一

---

## 风险指标

### Total Returns（策略收益）

策略最终股票和现金的总价值 / 策略开始股票和现金的总价值 - 1

### Total Annualized Returns（策略年化收益）

(1 + 策略收益)^(250/策略执行天数) - 1

### Alpha（阿尔法）

α > 0：策略相对于风险，获得了超额收益
α = 0：策略相对于风险，获得了适当收益
α < 0：策略相对于风险，获得了较少收益

### Beta（贝塔）

| Beta值 | 解释 |
|--------|------|
| β < 0 | 投资组合和基准走向通常反方向 |
| β = 0 | 投资组合和基准走向没有相关性 |
| 0 < β < 1 | 投资组合和基准走向相同，但幅度更小 |
| β = 1 | 投资组合和基准走向相同，幅度贴近 |
| β > 1 | 投资组合和基准走向相同，但幅度更大 |

### Sharpe（夏普比率）

表示每承受一单位总风险，会产生多少的超额报酬。

### Sortino（索提诺比率）

表示每承担一单位的下行风险，将会获得多少超额回报。

### Max Drawdown（最大回撤）

描述策略可能出现的最糟糕的情况，最极端可能的亏损情况。

### 胜率(%)

盈利次数 / 总交易次数

### 盈亏比

总盈利额 / 总亏损额

---

## 策略设置函数

### set_benchmark - 设置基准

```python
set_benchmark(security)
```

设置策略的比较基准，默认为沪深300指数。

**参数**：
- `security`: 股票/指数/ETF代码

**示例**：
```python
set_benchmark('600000.XSHG')
```

### set_order_cost - 设置佣金/印花税

```python
set_order_cost(cost, type, ref=None)
```

**参数**：
- `cost`: OrderCost对象
  - `open_tax`: 买入时印花税
  - `close_tax`: 卖出时印花税
  - `open_commission`: 买入时佣金
  - `close_commission`: 卖出时佣金
  - `close_today_commission`: 平今仓佣金
  - `min_commission`: 最低佣金
- `type`: 'stock'/'fund'/'index_futures'/'futures'
- `ref`: 参考代码

**示例**：
```python
# 股票类
set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
    close_commission=0.0003, close_today_commission=0, min_commission=5), 
    type='stock')

# 期货类
set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.000023,
    close_commission=0.000023, close_today_commission=0.0023, min_commission=0),
    type='index_futures')
```

### set_slippage - 设置滑点

```python
set_slippage(object)
```

**固定滑点**：
```python
set_slippage(FixedSlippage(0.02))  # 固定值
set_slippage(PriceRelatedSlippage(0.002))  # 百分比
```

默认滑点是 `PriceRelatedSlippage(0.00246)`

### set_option - 设置选项

#### 设置动态复权(真实价格)模式

```python
set_option('use_real_price', True)
```

#### 设置成交量比例

```python
set_option('order_volume_ratio', 0.25)
```

#### 设置是否开启盘口撮合模式

```python
set_option('match_with_order_book', True)  # 默认开启
```

### set_universe - 设置股票池

```python
set_universe(security_list)
```

设置history函数的默认security_list。

```python
set_universe(['000001.XSHE', '600000.XSHG'])
```

---

## 数据获取函数

### get_price - 获取历史数据

```python
get_price(security, start_date=None, end_date=None, frequency='daily',
    fields=None, skip_paused=False, fq='pre', count=None)
```

获取一支或者多只股票的行情数据。

**参数**：
- `security`: 一支股票代码或者一个股票代码的list
- `count`: 与start_date二选一，返回结果集的行数
- `start_date`: 开始时间
- `end_date`: 结束时间，默认'2015-12-31'
- `frequency`: 'Xd'/'Xm'/'daily'/'minute'
- `fields`: 行情数据字段，默认['open', 'close', 'high', 'low', 'volume', 'money']
- `skip_paused`: 是否跳过不交易日期
- `fq`: 复权选项，'pre'-前复权，None-不复权，'post'-后复权

**返回**：
- 一支股票：返回pandas.DataFrame
- 多支股票：返回pandas.Panel

**示例**：
```python
# 获取一支股票
df = get_price('000001.XSHE')
df = get_price('000001.XSHE', start_date='2015-01-01', end_date='2015-01-31',
    frequency='minute', fields=['open', 'close'])
df = get_price('000001.XSHE', count=2, end_date='2015-01-31',
    frequency='daily', fields=['open', 'close'])

# 获取多只股票
panel = get_price(get_index_stocks('000903.XSHG'))
df_open = panel['open']
```

### history - 获取历史数据（回测专用）

```python
history(count, unit='1d', field='avg', security_list=None, df=True,
    skip_paused=False, fq='pre')
```

**参数**：
- `count`: 数量，返回的结果集的行数
- `unit`: 'Xd'/'Xm'
- `field`: 数据类型
- `security_list`: 股票列表，None表示context.universe
- `df`: True返回pandas.DataFrame，False返回dict
- `skip_paused`: 是否跳过不交易日期
- `fq`: 复权选项

**示例**：
```python
h = history(5, security_list=['000001.XSHE', '000002.XSHE'])
h['000001.XSHE']  # 过去5天的每天平均价
h['000001.XSHE'][-1]  # 昨天的平均价
h.iloc[-1]  # 所有股票在昨天的平均价
```

### attribute_history - 获取历史数据（回测专用）

```python
attribute_history(security, count, unit='1d', fields=None, df=True,
    skip_paused=False, fq='pre')
```

与history类似，但第一个参数是security。

```python
close_data = attribute_history(security, 5, '1d', ['close'])
```

### get_history - 获取历史数据（通用）

```python
get_history(count, frequency='1d', field='close', security_list=None,
    fq=None, include=False)
```

### get_current_data - 获取当前数据

```python
get_current_data(security)
```

获取当天的开盘价/是否停牌/涨跌停价。

### get_trade_days - 获取交易日

```python
get_trade_days(start_date=None, end_date=None, count=None)
```

### get_all_trade_days - 获取所有交易日

```python
get_all_trade_days()
```

### get_previous_trade_date - 获取前一交易日

```python
get_previous_trade_date(date)
```

### get_next_trade_date - 获取下一交易日

```python
get_next_trade_date(date)
```

### get_all_securities - 获取所有股票信息

```python
get_all_securities(types=[], date=None)
```

**参数**：
- `types`: 类型列表，['stock']-股票，['fund']-基金，['index']-指数，['futures']-期货
- `date`: 日期，返回该日期存在的股票

**返回**：pandas.DataFrame，index为股票代码

```python
# 获取所有A股
stocks = get_all_securities(['stock'])

# 获取所有基金
funds = get_all_securities(['fund'])
```

### get_security_info - 获取股票信息

```python
get_security_info(security)
```

### get_index_stocks - 获取指数成分股

```python
get_index_stocks(index, date=None)
```

```python
# 获取沪深300成分股
stocks = get_index_stocks('000300.XSHG')
```

### get_industry_stocks - 获取行业成分股

```python
get_industry_stocks(industry, date=None)
```

```python
# 获取计算机行业股票
stocks = get_industry_stocks('I64')
```

### get_concept_stocks - 获取概念成分股

```python
get_concept_stocks(concept, date=None)
```

### get_fundamentals - 获取财务数据

```python
get_fundamentals(query_object, statDate=None)
```

```python
q = query(valuation.pe_ratio, valuation.pb_ratio
    ).filter(valuation.code == '000001.XSHE')
df = get_fundamentals(q, statDate='2020q1')
```

### get_fundamentals_continuously - 连续获取财务数据

```python
get_fundamentals_continuously(query_object, start_date, end_date)
```

---

## 交易函数

### order - 按数量下单

```python
order(security, amount, style=None)
```

**参数**：
- `security`: 股票代码
- `amount`: 数量（正数买入，负数卖出）
- `style`: 订单类型，None代表市价单

**返回**：Order对象或None

**示例**：
```python
order('000001.XSHE', 100)  # 买入100股
order('000001.XSHE', -100)  # 卖出100股
order('000001.XSHE', 100, LimitOrderStyle(10.5))  # 限价买入
```

### order_target - 目标数量下单

```python
order_target(security, amount, style=None)
```

调整持仓到目标数量。

```python
order_target('000001.XSHE', 1000)  # 调整持仓到1000股
order_target('000001.XSHE', 0)  # 清仓
```

### order_value - 按价值下单

```python
order_value(security, value, style=None)
```

按价值买卖股票。

```python
order_value('000001.XSHE', 10000)  # 买入价值10000元的股票
```

### order_target_value - 目标市值下单

```python
order_target_value(security, value, style=None)
```

调整持仓到目标市值。

```python
order_target_value('000001.XSHE', 50000)  # 调整持仓市值到50000元
```

### 订单类型

#### MarketOrderStyle - 市价单

```python
order('000001.XSHE', 100, MarketOrderStyle())
```

#### LimitOrderStyle - 限价单

```python
order('000001.XSHE', 100, LimitOrderStyle(10.5))
```

### cancel_order - 撤单

```python
cancel_order(order)
```

### get_open_orders - 获取未完成订单

```python
get_open_orders()
```

### get_order - 获取订单

```python
get_order(order_id)
```

### get_orders - 获取所有订单

```python
get_orders()
```

---

## 融资融券函数

### margin_trade - 担保品买卖

```python
margin_trade(security, amount, style=None)
```

### margincash_open - 融资买入

```python
margincash_open(security, amount, style=None)
```

### margincash_close - 卖券还款

```python
margincash_close(security, amount, style=None)
```

### marginsec_open - 融券卖出

```python
marginsec_open(security, amount, style=None)
```

### marginsec_close - 买券还券

```python
marginsec_close(security, amount, style=None)
```

### get_margincash_stocks - 获取融资标的

```python
get_margincash_stocks()
```

### get_marginsec_stocks - 获取融券标的

```python
get_marginsec_stocks()
```

---

## 期货专用函数

### order - 期货下单

```python
order(security, amount, style=None, side='long', pindex=0)
```

**参数**：
- `security`: 期货合约代码
- `amount`: 数量（手）
- `style`: 订单类型
- `side`: 'long'-多单，'short'-空单
- `pindex`: 仓位号

```python
# 开多单
order('IF1412.CCFX', 1, side='long', pindex=0)

# 开空单
order('IF1412.CCFX', 1, side='short', pindex=0)

# 平多单
order('IF1412.CCFX', -1, side='long', pindex=0)

# 平空单
order('IF1412.CCFX', -1, side='short', pindex=0)
```

### order_target - 期货目标数量下单

```python
order_target(security, amount, style=None, side='long', pindex=0)
```

```python
# 平掉空单
order_target('IF1412.CCFX', 0, side='short', pindex=1)
```

---

## 其他函数

### record - 画图函数

```python
record(**kwargs)
```

在图表上画出额外曲线。

```python
record(price=d.price, open=d.open, close=d.close)
record(price=100)  # 画一条100的直线
```

### send_message - 发送消息

```python
send_message(message, channel='weixin')
```

发送微信消息（模拟交易专用）。

```python
send_message("测试消息")
```

### log - 日志

```python
log.error(content)
log.warn(content)
log.info(content)
log.debug(content)
```

---

## 对象说明

### g - 全局对象

全局变量对象，用于存储策略中的全局变量。

```python
g.security = '600570.XSHG'
g.flag = False
```

**注意**：以'__'开头的变量为私有变量，不会被持久化保存。

### Context - 上下文对象

**主要属性**：
- `portfolio`: Portfolio对象，账户信息
- `current_dt`: 当前时间
- `universe`: 股票池

### Portfolio - 账户对象

**主要属性**：
- `cash`: 可用资金
- `positions`: 持仓字典
- `total_value`: 总资产
- `starting_cash`: 初始资金
- `positions_value`: 持仓市值
- `returns`: 收益率

### Position - 持仓对象

**主要属性**：
- `total_amount`: 持仓数量
- `closeable_amount`: 可卖数量
- `avg_cost`: 持仓成本
- `security`: 标的代码
- `price`: 当前价格
- `value`: 持仓市值
- `pnl`: 持仓盈亏

### SecurityUnitData - 行情数据对象

**主要属性**：
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量
- `money`: 成交额
- `price`: 最新价
- `high_limit`: 涨停价
- `low_limit`: 跌停价
- `paused`: 是否停牌
- `pre_close`: 前收盘价
- `factor`: 复权因子

### Order - 订单对象

**主要属性**：
- `order_id`: 订单编号
- `status`: 订单状态
- `amount`: 委托数量
- `filled`: 成交数量
- `price`: 委托价格
- `security`: 标的代码

---

## Python库

### 标准库

支持所有Python标准库，常用包括：

| 库名 | 说明 |
|------|------|
| datetime | 日期时间处理 |
| collections | 高级数据结构 |
| json | JSON处理 |
| math | 数学函数 |
| numpy | 数值计算 |
| pandas | 数据分析 |
| re | 正则表达式 |

### 第三方库

| 模块名称 | 版本 | 简介 |
|----------|------|------|
| numpy | 1.9.3 | 数值计算扩展 |
| pandas | 0.16.2 | 数据分析库 |
| scipy | 0.15.1 | 科学计算工具包 |
| sklearn | 0.18 | 机器学习模块 |
| talib | 0.4.9 | 技术分析库 |
| matplotlib | 1.4.3 | 2D绘图库 |
| seaborn | 0.6.0 | 统计数据可视化 |
| statsmodels | 0.6.1 | 统计模型 |
| requests | 2.7.0 | 网络访问 |
| jieba | 0.37 | 中文分词 |
| gensim | 0.12.2 | 文本相似度计算 |
| hmmlearn | 0.2.0 | 隐马可夫模型 |
| theano | 0.8.1 | 深度学习库 |
| xlrd | 1.0.0 | 读取Excel |
| xlwt | 1.1.2 | 写入Excel |

---

## 策略示例

### 双均线策略

```python
import jqdata 
 
def initialize(context): 
    g.security = '000001.XSHE' 
    set_benchmark('000300.XSHG') 
    set_option('use_real_price', True) 
 
def handle_data(context, data): 
    security = g.security 
    close_data = attribute_history(security, 10, '1d', ['close'], df=False) 
    ma5 = close_data['close'][-5:].mean() 
    ma10 = close_data['close'].mean() 
    cash = context.portfolio.cash 
 
    if ma5 > ma10: 
        order_value(security, cash) 
        log.info("Buying %s" % (security)) 
    elif ma5 < ma10 and context.portfolio.positions[security].closeable_amount > 0: 
        order_target(security, 0) 
        log.info("Selling %s" % (security)) 
 
    record(ma5=ma5)
    record(ma10=ma10)
```

### 均线回归策略

```python
import jqdata 
 
def initialize(context): 
    g.security = '000001.XSHE' 
    set_benchmark('000300.XSHG') 
    set_option('use_real_price', True) 
 
def handle_data(context, data): 
    security = g.security 
    close_data = attribute_history(security, 5, '1d', ['close']) 
    MA5 = close_data['close'].mean() 
    current_price = close_data['close'][-1] 
    cash = context.portfolio.cash 
 
    if current_price > 1.05*MA5: 
        order_value(security, cash) 
        log.info("Buying %s" % (security)) 
    elif current_price < 0.95*MA5 and context.portfolio.positions[security].closeable_amount > 0: 
        order_target(security, 0) 
        log.info("Selling %s" % (security)) 
    record(stock_price=current_price)
```

### 多股票持仓示例

```python
import jqdata 
 
def initialize(context): 
    g.stocks = ['000001.XSHE','000002.XSHE','000004.XSHE','000005.XSHE'] 
    set_benchmark('000300.XSHG') 
    set_option('use_real_price', True) 
 
def handle_data(context, data): 
    for security in g.stocks: 
        vwap = data[security].vwap(3) 
        price = data[security].close 
        cash = context.portfolio.cash 
 
        if price < vwap * 0.995 and context.portfolio.positions[security].closeable_amount > 0: 
            order(security, -100) 
            log.info("Selling %s" % (security)) 
        elif price > vwap * 1.005 and cash > 0: 
            order(security, 100) 
            log.info("Buying %s" % (security))
```

---

## 股票代码格式

| 市场 | 代码格式 | 示例 |
|------|----------|------|
| 上海证券交易所 | .XSHG | 600000.XSHG |
| 深圳证券交易所 | .XSHE | 000001.XSHE |
| 中金所期货 | .CCFX | IF1512.CCFX |
| 上期所期货 | .XSGE | AU1512.XSGE |
| 大商所期货 | .XDCE | M1512.XDCE |
| 郑商所期货 | .XZCE | CF1512.XZCE |

---

> 文档来源：JoinQuant（聚宽）官方API文档  
> 更新日期：2026-05-10
