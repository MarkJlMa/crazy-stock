# PTrade版本 - 三架马车策略（小市值-白马-ETF组合）
# 原始聚宽策略来源：https://www.joinquant.com/post/62749
# 转换日期：2026-05-12

"""
三种策略集合在一起
策略1：小市值策略
策略2：白马攻防策略
策略3：ETF轮动策略

注意：
1. PTrade中财务数据查询方式与聚宽完全不同，需要使用get_fundamentals的新语法
2. 回测环境不支持get_snapshot，需要使用get_history/get_price替代
"""
import numpy as np
import pandas as pd
import math
from datetime import datetime, timedelta


def convert_code_jq_to_ptrade(code):
    """聚宽代码转PTrade代码"""
    if isinstance(code, str):
        return code.replace('.XSHG', '.SS').replace('.XSHE', '.SZ')
    elif isinstance(code, list):
        return [c.replace('.XSHG', '.SS').replace('.XSHE', '.SZ') for c in code]
    return code


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


def get_all_positions_compat(context=None):
    """
    获取所有持仓（兼容回测和实盘环境）

    返回:
        持仓列表，每个元素包含 sid, amount, enable_amount, cost_basis, last_sale_price 等属性
    """
    # is_trade() 返回 True 表示实盘，False 表示回测
    if not is_trade():
        # 回测环境：通过context.portfolio.positions获取
        positions = []
        if context and hasattr(context, 'portfolio') and hasattr(context.portfolio, 'positions'):
            for stock, pos in context.portfolio.positions.items():
                # 创建兼容的持仓对象
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
        # 回测环境：通过context.portfolio.positions获取
        if context and hasattr(context, 'portfolio') and hasattr(context.portfolio, 'positions'):
            pos = context.portfolio.positions.get(stock, None)
            if pos:
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


def initialize(context):
    set_params(context)
    # PTrade必须设置股票池，初始设为空列表，后续动态更新
    g.security = []
    set_universe(g.security)

    # 子策略执行计划
    # PTrade定时任务需要传入context参数，时间格式为字符串
    if g.portfolio_value_proportion[0] > 0:  # 小市值策略
        run_daily(context, xsz_get_stock_list, time='9:05')
        run_daily(context, xsz_adjustment, time='10:00')

    if g.portfolio_value_proportion[1] > 0:  # 白马策略
        run_daily(context, bm_before_market_open, time='9:00')
        run_daily(context, bm_adjust_position, time='9:45')

    if g.portfolio_value_proportion[2] > 0:  # ETF策略
        run_daily(context, trade, time='10:00')

    run_daily(context, sell_stocks, time='10:00')     # 止损函数
    run_daily(context, check_limit_up, time='14:00')  # 检查涨停板
    run_daily(context, print_position_info, time='14:55')

    # is_trade() 返回 True 表示实盘，False 表示回测
    log.info(f"运行模式: {'实盘' if is_trade() else '回测'}")


# 参数设置
def set_params(context):
    g.run_stoploss = True    # 是否进行止损
    g.stoploss_limit = 0.08  # 止损线

    g.stock_num = 5          # 策略1和策略2分别持股数量
    g.up_price = 50          # 个股价格上限
    g.pass_months = [1, 4]   # 空仓月份（1月和4月）

    # 策略持仓记录
    g.strategy_holdings = {
        1: [],  # 小市值策略持仓
        2: [],  # 白马策略持仓
    }

    # 策略1全局变量
    g.trading_signal = True
    g.yesterday_HL_list = [] # 昨日涨停股票
    g.target_list = []       # 目标持仓股票
    g.limitup_stocks = []    # 涨停股票避免买入
    g.min_mv = 10            # 最小市值(亿)
    g.max_mv = 100           # 最大市值(亿)
    g.reason_to_sell = {}    # 卖出原因记录

    # 策略2全局变量
    g.check_out_lists = []
    g.market_temperature = "warm"
    g.roe = 10  # ROE权重
    g.roa = 6   # ROA权重

    # 策略3全局变量 - ETF代码已转换为PTrade格式
    g.etf_pool = [
        '518880.SS',  # 黄金ETF
        '513100.SS',  # 纳指100
        '159915.SZ',  # 创业板
        '510180.SS',  # 上证180
        '512290.SS',  # 生物医药
        '513020.SS',  # 港股科技
        '515070.SS',  # 人工智能
        '588120.SS',  # 科创板
    ]
    g.m_days = 25  # 动量参考天数
    g.etf_pre = None  # 上次持有的ETF
    g.portfolio_value_proportion = [0.57, 0.36, 0.07]  # 策略资金占比


# 打印持仓信息
def print_position_info(context):
    log.info('=' * 50)
    log.info('持仓信息')
    log.info('=' * 50)

    # 策略1：小市值策略持仓
    log.info(f'【小市值策略】资金占比: {g.portfolio_value_proportion[0]*100:.0f}%')
    strategy1_value = 0
    for stock in g.strategy_holdings[1]:
        pos = get_position_compat(context, stock)
        if pos and pos.amount > 0:
            ret = 100 * (pos.last_sale_price / pos.cost_basis - 1) if pos.cost_basis > 0 else 0
            market_value = pos.amount * pos.last_sale_price
            strategy1_value += market_value
            log.info(f'  {stock}: {pos.amount:.0f}股, 成本{pos.cost_basis:.2f}, 现价{pos.last_sale_price:.2f}, 收益{ret:+.2f}%, 市值{market_value:.0f}')
    if not g.strategy_holdings[1] or strategy1_value == 0:
        log.info('  (空仓)')
    log.info(f'  小市值策略市值: {strategy1_value:.0f}')

    # 策略2：白马策略持仓
    log.info(f'【白马策略】资金占比: {g.portfolio_value_proportion[1]*100:.0f}%')
    strategy2_value = 0
    for stock in g.strategy_holdings[2]:
        pos = get_position_compat(context, stock)
        if pos and pos.amount > 0:
            ret = 100 * (pos.last_sale_price / pos.cost_basis - 1) if pos.cost_basis > 0 else 0
            market_value = pos.amount * pos.last_sale_price
            strategy2_value += market_value
            log.info(f'  {stock}: {pos.amount:.0f}股, 成本{pos.cost_basis:.2f}, 现价{pos.last_sale_price:.2f}, 收益{ret:+.2f}%, 市值{market_value:.0f}')
    if not g.strategy_holdings[2] or strategy2_value == 0:
        log.info('  (空仓)')
    log.info(f'  白马策略市值: {strategy2_value:.0f}')

    # 策略3：ETF策略持仓
    log.info(f'【ETF策略】资金占比: {g.portfolio_value_proportion[2]*100:.0f}%')
    strategy3_value = 0
    positions = get_all_positions_compat(context)
    for position in positions:
        if position.sid in g.etf_pool:
            ret = 100 * (position.last_sale_price / position.cost_basis - 1) if position.cost_basis > 0 else 0
            market_value = position.amount * position.last_sale_price
            strategy3_value += market_value
            log.info(f'  {position.sid}: {position.amount:.0f}股, 成本{position.cost_basis:.2f}, 现价{position.last_sale_price:.2f}, 收益{ret:+.2f}%, 市值{market_value:.0f}')
    if strategy3_value == 0:
        log.info('  (空仓)')
    log.info(f'  ETF策略市值: {strategy3_value:.0f}')

    # 总计
    total_value = strategy1_value + strategy2_value + strategy3_value
    log.info('-' * 50)
    log.info(f'总市值: {total_value:.0f}, 可用资金: {context.portfolio.cash:.0f}, 总资产: {context.portfolio.total_value:.0f}')
    log.info('=' * 50)


# ====================== 策略1: 小市值策略 ======================
def xsz_get_stock_list(context):
    """选股模块"""
    MKT_index = '399101.SZ'  # 中小板指，已转换为PTrade格式
    initial_list = filter_stocks(context, get_index_stocks(MKT_index))

    if not initial_list:
        return []

    # PTrade财务数据查询方式不同，这里需要重写
    # 由于PTrade的get_fundamentals语法与聚宽完全不同，这里使用简化版本
    # 实际使用时需要根据PTrade的财务数据接口进行调整
    final_list = []
    for stock in initial_list:
        try:
            # 使用统一的数据获取函数
            data = get_stock_data(stock)
            if data is None:
                continue

            last_price = data.get('last_px', 0)
            if last_price <= 0:
                continue

            # 价格过滤
            if last_price > g.up_price:
                continue

            # 市值过滤（实盘环境有市值数据，回测环境需要通过其他方式获取）
            if is_trade():
                market_cap = data.get('total_market_value', 0)
                if market_cap > 0:
                    # 市值过滤 (单位：亿)
                    if not (g.min_mv <= market_cap / 100000000 <= g.max_mv):
                        continue

            final_list.append(stock)

            if len(final_list) >= g.stock_num * 3:
                break
        except Exception as e:
            log.error(f"获取股票{stock}数据失败: {str(e)}")
            continue

    return final_list


def xsz_adjustment(context):
    """调整持仓"""
    g.trading_signal = today_is_between(context)
    if not g.trading_signal:
        # 只清空本策略持仓
        for stock in g.strategy_holdings[1][:]:
            order_target_value(stock, 0)
            if stock in g.strategy_holdings[1]:
                g.strategy_holdings[1].remove(stock)
        log.info('小市值策略：空仓月份，已清仓')
        return

    g.target_list = xsz_get_stock_list(context)[:g.stock_num]
    log.info(f'小市值目标持仓: {g.target_list}')

    # 获取当前持仓
    current_holdings = g.strategy_holdings[1][:]

    # 卖出不在目标列表中的股票（除昨日涨停股）
    sell_list = [s for s in current_holdings
                if s not in g.target_list and s not in g.yesterday_HL_list]

    for stock in sell_list:
        order_target_value(stock, 0)
        if stock in g.strategy_holdings[1]:
            g.strategy_holdings[1].remove(stock)
        log.info(f"小市值策略卖出: {stock}")

    # 计算可用资金（策略1专用部分）
    strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
    current_value = 0
    for stock in g.strategy_holdings[1]:
        pos = get_position_compat(context, stock)
        if pos:
            current_value += pos.amount * pos.last_sale_price
    available_cash = max(0, strategy_value - current_value)

    # 买入新标的
    buy_list = [s for s in g.target_list if s not in current_holdings]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            if open_position(stock, cash_per_stock, strategy_id=1):
                log.info(f"小市值策略买入: {stock}, 金额: {cash_per_stock:.2f}")


def filter_stocks(context, stock_list):
    """股票过滤"""
    filtered = []

    for stock in stock_list:
        try:
            # 使用统一的数据获取函数
            data = get_stock_data(stock)
            if data is None:
                continue

            # 停牌检查（回测环境默认为TRADING）
            if data.get('trade_status') != 'TRADING':
                continue

            # 板块过滤 (排除创业板/科创板/北交所)
            code = stock.split('.')[0]
            if code.startswith(('30', '68', '8', '4')):
                continue

            # 价格过滤 (非涨停跌停)
            last_price = data.get('last_px', 0)
            high_limit = data.get('limit_up', 0)
            low_limit = data.get('limit_down', 0)

            if high_limit > 0 and last_price >= high_limit:  # 涨停
                continue
            if low_limit > 0 and last_price <= low_limit:   # 跌停
                continue

            filtered.append(stock)
        except Exception as e:
            log.error(f"过滤股票{stock}时出错: {str(e)}")
            continue

    return filtered


def today_is_between(context):
    """判断是否空仓月份"""
    # PTrade中获取当前日期的方式
    current_dt = datetime.now()
    month = current_dt.month
    day = current_dt.day

    if month in g.pass_months:
        return False
    elif month in [3, 12] and day >= 16:
        return False
    return True


# ====================== 策略2: 白马攻防策略 ======================
def bm_adjust_position(context):
    if not g.check_out_lists:
        bm_before_market_open(context)

    buy_stocks = g.check_out_lists

    # 卖出不在目标列表中的股票（只处理本策略持仓）
    for stock in g.strategy_holdings[2][:]:
        data = get_stock_data(stock)
        if data is None:
            continue

        # 不在买入列表则卖出
        if stock not in buy_stocks:
            # 涨停无法卖出时跳过
            last_price = data.get('last_px', 0)
            high_limit = data.get('limit_up', 0)
            if high_limit > 0 and last_price >= high_limit:
                continue

            order_target_value(stock, 0)
            if stock in g.strategy_holdings[2]:
                g.strategy_holdings[2].remove(stock)
            log.info(f"白马策略调出: {stock}")

    # 买入新标的
    position_count = len([s for s in g.strategy_holdings[2] if get_position_compat(context, s).amount > 0])

    if len(buy_stocks) > position_count:
        # 使用策略2专用资金
        value = context.portfolio.total_value * g.portfolio_value_proportion[1] / g.stock_num

        for stock in buy_stocks:
            if stock not in g.strategy_holdings[2]:
                if open_position(stock, value, strategy_id=2):
                    if len(g.strategy_holdings[2]) >= g.stock_num:
                        break


def open_position(security, value, strategy_id):
    """开仓买入并记录策略持仓"""
    if value > 0:
        order = order_target_value(security, value)
        if order:
            # 记录策略持仓
            if security not in g.strategy_holdings[strategy_id]:
                g.strategy_holdings[strategy_id].append(security)
            log.info(f"策略{strategy_id}买入 {security}, 金额: {value:.2f}")
            return True
    return False


def Market_temperature(context):
    """市场温度判断"""
    # PTrade获取历史数据方式
    try:
        index_code = '000300.SS'  # 沪深300，已转换格式
        df = get_history(220, '1d', 'close', security_list=index_code)

        if df is None or df.empty:
            return

        index300 = df['close'].values

        market_height = (np.mean(index300[-5:]) - np.min(index300)) / (np.max(index300) - np.min(index300))

        if market_height < 0.20:
            g.market_temperature = "cold"
        elif market_height > 0.90:
            g.market_temperature = "hot"
        elif np.max(index300[-60:]) / np.min(index300) > 1.20:
            g.market_temperature = "warm"

        log.info(f"市场温度: {g.market_temperature}")
    except Exception as e:
        log.error(f"市场温度计算失败: {str(e)}")


def bm_before_market_open(context):
    """开盘前运行函数"""
    Market_temperature(context)
    g.check_out_lists = []

    # 获取沪深300成分股（代码已转换）
    all_stocks = get_index_stocks('000300.SS')

    # 过滤股票
    filtered_stocks = []
    for stock in all_stocks:
        try:
            # 使用统一的数据获取函数
            data = get_stock_data(stock)
            if data is None:
                continue

            # 过滤涨停跌停开盘、停牌等
            last_price = data.get('last_px', 0)
            high_limit = data.get('limit_up', 0)
            low_limit = data.get('limit_down', 0)

            if high_limit > 0 and last_price >= high_limit:
                continue
            if low_limit > 0 and last_price <= low_limit:
                continue

            # 板块过滤
            code = stock.split('.')[0]
            if code.startswith(('30', '68', '8', '4')):
                continue

            filtered_stocks.append(stock)
        except:
            continue

    # 过滤高价股
    filtered_stocks = filter_highprice_stock(context, filtered_stocks)

    # 根据市场温度选股
    # 注意：PTrade的财务数据查询方式与聚宽完全不同
    # 这里需要根据PTrade的财务数据接口重写选股逻辑
    # 以下是简化版本，实际使用时需要完善

    g.check_out_lists = filtered_stocks[:g.stock_num]
    log.info(f"今日股票池: {g.check_out_lists}")


def MOM(stock, days):
    """动量计算"""
    try:
        df = get_history(days, '1d', 'close', security_list=stock)
        if df is None or df.empty:
            return -100

        y = np.log(df['close'].values)
        n = len(y)
        x = np.arange(n)
        weights = np.linspace(1, 2, n)
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        residuals = y - (slope * x + intercept)
        weighted_residuals = weights * residuals**2
        r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y))**2))
        score = annualized_returns * r_squared
        return score
    except:
        return -100


def Moment_rank(stock_pool, days, ll, hh):
    """动量排名"""
    score_list = []
    for stock in stock_pool:
        score = MOM(stock, days)
        score_list.append(score)

    df = pd.DataFrame(index=stock_pool, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)
    df = df[(df['score'] > ll) & (df['score'] < hh)]
    rank_list = list(df.index)
    return rank_list


def filter_highprice_stock(context, stock_list):
    """过滤高价股（>50元）"""
    hold_list = []
    positions = get_all_positions_compat(context)
    for position in positions:
        hold_list.append(position.sid)

    result = []
    for stock in stock_list:
        if stock in hold_list:
            result.append(stock)
            continue

        try:
            # 使用统一的数据获取函数
            price = get_stock_price(stock)
            if price is not None and price <= g.up_price:
                result.append(stock)
        except:
            continue

    return result


# ====================== 策略3: ETF轮动策略 ======================
def get_etf_rank(etf_pool):
    """ETF动量排名"""
    score_list = []
    for etf in etf_pool:
        try:
            df = get_history(g.m_days, '1d', 'close', security_list=etf)
            if df is None or df.empty:
                score_list.append(-100)
                continue

            y = np.log(df['close'].values)
            x = np.arange(len(y))

            # 线性回归
            slope, intercept = np.polyfit(x, y, 1)
            annualized_returns = np.exp(slope * 250) - 1  # 年化收益

            # 计算R平方
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred)**2)
            ss_tot = np.sum((y - np.mean(y))**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            score = annualized_returns * r_squared
            score_list.append(score)
        except:
            score_list.append(-100)

    df = pd.DataFrame({'etf': etf_pool, 'score': score_list})
    return df.sort_values('score', ascending=False)


def trade(context):
    """ETF交易"""
    # 获取动量最高的ETF
    rank_df = get_etf_rank(g.etf_pool)
    if rank_df.empty:
        return

    sel_etf = rank_df.iloc[0]['etf']
    current_etf = None

    # 检查当前持仓
    positions = get_all_positions_compat(context)
    for position in positions:
        if position.sid in g.etf_pool:
            current_etf = position.sid
            break

    # 策略3专用资金
    strategy_cash = context.portfolio.total_value * g.portfolio_value_proportion[2]

    # 需要调仓的情况
    if current_etf and current_etf != sel_etf:
        order_target_value(current_etf, 0)  # 卖出原ETF
        order_target_value(sel_etf, strategy_cash)  # 买入新ETF
        log.info(f"ETF调仓: {current_etf} -> {sel_etf}")
        g.etf_pre = sel_etf

    # 馀次买入或恢复持仓
    elif not current_etf and strategy_cash > 0:
        order_target_value(sel_etf, strategy_cash)
        log.info(f"ETF建仓: {sel_etf}")
        g.etf_pre = sel_etf


# ====================== 公共策略函数 ======================
def sell_stocks(context):
    """止盈止损"""
    if not g.run_stoploss:
        return

    positions = get_all_positions_compat(context)
    for position in positions:
        stock = position.sid
        cost = position.cost_basis
        price = position.last_sale_price

        # 盈利100%止盈
        if price >= cost * 2:
            order_target_value(stock, 0)
            # 从策略持仓记录中移除
            for strategy_id in [1, 2]:
                if stock in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].remove(stock)
            log.info(f"止盈卖出 {stock}, 收益率:{(price/cost-1):.2%}")

        # 亏损止损
        elif price <= cost * (1 - g.stoploss_limit):
            order_target_value(stock, 0)
            # 从策略持仓记录中移除
            for strategy_id in [1, 2]:
                if stock in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].remove(stock)
            log.info(f"止损卖出 {stock}, 亏损:{(1 - price/cost):.2%}")
            g.reason_to_sell[stock] = 'stoploss'


def check_limit_up(context):
    """检查昨日涨停股今日表现"""
    # 获取当前持仓
    positions = get_all_positions_compat(context)
    holdings = [p.sid for p in positions]

    # 获取昨日涨停股
    if holdings:
        g.yesterday_HL_list = []

        for stock in holdings:
            try:
                # 获取昨日数据
                df = get_history(1, '1d', ['close', 'high_limit'], security_list=stock)
                if df is not None and not df.empty:
                    close = df['close'].iloc[-1]
                    high_limit = df['high_limit'].iloc[-1] if 'high_limit' in df.columns else 0
                    if high_limit > 0 and close >= high_limit * 0.999:
                        g.yesterday_HL_list.append(stock)
            except:
                continue
    else:
        g.yesterday_HL_list = []

    # 检查涨停是否打开
    for stock in g.yesterday_HL_list:
        try:
            # 使用统一的数据获取函数
            data = get_stock_data(stock)
            if data is None:
                continue

            last_price = data.get('last_px', 0)
            high_limit = data.get('limit_up', 0)

            if high_limit > 0 and last_price < high_limit * 0.99:  # 打开超过1%
                order_target_value(stock, 0)
                # 从策略持仓记录中移除
                for strategy_id in [1, 2]:
                    if stock in g.strategy_holdings[strategy_id]:
                        g.strategy_holdings[strategy_id].remove(stock)
                log.info(f"涨停打开卖出 {stock}")
                g.reason_to_sell[stock] = 'limitup'
                g.limitup_stocks.append(stock)
        except Exception as e:
            log.error(f"处理股票{stock}时出错: {str(e)}")


# PTrade必选函数 - 按周期执行（回测需要此函数才能正常结束）
def handle_data(context, data):
    """
    PTrade回测引擎必选函数
    由于本策略使用run_daily定时任务执行交易，此函数保持简单
    """
    pass


# 盘后处理函数（可选，用于日志记录）
def after_trading_end(context, data):
    """每日收盘后执行"""
    pass