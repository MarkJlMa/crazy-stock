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

**参考文档**（位于项目 `.claude/reference/` 目录）：
- 聚宽API文档：`.claude/reference/JoinQuant_API_Documentation.md`
- PTrade API文档：`.claude/reference/Ptrade_API_Documentation.md`
- API对比文档：`.claude/reference/JoinQuant_vs_PTrade_API_Comparison.md`

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

### 1.11 回测与实盘环境适配

**重要**：PTrade回测环境和实盘环境存在显著差异，转换后的代码**必须同时支持两种环境**。

#### 环境判断方法

PTrade提供内置函数 `is_trade()` 用于判断运行模式：

```python
is_trade()  # 返回 True 表示实盘，False 表示回测
```

| 返回值 | 说明 |
|--------|------|
| `True` | 实盘交易模式 |
| `False` | 回测模式 |

**使用示例**：

```python
def initialize(context):
    log.info(f"运行模式: {'实盘' if is_trade() else '回测'}")


def some_function():
    if is_trade():
        # 实盘环境逻辑
        snapshot = get_snapshot(stock)
    else:
        # 回测环境逻辑
        df = get_history(1, '1d', 'close', security_list=stock)
```

#### 函数可用性对比

##### 仅实盘环境支持的函数

以下函数**仅支持实盘交易环境**，在回测环境中调用会报错或输出警告：

| 函数 | 说明 | 回测替代方案 |
|------|------|-------------|
| `get_snapshot()` | 获取实时行情快照 | 使用 `get_history()` |
| `get_gear_price()` | 获取档位行情价格 | 使用 `get_history()` |
| `get_individual_entrust()` | 获取逐笔委托行情 | 无替代 |
| `get_individual_transaction()` | 获取逐笔成交行情 | 无替代 |
| `get_tick_direction()` | 获取分时成交行情 | 无替代 |
| `get_sort_msg()` | 获取板块涨幅排名 | 无替代 |
| `order_market()` | 市价委托 | 使用限价单 `order()` |
| `order_tick()` | tick级别下单 | 使用 `order()` |
| `tick_data()` | tick级别回调 | 使用 `handle_data()` |
| `run_interval()` | 按秒级周期运行 | 使用 `run_daily()` |
| `ipo_stocks_order()` | 新股申购 | 无替代 |
| `after_trading_order()` | 盘后固定价委托 | 无替代 |
| `get_cb_list()` | 获取可转债列表 | 使用静态列表 |
| `get_etf_list()` | 获取ETF列表 | 使用静态列表 |
| `get_deliver()` | 获取交割单 | 无替代 |
| `get_fundjour()` | 获取资金流水 | 无替代 |
| `cancel_order_ex()` | 批量撤单 | 使用 `cancel_order()` |
| `get_all_orders()` | 获取全部订单 | 使用 `get_orders()` |
| `get_all_positions()` | 获取全部持仓 | 使用 `context.portfolio.positions` 或 `get_positions()` |

##### 仅回测环境支持的函数

以下函数**仅支持回测环境**：

| 函数 | 说明 |
|------|------|
| `set_commission()` | 设置佣金费率 |
| `set_fixed_slippage()` | 设置固定滑点 |
| `set_slippage()` | 设置滑点比例 |
| `set_volume_ratio()` | 设置成交比例 |
| `set_limit_mode()` | 设置成交数量限制模式 |
| `set_yesterday_position()` | 设置底仓 |
| `convert_position_from_csv()` | 从CSV导入持仓 |
| `get_trades_file()` | 获取回测成交记录 |

##### 回测和实盘都支持的函数

以下函数**在回测和实盘环境都可用**：

| 函数 | 说明 |
|------|------|
| `set_universe()` | 设置股票池 |
| `set_benchmark()` | 设置基准 |
| `run_daily()` | 按日周期运行 |
| `get_trading_day()` | 获取交易日期 |
| `get_trade_days()` | 获取指定范围交易日 |
| `get_history()` | 获取历史行情 |
| `get_price()` | 获取历史数据 |
| `get_Ashares()` | 获取A股列表 |
| `get_index_stocks()` | 获取指数成分股 |
| `get_fundamentals()` | 获取财务数据 |
| `get_MACD()` | MACD指标 |
| `get_KDJ()` | KDJ指标 |
| `get_RSI()` | RSI指标 |
| `order()` | 按数量下单 |
| `order_target()` | 目标数量下单 |
| `order_value()` | 按价值下单 |
| `order_target_value()` | 目标价值下单 |
| `cancel_order()` | 撤单 |
| `get_order()` | 获取订单 |
| `get_orders()` | 获取全部订单 |
| `get_open_orders()` | 获取未完成订单 |
| `get_trades()` | 获取成交记录 |
| `get_position()` | 获取单只股票持仓 |
| `get_positions()` | 获取多只股票持仓 |
| `is_trade()` | 判断运行模式 |
| `log.info/warn/error()` | 日志输出 |

**注意**：`get_all_positions()` 在回测环境会输出WARNING警告，官方明确说明不可用，应使用 `get_positions()` 或 `context.portfolio.positions` 替代。

#### 持仓获取差异

**重要**：持仓获取函数在回测和实盘环境存在以下差异：

##### 函数支持情况

| 函数 | 回测支持 | 实盘支持 | 说明 |
|------|---------|---------|------|
| `get_position('code')` | ✅ 支持 | ✅ 支持 | 获取单只股票持仓 |
| `get_position()` 不传参 | ✅ 支持 | ✅ 支持 | 返回SymbolDict（空字典） |
| `get_positions()` | ✅ 支持 | ✅ 支持 | 获取多只股票持仓 |
| `get_all_positions()` | ❌ 不支持 | ✅ 支持 | 回测输出WARNING，不可用 |

##### 属性名称差异

`get_position()` 返回的持仓对象在回测和实盘环境属性名称不同：

| 属性 | 回测环境 | 实盘环境 |
|------|---------|---------|
| 持仓数量 | `total_amount` | `amount` |
| 可用数量 | `closeable_amount` | `enable_amount` |
| 持仓成本 | `avg_cost` | `cost_basis` |
| 标的代码 | `security` | `sid` |
| 最新价格 | `last_sale_price` | `last_sale_price` |

##### 回测环境持仓获取方式

在回测环境中，推荐使用以下方式获取持仓：

```python
# 方式1：使用get_position()获取单只股票
position = get_position('000001.SZ')
if position.amount > 0:  # 注意：回测环境用amount，不是total_amount
    log.info(f"持仓数量: {position.amount}")

# 方式2：使用get_positions()获取多只股票
positions = get_positions()  # 返回SymbolDict

# 方式3：通过context.portfolio.positions遍历
for stock, pos in context.portfolio.positions.items():
    log.info(f"{stock}: {pos.total_amount}")
```

#### 必须实现的兼容函数

转换后的策略**必须**包含以下兼容函数，确保回测和实盘都能正常运行：

##### 1. 统一数据获取函数

```python
def get_stock_data(stock, fields=None):
    """
    统一的股票数据获取函数，自动适配回测和实盘环境

    参数:
        stock: 股票代码
        fields: 需要获取的字段列表，如 ['close', 'high_limit', 'low_limit']
                如果为None，返回字典格式的快照数据

    返回:
        回测环境: DataFrame或字典（基于get_history）
        实盘环境: 字典（基于get_snapshot）
    """
    # is_trade() 返回 True 表示实盘，False 表示回测
    if not is_trade():
        # 回测环境：使用get_history获取最近数据
        if fields is None:
            fields = ['close', 'high_limit', 'low_limit', 'open', 'volume']

        try:
            df = get_history(1, '1d', fields, security_list=stock)
            if df is None or df.empty:
                return None

            # 转换为字典格式，模拟snapshot返回
            result = {}
            for field in fields:
                if field in df.columns:
                    result[field] = df[field].iloc[-1]
                elif field == 'last_px':
                    result['last_px'] = df['close'].iloc[-1]
                elif field == 'limit_up':
                    result['limit_up'] = df['high_limit'].iloc[-1] if 'high_limit' in df.columns else 0
                elif field == 'limit_down':
                    result['limit_down'] = df['low_limit'].iloc[-1] if 'low_limit' in df.columns else 0

            # 添加兼容字段
            result['last_px'] = result.get('close', 0)
            result['limit_up'] = result.get('high_limit', 0)
            result['limit_down'] = result.get('low_limit', 0)
            result['trade_status'] = 'TRADING'  # 回测默认为交易状态

            return result
        except Exception as e:
            log.error(f"回测环境获取{stock}数据失败: {str(e)}")
            return None
    else:
        # 实盘环境：使用get_snapshot
        try:
            snapshot = get_snapshot(stock)
            if snapshot is None:
                return None

            # 转换字段名以保持一致性
            result = {
                'close': snapshot.get('last_px', 0),
                'last_px': snapshot.get('last_px', 0),
                'high_limit': snapshot.get('limit_up', 0),
                'limit_up': snapshot.get('limit_up', 0),
                'low_limit': snapshot.get('limit_down', 0),
                'limit_down': snapshot.get('limit_down', 0),
                'open': snapshot.get('open_px', 0),
                'volume': snapshot.get('business_volume', 0),
                'trade_status': snapshot.get('trade_status', 'TRADING'),
                'total_market_value': snapshot.get('total_market_value', 0),
            }
            return result
        except Exception as e:
            log.error(f"实盘环境获取{stock}数据失败: {str(e)}")
            return None
```

##### 2. 持仓获取兼容函数

```python
def get_all_positions_compat(context=None):
    """
    获取所有持仓（兼容回测和实盘环境）

    注意：回测环境不支持get_all_positions()，使用get_positions()替代

    返回:
        持仓列表，每个元素包含 sid, amount, enable_amount, cost_basis, last_sale_price 等属性
    """
    # is_trade() 返回 True 表示实盘，False 表示回测
    if not is_trade():
        # 回测环境：使用get_positions()或context.portfolio.positions
        positions = []
        # 方式1：使用get_positions()
        pos_dict = get_positions()
        if pos_dict:
            for stock, pos in pos_dict.items():
                class PositionCompat:
                    pass
                p = PositionCompat()
                p.sid = stock
                p.amount = pos.total_amount if hasattr(pos, 'total_amount') else pos.amount
                p.enable_amount = pos.closeable_amount if hasattr(pos, 'closeable_amount') else pos.enable_amount
                p.cost_basis = pos.avg_cost if hasattr(pos, 'avg_cost') else pos.cost_basis
                p.last_sale_price = pos.last_sale_price if hasattr(pos, 'last_sale_price') else pos.price
                positions.append(p)
        # 方式2：通过context.portfolio.positions获取（备用）
        elif context and hasattr(context, 'portfolio') and hasattr(context.portfolio, 'positions'):
            for stock, pos in context.portfolio.positions.items():
                class PositionCompat:
                    pass
                p = PositionCompat()
                p.sid = stock
                p.amount = pos.total_amount if hasattr(pos, 'total_amount') else pos.amount
                p.enable_amount = pos.closeable_amount if hasattr(pos, 'closeable_amount') else pos.enable_amount
                p.cost_basis = pos.avg_cost if hasattr(pos, 'avg_cost') else pos.cost_basis
                p.last_sale_price = pos.last_sale_price if hasattr(pos, 'last_sale_price') else pos.price
                positions.append(p)
        return positions
    else:
        # 实盘环境：使用get_all_positions
        return get_all_positions()


def get_position_compat(context, stock):
    """
    获取指定股票持仓（兼容回测和实盘环境）

    参数:
        context: 上下文对象
        stock: 股票代码

    返回:
        持仓对象，包含 amount, enable_amount, cost_basis, last_sale_price 等属性
    """
    # is_trade() 返回 True 表示实盘，False 表示回测
    if not is_trade():
        # 回测环境：直接使用get_position()
        pos = get_position(stock)
        if pos and hasattr(pos, 'amount') and pos.amount > 0:
            # 创建兼容的持仓对象
            class PositionCompat:
                pass
            p = PositionCompat()
            p.sid = stock
            p.amount = pos.total_amount if hasattr(pos, 'total_amount') else pos.amount
            p.enable_amount = pos.closeable_amount if hasattr(pos, 'closeable_amount') else pos.enable_amount
            p.cost_basis = pos.avg_cost if hasattr(pos, 'avg_cost') else pos.cost_basis
            p.last_sale_price = pos.last_sale_price if hasattr(pos, 'last_sale_price') else pos.price
            return p
        # 返回空持仓对象
        class PositionCompat:
            pass
        p = PositionCompat()
        p.sid = stock
        p.amount = 0
        p.enable_amount = 0
        p.cost_basis = 0
        p.last_sale_price = 0
        return p
    else:
        # 实盘环境：使用get_position
        return get_position(stock)
```

##### 3. 辅助函数

```python
def get_stock_price(stock):
    """获取股票当前价格（兼容回测和实盘）"""
    data = get_stock_data(stock)
    if data is None:
        return None
    return data.get('last_px', data.get('close', 0))


def get_stock_limit_prices(stock):
    """获取股票涨停跌停价（兼容回测和实盘）"""
    data = get_stock_data(stock)
    if data is None:
        return None, None
    return data.get('limit_up', 0), data.get('limit_down', 0)
```

#### 字段映射表

| 统一字段名 | 回测来源 (get_history) | 实盘来源 (get_snapshot) |
|-----------|----------------------|------------------------|
| `last_px` / `close` | `df['close'].iloc[-1]` | `snapshot['last_px']` |
| `limit_up` / `high_limit` | `df['high_limit'].iloc[-1]` | `snapshot['limit_up']` |
| `limit_down` / `low_limit` | `df['low_limit'].iloc[-1]` | `snapshot['limit_down']` |
| `open` | `df['open'].iloc[-1]` | `snapshot['open_px']` |
| `volume` | `df['volume'].iloc[-1]` | `snapshot['business_volume']` |
| `trade_status` | 默认 `'TRADING'` | `snapshot['trade_status']` |
| `total_market_value` | ❌ 无 | `snapshot['total_market_value']` |

#### 使用示例

```python
def initialize(context):
    g.security = '000001.SZ'
    set_universe(g.security)
    log.info(f"运行模式: {'实盘' if is_trade() else '回测'}")


def handle_data(context, data):
    # 获取股票数据（自动适配回测和实盘）
    stock_data = get_stock_data(g.security)
    if stock_data is None:
        return

    current_price = stock_data.get('last_px', 0)
    limit_up = stock_data.get('limit_up', 0)

    # 获取持仓（自动适配回测和实盘）
    position = get_position_compat(context, g.security)

    if position.amount == 0 and current_price < limit_up * 0.99:
        # 未涨停时买入
        order_value(g.security, context.portfolio.cash * 0.95)
        log.info(f"买入 {g.security}, 价格: {current_price}")
```

#### 环境适配检查清单

转换后的策略必须检查以下项目：

- [ ] 使用 `is_trade()` 判断运行环境
- [ ] 数据获取使用 `get_stock_data()` 兼容函数
- [ ] 持仓获取使用 `get_position_compat()` 和 `get_all_positions_compat()` 兼容函数
- [ ] 不在回测环境调用仅实盘支持的函数（如 `get_snapshot()`、`order_market()`）
- [ ] 不在实盘环境调用仅回测支持的函数（如 `set_commission()`）
- [ ] 测试回测环境能正常运行并输出汇总数据
- [ ] 测试实盘环境能正常获取数据和下单

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
- [ ] **环境适配**：回测环境不支持 `get_snapshot()`，需要使用统一数据获取函数

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

### Q6: 回测环境不支持get_snapshot怎么办？

使用统一的 `get_stock_data()` 函数，根据 `g.__is_backtest` 标记自动选择 `get_history()` 或 `get_snapshot()`。

### Q7: 如何获取涨停跌停价格？

- **回测环境**：使用 `get_history(1, '1d', ['high_limit', 'low_limit'], security_list=stock)`
- **实盘环境**：使用 `get_snapshot(stock)` 获取 `limit_up` 和 `limit_down` 字段
- **推荐**：使用统一的 `get_stock_data()` 函数自动适配

### Q8: 回测环境如何获取持仓？

**回测环境持仓函数支持情况**：

| 函数 | 回测支持 | 说明 |
|------|---------|------|
| `get_position('code')` | ✅ 支持 | 获取单只股票持仓，返回Position对象 |
| `get_position()` 不传参 | ✅ 支持 | 返回SymbolDict（空字典） |
| `get_positions()` | ✅ 支持 | 返回SymbolDict |
| `get_all_positions()` | ❌ 不支持 | 输出WARNING警告，不可用 |

**推荐使用方式**：

```python
# 回测环境获取持仓
if not is_trade():
    # 方式1：获取单只股票持仓
    position = get_position('000001.SZ')
    if position.amount > 0:
        log.info(f"持仓数量: {position.amount}")

    # 方式2：获取所有持仓
    positions = get_positions()
    for stock, pos in positions.items():
        log.info(f"{stock}: {pos.total_amount}")

    # 方式3：通过context.portfolio.positions
    for stock, pos in context.portfolio.positions.items():
        log.info(f"{stock}: {pos.total_amount}")
```

**兼容函数**：使用 `get_all_positions_compat(context)` 和 `get_position_compat(context, stock)` 自动适配回测和实盘环境。

---

> 文档版本：1.6
> 更新日期：2026-05-13
> 更新内容：修正持仓函数在回测环境的支持情况：get_position()和get_positions()支持回测，get_all_positions()不支持回测（输出WARNING）
