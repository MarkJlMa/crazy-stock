"""
策略名称：
小市值日线交易策略
运行周期:
日线
策略流程：
盘前将中小板综成分股中st、停牌、退市的股票过滤得到股票池
盘中换仓，始终持有当日流通市值最小的股票（涨停标的不换仓）。
注意事项：
策略中调用的order_target_value接口的使用有场景限制，回测可以正常使用，交易谨慎使用。
回测场景下撮合是引擎计算的，因此成交之后持仓信息的更新是瞬时的，但交易场景下信息的更新依赖于柜台数据
的返回，无法做到瞬时同步，可能造成重复下单。详细原因请看帮助文档。

策略弊端：
1. 小市值股票流动性差，大资金难以进出，容易产生较大滑点
2. 小市值股票波动大，风险较高，可能出现大幅回撤
3. 策略换仓频率较高，交易成本侵蚀收益
4. 小市值股票容易受市场情绪影响，极端行情下可能连续跌停无法卖出
5. 策略依赖历史市值数据，存在一定的滞后性

回测与实盘差异：
1. 滑点差异：回测通常难以准确模拟小市值股票的真实滑点，实盘滑点可能更大
2. 成交时间：回测按收盘价成交，实盘需在交易时段内成交，价格可能偏离
3. 停牌处理：回测可自动跳过停牌股，实盘停牌股无法卖出，可能影响资金利用率
4. 涨跌停限制：回测涨停股可能仍能买入，实盘涨停股买入困难；跌停股实盘无法卖出
5. 流动性风险：回测假设能按目标市值成交，实盘小市值股票可能因流动性不足无法完全成交
6. 数据延迟：实盘行情数据可能有延迟，影响决策时效性
"""


# 初始化
def initialize(context):
    # 设置基准指数
    set_benchmark("000300.XSHG")
    # 股票池对应指数代码
    g.index = "399101.XBHS"  # 中小板综
    # 持有股票数量
    g.buy_stock_count = 10
    # 筛选股票数量
    g.screen_stock_count = 10
    if not is_trade():
        set_backtest()  # 设置回测条件
    
    # 打印持仓信息
    run_daily(context, print_position_info, "14:55")


# 设置回测条件
def set_backtest():
    set_limit_mode("UNLIMITED")
    # 设置交易费用：万1不免五
    set_commission(commission_ratio=0.0001, min_commission=5.0, type="STOCK")


# 盘前处理
def before_trading_start(context, data):
    g.pre_position_list = list(get_positions().keys())
    g.stock_list = get_index_stocks(g.index)
    # 指数成分股按昨日收盘时的流通市值进行从小到大排序，截取市值最小的100个标的进行股票状态筛选（考虑回测速度）
    df = get_fundamentals(g.stock_list, "valuation", fields=["total_value", "a_floats", "float_value"],
                          date=context.previous_date).sort_values(by="float_value").head(100)
    stock_list_tmp = df.index.tolist()
    # 将ST、停牌、退市三种状态的股票剔除当日的股票池
    stock_list_tmp = filter_stock_by_status(stock_list_tmp, filter_type=["ST", "HALT", "DELISTING"], query_date=None)
    # 保留状态筛选后的股票，并取其中流通市值最小的10个股票
    df = df[df.index.isin(stock_list_tmp)]
    g.df = df.head(g.screen_stock_count)


# 盘中处理
def handle_data(context, data):
    buy_stocks = get_trade_stocks(context, data)
    log.info("buy_stocks:%s" % buy_stocks)
    trade(context, buy_stocks)


# 交易函数
def trade(context, buy_stocks):
    # 获取持仓中涨停的标的（涨停股不卖，包括买入后变成ST的涨停股）
    hold_up_limit_stocks = []
    for stock in list(context.portfolio.positions.keys()):
        try:
            limit_info = check_limit(stock)
            if limit_info.get(stock) == 1:
                hold_up_limit_stocks.append(stock)
        except:
            pass

    # 计算总资产和目标平均市值
    total_value = context.portfolio.portfolio_value
    target_value_per_stock = total_value / g.buy_stock_count

    # 第一步：卖出不在买入列表且非涨停的标的（清仓）
    # 注意：涨停股不卖，即使变成ST也不卖（等开板后再处理）
    for stock in context.portfolio.positions:
        if stock not in buy_stocks and stock not in hold_up_limit_stocks:
            order_target_value(stock, 0)
            log.info("清仓卖出: %s" % stock)

    # 第二步：对目标持仓进行调仓（涨多的卖掉，平给其他股票）
    # 排除涨停股，只对可交易的目标股票进行平均持仓调整
    tradeable_stocks = [stock for stock in buy_stocks if stock not in hold_up_limit_stocks]

    for stock in tradeable_stocks:
        current_pos = context.portfolio.positions.get(stock)
        if current_pos and current_pos.amount > 0:
            current_value = current_pos.amount * current_pos.last_sale_price
            # 如果当前持仓市值超过目标市值，卖出超额部分
            if current_value > target_value_per_stock * 1.05:  # 5%容差
                order_target_value(stock, target_value_per_stock)
                log.info("调仓卖出: %s, 当前市值 %.2f -> 目标市值 %.2f" % (stock, current_value, target_value_per_stock))
        else:
            # 不在持仓中，需要买入
            order_target_value(stock, target_value_per_stock)
            log.info("买入: %s, 目标市值 %.2f" % (stock, target_value_per_stock))


# 获取买入股票池（涨停股不参与换仓）
def get_trade_stocks(context, data):
    # 获取持仓中涨停的标的
    hold_up_limit_stock = [stock.replace("XSHG", "SS").replace("XSHE", "SZ") for stock in g.pre_position_list if check_limit(stock)[stock] == 1]
    df = g.df
    if df.empty:
        return hold_up_limit_stock
    df["code"] = df.index
    # 计算当时最新的流通市值（昨日的流通股本*最新价）
    df["curr_float_value"] = df.apply(lambda x: x["a_floats"] * data[x["code"]].price, axis=1)
    df = df[df["curr_float_value"] != 0]
    # 获取股票标的（按流通市值从小到大排序）        
    stocks = df.sort_values(by="curr_float_value").index.tolist()
    # 计算本次拟买入的数量（最大持仓量-持仓中涨停的数量（因为涨停股不卖））
    count = g.buy_stock_count - len(hold_up_limit_stock)
    check_out_lists = stocks[:count]
    check_out_lists = check_out_lists + hold_up_limit_stock
    return check_out_lists

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