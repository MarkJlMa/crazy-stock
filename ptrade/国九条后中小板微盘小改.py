# PTrade策略 - 国九条后中小板微盘小改
# 转换自聚宽策略：https://www.joinquant.com/post/47946
# 原作者：子匀

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ============== 兼容函数 ==============

def get_stock_data(stock, fields=None):
    """
    统一的股票数据获取函数，自动适配回测和实盘环境
    """
    if not is_trade():
        # 回测环境
        if fields is None:
            fields = ['close', 'high_limit', 'low_limit', 'open', 'volume']

        try:
            df = get_history(1, '1d', fields, security_list=stock)
            if df is None or df.empty:
                return None

            result = {}
            for field in fields:
                if field in df.columns:
                    result[field] = df[field].iloc[-1]

            result['last_px'] = result.get('close', 0)
            result['limit_up'] = result.get('high_limit', 0)
            result['limit_down'] = result.get('low_limit', 0)
            result['trade_status'] = 'TRADING'

            return result
        except Exception as e:
            log.error(f"回测环境获取{stock}数据失败: {str(e)}")
            return None
    else:
        # 实盘环境
        try:
            snapshot = get_snapshot(stock)
            if snapshot is None:
                return None

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
            }
            return result
        except Exception as e:
            log.error(f"实盘环境获取{stock}数据失败: {str(e)}")
            return None


def get_all_positions_compat(context=None):
    """获取所有持仓（兼容回测和实盘环境）"""
    if not is_trade():
        positions = []
        if context and hasattr(context, 'portfolio') and hasattr(context.portfolio, 'positions'):
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
        return get_all_positions()


def get_position_compat(context, stock):
    """获取指定股票持仓（兼容回测和实盘环境）"""
    if not is_trade():
        if context and hasattr(context, 'portfolio') and hasattr(context.portfolio, 'positions'):
            pos = context.portfolio.positions.get(stock, None)
            if pos:
                class PositionCompat:
                    pass
                p = PositionCompat()
                p.sid = stock
                p.amount = pos.total_amount if hasattr(pos, 'total_amount') else pos.amount
                p.enable_amount = pos.closeable_amount if hasattr(pos, 'closeable_amount') else pos.enable_amount
                p.cost_basis = pos.avg_cost if hasattr(pos, 'avg_cost') else pos.cost_basis
                p.last_sale_price = pos.last_sale_price if hasattr(pos, 'last_sale_price') else pos.price
                return p
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
        return get_position(stock)


def convert_code_jq_to_ptrade(code):
    """聚宽代码转PTrade代码"""
    if isinstance(code, str):
        return code.replace('.XSHG', '.SS').replace('.XSHE', '.SZ')
    elif isinstance(code, list):
        return [c.replace('.XSHG', '.SS').replace('.XSHE', '.SZ') for c in code]
    return code


# ============== 初始化函数 ==============

def initialize(context):
    log.info(f"运行模式: {'实盘' if is_trade() else '回测'}")

    # 基准设置
    set_benchmark('399101.SZ')  # 中小板指

    # 回测环境设置
    if not is_trade():
        set_commission(commission_ratio=0.00025, min_commission=5.0)
        set_fixed_slippage(fixedslippage=0.0003)

    # 初始化全局变量
    g.trading_signal = True
    g.run_stoploss = True
    g.filter_audit = False
    g.adjust_num = True

    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.pass_months = [1, 4]
    g.limitup_stocks = []

    g.min_mv = 10
    g.max_mv = 100
    g.stock_num = 4

    g.stoploss_list = []
    g.other_sale = []
    g.stoploss_strategy = 3
    g.stoploss_limit = 0.09
    g.stoploss_market = 0.05
    g.highest = 50
    g.money_etf = '511880.SS'

    # 设置股票池
    g.security = '399101.SZ'
    set_universe(g.security)

    # 设置定时任务
    run_daily(context, prepare_stock_list, time='9:05')
    run_daily(context, trade_afternoon, time='14:00')
    run_daily(context, stop_loss, time='10:00')
    run_daily(context, close_account, time='14:50')
    run_daily(context, weekly_adjustment, time='10:00')


# ============== 核心策略函数 ==============

def prepare_stock_list(context):
    """准备股票池"""
    g.limitup_stocks = []

    # 获取持仓列表
    positions = get_all_positions_compat(context)
    g.hold_list = [p.sid for p in positions if p.amount > 0]

    # 获取昨日涨停列表
    if g.hold_list:
        g.yesterday_HL_list = []
        for stock in g.hold_list:
            data = get_stock_data(stock, ['close', 'high_limit'])
            if data and data.get('close', 0) >= data.get('high_limit', 0) * 0.998:
                g.yesterday_HL_list.append(stock)
    else:
        g.yesterday_HL_list = []

    # 判断是否为可交易日
    g.trading_signal = today_is_between(context)


def get_stock_list(context):
    """选股模块"""
    final_list = []
    MKT_index = '399101.SZ'

    # 获取指数成分股
    try:
        index_stocks = get_index_stocks(MKT_index)
        index_stocks = convert_code_jq_to_ptrade(index_stocks) if index_stocks else []
    except:
        log.error("获取指数成分股失败")
        return [g.money_etf]

    initial_list = filter_stocks(context, index_stocks)

    if not initial_list:
        log.info('无适合股票，买入ETF')
        return [g.money_etf]

    # 获取财务数据筛选
    try:
        # PTrade财务数据查询
        df = get_fundamentals(initial_list, 'valuation', ['code', 'market_cap'])
        if df is not None and not df.empty:
            # 筛选市值范围
            df = df[(df['market_cap'] >= g.min_mv) & (df['market_cap'] <= g.max_mv)]
            df = df.sort_values('market_cap').head(g.stock_num * 3)
            final_list = df['code'].tolist()
    except Exception as e:
        log.error(f"获取财务数据失败: {str(e)}")
        final_list = initial_list[:g.stock_num * 3]

    if final_list:
        # 过滤价格过高的股票
        filtered_list = []
        for stock in final_list:
            if stock in g.hold_list:
                filtered_list.append(stock)
            else:
                data = get_stock_data(stock, ['close'])
                if data and data.get('close', 0) <= g.highest:
                    filtered_list.append(stock)
        return filtered_list
    else:
        log.info('无适合股票，买入ETF')
        return [g.money_etf]


def weekly_adjustment(context):
    """每周调仓"""
    if g.trading_signal:
        if g.adjust_num:
            new_num = adjust_stock_num(context)
            g.stock_num = new_num
            log.info(f'持仓数量修改为{new_num}')

        g.target_list = get_stock_list(context)[:g.stock_num]
        log.info(f'目标股票: {g.target_list}')

        sell_list = [stock for stock in g.hold_list
                     if stock not in g.target_list and stock not in g.yesterday_HL_list]
        hold_list = [stock for stock in g.hold_list
                     if stock in g.target_list or stock in g.yesterday_HL_list]

        log.info(f"卖出: {sell_list}")
        log.info(f"已持有: {hold_list}")

        for stock in sell_list:
            order_target_value(stock, 0)

        buy_list = [stock for stock in g.target_list if stock not in g.hold_list]
        buy_security(context, buy_list, len(buy_list))
    else:
        buy_security(context, [g.money_etf], 1)
        log.info('该月份为空仓月份，持有银华日利ETF')


def check_limit_up(context):
    """检查涨停股票"""
    if g.yesterday_HL_list:
        for stock in g.yesterday_HL_list:
            data = get_stock_data(stock, ['close', 'high_limit'])
            if data:
                current_price = data.get('close', 0)
                limit_up = data.get('high_limit', 0)

                if current_price < limit_up * 0.998:
                    log.info(f"{stock}涨停打开，卖出")
                    order_target_value(stock, 0)
                    g.other_sale.append(stock)
                    g.limitup_stocks.append(stock)
                else:
                    log.info(f"{stock}涨停，继续持有")


def check_remain_amount(context):
    """检查剩余资金并买入"""
    addstock_num = len(g.other_sale)
    loss_num = len(g.stoploss_list)

    positions = get_all_positions_compat(context)
    g.hold_list = [p.sid for p in positions if p.amount > 0]

    if len(g.hold_list) < g.stock_num:
        num_stocks_to_buy = min(addstock_num, g.stock_num - len(g.hold_list))
        target_list = [stock for stock in g.target_list
                       if stock not in g.limitup_stocks][:num_stocks_to_buy]

        if target_list:
            log.info(f'有余额可用{round(context.portfolio.cash, 2)}元，买入{target_list}')
            buy_security(context, target_list, len(target_list))

        if loss_num != 0:
            log.info(f'有余额可用{round(context.portfolio.cash, 2)}元，买入货币基金{g.money_etf}')
            buy_security(context, [g.money_etf], loss_num)

    g.stoploss_list = []
    g.other_sale = []


def trade_afternoon(context):
    """下午交易检查"""
    if g.trading_signal:
        check_limit_up(context)
        check_remain_amount(context)
        buy_security(context, [g.money_etf], 1)


def stop_loss(context):
    """止盈止损"""
    if g.run_stoploss:
        positions = get_all_positions_compat(context)

        if g.stoploss_strategy in [1, 3]:
            for pos in positions:
                if pos.amount <= 0:
                    continue

                stock = pos.sid
                price = pos.last_sale_price
                avg_cost = pos.cost_basis

                # 个股盈利止盈
                if price >= avg_cost * 2:
                    order_target_value(stock, 0)
                    log.info(f"收益100%止盈，卖出{stock}")
                    g.other_sale.append(stock)
                # 个股止损
                elif price < avg_cost * (1 - g.stoploss_limit):
                    order_target_value(stock, 0)
                    log.info(f"止损，卖出{stock}")
                    g.stoploss_list.append(stock)

        if g.stoploss_strategy in [2, 3]:
            # 市场趋势止损
            try:
                index_stocks = get_index_stocks('399101.SZ')
                if index_stocks:
                    down_count = 0
                    total_count = 0
                    for stock in index_stocks[:50]:  # 取前50只成分股
                        data = get_stock_data(stock, ['close', 'open'])
                        if data:
                            close = data.get('close', 0)
                            open_px = data.get('open', 0)
                            if open_px > 0:
                                down_ratio = 1 - close / open_px
                                down_count += down_ratio
                                total_count += 1

                    if total_count > 0:
                        avg_down = down_count / total_count
                        if avg_down >= g.stoploss_market:
                            log.info(f"大盘惨跌，平均降幅{avg_down:.2%}")
                            for pos in positions:
                                if pos.amount > 0:
                                    order_target_value(pos.sid, 0)
            except Exception as e:
                log.error(f"市场趋势止损计算失败: {str(e)}")


def adjust_stock_num(context):
    """动态调整持仓数量"""
    ma_para = 10

    try:
        df = get_history(ma_para, '1d', 'close', security_list='399101.SZ')
        if df is None or df.empty:
            return 4

        ma = df['close'].mean()
        last_row = df['close'].iloc[-1]
        diff = last_row - ma

        if diff >= 500:
            return 3
        elif diff >= 200:
            return 3
        elif diff >= -200:
            return 4
        elif diff >= -500:
            return 5
        else:
            return 6
    except:
        return 4


def filter_stocks(context, stock_list):
    """过滤股票"""
    filtered_stocks = []

    for stock in stock_list:
        try:
            data = get_stock_data(stock, ['close', 'high_limit', 'low_limit'])
            if data is None:
                continue

            # 过滤市场类型
            if stock.startswith('30') or stock.startswith('68') or \
               stock.startswith('8') or stock.startswith('4'):
                continue

            # 涨跌停过滤
            close = data.get('close', 0)
            high_limit = data.get('high_limit', 0)
            low_limit = data.get('low_limit', 0)

            if stock not in g.hold_list:
                if close >= high_limit * 0.998:  # 涨停
                    continue
                if close <= low_limit * 1.002:  # 跌停
                    continue

            # 次新股过滤（需要获取上市日期）
            # PTrade中可以通过get_security_info获取
            # 这里简化处理，假设已过滤

            filtered_stocks.append(stock)
        except Exception as e:
            continue

    return filtered_stocks


def buy_security(context, target_list, num):
    """买入模块"""
    if num == 0 or not target_list:
        return

    positions = get_all_positions_compat(context)
    position_count = len([p for p in positions if p.amount > 0])

    value = context.portfolio.cash / num

    for stock in target_list:
        if stock and value > 0:
            order_target_value(stock, value)
            log.info(f"买入{stock}（{round(value, 2)}元）")

            positions = get_all_positions_compat(context)
            if len([p for p in positions if p.amount > 0]) >= g.stock_num:
                break


def today_is_between(context):
    """判断是否跳过指定月份"""
    today = datetime.now()
    month = today.month

    if month in g.pass_months:
        try:
            df = get_history(3, '1d', 'close', security_list='399303.SZ')
            if df is not None and len(df) >= 3:
                close = df['close'].values
                if close[-1] > close[-2] * 0.995 and close[-1] > close[-3] * 0.994:
                    return True
            return False
        except:
            return False
    else:
        return True


def close_account(context):
    """收盘清仓"""
    if not g.trading_signal:
        positions = get_all_positions_compat(context)
        g.hold_list = [p.sid for p in positions if p.amount > 0]

        if g.hold_list and g.hold_list != [g.money_etf]:
            for stock in g.hold_list:
                if stock == g.money_etf:
                    continue

                data = get_stock_data(stock, ['close', 'low_limit'])
                if data:
                    close = data.get('close', 0)
                    low_limit = data.get('low_limit', 0)

                    if close <= low_limit * 1.002:  # 跌停不卖
                        continue

                order_target_value(stock, 0)
                log.info(f"卖出{stock}")


def handle_data(context, data):
    """主处理函数（可选）"""
    pass
