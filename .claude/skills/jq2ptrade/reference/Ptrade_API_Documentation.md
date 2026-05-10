# PTrade 量化交易 API 接口文档

> 本文档整理自 PTrade 官方 API 文档，用于快速查阅和参考。

## 目录

- [概述](#概述)
- [快速入门](#快速入门)
- [策略引擎](#策略引擎)
- [设置函数](#设置函数)
- [定时周期性函数](#定时周期性函数)
- [获取信息函数](#获取信息函数)
- [交易相关函数](#交易相关函数)
- [融资融券专用函数](#融资融券专用函数)
- [期货专用函数](#期货专用函数)
- [技术指标计算函数](#技术指标计算函数)
- [其他函数](#其他函数)
- [对象说明](#对象说明)
- [数据字典](#数据字典)
- [代码尾缀](#代码尾缀)

---

## 概述

### PTrade 简介

PTrade 是由恒生电子开发的量化交易平台，运行在券商机房，属于托管模式。主要特点：

- **稳定性高**：托管在券商机房，不受本地网络和电脑故障影响
- **速度快**：内网环境，行情和委托速度优于本地部署
- **支持品种**：股票、基金ETF、可转债(T+0)、债券、期货等
- **最小粒度**：tick级别，最小时间粒度3秒
- **行情档位**：默认可获取十档委托数据

### 支持的券商

- 国金证券
- 国盛证券
- 东莞证券
- 湘财证券
- 长江证券
- 国泰君安-海通
- 山西证券
- 申万宏源

### Python 版本

- 国金证券 PTrade：Python 3.11
- 其他券商：Python 3.5（部分函数返回格式有差异）

---

## 快速入门

### 策略基本结构

一个完整的策略需要两个必须函数：

```python
def initialize(context):
    # 初始化函数，策略启动时执行一次
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 交易函数，按周期执行
    pass
```

### 策略运行周期

| 周期 | 说明 |
|------|------|
| 日线级别 | 每天运行一次，回测15:00，交易14:50(可配) |
| 分钟级别 | 每分钟运行一次，9:30-15:00 |
| Tick级别 | 最小3秒运行一次 |

### 策略运行时间

- **盘前运行**：9:30之前，执行 `before_trading_start`
- **盘中运行**：9:31-15:00，执行 `handle_data`
- **盘后运行**：15:30，执行 `after_trading_end`

### 支持的业务类型

**回测支持**：
- 普通股票买卖（单位：股）
- 可转债买卖（单位：张，T+0）
- 融资融券担保品买卖
- 期货投机类型交易（单位：手，T+0）
- LOF基金买卖
- ETF基金买卖

**交易支持**：
- 普通股票买卖
- 可转债买卖
- 融资融券交易
- ETF申赎、套利
- 国债逆回购
- 期货投机类型交易

### 最小价差

| 标的 | 最小价差 |
|------|----------|
| 股票 | 0.01 |
| 可转债 | 0.001 |
| LOF | 0.001 |
| ETF | 0.001 |
| 国债逆回购 | 0.005 |
| 股指期货 | 0.2 |
| 国债期货 | 0.005 |

---

## 策略引擎

### initialize（必选）

策略初始化函数，仅在策略启动时执行一次。

```python
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
```

**可调用接口**：
- `set_universe` - 设置股票池
- `set_benchmark` - 设置基准
- `set_commission` - 设置佣金费率
- `set_fixed_slippage` - 设置固定滑点
- `set_slippage` - 设置滑点
- `set_volume_ratio` - 设置成交比例
- `set_limit_mode` - 设置成交数量限制模式
- `set_yesterday_position` - 设置底仓
- `set_parameters` - 设置策略配置参数
- `run_daily` - 按日周期处理
- `run_interval` - 按设定周期处理

### before_trading_start（可选）

每天开始交易前调用一次。

```python
def before_trading_start(context, data):
    log.info("盘前初始化")
```

- 回测环境：每个交易日8:30执行
- 交易环境：开启交易时立即执行，从隔日开始每天9:10执行

### handle_data（必选）

按指定周期频率运行，是策略交易的主要模块。

```python
def handle_data(context, data):
    current_price = data[g.security].price
    order(g.security, 100)
```

**参数说明**：
- `context`：Context对象，存放账户及持仓信息
- `data`：字典，key为标的代码，value为SecurityUnitData对象

### after_trading_end（可选）

每天交易结束后调用。

```python
def after_trading_end(context, data):
    log.info("盘后处理")
```

执行时间一般为15:30。

### tick_data（可选）

用于处理tick级别策略，每隔3秒执行一次。

```python
def tick_data(context, data):
    security = g.security
    current_price = eval(data[security]['tick']['bid_grp'][0])[1][0]
    if current_price > 38.19:
        order_tick(security, 100, 1)
```

**data结构**：
```python
{'股票代码': {
    'order': DataFrame/None,      # 逐笔委托
    'tick': DataFrame,           # 当前tick数据
    'transcation': DataFrame/None # 逐笔成交
}}
```

### on_order_response（可选）

委托主推回调函数，比引擎更新Order状态更快。

```python
def on_order_response(context, order_list):
    log.info(order_list)
```

**返回字段**：
- `entrust_no` - 委托编号
- `order_time` - 委托时间
- `stock_code` - 股票代码
- `amount` - 委托数量
- `price` - 委托价格
- `business_amount` - 成交数量
- `status` - 委托状态
- `order_id` - 订单编号

### on_trade_response（可选）

成交主推回调函数。

```python
def on_trade_response(context, trade_list):
    log.info(trade_list)
```

**返回字段**：
- `entrust_no` - 委托编号
- `business_time` - 成交时间
- `stock_code` - 股票代码
- `entrust_bs` - 成交方向（1-买，2-卖）
- `business_amount` - 成交数量
- `business_price` - 成交价格
- `business_balance` - 成交额

---

## 设置函数

### set_universe - 设置股票池

```python
set_universe(security_list)
```

设置或更新策略要操作的股票池。

**参数**：
- `security_list`：股票列表，支持单支或多支（list[str]/str）

```python
def initialize(context):
    g.security = ['600570.SS', '600571.SS']
    set_universe(g.security)
```

### set_benchmark - 设置基准

```python
set_benchmark(sids)
```

设置策略的比较基准，默认为沪深300指数(000300.SS)。

```python
def initialize(context):
    set_benchmark('000016.SS')  # 上证50
```

### set_commission - 设置佣金费率

```python
set_commission(commission_ratio=0.0003, min_commission=5.0, type="STOCK")
```

**参数**：
- `commission_ratio`：佣金费率，默认万分之三
- `min_commission`：最低交易佣金，默认5元
- `type`：交易类型（STOCK/ETF/LOF）

**手续费计算**：
- 手续费 = 佣金费 + 经手费
- 佣金费 = 佣金费率 × 交易总金额（不低于最低佣金）
- 经手费 = 万分之0.487 × 交易总金额

### set_fixed_slippage - 设置固定滑点

```python
set_fixed_slippage(fixedslippage=0.0)
```

设置固定滑点，成交价格 = 委托价格 ± fixedslippage/2

### set_slippage - 设置滑点比例

```python
set_slippage(slippage=0.1)
```

设置滑点比例，成交价格 = 委托价格 ± 委托价格 × slippage/2

### set_volume_ratio - 设置成交比例

```python
set_volume_ratio(volume_ratio=0.25)
```

设置回测中单笔委托的成交比例，默认0.25。

### set_limit_mode - 设置成交数量限制模式

```python
set_limit_mode(limit_mode='LIMIT')
```

**参数**：
- `'LIMIT'`：限制（默认）
- `'UNLIMITED'`：不限制

### set_yesterday_position - 设置底仓

```python
set_yesterday_position(poslist)
```

设置回测的初始底仓。

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

### set_parameters - 设置策略配置参数

```python
set_parameters(**kwargs)
```

**支持的参数**：
- `holiday_not_do_before`：节假日是否执行before_trading_start
- `tick_data_no_l2`：tick_data是否包含order和transaction
- `receive_other_response`：是否接收非本交易产生的主推
- `receive_cancel_response`：是否接收撤单委托产生的主推
- `not_restart_trade`：交易时间段服务器重启是否自动拉起
- `server_restart_not_do_before`：服务器重启是否重复执行before_trading_start

### set_email_info - 设置邮件信息

```python
set_email_info(email_address, smtp_code, email_subject)
```

设置邮件信息，交易报错终止时发送提示邮件。

---

## 定时周期性函数

### run_daily - 按日周期处理

```python
run_daily(context, func, time='9:31')
```

以日为单位周期性运行指定函数。

```python
def initialize(context):
    run_daily(context, get_finance, time='9:31')

def get_finance(context):
    re = get_fundamentals(g.security, 'balance_statement', 'total_assets')
    log.info(re)
```

### run_interval - 按设定周期处理

```python
run_interval(context, func, seconds=10)
```

以设定时间间隔周期性运行指定函数，最小间隔3秒。

```python
def initialize(context):
    run_interval(context, interval_handle, seconds=10)

def interval_handle(context):
    snapshot = get_snapshot(g.security)
    log.info(snapshot)
```

---

## 获取信息函数

### 获取基础信息

#### get_trading_day - 获取交易日期

```python
get_trading_day(day)
```

获取当前时间数天前或数天后的交易日期。

```python
previous_date = get_trading_day(-1)  # 前一天
next_date = get_trading_day(1)       # 后一天
```

#### get_all_trades_days - 获取全部交易日期

```python
get_all_trades_days(date=None)
```

获取某个日期之前的所有交易日日期。

#### get_trade_days - 获取指定范围交易日期

```python
get_trade_days(start_date=None, end_date=None, count=None)
```

```python
trade_days = get_trade_days('2016-01-01', '2016-02-01')
trade_days = get_trade_days(count=10)
```

#### get_trading_day_by_date - 按日期获取指定交易日

```python
get_trading_day_by_date(query_date, day=0)
```

### 获取市场信息

#### get_market_list - 获取市场列表

```python
get_market_list()
```

返回当前市场列表目录，返回DataFrame包含：
- `finance_mic` - 市场编码
- `finance_name` - 市场名称

#### get_market_detail - 获取市场详细信息

```python
get_market_detail(finance_mic)
```

```python
get_market_detail('XSHG')  # 上海证券交易所
```

#### get_cb_list - 获取可转债市场代码表

```python
get_cb_list()
```

返回当前可转债市场的所有代码列表（包含停牌代码）。

#### get_cb_info - 获取可转债基础信息

```python
get_cb_info()
```

返回DataFrame，包含：
- `bond_code` - 可转债代码
- `bond_name` - 可转债名称
- `stock_code` - 股票代码
- `stock_name` - 股票名称
- `list_date` - 上市日期
- `premium_rate` - 溢价率（%）
- `convert_date` - 转股起始日
- `maturity_date` - 到期日
- `convert_rate` - 转股比例
- `convert_price` - 转股价格
- `convert_value` - 转股价值

#### get_reits_list - 获取公募REITs基金代码列表

```python
get_reits_list(date=None)
```

### 获取行情信息

#### get_history - 获取历史行情

```python
get_history(count, frequency='1d', field='close', security_list=None, fq=None, include=False, fill='nan', is_dict=False)
```

获取最近N条历史行情K线数据。

**参数**：
- `count`：K线数量
- `frequency`：K线周期（1m/5m/15m/30m/60m/120m/1d/1w/mo/1q/1y）
- `field`：行情字段（open/high/low/close/volume/money/price）
- `security_list`：股票列表
- `fq`：复权选项（pre-前复权，post-后复权，None-不复权）
- `include`：是否包含当前周期
- `fill`：填充方式（pre/nan）
- `is_dict`：返回是否为字典格式

```python
# 获取过去5天收盘价
his = get_history(5, '1d', 'close', security_list=g.security)

# 获取过去10分钟成交量
his = get_history(10, '1m', 'volume')
```

#### get_price - 获取历史数据

```python
get_price(security, start_date=None, end_date=None, frequency='1d', fields=None, fq=None, count=None, is_dict=False)
```

获取指定时间段内的历史行情K线数据。

```python
# 获取指定日期范围数据
df = get_price('600570.SS', start_date='20170201', end_date='20170213', frequency='1d')

# 获取最近100根K线
df = get_price('600570.SS', end_date='20170213', count=100, frequency='1d')
```

#### get_snapshot - 取行情快照

```python
get_snapshot(security)
```

获取实时行情快照。

#### get_gear_price - 获取档位行情价格

```python
get_gear_price(security)
```

获取指定代码的档位行情价格。

#### get_individual_entrust - 获取逐笔委托行情

```python
get_individual_entrust(security)
```

#### get_individual_transaction - 获取逐笔成交行情

```python
get_individual_transaction(security)
```

#### get_tick_direction - 获取分时成交行情

```python
get_tick_direction(security)
```

#### get_sort_msg - 获取板块涨幅排名

```python
get_sort_msg()
```

获取板块、行业的涨幅排名。

#### get_etf_info - 获取ETF信息

```python
get_etf_info(etf_code)
```

#### get_etf_stock_info - 获取ETF成分券信息

```python
get_etf_stock_info(etf_code)
```

#### get_ipo_stocks - 获取当日IPO申购标的

```python
get_ipo_stocks()
```

### 获取股票信息

#### get_stock_name - 获取股票名称

```python
get_stock_name(security)
```

#### get_stock_info - 获取股票基础信息

```python
get_stock_info(security)
```

#### get_stock_status - 获取股票状态信息

```python
get_stock_status(security, date)
```

#### get_stock_exrights - 获取股票除权除息信息

```python
get_stock_exrights(security)
```

#### get_stock_blocks - 获取股票所属板块信息

```python
get_stock_blocks(security)
```

#### get_index_stocks - 获取指数成份股

```python
get_index_stocks(index)
```

#### get_industry_stocks - 获取行业成份股

```python
get_industry_stocks(industry)
```

#### get_Ashares - 获取A股代码列表

```python
get_Ashares(date=None)
```

#### get_etf_list - 获取ETF代码

```python
get_etf_list()
```

#### get_fundamentals - 获取财务数据

```python
get_fundamentals(security, table_type, field)
```

---

## 交易相关函数

### 股票交易函数

#### order - 按数量买卖

```python
order(security, amount, limit_price=None)
```

按数量买卖股票。

**参数**：
- `security`：股票代码
- `amount`：数量（正数买入，负数卖出）
- `limit_price`：限价（可选）

```python
order('600570.SS', 100)        # 买入100股
order('600570.SS', -100)        # 卖出100股
order('600570.SS', 100, 38.5)   # 限价38.5买入100股
```

#### order_target - 指定目标数量买卖

```python
order_target(security, amount, limit_price=None)
```

调整持仓到目标数量。

```python
order_target('600570.SS', 1000)  # 调整持仓到1000股
order_target('600570.SS', 0)      # 清仓
```

#### order_value - 指定目标价值买卖

```python
order_value(security, value, limit_price=None)
```

按价值买卖股票。

```python
order_value('600570.SS', 10000)  # 买入价值10000元的股票
```

#### order_target_value - 指定持仓市值买卖

```python
order_target_value(security, value, limit_price=None)
```

调整持仓到目标市值。

```python
order_target_value('600570.SS', 50000)  # 调整持仓市值到50000元
```

#### order_market - 按市价委托

```python
order_market(security, amount, market_type=None, limit_price=None)
```

按市价进行委托。

**market_type类型**：
- `1`：对手方最优价格
- `2`：本方最优价格
- `3`：即时成交剩余撤销
- `4`：最优五档即时成交剩余撤销
- `5`：全额成交或撤销

```python
order_market('600570.SS', 100, market_type=4)  # 最优五档即时成交
```

#### order_tick - tick行情触发买卖

```python
order_tick(security, amount, side, price=None)
```

tick级别交易专用。

**参数**：
- `side`：1-买一价，2-买二价，...，6-卖一价，7-卖二价，...

### 公共交易函数

#### cancel_order - 撤单

```python
cancel_order(order_id)
```

撤销指定订单。

```python
cancel_order('order_id_123')
```

#### cancel_order_ex - 撤单（扩展）

```python
cancel_order_ex(order_list)
```

批量撤单。

#### get_open_orders - 获取未完成订单

```python
get_open_orders(security=None)
```

#### get_order - 获取指定订单

```python
get_order(order_id)
```

#### get_orders - 获取全部订单

```python
get_orders()
```

#### get_all_orders - 获取账户当日全部订单

```python
get_all_orders()
```

#### get_trades - 获取当日成交订单

```python
get_trades()
```

#### get_position - 获取持仓信息

```python
get_position(security)
```

获取单支股票的持仓信息。

#### get_positions - 获取多支股票持仓信息

```python
get_positions(security_list)
```

#### get_all_positions - 获取全部持仓信息

```python
get_all_positions()
```

### 其他交易函数

#### ipo_stocks_order - 新股一键申购

```python
ipo_stocks_order()
```

#### after_trading_order - 盘后固定价委托

```python
after_trading_order(security, amount, price)
```

#### after_trading_cancel_order - 盘后固定价委托撤单

```python
after_trading_cancel_order(order_id)
```

#### etf_basket_order - ETF成分券篮子下单

```python
etf_basket_order(etf_code, amount, direction)
```

#### etf_purchase_redemption - ETF基金申赎接口

```python
etf_purchase_redemption(etf_code, amount, direction)
```

#### debt_to_stock_order - 债转股委托

```python
debt_to_stock_order(bond_code, amount)
```

---

## 融资融券专用函数

### 融资融券交易类函数

#### margin_trade - 担保品买卖

```python
margin_trade(security, amount, limit_price=None)
```

#### margincash_open - 融资买入

```python
margincash_open(security, amount, limit_price=None)
```

#### margincash_close - 卖券还款

```python
margincash_close(security, amount, limit_price=None)
```

#### margincash_direct_refund - 直接还款

```python
margincash_direct_refund(amount)
```

#### marginsec_open - 融券卖出

```python
marginsec_open(security, amount, limit_price=None)
```

#### marginsec_close - 买券还券

```python
marginsec_close(security, amount, limit_price=None)
```

#### marginsec_direct_refund - 直接还券

```python
marginsec_direct_refund(security, amount)
```

### 融资融券查询类函数

#### get_margincash_stocks - 获取融资标的

```python
get_margincash_stocks()
```

#### get_marginsec_stocks - 获取融券标的

```python
get_marginsec_stocks()
```

#### get_margin_contract - 合约查询

```python
get_margin_contract()
```

#### get_margin_contractreal - 实时合约查询

```python
get_margin_contractreal()
```

#### get_margin_assert - 信用资产查询

```python
get_margin_assert()
```

#### get_assure_security_list - 担保券查询

```python
get_assure_security_list()
```

#### get_margincash_open_amount - 融资标的最大可买数量

```python
get_margincash_open_amount(security)
```

#### get_marginsec_open_amount - 融券标的最大可卖数量

```python
get_marginsec_open_amount(security)
```

---

## 期货专用函数

### 期货交易类函数

#### buy_open - 开多

```python
buy_open(security, amount, limit_price=None)
```

#### sell_close - 多平

```python
sell_close(security, amount, limit_price=None)
```

#### sell_open - 空开

```python
sell_open(security, amount, limit_price=None)
```

#### buy_close - 空平

```python
buy_close(security, amount, limit_price=None)
```

### 期货查询类函数

#### get_margin_rate - 获取保证金比例

```python
get_margin_rate()
```

#### get_instruments - 获取合约信息

```python
get_instruments()
```

### 期货设置类函数

#### set_future_commission - 设置期货手续费

```python
set_future_commission(commission_ratio)
```

#### set_margin_rate - 设置期货保证金比例

```python
set_margin_rate(margin_ratio)
```

---

## 技术指标计算函数

### get_MACD - 异同移动平均线

```python
get_MACD(security, fastperiod=12, slowperiod=26, signalperiod=9)
```

### get_KDJ - 随机指标

```python
get_KDJ(security, n=9, m=3, weight=3)
```

### get_RSI - 相对强弱指标

```python
get_RSI(security, n=14)
```

### get_CCI - 顺势指标

```python
get_CCI(security, n=14)
```

---

## 其他函数

### log - 日志记录

```python
log.info(message)
log.warn(message)
log.error(message)
```

### is_trade - 业务代码场景判断

```python
is_trade()
```

判断当前是否为交易时间。

### check_limit - 涨跌停状态判断

```python
check_limit(security)
```

返回：1-涨停，2-跌停，3-未涨跌停

### send_email - 发送邮箱信息

```python
send_email(subject, content)
```

### send_qywx - 发送企业微信信息

```python
send_qywx(content)
```

### permission_test - 权限校验

```python
permission_test()
```

### create_dir - 创建文件路径

```python
create_dir(path)
```

### get_research_path - 获取研究路径

```python
get_research_path()
```

### get_user_name - 获取资金账号

```python
get_user_name()
```

### get_trade_name - 获取交易名称

```python
get_trade_name()
```

### filter_stock_by_status - 过滤指定状态的股票

```python
filter_stock_by_status(stock_list, status_list)
```

---

## 对象说明

### g - 全局对象

全局变量对象，用于存储策略中的全局变量。

```python
g.security = '600570.SS'
g.flag = False
```

**注意**：以`__`开头的变量为私有变量，不会被持久化保存。

### Context - 上下文对象

存放当前的账户及持仓信息。

**主要属性**：
- `portfolio`：Portfolio对象，账户信息
- `blotter`：委托信息
- `current_dt`：当前时间

### SecurityUnitData对象

存放当前周期的数据。

**主要属性**：
- `open`：开盘价
- `high`：最高价
- `low`：最低价
- `close`：收盘价
- `volume`：成交量
- `price`：最新价

### Portfolio对象

账户信息对象。

**主要属性**：
- `cash`：可用资金
- `positions`：持仓字典
- `total_value`：总资产
- `starting_cash`：初始资金

### Position对象

持仓信息对象。

**主要属性**：
- `amount`：持仓数量
- `enable_amount`：可用数量
- `cost_basis`：持仓成本
- `sid`：标的代码

### Order对象

订单对象。

**主要属性**：
- `order_id`：订单编号
- `status`：订单状态
- `amount`：委托数量
- `filled`：成交数量
- `price`：委托价格
- `security`：标的代码

---

## 数据字典

### status - 订单状态

| 值 | 说明 |
|----|------|
| 0 | 待报 |
| 1 | 已报 |
| 2 | 已报待撤 |
| 3 | 部成 |
| 4 | 部成待撤 |
| 5 | 全成 |
| 6 | 已撤 |
| 7 | 废单 |
| 8 | 已撤部成 |
| 9 | 废单（已报） |

### entrust_bs - 委托方向

| 值 | 说明 |
|----|------|
| 1 | 买入 |
| 2 | 卖出 |

### entrust_type - 委托类别

| 值 | 说明 |
|----|------|
| 0 | 委托 |
| 2 | 撤单 |
| 4 | 确认 |
| 6 | 信用融资 |
| 7 | 信用融券 |
| 9 | 信用交易 |

### entrust_prop - 委托属性

| 值 | 说明 |
|----|------|
| 0 | 买卖 |
| 1 | 配股 |
| 3 | 申购 |
| 7 | 转股 |
| 9 | 股息 |
| N | ETF申赎 |
| Q | 对手方最优价格 |
| R | 最优五档即时成交剩余转限价 |
| S | 本方最优价格 |
| T | 即时成交剩余撤销 |
| U | 最优五档即时成交剩余撤销 |

### trade_status - 交易状态

| 值 | 说明 |
|----|------|
| START | 市场启动 |
| PRETR | 盘前 |
| OCALL | 开始集合竞价 |
| TRADE | 交易(连续撮合) |
| HALT | 暂停交易 |
| SUSP | 停盘 |
| BREAK | 休市 |
| POSTR | 盘后 |
| ENDTR | 交易结束 |
| STOPT | 长期停盘 |
| DELISTED | 退市 |

---

## 代码尾缀

| 市场品种 | 尾缀全称 | 尾缀简称 |
|----------|----------|----------|
| 上海市场证券 | XSHG | SS |
| 深圳市场证券 | XSHE | SZ |
| 指数 | XBHS | - |
| 中金所期货 | CCFX | - |
| 上海股票期权 | XSHO | - |
| 深圳股票期权 | XSZO | - |
| 上海港股通 | XHKG-SS | - |
| 深圳港股通 | XHKG-SZ | - |

**示例**：
- 上海股票：`600570.SS`
- 深圳股票：`000001.SZ`
- 沪深300指数：`000300.SS`

---

## 持久化处理

策略中断后重启时，全局变量会清空。使用pickle模块进行持久化处理。

```python
import pickle

def initialize(context):
    try:
        with open(get_research_path() + 'hold_days.pkl', 'rb') as f:
            g.hold_days = pickle.load(f)
    except:
        g.hold_days = defaultdict(list)
```

**注意事项**：
1. 框架会在`before_trading_start`、`handle_data`、`after_trading_end`后触发持久化
2. 无法被序列化的变量不会被保存
3. 以`__`开头的变量为私有变量，不会被保存

---

## 异常处理

交易场景数据缺失可能导致策略终止，建议添加异常处理。

```python
try:
    # 尝试执行的代码
    print(a)
except Exception as e:
    log.error(f"出现异常: {e}")
    a = 1
finally:
    # 无论是否发生异常都会执行
    log.info("执行完毕")
```

---

## 注意事项

### 关于限价交易的价格

不同标的价格精度不同：
- 股票：小数点两位
- 可转债/ETF/LOF：小数点三位
- 股指期货：小数点一位

使用限价单时务必处理价格精度，否则可能导致委托失败。

### 关于废单

如果是废单（如下单价格超过价格笼子），`order`函数仍会返回`order_id`，委托回调中状态为2（已报），但成交回调中状态为9（废单）。

### 内置第三方库

PTrade无法通过pip安装第三方库，只允许使用内置库。常见内置库包括：
- numpy
- pandas
- talib
- sklearn
- scipy
- 等等

---

## 策略示例

### 双均线策略

```python
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
    g.short_window = 5
    g.long_window = 20

def handle_data(context, data):
    df = get_history(g.long_window, '1d', 'close', g.security)
    short_ma = df['close'][-g.short_window:].mean()
    long_ma = df['close'][-g.long_window:].mean()
    
    position = get_position(g.security)
    
    if short_ma > long_ma and position.amount == 0:
        order_value(g.security, context.portfolio.cash * 0.95)
        log.info('买入')
    elif short_ma < long_ma and position.amount > 0:
        order_target(g.security, 0)
        log.info('卖出')
```

### 盘后逆回购

```python
def initialize(context):
    g.security = '131810.SZ'  # R-001
    set_universe(g.security)
    run_daily(context, reverse_repo, '15:00')

def reverse_repo(context):
    cash = context.portfolio.cash
    if cash > 1000:
        order(g.security, int(cash / 1000) * 10)
        log.info(f'逆回购: {cash}')
```

---

> 文档来源：https://ptradeapi.com/
