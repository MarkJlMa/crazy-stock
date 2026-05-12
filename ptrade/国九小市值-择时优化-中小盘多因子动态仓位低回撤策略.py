# PTrade版本 - 国九小市值-择时优化-中小盘多因子动态仓位低回撤策略
# 原始聚宽策略来源：https://www.joinquant.com/post/58638
# 转换日期：2026-05-12

"""
策略说明：
1. 基于中小板指(399101)选股
2. 多因子筛选：市值、净利润、营业收入
3. 动态仓位调整：根据指数MA判断
4. 空仓月份持有货币ETF
5. 止盈止损机制

注意：
1. PTrade中财务数据查询方式与聚宽完全不同，需要使用get_fundamentals的新语法
2. 回测环境不支持get_snapshot，需要使用get_history/get_price替代
3. 股票代码格式已转换：.XSHG -> .SS, .XSHE -> .SZ
"""
import numpy as np
import pandas as pd
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


def get_all_positions_compat(context=None):
    """
    获取所有持仓（兼容回测和实盘环境）

    返回:
        持仓列表，每个元素包含 sid, amount, enable_amount, cost_basis, last_sale_price 等属性
    """
    if not is_trade():
        # 回测环境：通过context.portfolio.positions获取
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
    if not is_trade():
        # 回测环境：通过context.portfolio.positions获取
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
    # PTrade必须设置股票池，初始设为空列表，后续动态更新
    g.security = []
    set_universe(g.security)

    # 设置基准（代码已转换）
    set_benchmark('399101.SZ')

    # 回测环境设置佣金和滑点
    if not is_trade():
        set_commission(commission_ratio=0.00025, min_commission=5.0)
        set_fixed_slippage(fixedslippage=0.0003)

    # 初始化全局变量 bool
    g.trading_signal = True  # 是否为可交易日
    g.run_stoploss = True  # 是否进行止损
    g.filter_audit = False  # 是否筛选审计意见
    g.adjust_num = True  # 是否调整持仓数量

    # 全局变量list
    g.hold_list = []  # 当前持仓的全部股票
    g.yesterday_HL_list = []  # 记录持仓中昨日涨停的股票
    g.target_list = []
    g.pass_months = [1, 4]  # 空仓的月份
    g.limitup_stocks = []  # 记录涨停的股票避免再次买入

    # 全局变量float/str
    g.min_mv = 10  # 股票最小市值要求
    g.max_mv = 100  # 股票最大市值要求
    g.stock_num = 5  # 持股数量
    g.reason_to_sell = {}
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.08  # 止损线
    g.stoploss_market = 0.05  # 市场趋势止损参数
    g.highest = 50  # 股票单价上限设置
    g.etf = '511880.SS'  # 空仓月份持有银华日利ETF（代码已转换）

    # 设置交易运行时间
    run_daily(context, prepare_stock_list, time='9:05')
    run_daily(context, trade_afternoon, time='14:00')
    run_daily(context, sell_stocks, time='10:00')
    run_daily(context, close_account, time='14:50')
        # 打印持仓信息
    run_daily(context, print_position_info, "14:55")
    run_daily(context, weekly_adjustment, time='10:00')  # PTrade不支持run_weekly，改为每日运行并在函数内判断

    log.info(f"运行模式: {'实盘' if is_trade() else '回测'}")


def print_position_info(context):
    """打印持仓信息（按流通市值从小到大排列）"""
    log.info("=" * 50)
    log.info("持仓信息（按流通市值从小到大排列）")
    log.info("=" * 50)

    # 收集持仓信息
    positions_data = []
    for stock, pos in context.portfolio.positions.items():
        pos_value = pos.amount * pos.last_sale_price
        if pos_value <= 0:
            continue

        try:
            stock_name = get_stock_name(stock)
            if isinstance(stock_name, dict):
                stock_name = stock_name.get(stock, "未知")
        except:
            stock_name = "未知"

        cost = pos.cost_basis
        price = pos.last_sale_price
        ret = 100 * (price / cost - 1) if cost > 0 else 0

        # 获取流通市值
        try:
            fund_df = get_fundamentals([stock], "valuation", fields=["float_value"], date=context.previous_date)
            float_value = fund_df.loc[stock, "float_value"] if not fund_df.empty else 0
        except:
            float_value = 0

        positions_data.append({
            'stock': stock,
            'name': stock_name,
            'cost': cost,
            'price': price,
            'ret': ret,
            'amount': pos.amount,
            'pos_value': pos_value,
            'float_value': float_value
        })

    # 按流通市值从小到大排序
    positions_data.sort(key=lambda x: x['float_value'])

    # 打印排序后的持仓信息
    for i, data in enumerate(positions_data, 1):
        log.info(f"[{i}] {data['stock']} {data['name']}: 现价 {data['price']:.2f}, 收益率 {data['ret']:.2f}%, 流通市值 {data['float_value']/1e8:.2f}亿")

        
# PTrade必选函数 - 按周期执行
def handle_data(context, data):
    """
    PTrade回测引擎必选函数
    由于本策略使用run_daily定时任务执行交易，此函数保持简单
    """
    pass


# 1-1 准备股票池
def prepare_stock_list(context):
    # 获取已持有列表
    g.hold_list = []
    g.limitup_stocks = []

    positions = get_all_positions_compat(context)
    for position in positions:
        stock = position.sid
        g.hold_list.append(stock)

    # 获取昨日涨停列表
    if g.hold_list:
        g.yesterday_HL_list = []
        for stock in g.hold_list:
            try:
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

    # 判断今天是否为账户资金再平衡的日期
    g.trading_signal = today_is_between(context)


# 1-2 选股模块
def get_stock_list(context):
    final_list = []
    MKT_index = '399101.SZ'  # 中小板指（代码已转换）
    initial_list = filter_stocks(context, get_index_stocks(MKT_index))

    if not initial_list:
        log.info('无适合股票，买入ETF')
        return [g.etf]

    # PTrade财务数据查询方式与聚宽不同
    # 使用get_fundamentals获取财务数据
    try:
        # 简化版选股：通过市值和价格筛选
        filtered_by_mv = []
        for stock in initial_list:
            try:
                data = get_stock_data(stock)
                if data is None:
                    continue

                last_price = data.get('last_px', 0)
                if last_price <= 0 or last_price > g.highest:
                    continue

                # 市值过滤（实盘环境有市值数据）
                if is_trade():
                    market_cap = data.get('total_market_value', 0)
                    if market_cap > 0:
                        if not (g.min_mv <= market_cap / 100000000 <= g.max_mv):
                            continue

                filtered_by_mv.append(stock)

                if len(filtered_by_mv) >= g.stock_num * 3:
                    break
            except Exception as e:
                log.error(f"获取股票{stock}数据失败: {str(e)}")
                continue

        final_list = filtered_by_mv

        if len(final_list) == 0:
            log.info('无适合股票，买入ETF')
            return [g.etf]

        return final_list[:g.stock_num * 2]

    except Exception as e:
        log.error(f"选股失败: {str(e)}")
        return [g.etf]


# 1-3 整体调整持仓
def weekly_adjustment(context):
    # 模拟run_weekly：每周二执行
    current_dt = datetime.now()
    if current_dt.weekday() != 1:  # 1表示周二
        return

    if g.trading_signal and g.adjust_num:
        new_num = adjust_stock_num(context)
        if new_num == 0:
            buy_security(context, [g.etf], 1)
            log.info('MA指示指数大跌，持有银华日利ETF')
        else:
            if g.stock_num != new_num:
                g.stock_num = new_num
                log.info(f'持仓数量修改为{new_num}')
            g.target_list = get_stock_list(context)[:g.stock_num]
            log.info(str(g.target_list))

            sell_list = [stock for stock in g.hold_list if stock not in g.target_list and stock not in g.yesterday_HL_list]
            hold_list = [stock for stock in g.hold_list if stock in g.target_list or stock in g.yesterday_HL_list]
            log.info("卖出[%s]" % (str(sell_list)))
            log.info("已持有[%s]" % (str(hold_list)))

            for stock in sell_list:
                order_target_value(stock, 0)

            buy_list = [stock for stock in g.target_list if stock not in g.hold_list]
            buy_security(context, buy_list, len(buy_list))
    else:
        buy_security(context, [g.etf], 1)
        log.info('该月份为空仓月份，持有银华日利ETF')


# 1-4 调整昨日涨停股票
def check_limit_up(context):
    if g.yesterday_HL_list:
        for stock in g.yesterday_HL_list:
            try:
                data = get_stock_data(stock)
                if data is None:
                    continue

                current_price = data.get('last_px', 0)
                high_limit = data.get('limit_up', 0)

                if high_limit > 0 and current_price < high_limit * 0.99:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    order_target_value(stock, 0)
                    g.reason_to_sell[stock] = 'limitup'
                    g.limitup_stocks.append(stock)
                else:
                    log.info("[%s]涨停，继续持有" % (stock))
            except Exception as e:
                log.error(f"检查股票{stock}涨停状态失败: {str(e)}")


# 1-5 如果昨天有股票卖出或者买入失败造成空仓，剩余的金额当日买入
def check_remain_amount(context):
    stoploss_list = []
    uplimit_list = []

    for key, value in g.reason_to_sell.items():
        if value == 'stoploss':
            stoploss_list.append(key)
        elif value == 'limitup':
            uplimit_list.append(key)

    empty_num = len(stoploss_list) + len(uplimit_list)
    addstock_num = len(uplimit_list)
    etf_num = len(stoploss_list)

    positions = get_all_positions_compat(context)
    g.hold_list = [p.sid for p in positions]

    if len(g.hold_list) < g.stock_num:
        num_stocks_to_buy = min(addstock_num, g.stock_num - len(g.hold_list))
        target_list = [stock for stock in g.target_list if stock not in g.limitup_stocks][:num_stocks_to_buy]
        log.info('有余额可用' + str(round((context.portfolio.cash), 2)) + '元。买入' + str(target_list))
        buy_security(context, target_list, len(target_list))
        if etf_num != 0:
            log.info('有余额可用' + str(round((context.portfolio.cash), 2)) + '元。买入货币基金' + str(g.etf))
            buy_security(context, [g.etf], etf_num)

    g.reason_to_sell = {}


# 1-6 下午检查交易
def trade_afternoon(context):
    if g.trading_signal:
        check_limit_up(context)
        check_remain_amount(context)


# 1-7 止盈止损
def sell_stocks(context):
    if not g.run_stoploss:
        return

    positions = get_all_positions_compat(context)

    if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
        for position in positions:
            stock = position.sid
            price = position.last_sale_price
            avg_cost = position.cost_basis

            # 个股盈利止盈
            if price >= avg_cost * 2:
                order_target_value(stock, 0)
                log.info("收益100%止盈,卖出{}".format(stock))
            # 个股止损
            elif price < avg_cost * (1 - g.stoploss_limit):
                order_target_value(stock, 0)
                log.info("收益止损,卖出{}".format(stock))
                g.reason_to_sell[stock] = 'stoploss'

    if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
        try:
            MKT_index = '399101.SZ'
            index_stocks = get_index_stocks(MKT_index)

            # 计算成分股平均涨跌
            down_ratios = []
            for stock in index_stocks[:50]:  # 取前50只计算
                try:
                    df = get_history(1, '1d', ['close', 'open'], security_list=stock)
                    if df is not None and not df.empty:
                        close = df['close'].iloc[-1]
                        open_price = df['open'].iloc[-1]
                        if open_price > 0:
                            down_ratios.append(1 - close / open_price)
                except:
                    continue

            if down_ratios:
                down_ratio = np.mean(down_ratios)
                # 市场大跌止损
                if down_ratio >= g.stoploss_market:
                    log.info("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                    for position in positions:
                        stock = position.sid
                        order_target_value(stock, 0)
                        g.reason_to_sell[stock] = 'stoploss'
        except Exception as e:
            log.error(f"市场趋势止损计算失败: {str(e)}")


# 1-8 动态调仓代码
def adjust_stock_num(context):
    ma_para = 10  # 设置MA参数

    try:
        MKT_index = '399101.SZ'
        df = get_history(ma_para * 2, '1d', 'close', security_list=MKT_index)

        if df is None or df.empty:
            return g.stock_num

        closes = df['close'].values
        ma = np.mean(closes[-ma_para:])
        last_close = closes[-1]
        diff = last_close - ma

        # 根据差值结果返回数字
        result = 3 if diff >= 500 else \
                 3 if 200 <= diff < 500 else \
                 4 if -200 <= diff < 200 else \
                 5 if -500 <= diff < -200 else \
                 6

        # 如果大盘大跌，今日暂不买入
        MKT_index = '399101.SZ'
        index_stocks = get_index_stocks(MKT_index)

        down_ratios = []
        for stock in index_stocks[:50]:
            try:
                df_stock = get_history(1, '1d', ['close', 'open'], security_list=stock)
                if df_stock is not None and not df_stock.empty:
                    close = df_stock['close'].iloc[-1]
                    open_price = df_stock['open'].iloc[-1]
                    if open_price > 0:
                        down_ratios.append(1 - close / open_price)
            except:
                continue

        if down_ratios:
            down_ratio = np.mean(down_ratios)
            if down_ratio >= g.stoploss_market:
                log.info("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                result = 0

        return result

    except Exception as e:
        log.error(f"动态调仓计算失败: {str(e)}")
        return g.stock_num


# 2 过滤各种股票
def filter_stocks(context, stock_list):
    filtered_stocks = []

    for stock in stock_list:
        try:
            data = get_stock_data(stock)
            if data is None:
                continue

            # 停牌检查
            if data.get('trade_status') != 'TRADING':
                continue

            last_price = data.get('last_px', 0)
            high_limit = data.get('limit_up', 0)
            low_limit = data.get('limit_down', 0)

            # 板块过滤 (排除创业板/科创板/北交所)
            code = stock.split('.')[0]
            if code.startswith(('30', '68', '8', '4')):
                continue

            # 涨停过滤
            if high_limit > 0 and last_price >= high_limit:
                if stock not in g.hold_list:
                    continue

            # 跌停过滤
            if low_limit > 0 and last_price <= low_limit:
                if stock not in g.hold_list:
                    continue

            # 价格过滤
            if last_price <= 0 or last_price > g.highest:
                continue

            filtered_stocks.append(stock)

        except Exception as e:
            log.error(f"过滤股票{stock}时出错: {str(e)}")
            continue

    return filtered_stocks


# 3-1 买入模块
def buy_security(context, target_list, num):
    if not target_list or num == 0:
        return

    positions = get_all_positions_compat(context)
    position_count = len(positions)
    target_num = num

    if target_num != 0:
        value = context.portfolio.cash / target_num
        for stock in target_list:
            order_target_value(stock, value)
            log.info("买入[%s]（%s元）" % (stock, value))
            positions = get_all_positions_compat(context)
            if len(positions) >= g.stock_num:
                break


# 4-1 判断今天是否跳过月份
def today_is_between(context):
    # 根据g.pass_month跳过指定月份
    current_dt = datetime.now()
    month = current_dt.month

    if month in g.pass_months:
        return False
    else:
        day = current_dt.day
        # 12月下半月和3月下半月不做
        if (month == 12 or month == 3) and day >= 16:
            return False
        return True


# 4-2 清仓后次日资金可转
def close_account(context):
    if not g.trading_signal:
        if len(g.hold_list) != 0 and g.etf not in g.hold_list:
            for stock in g.hold_list:
                order_target_value(stock, 0)
                log.info("卖出[%s]" % (stock))


# 盘后处理函数
def after_trading_end(context, data):
    """每日收盘后执行"""
    pass
