---
name: ptrade-review
description: |
  PTrade代码审核工具。检查PTrade策略代码是否符合平台要求，包括回测/实盘兼容性、API使用规范、代码格式等。
  触发关键词：审核ptrade、检查ptrade、ptrade审核、ptrade检查、review ptrade、ptrade-review
metadata:
  openclaw:
    emoji: "🔍"
---

# PTrade代码审核 Skill

## 概述

本Skill用于审核PTrade策略代码，确保代码符合平台要求，能在回测和实盘环境正常运行。

**参考文档**（位于项目 `.claude/reference/` 目录）：
- PTrade API文档：`.claude/reference/Ptrade_API_Documentation.md`
- API对比文档：`.claude/reference/JoinQuant_vs_PTrade_API_Comparison.md`

---

## 一、审核检查清单

### 1.1 必要性检查

| 检查项 | 要求 | 错误级别 |
|--------|------|---------|
| `set_universe()` | 必须在initialize中调用 | ❌ 致命错误 |
| 股票代码格式 | 使用 `.SS` 或 `.SZ` | ❌ 致命错误 |
| 全局变量初始化 | 在initialize中初始化g变量 | ⚠️ 警告 |

### 1.2 回测/实盘兼容性检查

| 检查项 | 回测支持 | 实盘支持 | 错误级别 |
|--------|---------|---------|---------|
| `get_snapshot()` | ❌ | ✅ | ❌ 回测致命错误 |
| `get_all_positions()` | ❌ | ✅ | ⚠️ 回测警告 |
| `order_market()` | ❌ | ✅ | ❌ 回测致命错误 |
| `set_commission()` | ✅ | ❌ | ⚠️ 实盘警告 |
| `set_slippage()` | ✅ | ❌ | ⚠️ 实盘警告 |

### 1.3 函数使用检查

| 检查项 | 正确用法 | 错误级别 |
|--------|---------|---------|
| `run_daily()` | 必须传入context参数 | ❌ 错误 |
| `get_history()` | 使用正确的unit参数 | ⚠️ 警告 |
| `get_fundamentals()` | 使用正确的表名和字段 | ⚠️ 警告 |
| 持仓属性访问 | 回测用total_amount，实盘用amount | ⚠️ 警告 |

### 1.4 代码格式检查

| 检查项 | 要求 | 错误级别 |
|--------|------|---------|
| 下单数量 | 必须是100的整数倍 | ❌ 错误 |
| 价格精度 | 股票0.01，ETF/可转债0.001 | ⚠️ 警告 |
| 日志输出 | 使用log.info/warn/error | ⚠️ 警告 |

---

## 二、函数可用性对照表

### 2.1 仅实盘环境支持的函数

以下函数在回测环境调用会报错或输出警告：

| 函数 | 说明 | 回测行为 |
|------|------|---------|
| `get_snapshot()` | 实时行情快照 | ❌ 报错 |
| `get_gear_price()` | 档位行情价格 | ❌ 报错 |
| `get_individual_entrust()` | 逐笔委托行情 | ❌ 报错 |
| `get_individual_transaction()` | 逐笔成交行情 | ❌ 报错 |
| `get_tick_direction()` | 分时成交行情 | ❌ 报错 |
| `get_sort_msg()` | 板块涨幅排名 | ❌ 报错 |
| `order_market()` | 市价委托 | ❌ 报错 |
| `order_tick()` | tick级别下单 | ❌ 报错 |
| `tick_data()` | tick级别回调 | ❌ 报错 |
| `run_interval()` | 按秒级周期运行 | ❌ 报错 |
| `ipo_stocks_order()` | 新股申购 | ❌ 报错 |
| `after_trading_order()` | 盘后固定价委托 | ❌ 报错 |
| `get_cb_list()` | 可转债列表 | ❌ 报错 |
| `get_etf_list()` | ETF列表 | ❌ 报错 |
| `get_deliver()` | 交割单 | ❌ 报错 |
| `get_fundjour()` | 资金流水 | ❌ 报错 |
| `cancel_order_ex()` | 批量撤单 | ❌ 报错 |
| `get_all_orders()` | 全部订单 | ❌ 报错 |
| `get_all_positions()` | 全部持仓 | ⚠️ WARNING |

### 2.2 仅回测环境支持的函数

以下函数在实盘环境调用无效或报错：

| 函数 | 说明 | 实盘行为 |
|------|------|---------|
| `set_commission()` | 设置佣金 | ⚠️ 无效 |
| `set_fixed_slippage()` | 设置固定滑点 | ⚠️ 无效 |
| `set_slippage()` | 设置滑点比例 | ⚠️ 无效 |
| `set_volume_ratio()` | 设置成交比例 | ⚠️ 无效 |
| `set_limit_mode()` | 成交数量限制 | ⚠️ 无效 |
| `set_yesterday_position()` | 设置底仓 | ⚠️ 无效 |
| `convert_position_from_csv()` | CSV导入持仓 | ⚠️ 无效 |
| `get_trades_file()` | 回测成交记录 | ⚠️ 无效 |

### 2.3 回测和实盘都支持的函数

| 函数 | 说明 | 注意事项 |
|------|------|---------|
| `set_universe()` | 设置股票池 | 必须调用 |
| `set_benchmark()` | 设置基准 | - |
| `run_daily()` | 按日周期运行 | 需传入context |
| `get_trading_day()` | 获取交易日期 | - |
| `get_trade_days()` | 获取交易日列表 | - |
| `get_history()` | 获取历史行情 | - |
| `get_price()` | 获取历史数据 | - |
| `get_Ashares()` | 获取A股列表 | - |
| `get_index_stocks()` | 指数成分股 | - |
| `get_fundamentals()` | 获取财务数据 | - |
| `get_MACD()` | MACD指标 | - |
| `get_KDJ()` | KDJ指标 | - |
| `get_RSI()` | RSI指标 | - |
| `order()` | 按数量下单 | 数量需100整数倍 |
| `order_target()` | 目标数量下单 | - |
| `order_value()` | 按价值下单 | - |
| `order_target_value()` | 目标价值下单 | - |
| `cancel_order()` | 撤单 | - |
| `get_order()` | 获取订单 | - |
| `get_orders()` | 全部订单 | - |
| `get_open_orders()` | 未完成订单 | - |
| `get_trades()` | 成交记录 | - |
| `get_position()` | 单只股票持仓 | ✅ 回测支持 |
| `get_positions()` | 多只股票持仓 | ✅ 回测支持 |
| `is_trade()` | 判断运行模式 | - |
| `log.info/warn/error()` | 日志输出 | - |

---

## 三、持仓属性差异

### 3.1 属性名称对照

| 属性 | 回测环境 | 实盘环境 |
|------|---------|---------|
| 持仓数量 | `total_amount` | `amount` |
| 可用数量 | `closeable_amount` | `enable_amount` |
| 持仓成本 | `avg_cost` | `cost_basis` |
| 标的代码 | `security` | `sid` |
| 最新价格 | `last_sale_price` | `last_sale_price` |

### 3.2 推荐的兼容写法

```python
def get_position_compat(context, stock):
    """获取持仓（兼容回测和实盘）"""
    pos = get_position(stock)
    if pos:
        # 使用兼容属性访问
        amount = pos.total_amount if hasattr(pos, 'total_amount') else pos.amount
        enable_amount = pos.closeable_amount if hasattr(pos, 'closeable_amount') else pos.enable_amount
        cost = pos.avg_cost if hasattr(pos, 'avg_cost') else pos.cost_basis
        return {
            'amount': amount,
            'enable_amount': enable_amount,
            'cost': cost
        }
    return {'amount': 0, 'enable_amount': 0, 'cost': 0}
```

---

## 四、审核流程

### 4.1 审核步骤

1. **必要性检查**：检查set_universe、股票代码格式等必要项
2. **环境兼容检查**：检查是否使用了环境不兼容的函数
3. **函数使用检查**：检查函数参数是否正确
4. **代码格式检查**：检查下单数量、价格精度等
5. **生成审核报告**：输出审核结果和修改建议

### 4.2 错误级别

| 级别 | 说明 | 处理方式 |
|------|------|---------|
| ❌ 致命错误 | 会导致代码无法运行 | 必须修改 |
| ❌ 错误 | 可能导致运行异常 | 建议修改 |
| ⚠️ 警告 | 可能导致功能异常 | 可选修改 |
| ✅ 通过 | 符合要求 | 无需修改 |

---

## 五、审核报告格式

```markdown
## PTrade代码审核报告

### 概要
- 文件：xxx.py
- 审核时间：2026-05-13
- 错误数量：致命错误 X 个，错误 X 个，警告 X 个

### 详细检查结果

#### 1. 必要性检查
| 检查项 | 结果 | 说明 |
|--------|------|------|
| set_universe() | ✅/❌ | ... |

#### 2. 环境兼容性检查
| 检查项 | 结果 | 说明 |
|--------|------|------|
| get_snapshot() | ✅/❌ | ... |

#### 3. 函数使用检查
| 检查项 | 结果 | 说明 |
|--------|------|------|
| run_daily() | ✅/❌ | ... |

#### 4. 代码格式检查
| 检查项 | 结果 | 说明 |
|--------|------|------|
| 下单数量 | ✅/❌ | ... |

### 修改建议

1. [具体修改建议]
2. [具体修改建议]

### 修改后的代码示例

[展示修改后的关键代码片段]
```

---

## 六、常见问题修复

### 6.1 缺少set_universe()

**问题**：
```python
def initialize(context):
    g.security = '000001.SZ'
    # 缺少set_universe调用
```

**修复**：
```python
def initialize(context):
    g.security = '000001.SZ'
    set_universe(g.security)  # 必须添加
```

### 6.2 股票代码格式错误

**问题**：
```python
order('000001.XSHE', 100)  # 使用聚宽格式
```

**修复**：
```python
order('000001.SZ', 100)  # 使用PTrade格式
```

### 6.3 回测环境使用get_snapshot()

**问题**：
```python
def handle_data(context, data):
    snapshot = get_snapshot('000001.SZ')  # 回测不支持
```

**修复**：
```python
def handle_data(context, data):
    if is_trade():
        snapshot = get_snapshot('000001.SZ')
    else:
        df = get_history(1, '1d', 'close', security_list='000001.SZ')
```

### 6.4 run_daily缺少context参数

**问题**：
```python
def initialize(context):
    run_daily(my_func, time='9:30')  # 缺少context
```

**修复**：
```python
def initialize(context):
    run_daily(context, my_func, time='9:30')  # 添加context
```

### 6.5 下单数量不是100整数倍

**问题**：
```python
order('000001.SZ', 150)  # 不是100整数倍
```

**修复**：
```python
order('000001.SZ', 100)  # 或 200, 300...
```

### 6.6 持仓属性访问不兼容

**问题**：
```python
position = get_position('000001.SZ')
amount = position.total_amount  # 实盘环境不存在此属性
```

**修复**：
```python
position = get_position('000001.SZ')
amount = position.total_amount if hasattr(position, 'total_amount') else position.amount
```

---

## 七、自动审核脚本

```python
import re

def review_ptrade_code(code, filename='unknown'):
    """审核PTrade代码"""

    errors = {
        'critical': [],  # 致命错误
        'error': [],     # 错误
        'warning': []    # 警告
    }

    # 1. 必要性检查
    # 检查set_universe
    if 'def initialize(context):' in code and 'set_universe' not in code:
        errors['critical'].append('缺少set_universe()调用')

    # 检查股票代码格式
    jq_codes = re.findall(r'[\'"][0-9]{6}\.[XSHG|XSHE][\'"]', code)
    if jq_codes:
        errors['critical'].append(f'使用聚宽代码格式: {jq_codes}')

    # 2. 环境兼容性检查
    # 检查回测不支持的函数
    backtest_unsupported = [
        'get_snapshot', 'get_gear_price', 'order_market', 'order_tick',
        'tick_data', 'run_interval', 'ipo_stocks_order', 'after_trading_order'
    ]
    for func in backtest_unsupported:
        if func + '(' in code:
            if 'is_trade()' not in code:
                errors['critical'].append(f'回测环境不支持{func}()，需添加is_trade()判断')

    # 检查get_all_positions
    if 'get_all_positions()' in code:
        errors['warning'].append('get_all_positions()在回测环境输出WARNING，建议使用get_positions()')

    # 3. 函数使用检查
    # 检查run_daily参数
    run_daily_calls = re.findall(r'run_daily\([^)]+\)', code)
    for call in run_daily_calls:
        if 'context,' not in call and 'context,' not in call.replace(' ', ''):
            errors['error'].append(f'run_daily缺少context参数: {call}')

    # 4. 代码格式检查
    # 检查下单数量
    order_calls = re.findall(r'order\([^,]+,\s*(\d+)', code)
    for amount in order_calls:
        if int(amount) % 100 != 0:
            errors['error'].append(f'下单数量{amount}不是100整数倍')

    return {
        'filename': filename,
        'errors': errors,
        'summary': {
            'critical': len(errors['critical']),
            'error': len(errors['error']),
            'warning': len(errors['warning'])
        }
    }


def generate_report(result):
    """生成审核报告"""
    report = f"""## PTrade代码审核报告

### 概要
- 文件：{result['filename']}
- 审核时间：{datetime.now().strftime('%Y-%m-%d')}
- 错误数量：致命错误 {result['summary']['critical']} 个，错误 {result['summary']['error']} 个，警告 {result['summary']['warning']} 个

### 详细检查结果

#### 致命错误
"""
    for err in result['errors']['critical']:
        report += f"- ❌ {err}\n"

    report += "\n#### 错误\n"
    for err in result['errors']['error']:
        report += f"- ❌ {err}\n"

    report += "\n#### 警告\n"
    for err in result['errors']['warning']:
        report += f"- ⚠️ {err}\n"

    return report
```

---

> 文档版本：1.0
> 更新日期：2026-05-13
> 更新内容：创建PTrade代码审核Skill