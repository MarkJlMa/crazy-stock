"""
策略名称：三驾马车组合策略
运行周期：日线
策略说明：
    本策略由三个子策略组合而成：
    策略1：小市值策略（57%资金）- 选取中小板中市值较小、基本面优质的股票
    策略2：白马股策略（36%资金）- 基于市场温度选取沪深300中的优质白马股
    策略3：ETF轮动策略（7%资金）- 动量轮动选择表现最佳的ETF

    风控模块：
    - 止损：8%
    - 止盈：100%
    - 涨停股处理：涨停股次日开盘卖出

注意事项：
    策略中调用的order_target_value接口的使用有场景限制，回测可以正常使用，交易谨慎使用。
    回测场景下撮合是引擎计算的，因此成交之后持仓信息的更新是瞬时的，但交易场景下信息的更新依赖于柜台数据
    的返回，无法做到瞬时同步，可能造成重复下单。详细原因请看帮助文档。
"""

import numpy as np
import pandas as pd
import math
from datetime import datetime


# ====================== 初始化函数 ======================
def initialize(context):
    set_params(context)
    set_benchmark("000300.XSHG")

    if not is_trade():
        set_backtest()

    # 设置定时任务
    # 策略1：小市值策略 - 每周二执行选股和调仓
    run_daily(context, xsz_daily_check, "10:00")

    # 策略2：白马股策略 - 每月第一个交易日
    run_daily(context, bm_daily_check, "09:45")

    # 策略3：ETF轮动 - 每日执行
    run_daily(context, etf_trade, "10:00")

    # 风控模块 - 每日执行
    run_daily(context, sell_stocks, "10:00")
    run_daily(context, check_limit_up, "14:00")

    # 打印持仓信息
    run_daily(context, print_position_info, "14:55")


# 设置策略参数
def set_params(context):
    # 风控参数
    g.run_stoploss = True
    g.stoploss_limit = 0.08

    # 通用参数
    g.stock_num = 5
    g.up_price = 50
    g.pass_months = [1, 4]

    # 策略持仓记录
    g.strategy_holdings = {
        1: [],
        2: [],
    }

    # 策略1：小市值参数
    g.trading_signal = True
    g.yesterday_HL_list = []
    g.target_list = []
    g.limitup_stocks = []
    g.min_mv = 10
    g.max_mv = 100
    g.reason_to_sell = {}

    # 策略2：白马股参数
    g.check_out_lists = []
    g.market_temperature = "warm"
    g.roe_weight = 10
    g.roa_weight = 6
    g.last_bm_month = -1

    # 策略3：ETF参数
    g.etf_pool = [
        "518880.XSHG",  # 黄金ETF
        "513100.XSHG",  # 纳指100
        "159915.XSHE",  # 创业板
        "510180.XSHG",  # 上证180
        "512290.XSHG",  # 生物医药
        "513020.XSHG",  # 港股科技
        "515070.XSHG",  # 人工智能
        "588120.XSHG",  # 科创板
    ]
    g.m_days = 25
    g.etf_pre = None

    # 资金分配比例 [策略1, 策略2, 策略3]
    g.portfolio_value_proportion = [0.57, 0.36, 0.07]


# 设置回测条件
def set_backtest():
    set_commission(0.00025, 5.0)
    set_slippage(0.002)
    set_limit_mode("UNLIMITED")


# ====================== 策略1：小市值策略 ======================
def xsz_daily_check(context):
    """小市值策略每日检查 - 周二执行选股和调仓"""
    current_dt = get_current_dt(context)

    # 判断是否为周二 (weekday=1)
    if current_dt.weekday() != 1:
        return

    # 判断是否空仓月份
    month = current_dt.month
    day = current_dt.day

    if month in g.pass_months:
        g.trading_signal = False
    elif month in [3, 12] and day >= 16:
        g.trading_signal = False
    else:
        g.trading_signal = True

    if not g.trading_signal:
        # 空仓月份清仓
        for stock in g.strategy_holdings[1][:]:
            order_target_value(stock, 0)
            if stock in g.strategy_holdings[1]:
                g.strategy_holdings[1].remove(stock)
        log.info("小市值策略：空仓月份，已清仓")
        return

    # 获取目标股票池
    g.target_list = xsz_get_stock_list(context)[:g.stock_num]
    log.info(f"小市值目标持仓: {g.target_list}")

    if not g.target_list:
        return

    # 调仓
    xsz_adjust_position(context)


def xsz_get_stock_list(context):
    """小市值选股模块"""
    index_code = "399101.XBHS"
    try:
        initial_list = get_index_stocks(index_code)
    except:
        initial_list = get_Ashares()

    if not initial_list:
        return []

    # 过滤股票
    filtered_list = filter_stocks(context, initial_list)

    if not filtered_list:
        return []

    # 获取财务数据
    try:
        df = get_fundamentals(filtered_list, "valuation",
                              fields=["market_cap", "turnover_ratio"])
        if df.empty:
            return []

        # 市值筛选
        df = df[(df["market_cap"] >= g.min_mv) & (df["market_cap"] <= g.max_mv)]
        df = df[df["turnover_ratio"] > 0.5]

        # 按市值排序
        df = df.sort_values(by="market_cap").head(g.stock_num * 3)

        return df.index.tolist()
    except Exception as e:
        log.error(f"小市值选股错误: {e}")
        return []


def xsz_adjust_position(context):
    """小市值调仓"""
    current_holdings = g.strategy_holdings[1][:]

    # 卖出不在目标列表中的股票（排除涨停股）
    sell_list = [s for s in current_holdings
                  if s not in g.target_list and s not in g.yesterday_HL_list]

    for stock in sell_list:
        order_target_value(stock, 0)
        if stock in g.strategy_holdings[1]:
            g.strategy_holdings[1].remove(stock)
        log.info(f"小市值策略卖出: {stock}")

    # 计算可用资金
    strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
    current_value = sum([pos.amount * pos.last_sale_price for pos in context.portfolio.positions.values()
                          if pos.sid in g.strategy_holdings[1]])
    available_cash = max(0, strategy_value - current_value)

    # 买入新股票
    buy_list = [s for s in g.target_list if s not in current_holdings]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            if open_position(stock, cash_per_stock, strategy_id=1):
                log.info(f"小市值策略买入: {stock}, 金额: {cash_per_stock:.2f}")


# ====================== 策略2：白马股策略 ======================
def bm_daily_check(context):
    """白马股策略每日检查 - 每月前5个交易日执行"""
    current_dt = get_current_dt(context)
    month = current_dt.month
    day = current_dt.day

    # 只在每月前5个交易日执行一次
    if day > 5:
        return

    # 同一个月只执行一次
    if g.last_bm_month == month:
        return

    g.last_bm_month = month

    # 计算市场温度
    calculate_market_temperature(context)

    # 获取股票池
    bm_before_market_open(context)

    # 调仓
    bm_adjust_position(context)


def calculate_market_temperature(context):
    """市场温度判断"""
    try:
        df = get_price("000300.XSHG", frequency="1d", fields=["close"], count=220)
        if df.empty:
            return

        close = df["close"].values
        ma5 = np.mean(close[-5:])
        min_price = np.min(close)
        max_price = np.max(close)

        market_height = (ma5 - min_price) / (max_price - min_price)

        if market_height < 0.20:
            g.market_temperature = "cold"
        elif market_height > 0.90:
            g.market_temperature = "hot"
        elif np.max(close[-60:]) / min_price > 1.20:
            g.market_temperature = "warm"

        log.info(f"市场温度: {g.market_temperature}")
    except Exception as e:
        log.error(f"计算市场温度错误: {e}")


def bm_before_market_open(context):
    """白马股选股"""
    g.check_out_lists = []

    try:
        all_stocks = get_index_stocks("000300.XSHG")
    except:
        all_stocks = []

    if not all_stocks:
        return

    # 过滤股票
    all_stocks = filter_stocks(context, all_stocks)
    all_stocks = filter_highprice_stock(context, all_stocks)

    if not all_stocks:
        return

    # 获取财务数据
    try:
        df = get_fundamentals(all_stocks, "valuation",
                              fields=["pb_ratio", "roe", "roa"])

        if df.empty:
            return

        # 根据市场温度筛选
        if g.market_temperature == "cold":
            df = df[(df["pb_ratio"] > 0) & (df["pb_ratio"] < 1)]
            df = df[df["roe"] > 0.10]
        elif g.market_temperature == "warm":
            df = df[(df["pb_ratio"] > 0) & (df["pb_ratio"] < 1)]
            df = df[df["roe"] > 0.12]
        else:  # hot
            df = df[df["pb_ratio"] > 0]
            df = df[df["roe"] > 0.15]

        # 排序打分
        df["roe_rank"] = df["roe"].rank(ascending=False)
        df["roa_rank"] = df["roa"].rank(ascending=False)
        df["point"] = g.roe_weight * df["roe_rank"] + g.roa_weight * df["roa_rank"]

        df = df.sort_values(by="point")
        g.check_out_lists = df.index.tolist()[:g.stock_num]

        log.info(f"白马股选股: {g.check_out_lists}")
    except Exception as e:
        log.error(f"白马股选股错误: {e}")


def bm_adjust_position(context):
    """白马股调仓"""
    buy_stocks = g.check_out_lists

    if not buy_stocks:
        return

    # 卖出不在列表中的股票
    for stock in g.strategy_holdings[2][:]:
        if stock not in buy_stocks:
            order_target_value(stock, 0)
            if stock in g.strategy_holdings[2]:
                g.strategy_holdings[2].remove(stock)
            log.info(f"白马股策略卖出: {stock}")

    # 买入新股票
    position_count = len([s for s in context.portfolio.positions.keys()
                          if s in g.strategy_holdings[2]])

    if len(buy_stocks) > position_count:
        value = context.portfolio.total_value * g.portfolio_value_proportion[1] / g.stock_num

        for stock in buy_stocks:
            if stock not in g.strategy_holdings[2]:
                if open_position(stock, value, strategy_id=2):
                    if len(g.strategy_holdings[2]) >= g.stock_num:
                        break


# ====================== 策略3：ETF轮动策略 ======================
def etf_trade(context):
    """ETF轮动策略"""
    rank_df = get_etf_rank(g.etf_pool)

    if rank_df.empty:
        return

    sel_etf = rank_df.iloc[0]["etf"]
    current_etf = None

    # 检查当前持仓
    for asset in context.portfolio.positions:
        if asset in g.etf_pool:
            current_etf = asset
            break

    # 策略3专用资金
    strategy_cash = context.portfolio.total_value * g.portfolio_value_proportion[2]

    # 换仓
    if current_etf and current_etf != sel_etf:
        order_target_value(current_etf, 0)
        order_target_value(sel_etf, strategy_cash)
        log.info(f"ETF换仓: {current_etf} -> {sel_etf}")
        g.etf_pre = sel_etf
    elif not current_etf and strategy_cash > 0:
        order_target_value(sel_etf, strategy_cash)
        log.info(f"ETF建仓: {sel_etf}")
        g.etf_pre = sel_etf


def get_etf_rank(etf_pool):
    """ETF动量排名"""
    score_list = []

    for etf in etf_pool:
        try:
            df = get_price(etf, frequency="1d", fields=["close"], count=g.m_days)
            if df.empty:
                score_list.append(-100)
                continue

            y = np.log(df["close"].values)
            x = np.arange(len(y))

            # 线性回归
            slope, intercept = np.polyfit(x, y, 1)
            annualized_returns = np.exp(slope * 250) - 1

            # 计算R平方
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            score = annualized_returns * r_squared
            score_list.append(score)
        except:
            score_list.append(-100)

    df = pd.DataFrame({"etf": etf_pool, "score": score_list})
    return df.sort_values("score", ascending=False)


# ====================== 风控模块 ======================
def sell_stocks(context):
    """止盈止损"""
    if not g.run_stoploss:
        return

    for stock, pos in context.portfolio.positions.items():
        # 计算持仓市值
        pos_value = pos.amount * pos.last_sale_price
        if pos_value <= 0:
            continue

        current_price = pos.last_sale_price
        cost = pos.cost_basis

        if cost <= 0:
            continue

        # 止盈：盈利100%
        if current_price >= cost * 2:
            order_target_value(stock, 0)
            for strategy_id in [1, 2]:
                if stock in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].remove(stock)
            log.info(f"止盈卖出 {stock}, 收益率: {(current_price/cost-1):.2%}")

        # 止损：亏损8%
        elif current_price <= cost * (1 - g.stoploss_limit):
            order_target_value(stock, 0)
            for strategy_id in [1, 2]:
                if stock in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].remove(stock)
            log.info(f"止损卖出 {stock}, 亏损: {(1-current_price/cost):.2%}")
            g.reason_to_sell[stock] = "stoploss"


def check_limit_up(context):
    """检查涨停股，次日卖出"""
    holdings = list(context.portfolio.positions.keys())

    if not holdings:
        g.yesterday_HL_list = []
        return

    # 获取涨停信息
    g.yesterday_HL_list = []
    for stock in holdings:
        try:
            limit_info = check_limit(stock)
            if limit_info and limit_info.get(stock) == 1:
                g.yesterday_HL_list.append(stock)
        except:
            pass

    # 涨停股次日卖出
    for stock in g.yesterday_HL_list:
        try:
            # 检查是否开板
            limit_info = check_limit(stock)
            if limit_info and limit_info.get(stock) != 1:
                order_target_value(stock, 0)
                for strategy_id in [1, 2]:
                    if stock in g.strategy_holdings[strategy_id]:
                        g.strategy_holdings[strategy_id].remove(stock)
                log.info(f"涨停开板卖出 {stock}")
                g.reason_to_sell[stock] = "limitup"
                g.limitup_stocks.append(stock)
        except Exception as e:
            log.error(f"处理涨停股{stock}时出错: {e}")


# ====================== 工具函数 ======================
def filter_stocks(context, stock_list):
    """股票过滤"""
    filtered = []

    # 过滤ST、停牌、退市
    try:
        status_filtered = filter_stock_by_status(stock_list,
                                                  filter_type=["ST", "HALT", "DELISTING"],
                                                  query_date=None)
    except:
        status_filtered = stock_list

    for stock in status_filtered:
        # 过滤创业板、科创板、北交所
        if stock.startswith(("30", "68", "8", "4")):
            continue

        # 价格过滤
        try:
            df = get_price(stock, frequency="1d", fields=["close", "high_limit", "low_limit"], count=1)
            if df.empty:
                continue

            last_price = df["close"].iloc[-1]
            high_limit = df["high_limit"].iloc[-1]
            low_limit = df["low_limit"].iloc[-1]

            # 过滤涨停、跌停
            if last_price >= high_limit * 0.999:
                continue
            if last_price <= low_limit * 1.001:
                continue

            # 过滤高价股
            if last_price > g.up_price:
                continue

            filtered.append(stock)
        except:
            continue

    return filtered


def filter_highprice_stock(context, stock_list):
    """过滤高价股"""
    hold_list = list(context.portfolio.positions.keys())
    filtered = []

    for stock in stock_list:
        try:
            df = get_price(stock, frequency="1d", fields=["close"], count=1)
            if df.empty:
                continue

            last_price = df["close"].iloc[-1]
            if stock in hold_list or last_price <= g.up_price:
                filtered.append(stock)
        except:
            continue

    return filtered


def open_position(security, value, strategy_id):
    """开仓并记录策略持仓"""
    if value > 0:
        order_target_value(security, value)
        if security not in g.strategy_holdings[strategy_id]:
            g.strategy_holdings[strategy_id].append(security)
        log.info(f"策略{strategy_id}买入 {security}, 金额: {value:.2f}")
        return True
    return False


def get_current_dt(context):
    """获取当前时间"""
    if hasattr(context, "blotter") and hasattr(context.blotter, "current_dt"):
        return context.blotter.current_dt
    elif hasattr(context, "current_dt"):
        return context.current_dt
    else:
        return datetime.now()


def print_position_info(context):
    """打印持仓信息"""
    log.info("=" * 50)
    log.info("持仓信息")
    log.info("=" * 50)

    for stock, pos in context.portfolio.positions.items():
        pos_value = pos.amount * pos.last_sale_price
        if pos_value <= 0:
            continue

        try:
            stock_name = get_stock_name(stock)
        except:
            stock_name = "未知"

        cost = pos.cost_basis
        price = pos.last_sale_price
        ret = 100 * (price / cost - 1) if cost > 0 else 0

        log.info(f"股票: {stock}, 名称: {stock_name}, 成本: {cost:.2f}")
        log.info(f"现价: {price:.2f}, 收益率: {ret:.2f}%")
        log.info(f"持仓: {pos.amount:.0f}股, 市值: {pos_value:.2f}")
        log.info("-" * 50)
