#以下注释部分是PTrade版代码

"""
# 策略说明：ETF轮动策略（PTrade国金版）
# 原始策略来自聚宽，已转换为PTrade平台

"""
#以上注释部分是PTrade版代码

import numpy as np
import math
import pandas as pd
from datetime import datetime, date, timedelta

# ==================== PTrade 兼容层 ====================
def get_switch_code(code):
    # PTrade代码格式转换：只从 XSHG/XSHE 转换为 SS/SZ（单向，不会重复转换）
    if "XSHG" in code:
        return code.replace("XSHG", "SS")
    elif "XSHE" in code:
        return code.replace("XSHE", "SZ")
    # 如果已经是 SS/SZ 格式，直接返回（不做双向转换，避免重复）
    return code

def get_all_securities_ptrade():
    # 获取所有ETF列表
    etf_list = []
    
    if is_trade():
        # 实盘交易
        etf_list = get_etf_list()  # 获取ETF代码列表，仅支持交易模块
    else:
        # 回测场景
        code_list = get_trend_data().keys()  # 获取集中竞价期间代码数据
        
        for code in code_list:
            # 去掉所有可能的后缀
            bare = code.replace('.XSHG', '').replace('.XSHE', '').replace('.SS', '').replace('.SZ', '')
            # ETF代码前缀：159(深交所ETF), 51(上交所ETF), 52(上交所ETF), 56(货币ETF), 58(跨境ETF)
            if bare.startswith(('159', '51', '52', '56', '58')):
                etf_list.append(get_switch_code(code))
    
    return etf_list

def get_current_data_ptrade(stock):
    # 获取当前行情（回测/实盘兼容）
    # 返回字典包含：high_limit, low_limit, day_open, last_price
    current_data = {}
    if is_trade():
        # 实盘交易
        ret = get_snapshot(stock)
        current_data['high_limit'] = ret[stock]['up_px']
        current_data['low_limit'] = ret[stock]['down_px']
        current_data['day_open'] = ret[stock]['open_px']
        current_data['last_price'] = ret[stock]['last_px']
    else:
        # 回测环境
        his = get_history(1, '1d', ['high_limit', 'low_limit', 'open'], stock, fq='pre', include=True)
        if his is None or his.empty:
            return None
        current_data['high_limit'] = his['high_limit'].iloc[-1]
        current_data['low_limit'] = his['low_limit'].iloc[-1]
        current_data['day_open'] = his['open'].iloc[-1]

        # 获取今日分钟最新价
        his2 = get_history(1, '1m', ['price'], stock, fq='pre', include=True)
        if his2 is not None and not his2.empty:
            if 'price' in his2.columns:
                current_data['last_price'] = his2['price'].iloc[-1]
            elif 'close' in his2.columns:
                current_data['last_price'] = his2['close'].iloc[-1]
            else:
                # 取第一个数值列
                numeric_cols = his2.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    current_data['last_price'] = his2[numeric_cols[0]].iloc[-1]
                else:
                    current_data['last_price'] = 0
        else:
            # 回退：使用最近日线收盘价
            day_hist = get_history(50, '1d', ['close'], stock, fq='pre')
            if day_hist is not None and not day_hist.empty:
                current_data['last_price'] = day_hist['close'].iloc[-1]
            else:
                current_data['last_price'] = 0
    return current_data

def refresh_all_etf_cache(context):
    # 每天刷新全市场ETF列表和名称缓存
    try:
        raw_list = get_all_securities_ptrade()
        g.all_etf_cache = []
        g.all_etf_names = {}
        for code in raw_list:
            g.all_etf_cache.append(code)
            try:
                name = get_stock_name(code)
                if isinstance(name, dict):
                    name = name.get(code, code)
                g.all_etf_names[code] = str(name)
            except:
                g.all_etf_names[code] = code
        log.info(f"刷新全市场ETF缓存：{len(g.all_etf_cache)}只")
    except Exception as e:
        log.warning(f"刷新全市场ETF缓存失败: {e}")

def _normalize_price_df(df, security_list=None):
    # 标准化 get_history 返回的 DataFrame 格式，统一转为含 'time' 和 'code' 列的长格式。
    # security_list: 可选，用于在缺少code列时补充
    if df is None or df.empty:
        return df
    try:
        original_cols = df.columns.tolist() if hasattr(df, 'columns') else []
        
        # 1. 如果索引是 DatetimeIndex（可能是单只股票的情况）
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={'index': 'time'})
            # 如果没有 code 列，尝试添加
            if 'code' not in df.columns:
                # 检查是否有 security 列
                cols = df.columns.tolist()
                for code_col in ('security', 'Security', 'code', 'stock'):
                    if code_col in cols:
                        df = df.rename(columns={code_col: 'code'})
                        break
                else:
                    # 尝试从 security_list 参数获取
                    if security_list is not None:
                        if isinstance(security_list, str):
                            df['code'] = security_list
                        elif isinstance(security_list, (list, tuple)) and len(security_list) == 1:
                            df['code'] = security_list[0]
                        elif isinstance(security_list, (list, tuple)) and len(security_list) > 1:
                            # 多只股票但没有code列，需要从数据中推断
                            pass
                    # 如果还是没code，尝试用原始列的第一个字段名
                    if 'code' not in df.columns and original_cols:
                        # 检查是否可以用第一列作为代码标识
                        pass
        
        # 2. 如果有多级索引（日期 + 代码）
        elif isinstance(df.index, pd.MultiIndex):
            df = df.reset_index()
            cols = df.columns.tolist()
            for date_col in ('level_0', 'date', 'datetime', 'Date', 'Datetime'):
                if date_col in cols:
                    df = df.rename(columns={date_col: 'time'})
                    break
            for code_col in ('level_1', 'security', 'Security', 'code'):
                if code_col in cols:
                    df = df.rename(columns={code_col: 'code'})
                    break
        
        # 3. 其他情况
        else:
            if 'time' not in df.columns:
                if df.index.name is not None:
                    df = df.reset_index().rename(columns={df.index.name: 'time'})
                else:
                    df = df.reset_index().rename(columns={'index': 'time'})
            
            if 'code' not in df.columns:
                if security_list is not None:
                    if isinstance(security_list, str):
                        df['code'] = security_list
                    elif isinstance(security_list, (list, tuple)) and len(security_list) == 1:
                        df['code'] = security_list[0]
        
        # 确保 time 列存在
        if 'time' not in df.columns:
            df['time'] = None
            
    except Exception as e:
        log.warning("_normalize_price_df 异常: %s" % str(e))
    return df

def initialize(context):
    # 初始化策略（设置参数、全局变量、定时任务）
    # ==================== 系统设置 ====================
    # PTrade回测设置
    if not is_trade():
        set_volume_ratio(volume_ratio=1.0) #为了保证回测的时候完全卖出！
        set_slippage(slippage=0.0001)  # 设置滑点
        set_commission(commission_ratio=0.0001, min_commission=5.0, type="ETF")  # 设置交易费用
    
    log.info("【五福闹新春】v3.4启动！(PTrade国金版)")

    # 全市场ETF缓存
    g.all_etf_cache = []          # 全市场ETF列表（每天刷新）
    g.all_etf_names = {}          # 全市场ETF名称映射
    g.etf_money_df = None         # 成交额数据缓存（3日）

    g.sold_today = set()   # 记录当天已卖出的股票

    # 设置基准
    set_benchmark("510300.SS")

    # ==================== 固定ETF池 ====================
    g.fixed_etf_pool = [
        # 大宗商品ETF
        '518880.SS',  # 黄金ETF
        '161226.SZ',  # 国投白银LOF
        '159980.SZ',  # 有色ETF大成
        '501018.SS',  # 南方原油ETF
        '159985.SZ',  # 豆粕ETF
        # 海外ETF
        '513100.SS',  # 纳指ETF
        '159509.SZ',  # 纳指科技ETF景顺
        '513290.SS',  # 纳指生物
        '513500.SS',  # 标普500
        '159518.SZ',  # 标普油气ETF嘉实
        '159502.SZ',  # 标普生物科技ETF嘉实
        '159529.SZ',  # 标普消费ETF
        '513400.SS',  # 道琼斯
        '520830.SS',  # 沙特ETF
        '513520.SS',  # 日经ETF
        '513030.SS',  # 德国ETF
        # 港股ETF
        '513090.SS',  # 香港证券
        '513180.SS',  # 恒指科技
        '513120.SS',  # HK创新药
        '513330.SS',  # 恒生互联
        '513750.SS',  # 港股非银
        '159892.SZ',  # 恒生医药ETF
        '159605.SZ',  # 中概互联ETF
        '513190.SS',  # H股金融
        '510900.SS',  # 恒生中国
        '513630.SS',  # 香港红利
        '513920.SS',  # 港股通央企红利
        '159323.SZ',  # 港股通汽车ETF
        '513970.SS',  # 恒生消费
        # 指数ETF
        '510500.SS',  # 中证500ETF
        '512100.SS',  # 中证1000ETF
        '563300.SS',  # 中证2000
        '510300.SS',  # 沪深300ETF
        '512050.SS',  # A500E
        '510760.SS',  # 上证ETF
        '159915.SZ',  # 创业板ETF易方达
        '159949.SZ',  # 创业板50ETF
        '159967.SZ',  # 创业板成长ETF
        '588080.SS',  # 科创板50
        '588220.SS',  # 科创100
        '511380.SS',  # 可转债ETF
        # 行业ETF
        '513310.SS',  # 中韩芯片
        '588200.SS',  # 科创芯片
        '159852.SZ',  # 软件ETF
        '512880.SS',  # 证券ETF
        '159206.SZ',  # 卫星ETF
        '512400.SS',  # 有色金属ETF
        '512980.SS',  # 传媒ETF
        '159516.SZ',  # 半导体设备ETF
        '512480.SS',  # 半导体
        '515880.SS',  # 通信ETF
        '562500.SS',  # 机器人
        '159218.SZ',  # 卫星产业ETF
        '159869.SZ',  # 游戏ETF
        '159870.SZ',  # 化工ETF
        '159326.SZ',  # 电网设备ETF
        '159851.SZ',  # 金融科技ETF
        '560860.SS',  # 工业有色
        '159363.SZ',  # 创业板人工智能ETF华宝
        '588170.SS',  # 科创半导
        '159755.SZ',  # 电池ETF
        '512170.SS',  # 医疗ETF
        '512800.SS',  # 银行ETF
        '159819.SZ',  # 人工智能ETF易方达
        '512710.SS',  # 军工龙头
        '159638.SZ',  # 高端装备ETF嘉实
        '517520.SS',  # 黄金股
        '515980.SS',  # 人工智能
        '159995.SZ',  # 芯片ETF
        '159227.SZ',  # 航空航天ETF
        '512660.SS',  # 军工ETF
        '512690.SS',  # 酒ETF
        '516150.SS',  # 稀土基金
        '512890.SS',  # 红利低波
        '588790.SS',  # 科创智能
        '159992.SZ',  # 创新药ETF
        '512070.SS',  # 证券保险
        '562800.SS',  # 稀有金属
        '512010.SS',  # 医药ETF
        '515790.SS',  # 光伏ETF
        '510880.SS',  # 红利ETF
        '159928.SZ',  # 消费ETF
        '159883.SZ',  # 医疗器械ETF
        '159998.SZ',  # 计算机ETF
        '515220.SS',  # 煤炭ETF
        '561980.SS',  # 芯片设备
        '515400.SS',  # 大数据
        '515120.SS',  # 创新药
        '159566.SZ',  # 储能电池ETF易方达
        '515050.SS',  # 5GETF
        '516510.SS',  # 云计算ETF
        '159256.SZ',  # 创业板软件ETF华夏
        '159766.SZ',  # 旅游ETF
        '512200.SS',  # 地产ETF
        '513350.SS',  # 油气ETF
        '159583.SZ',  # 通信设备ETF
        '159732.SZ',  # 消费电子ETF
        '516160.SS',  # 新能源
        '516520.SS',  # 智能驾驶
        '562590.SS',  # 半导材料
        '515030.SS',  # 新汽车
        '512670.SS',  # 国防ETF
        '561330.SS',  # 矿业ETF
        '516190.SS',  # 文娱ETF
        '159840.SZ',  # 锂电池ETF工银
        '159611.SZ',  # 电力ETF
        '159981.SZ',  # 能源化工ETF
        '159865.SZ',  # 养殖ETF
        '561360.SS',  # 石油ETF
        '159667.SZ',  # 工业母机ETF
        '515170.SS',  # 食品饮料ETF
        '513360.SS',  # 教育ETF
        '159825.SZ',  # 农业ETF
        '515210.SS',  # 钢铁ETF
    ]

    g.filtered_fixed_pool = []           # 过滤后的固定ETF池
    g.dynamic_etf_pool = []              # 动态ETF池（初始为空）
    g.merged_etf_pool = []               # 合并后的ETF池
    g.ranked_etfs_result = []            # 动量计算结果的ETF列表
    g.target_etfs_list = []              # 目标ETF列表
    g.etf_names_dict = {}                # ETF名称字典
    g.cache_date = None                  # 缓存日期（用于止损）
    g.yesterday_close_cache = {}         # 昨日收盘价缓存（用于止损）

    # ==================== 策略核心参数 ====================
    g.holdings_num = 1                  # 持仓数量（1只）
    g.defensive_etf = "511880.SS"       # 防御型ETF（银华日利）
    g.min_money = 10                    # 最小交易金额（元）

    # 动量计算参数
    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9

    # 短期动量参数
    g.use_short_momentum_period = False
    g.short_momentum_lookback = 21
    g.short_momentum_min_score = 0
    g.short_momentum_max_score = 6

    # 过滤开关及参数
    g.enable_r2_filter = True
    g.r2_threshold = 0.4
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8
    g.enable_loss_filter = True
    g.loss = 0.97
    g.enable_premium_filter = True 

    # 滤波器参数
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.002
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002

    # ==================== 震荡期参数 ====================
    g.enable_range_bound_mode = True
    g.current_filter = 'laplace'
    g.risk_state = 'normal'
    g.lookback_high_low_days = 20
    g.risk_benchmark = '510300.SS'
    
    # 进入震荡期的条件开关
    g.enable_bias_trigger = True
    g.bias_threshold = 0.08
    g.ma_period = 20
    g.enable_rsi_trigger = True
    g.rsi_overbought = 70
    g.rsi_pullback = 65
    g.previous_rsi = None
    g.enable_stop_loss_trigger = True

    # 退出震荡期的条件开关
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.04
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.02
    g.max_range_bound_days = 20
    g.stable_days = 0
    
    # 震荡期控制
    g.filter_switch_cooldown = 3
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0

    # 风险监控数据
    g.stop_loss_triggered_today = False
    g.previous_drawdown = None
    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []
    
    # 止损参数
    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.95
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95

    # 流动性阈值设置
    g.avg_etf_money_threshold = None
    
    # ==================== 定时任务 ====================
    run_daily(context, morning_routine, time='09:00')
    run_daily(context, afternoon_routine, time='13:10')
    run_daily(context, reset_daily_flags, time='15:10')
    
    # 分钟级止损任务
    for hour in range(9, 15):
        for minute in range(0, 60):
            current_time = "%02d:%02d" % (hour, minute)
            if ('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57'):
                run_daily(context, lambda ctx, h=hour, m=minute: minute_level_stop_loss(ctx), time=current_time)
                run_daily(context, lambda ctx, h=hour, m=minute: minute_level_pct_stop_loss(ctx), time=current_time)
    
    # 打印策略初始化参数
    log.info("【策略参数初始化完成】")
    log.info("=== 动量得分过滤 ===")
    log.info("- 周期: %s天" % g.lookback_days)
    log.info("- 得分阈值: [%s, %s]" % (g.min_score_threshold, g.max_score_threshold))
    log.info("=== 短期动量得分过滤 ===")
    log.info("- 周期: %s天" % g.short_momentum_lookback)
    log.info("- 得分阈值: [%s, %s]" % (g.short_momentum_min_score, g.short_momentum_max_score))
    log.info("- 短期动量开关: %s" % ('启用' if g.use_short_momentum_period else '禁用'))
    log.info("=== 其他过滤条件 ===")
    log.info("- R²过滤: %s (阈值 > %.1f)" % ('启用' if g.enable_r2_filter else '禁用', g.r2_threshold))
    log.info("- 成交量过滤: %s (近%s日均量比 < %.1f)" % ('启用' if g.enable_volume_check else '禁用', g.volume_lookback, g.volume_threshold))
    log.info("- 短期风控过滤: %s" % ('启用' if g.enable_loss_filter else '禁用'))
    log.info("- 溢价率过滤: %s (PTrade版本暂不支持)" % ('禁用'))
    log.info("=== 止损机制 ===")
    log.info("- 分钟级固定比例止损: %s" % ('启用' if g.use_fixed_stop_loss else '禁用'))
    log.info("- 分钟级当日跌幅止损: %s" % ('启用' if g.use_pct_stop_loss else '禁用'))
    log.info("=== 震荡期机制 ===")
    log.info("- 震荡期开关: %s" % ('启用' if g.enable_range_bound_mode else '禁用'))
    log.info("=== 其他配置 ===")
    log.info("- 固定ETF池: %s只" % len(g.fixed_etf_pool))
    log.info("- 持仓数量: %s只" % g.holdings_num)
    log.info("- 防御ETF: %s" % g.defensive_etf)
    
    # 首次运行时，初始化震荡期状态（PTrade不支持在initialize阶段调用get_price，移到第一次晨间流水线）
    g.range_bound_initialized = False
    log.info("【策略提示】震荡期状态将在首次晨间流水线中初始化")

# ==================== 首次运行震荡期状态初始化 ====================
def init_range_bound_status(context):
    # 首次运行时，根据历史数据判断当前是否处于震荡期
    if not g.enable_range_bound_mode:
        return
    log.info("【首次运行】初始化震荡期状态...")
    try:
        end_date = get_trading_day(-1)
        end_date_str = str(end_date).replace('-', '')
        
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_history(lookback, '1d', ['close', 'high', 'low'], g.risk_benchmark, fq='pre', include=False)
        
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.info("【首次运行】数据不足，保持正常期")
            return
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = calculate_rsi(close, period=14)
        
        should_enter_range_bound = False
        signals = []
        
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter_range_bound = True
            signals.append("乖离率%.2f%%>%.0f%%" % (bias*100, g.bias_threshold*100))
        
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter_range_bound = True
                signals.append("RSI超买回落%.1f→%.1f" % (prev_rsi, current_rsi))
        
        if should_enter_range_bound:
            g.current_filter = 'range_bound'
            g.risk_state = 'range_bound'
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            log.info("【首次运行】初始化进入震荡期: %s" % '; '.join(signals))
        else:
            g.current_filter = 'laplace'
            g.risk_state = 'normal'
            if len(close) >= g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
            log.info("【首次运行】初始状态: 正常期(拉普拉斯滤波器)")
    except Exception as e:
        log.info("【首次运行】初始化震荡期状态异常: %s，保持正常期" % str(e))

# ==================== 任务流水线 ====================
def morning_routine(context):
    # 晨间准备流水线（09:00执行）
    log.info("=" * 80)
    log.info("【晨间流水线】启动...")
    
    # 首次运行时初始化震荡期状态
    if not g.range_bound_initialized:
        log.info("【首次运行】初始化震荡期状态...")
        init_range_bound_status(context)
        g.range_bound_initialized = True
    
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("【动态池更新】更新行业ETF动态池...")
    update_sector_pool(context)
    log.info("【固定池过滤】过滤固定ETF池流动性...")
    filter_fixed_pool_by_volume(context)
    log.info("【合并池】合并固定池与动态池...")
    daily_merge_etf_pools(context)
    log.info("【晨间流水线】执行完毕！")

def afternoon_routine(context):
    # 午后交易流水线（13:10执行）：震荡期退出检查 → 震荡期进入检查 → 动量计算 → 卖出执行 → 买入执行
    log.info("▶️ 【午后交易流水线】启动...")
    log.info("【震荡期退出检查】检查是否需要退出震荡期...")
    check_and_exit_range_bound_mode(context)
    log.info("【震荡期进入检查】检查是否需要进入震荡期...")
    check_and_enter_range_bound_mode(context)
    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info("⏸️ 【午后交易流水线】执行完毕！")

def reset_daily_flags(context):
    # 收盘后重置当日标志（15:10执行）：重置止损标志 → 更新震荡期统计
    g.stop_loss_triggered_today = False
    g.sold_today.clear()
    log.info("🔄 【收盘重置】今日止损标志已重置")
    # 更新震荡期交易日计数
    if g.current_filter == 'range_bound' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=str(g.range_bound_start_date).replace('-', ''), 
                                    end_date=context.blotter.current_dt.strftime('%Y%m%d'))
        g.range_bound_days_count = len(trade_days) - 1
        log.info("【震荡期统计】已持续 %s 个交易日" % g.range_bound_days_count)

# ==================== 持仓检查 ====================
def check_positions(context):
    # 盘前持仓检查
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.amount > 0:
            security_name = get_security_name(security)
            snapshot = get_snapshot(security) if is_trade() else {}
            paused = False
            if is_trade() and snapshot and snapshot.get(security):
                paused = snapshot[security].get('trade_status') in ['HALT', 'SUSP', 'STOPT']
            log.info("【持仓检查】%s %s, 数量: %s, 成本: %.3f" % 
                    (security, security_name, position.amount, position.cost_basis))
            if paused:
                log.info("⚠️ %s %s 今日停牌" % (security, security_name))

def monitor_drawdown(context):
    # 回撤监控：当策略回撤超过阈值时，记录
    try:
        current_value = context.portfolio.portfolio_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        
        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                record = {
                    'date': context.blotter.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'current_filter': g.current_filter,
                    'risk_state': g.risk_state
                }
                positions_info = []
                for security in context.portfolio.positions:
                    position = context.portfolio.positions[security]
                    if position.amount > 0:
                        security_name = get_security_name(security)
                        positions_info.append("%s:%s股" % (security_name, position.amount))
                record['positions'] = positions_info
                g.drawdown_records.append(record)
                log.info("【回撤预警】回撤达到 %.2f%% (阈值: %.0f%%)" % (current_drawdown*100, g.drawdown_threshold*100))
                log.info("  当前净值: %.0f  |  最高净值: %.0f" % (current_value, g.max_portfolio_value))
                log.info("  当前滤波器: %s  |  风险状态: %s" % (g.current_filter, g.risk_state))
    except Exception as e:
        log.error("【回撤监控】计算异常: %s" % str(e))

# ==================== 持仓检查 ====================
def calculate_global_etf_threshold(context):
    # 计算全市场ETF流动性阈值
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        # 刷新并获取ETF列表缓存
        if not g.all_etf_cache:
            refresh_all_etf_cache(context)
        
        etf_list = g.all_etf_cache
        
        if not etf_list:
            log.info("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        
        log.info("全市场ETF总数: %s只" % len(etf_list))
        
        # 使用get_history获取近3日成交额数据
        df = get_history(3, '1d', ['money'], etf_list, fq='pre', include=False)
        
        if df is None or df.empty:
            log.info("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        
        # 标准化DataFrame格式
        df = _normalize_price_df(df)
        
        # 缓存成交额数据
        g.etf_money_df = df.copy()
        
        # 按日期分组计算总成交额
        if 'time' in df.columns:
            daily_totals = df.groupby('time')['money'].sum()
            for day, money in daily_totals.items():
                day_str = day.strftime('%Y-%m-%d') if hasattr(day, 'strftime') else str(day)
                log.info("  %s 全市场ETF总成交额: %.2f亿元" % (day_str, money/1e8))
            
            if len(daily_totals) < 3:
                log.info("仅有%s个有效交易日，使用保守阈值1000万" % len(daily_totals))
                g.avg_etf_money_threshold = 10000000
                return
            
            avg_total_money = daily_totals.mean()
            threshold = avg_total_money / 20000
            g.avg_etf_money_threshold = threshold
            log.info("【全局阈值更新完成】近%s日全市场ETF日均总成交额=%.2f亿元，阈值=%.0f元" % 
                    (len(daily_totals), avg_total_money/1e8, threshold))
        else:
            log.info("数据格式异常，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            
    except Exception as e:
        log.info("计算全局阈值异常: %s，使用保守阈值1000万" % str(e))
        g.avg_etf_money_threshold = 10000000


def update_sector_pool(context):
    # 更新行业ETF动态池
    log.info("【动态池更新】开始执行")
    
    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    
    # 基金公司名称列表
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    
    # 噪音词列表
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    
    # 特别分组
    SPECIAL_GROUPS = sorted([
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创', '创成长'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True)},
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HS', 'H', '中概'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HS', 'H', '中概'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    
    # 排除关键词
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)
    
    # 使用缓存的 ETF 列表和名称
    if not g.all_etf_cache:
        refresh_all_etf_cache(context)
    etf_list = g.all_etf_cache
    etf_names_dict = g.all_etf_names
    
    if not etf_list:
        log.info("【动态池更新】未获取到任何ETF，动态池跳过")
        g.dynamic_etf_pool = []
        return

        return
    
    log.info("【动态池更新】全市场ETF总数: %s只" % len(etf_list))
    
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    
    # 分类ETF
    for code in etf_list:
        try:
            name = etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue
    
    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    
    log.info("【动态池更新】特别组分布: %s" % group_counts)
    log.info("【动态池更新】进入特别组: %s只" % len(special_etfs))
    log.info("【动态池更新】进入普通组: %s只" % len(normal_etfs))
    log.info("【动态池更新】排除ETF: %s只" % excluded_count)
    
    end_date = get_trading_day(-1)
    end_date_str = str(end_date).replace('-', '')
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    
    def filter_by_liquidity(etf_codes, group_name):
        # 按流动性过滤ETF
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            # 优先使用缓存的成交额数据
            if g.etf_money_df is not None and not g.etf_money_df.empty:
                df = g.etf_money_df[g.etf_money_df['code'].isin(etf_codes)]
                if df.empty:
                    log.warning("【%s】缓存成交额数据中无对应代码" % group_name)
                    return pd.Series(dtype=float), len(etf_codes)
            else:
                log.warning("【%s】成交额缓存不存在，重新获取" % group_name)
                price_data = get_history(TRADE_DAYS_COUNT, '1d', ['money'], etf_codes, fq='pre', include=False)
                if price_data is None or price_data.empty:
                    log.warning("【%s】无法获取成交额数据" % group_name)
                    return pd.Series(dtype=float), len(etf_codes)
                df = _normalize_price_df(price_data)

            total_money = df.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            return qualified_series, len(etf_codes) - len(qualified_series)
        except Exception as e:
            log.warning("【%s】计算成交额异常: %s" % (group_name, e))
            return pd.Series(dtype=float), len(etf_codes)
    
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")
    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()
    
    log.info("【动态池更新】普通组流动性过滤: %s→%s只" % (len(normal_etfs), len(normal_sorted)))
    log.info("【动态池更新】特别组流动性过滤: %s→%s只" % (len(special_etfs), len(special_sorted)))
    
    if not normal_sorted and not special_sorted:
        log.info("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return
    
    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []
    
    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    
    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_industry_groups:
                normal_industry_groups[industry_key] = []
            normal_industry_groups[industry_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue
    
    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = "%s_%s" % (matched_group, industry_key)
            if group_key not in special_industry_groups:
                special_industry_groups[group_key] = []
            special_industry_groups[group_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue
    
    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    log.info("【动态池更新完成】动态池共%s只ETF" % len(g.dynamic_etf_pool))
    
    if len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info("  %s %s 日均成交额: %.2f亿" % (item['code'], item['original_name'], item['money']/1e8))

# ==================== 固定池流动性过滤 ====================
def filter_fixed_pool_by_volume(context):
    # 每日对固定ETF池进行流动性过滤
    log.info("【固定池过滤】开始执行")
    
    if g.avg_etf_money_threshold is None:
        g.avg_etf_money_threshold = 10000000
    
    if not g.fixed_etf_pool:
        log.info("【固定池过滤】固定池为空，跳过")
        return
    
    dynamic_threshold = g.avg_etf_money_threshold
    TRADE_DAYS_COUNT = 3
    
    try:
        # 直接获取固定池的成交额数据
        price_data = get_history(TRADE_DAYS_COUNT, '1d', ['money'], g.fixed_etf_pool, fq='pre', include=False)
        
        if price_data is None or price_data.empty:
            log.info("【固定池过滤】无法获取成交额数据，使用全部固定ETF")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        
        # 标准化 DataFrame
        df = _normalize_price_df(price_data)
        
        if df is None or df.empty:
            log.info("【固定池过滤】DataFrame为空，使用全部固定ETF")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        
        # 计算每只ETF的平均日成交额
        total_money = df.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        
        # 过滤高于阈值的ETF
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        removed = set(g.fixed_etf_pool) - set(new_fixed_pool)
        
        log.info("【固定池过滤】流动性门槛=日均%.0f元，保留高流动性ETF(%s只)" % (dynamic_threshold, len(new_fixed_pool)))
        
        if removed:
            log.info("【固定池过滤】剔除低流动性ETF(%s只)" % len(removed))
        
        g.filtered_fixed_pool = new_fixed_pool
        
    except Exception as e:
        log.info("【固定池过滤】异常: %s，使用全部固定ETF" % str(e))
        g.filtered_fixed_pool = g.fixed_etf_pool[:]


def daily_merge_etf_pools(context):
    # 每日合并固定池和动态池
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    log.info("【合并ETF池】开始执行")
    log.info("【合并池统计】固定池: %s只, 动态池: %s只, 合并后: %s只" % 
            (len(g.filtered_fixed_pool), len(g.dynamic_etf_pool), len(merged)))
    g.merged_etf_pool = merged

# ==================== 退出震荡期检查 ====================
def check_and_exit_range_bound_mode(context):
    # 检查是否需要退出震荡期
    if not g.enable_range_bound_mode:
        return
    
    if g.current_filter != 'range_bound':
        return
    
    log.info("【震荡期退出检查】开始检测退出条件...")
    
    try:
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        end_date = get_trading_day(-1)
        end_date_str = str(end_date).replace('-', '')
        
        df = get_history(lookback, '1d', ['close', 'high', 'low'], g.risk_benchmark, fq='pre', include=False)
        
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.info("【震荡期退出检查】数据不足，跳过检查")
            return
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        
        recovery_signals = []
        ma = np.mean(close[-g.ma_period:])
        current_rsi = calculate_rsi(close, period=14)
        
        log.info("【震荡期数据】当前价: %.3f, 近%s日高点: %.3f, 低点: %.3f" % 
                (current_price, g.lookback_high_low_days, recent_high, recent_low))
        log.info("【震荡期数据】回撤: %.2f%%, 从低点涨幅: %.2f%%" % (current_drawdown*100, rise_from_low*100))
        
        # 退出条件1: 从低点上涨
        if g.enable_low_point_rise_trigger:
            if rise_from_low >= g.low_point_rise_threshold:
                recovery_signals.append("从近%s日低点上涨%.2f%%≥%.0f%%" % 
                                    (g.lookback_high_low_days, rise_from_low*100, g.low_point_rise_threshold*100))
        
        # 退出条件2: 企稳信号
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append("回撤收窄")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append("RSI回升")
            
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
            else:
                g.stable_days = 0
        # 更新前一日数据
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        
        # 震荡期天数超限
        range_bound_days = 0
        if hasattr(g, 'range_bound_start_date') and g.range_bound_start_date is not None:
            current_date_str = context.blotter.current_dt.strftime('%Y%m%d')
            start_date_str = str(g.range_bound_start_date).replace('-', '')
            trade_days = get_trade_days(start_date=start_date_str, end_date=current_date_str)
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append("震荡期满(%s个交易日)" % range_bound_days)
        
		# 判断是否满足恢复条件
        low_point_rise_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_signal_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_signal_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        
        should_recover = low_point_rise_condition or stable_signal_condition or force_condition
        
        if should_recover:
            # 检查切换冷却期
            can_switch = True
            if g.last_switch_date is not None:
                current_date_str = context.blotter.current_dt.strftime('%Y%m%d')
                last_switch_str = str(g.last_switch_date).replace('-', '')
                trade_days = get_trade_days(start_date=last_switch_str, end_date=current_date_str)
                days_since_switch = len(trade_days) - 1
                if days_since_switch < g.filter_switch_cooldown:
                    can_switch = False
                    log.info("【震荡期退出】冷却期中，距上次切换 %s 天" % days_since_switch)
            
            if can_switch:
                g.current_filter = 'laplace'
                g.risk_state = 'normal'
                g.last_switch_date = context.blotter.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info("【退出震荡期】切换回拉普拉斯滤波器: %s" % '; '.join(recovery_signals))
        else:
            log.info("【震荡期退出检查】未满足退出条件，保持震荡期")
    except Exception as e:
        log.info("【震荡期退出检查】判断出错: %s" % str(e))

# ==================== 进入震荡期检查 ====================
def check_and_enter_range_bound_mode(context):
    # 检查是否需要进入震荡期
    if not g.enable_range_bound_mode:
        return
    log.info("🔍 【震荡期检查】开始检测进入条件...")
    # 检查冷却期
    can_switch = True
    if g.last_switch_date is not None:
        current_date_str = context.blotter.current_dt.strftime('%Y%m%d')
        last_switch_str = str(g.last_switch_date).replace('-', '')
        trade_days = get_trade_days(start_date=last_switch_str, end_date=current_date_str)
        days_since_switch = len(trade_days) - 1
        if days_since_switch < g.filter_switch_cooldown:
            can_switch = False
            log.info("【震荡期检查】冷却期中，距上次切换 %s 天" % days_since_switch)
    # 如果当前已经是震荡期，或者不能切换，直接返回
    if g.current_filter == 'range_bound':
        log.info("【震荡期检查】当前已在震荡期，滤波器: 高斯")
        return
    
    if not can_switch:
        return
    
    risk_signals = []
    # 获取基准ETF的日线数据
    try:
        lookback = max(g.ma_period, g.lookback_high_low_days) + 10
        end_date = get_trading_day(-1)
        end_date_str = str(end_date).replace('-', '')
        
        df = get_history(lookback, '1d', ['close'], g.risk_benchmark, fq='pre', include=False)
        
        if df is not None and len(df) >= max(g.ma_period, g.lookback_high_low_days):
            close = df['close'].values
            current_price = close[-1]
            
            # 条件1: 乖离率过大
            if g.enable_bias_trigger:
                ma = np.mean(close[-g.ma_period:])
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append("乖离率过大(%.2f%%>%.0f%%)" % (bias*100, g.bias_threshold*100))
            
            # 条件2: RSI超买回落
            if g.enable_rsi_trigger:
                current_rsi = calculate_rsi(close, period=14)
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = calculate_rsi(close[:-1], period=14)
                    if prev_rsi is not None:
                        if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                            risk_signals.append("RSI超买回落(%.1f→%.1f)" % (prev_rsi, current_rsi))
    except Exception as e:
        log.info("【震荡期检查】获取基准数据异常: %s" % str(e))
    
    # 条件3: 持仓ETF触发止损（今日是否触发过）
    if g.enable_stop_loss_trigger and g.stop_loss_triggered_today:
        risk_signals.append("今日触发止损")
    
	# 触发切换
    if len(risk_signals) > 0:
        g.current_filter = 'range_bound'
        g.risk_state = 'range_bound'
        g.last_switch_date = context.blotter.current_dt.date()
        g.range_bound_start_date = context.blotter.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        log.info("【进入震荡期】切换到高斯滤波器: %s" % '; '.join(risk_signals))
    else:
        log.info("【震荡期检查】未满足进入条件，保持正常期")

# ==================== 动量得分计算 ====================
def calculate_and_log_ranked_etfs(context):
    # 计算合并池中的标的动量得分
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.info("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list

def calculate_momentum_score(price_series, lookback_days):
    # 计算动量得分（加权线性回归）
    if len(price_series) < lookback_days + 1:
        return None, None, None
    
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.exp(slope * 250) - 1
    ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    
    return momentum_score, annualized_returns, r_squared

def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    # 计算单个ETF的所有动量指标
    try:
        price_series = np.append(hist_closes, current_price)
        
        # 计算动量得分（25天）
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, g.lookback_days)
        if momentum_score is None:
            return None
        
        # 计算短期动量得分（21天）
        short_momentum_score, short_annualized_returns, short_r_squared = calculate_momentum_score(price_series, g.short_momentum_lookback)
        # 判断是否通过原动量过滤
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        # 判断是否通过短期动量过滤
        passed_short_momentum = (g.short_momentum_min_score <= short_momentum_score <= g.short_momentum_max_score) if short_momentum_score is not None else False
        
        # 成交量比
        volume_ratio = get_volume_ratio(hist_volumes, today_vol, g.volume_lookback)
        
        # 短期风控（近3日单日跌幅）
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False
        
         # 溢价率计算
        premium_rate, passed_premium = calculate_premium_rate(etf, context)
        
        # 滤波器计算
		# 拉普拉斯滤波器（正常期使用）
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        # 高斯滤波器（震荡期使用）
        gaussian_value = 0
        gaussian_slope = 0
        passed_gaussian = False
        
        if len(price_series) >= 10:
            try:
                # 计算拉普拉斯滤波值
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                # 计算高斯滤波值
                gaussian_values = gaussian_filter(price_series, sigma=g.gaussian_sigma)
                if len(gaussian_values) >= 2:
                    gaussian_value = gaussian_values[-1]
                    gaussian_slope = gaussian_values[-1] - gaussian_values[-2]
                    passed_gaussian = (current_price > gaussian_values[-1] and gaussian_slope > g.gaussian_min_slope)
            except Exception:
                pass
        # 根据当前模式选择使用的滤波器
        if g.current_filter == 'laplace':
            filter_value = laplace_value
            filter_slope = laplace_slope
            passed_filter = passed_laplace
        else:
            filter_value = gaussian_value
            filter_slope = gaussian_slope
            passed_filter = passed_gaussian
        
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'short_momentum_score': short_momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_short_momentum': passed_short_momentum,
            'passed_r2': r_squared > g.r2_threshold,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'gaussian_value': gaussian_value,
            'gaussian_slope': gaussian_slope,
            'passed_laplace': passed_laplace,
            'passed_gaussian': passed_gaussian,
            'filter_value': filter_value,
            'filter_slope': filter_slope,
            'passed_filter': passed_filter,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None

def get_volume_ratio(hist_volumes, today_vol, lookback_days=None):
    # 计算成交量比
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        projected_today_vol = today_vol * (240.0 / 130.0)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None

#  溢价率计算（回测不支持，但是基本不影响。
# 请注意！这里回测是不支持的，要实盘才可以用！
def calculate_premium_rate(etf, context):
    if not is_trade():
        return None, True
    # PTrade版本：使用get_etf_info计算溢价率
    try:
        # 获取ETF信息（仅股票交易模块可用）
        etf_info = get_etf_info(etf) #et_etf_info：回测不支持，仅实盘可用
        if not etf_info or etf not in etf_info:
            return None, True
        
        # 提取T-1日基金单位净值
        nav = etf_info[etf].get('nav_pre')
        if nav is None or nav <= 0:
            return None, True
        
        # 获取当前价格（从get_current_data或实时行情）
        current_data = get_current_data()
        if current_data and etf in current_data:
            etf_price = current_data[etf].last_price
        else:
            # 回测模式回退
            price_df = get_history(1, '1d', 'close', etf, include=True)
            if price_df is None or price_df.empty:
                return None, True
            etf_price = price_df['close'].iloc[-1]
        
        if etf_price <= 0:
            return None, True
        
        premium_rate = (etf_price - float(nav)) / float(nav) * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception as e:
        # 异常时默认通过溢价率校验（与原版逻辑一致）
        return None, True
        
# ==================== 滤波器函数 ====================
def gaussian_filter(price, sigma=1.2):
    # 高斯滤波器（震荡期使用）
    n = len(price)
    G = np.zeros(n)
    for t in range(n):
        weights = np.array([np.exp(-((i+1)**2) / (2 * sigma**2)) for i in range(t+1)])
        weights = weights[::-1]
        weights = weights / np.sum(weights)
        G[t] = np.sum(price[:t+1] * weights)
    return G

def laplace_filter(price, s=0.05):
    # 拉普拉斯滤波器（正常期使用）
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L

def calculate_rsi(close, period=14):
    # 计算单个RSI值
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None

# ==================== 过滤条件应用 ====================
def apply_filters(metrics_list):
    # 根据开关应用所有过滤条件
    # 判断使用哪种动量过滤（特殊期使用短期动量）
    use_short_momentum = g.use_short_momentum_period
    
    steps = [
        ('原动量', lambda m: m['passed_momentum'], not use_short_momentum),
        ('短期动量', lambda m: m['passed_short_momentum'], use_short_momentum),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
        ('动态滤波', lambda m: m['passed_filter'], g.enable_range_bound_mode),
    ]
    
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            before_count = len(filtered)
            filtered = [m for m in filtered if condition(m)]
            after_count = len(filtered)
    
    return filtered

def get_final_ranked_etfs(context):
    # 主筛选函数，从合并池中选出最终排名ETF（对齐聚宽）
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = get_trading_day(-1)  # 前一交易日
    end_date_str = str(end_date).replace('-', '')

    log.info("【动量得分计算】使用合并池，合计%s只ETF" % len(etf_set))
    log.info("【当前滤波器】%s模式" % g.current_filter.upper())

    use_short_momentum = g.use_short_momentum_period
    log.info("【动量模式】%s" % ('使用短期动量(21天,0-6分)' if use_short_momentum else '使用原动量(25天,0-5分)'))

    lookback = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 20
    safe_lookback = lookback + 20

    # ========== 1. 获取历史日线数据（close, volume） ==========
    hist_df = get_history(safe_lookback, '1d', ['close', 'volume'], etf_set, fq='pre', include=False)
    hist_df = _normalize_price_df(hist_df)
    if hist_df is None or len(hist_df) == 0:
        log.info("【动量计算】无法获取历史价格数据")
        return []

    # ========== 2. 获取今日分钟数据（到13:10为止） ==========
    # 聚宽原版在13:10运行，已交易130分钟（9:30-11:30共120分钟，13:00-13:10共10分钟）
    mins_elapsed = 130
    minute_price_df = get_history(mins_elapsed, '1m', ['close'], etf_set, fq='pre', include=True)
    minute_price_df = _normalize_price_df(minute_price_df)
    minute_vol_df = get_history(mins_elapsed, '1m', ['volume'], etf_set, fq='pre', include=True)
    minute_vol_df = _normalize_price_df(minute_vol_df)

    # 构建当前价格字典（取最后一分钟的价格）
    current_price_dict = {}
    if minute_price_df is not None and len(minute_price_df) > 0:
        for code, group in minute_price_df.groupby('code'):
            if not group.empty:
                current_price_dict[code] = group['close'].iloc[-1]
    else:
        # 分钟数据为空时回退到日线收盘价（不推荐，但保底）
        for code in etf_set:
            current_price_dict[code] = 0

    # 构建今日累计成交量字典（到13:10的分钟量总和）
    today_vol_dict = {}
    if minute_vol_df is not None and len(minute_vol_df) > 0:
        for code, group in minute_vol_df.groupby('code'):
            if not group.empty:
                today_vol_dict[code] = group['volume'].sum()
    else:
        for code in etf_set:
            today_vol_dict[code] = 0

    # ========== 3. 循环计算每个ETF的指标 ==========
    for etf in etf_set:
        # ----- 停牌过滤 -----
        if is_trade():
            # 实盘：通过 get_stock_status 查询停牌
            halt_status = get_stock_status(etf, 'HALT')
            if halt_status.get(etf, False):
                continue
        else:
            # 回测：当前价为0或成交量为0视为停牌
            if current_price_dict.get(etf, 0) == 0 or today_vol_dict.get(etf, 0) == 0:
                continue

        current_price = current_price_dict.get(etf, 0)
        if current_price == 0:
            continue

        # 提取该ETF的历史数据（已过滤停牌日）
        etf_hist = hist_df[hist_df['code'] == etf]
        if 'time' not in etf_hist.columns:
            etf_hist = etf_hist.reset_index().rename(columns={'index': 'time'})
        if etf_hist.empty:
            continue
        etf_hist = etf_hist.sort_values('time')
        raw_closes = etf_hist['close'].values
        raw_volumes = etf_hist['volume'].values

        # 过滤停牌日（成交量为0或NaN）
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]

        # 只保留最后 lookback 个有效数据
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]

        if len(hist_closes) < max(g.lookback_days, g.short_momentum_lookback):
            continue

        etf_name = get_security_name(etf)
        today_vol = today_vol_dict.get(etf, 0)

        metrics = calculate_all_metrics_for_etf(
            etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context
        )
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)

    # ========== 4. 处理无效得分并排序 ==========
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        short_score = item.get('short_momentum_score')
        if pd.isna(short_score) or (isinstance(short_score, float) and np.isnan(short_score)):
            item['short_momentum_score'] = float('-inf')

    if use_short_momentum:
        all_metrics.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    # ========== 5. 输出第一步日志 ==========
    log.info("")
    log.info(">>> 第一步：所有ETF按%s动量得分从大到小排序 <<<" % ('短期' if use_short_momentum else '原'))
    for m in all_metrics[:100]:
        def fmt_status(value_str, passed):
            return "%s %s" % (value_str, "✅" if passed else "❌")
        score_str = "%.4f" % m['momentum_score'] if m['momentum_score'] != float('-inf') else "nan"
        short_score_str = "%.4f" % m['short_momentum_score'] if m['short_momentum_score'] != float('-inf') else "nan"
        r2_str = "%.3f" % m['r_squared'] if not pd.isna(m['r_squared']) else "nan"
        vol_val = "%.2f" % m['volume_ratio'] if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = "%.4f" % min_ratio if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        premium_str = "%.2f%%" % m['premium_rate'] if m['premium_rate'] is not None else "N/A"
        line = ("%s %s: "
                "原动量: %s，"
                "短期动量: %s，"
                "R²: %s，"
                "成交量比值: %s，"
                "短期风控: %s，"
                "溢价率: %s，"
                "拉普拉斯滤波值: %.4f/斜率值: %.4f %s，"
                "高斯滤波值: %.4f/斜率值: %.4f %s") % (
                    m['etf'], m['etf_name'],
                    fmt_status(score_str, m['passed_momentum']),
                    fmt_status(short_score_str, m['passed_short_momentum']),
                    fmt_status(r2_str, m['passed_r2']),
                    fmt_status(vol_val, m['passed_volume']),
                    fmt_status(loss_val, m['passed_loss']),
                    fmt_status(premium_str, m['passed_premium']),
                    m['laplace_value'], m['laplace_slope'],
                    fmt_status('', m['passed_laplace']),
                    m['gaussian_value'], m['gaussian_slope'],
                    fmt_status('', m['passed_gaussian']),
                )
        log.info(line)

    # ========== 6. 应用过滤条件 ==========
    filtered_list = apply_filters(all_metrics)

    if use_short_momentum:
        filtered_list.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    top_10 = filtered_list[:10]

    log.info("")
    log.info(">>> 第二步：符合全部过滤条件的ETF按%s动量得分从大到小排序(前10名) <<<" % ('短期' if use_short_momentum else '原'))
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return "%s %s" % (value_str, "✅" if passed else "❌")
            score_str = "%.4f" % m['momentum_score'] if m['momentum_score'] != float('-inf') else "nan"
            short_score_str = "%.4f" % m['short_momentum_score'] if m['short_momentum_score'] != float('-inf') else "nan"
            r2_str = "%.3f" % m['r_squared'] if not pd.isna(m['r_squared']) else "nan"
            vol_val = "%.2f" % m['volume_ratio'] if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = "%.4f" % min_ratio if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = "%.2f%%" % m['premium_rate'] if m['premium_rate'] is not None else "N/A"
            line = ("%s %s: "
                    "原动量: %s，"
                    "短期动量: %s，"
                    "R²: %s，"
                    "成交量比值: %s，"
                    "短期风控: %s，"
                    "溢价率: %s，"
                    "拉普拉斯滤波值: %.4f/斜率值: %.4f %s，"
                    "高斯滤波值: %.4f/斜率值: %.4f %s") % (
                        m['etf'], m['etf_name'],
                        fmt_status(score_str, m['passed_momentum']),
                        fmt_status(short_score_str, m['passed_short_momentum']),
                        fmt_status(r2_str, m['passed_r2']),
                        fmt_status(vol_val, m['passed_volume']),
                        fmt_status(loss_val, m['passed_loss']),
                        fmt_status(premium_str, m['passed_premium']),
                        m['laplace_value'], m['laplace_slope'],
                        fmt_status('', m['passed_laplace']),
                        m['gaussian_value'], m['gaussian_slope'],
                        fmt_status('', m['passed_gaussian']),
                    )
            log.info(line)
    else:
        log.info("（无符合条件的ETF）")
        return []

    # ========== 7. 第三步：构建候选池 ==========
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        score_threshold = reference_score * g.score_threshold_ratio
        log.info("")
        log.info(">>> 第三步：选取动量得分≥第%s名得分%.4f×%.1f=%.4f的ETF <<<" %
                 (g.holdings_num, reference_score, g.score_threshold_ratio, score_threshold))
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log.info("")
        log.info(">>> 第三步：前10名不足%s只，全部作为候选池 <<<" % g.holdings_num)
        candidate_pool = top_10[:]

    log.info("【候选池】共%s只ETF：" % len(candidate_pool))
    for i, item in enumerate(candidate_pool):
        log.info("  %s. %s(%s)" % (i+1, item['etf_name'], item['etf']))

    # ========== 8. 第四步：结合当前持仓调整 ==========
    log.info("")
    log.info(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.amount > 0]
    log.info("当前持仓ETF：%s" % current_holdings)

    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log.info("其中存在于候选池中的持仓ETF：%s" % [item['etf'] for item in retained])

    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log.info("保留的持仓ETF数量(%s)超过目标持仓数(%s)，取前%s只" %
                 (len(retained), g.holdings_num, g.holdings_num))
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
        log.info("保留持仓ETF %s只，还需补充%s只" % (len(retained), need))

    log.info("【最终目标】共%s只ETF：" % len(final_result))
    for i, item in enumerate(final_result):
        log.info("  %s. %s(%s)" % (i+1, item['etf_name'], item['etf']))
    log.info("==================================================")

    return final_result

def get_final_ranked_etfs_bak(context):
    # 主筛选函数，从合并池中选出最终排名ETF
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = get_trading_day(-1)
    end_date_str = str(end_date).replace('-', '')
    
    log.info("【动量得分计算】使用合并池，合计%s只ETF" % len(etf_set))
    log.info("【当前滤波器】%s模式" % g.current_filter.upper())
    
    use_short_momentum = g.use_short_momentum_period
    log.info("【动量模式】%s" % ('使用短期动量(21天,0-6分)' if use_short_momentum else '使用原动量(25天,0-5分)'))
    
    lookback = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 20
    
    #safe_lookback = lookback + 20
    safe_lookback = lookback + 50
    
    # 获取历史数据
    hist_df = get_history(safe_lookback, '1d', ['close', 'volume'], etf_set, fq='pre', include=False)
    hist_df = _normalize_price_df(hist_df)
    
    if hist_df is None or len(hist_df) == 0:
        log.info("【动量计算】无法获取历史价格数据")
        return []
    
    # 获取今日分钟数据（用于成交量计算）
    today_str = context.blotter.current_dt.strftime('%Y%m%d')
    today_vol_df = get_history(240, '1m', ['volume'], etf_set, fq='pre', include=True)
    today_vol_df = _normalize_price_df(today_vol_df)
    
    # 计算今日累计成交量
    today_vols = {}
    if today_vol_df is not None and len(today_vol_df) > 0:
        for code in etf_set:
            code_data = today_vol_df.query('code == @code') if 'code' in today_vol_df.columns else today_vol_df
            if len(code_data) > 0:
                today_vols[code] = code_data['volume'].sum()
    
    # 获取当前价格和停牌状态
    snapshot_dict = {}
    if is_trade():
        snapshot_dict = get_snapshot(etf_set) or {}
    
    for etf in etf_set:
        try:
            # 检查停牌
            if is_trade():
                if etf in snapshot_dict:
                    trade_status = snapshot_dict[etf].get('trade_status', '')
                    if trade_status in ['HALT', 'SUSP', 'STOPT']:
                        continue
            
            # 提取该ETF的历史数据
            etf_data = hist_df.query('code == @etf') if 'code' in hist_df.columns else hist_df
            if len(etf_data) == 0:
                continue
            
            raw_closes = etf_data['close'].values
            raw_volumes = etf_data['volume'].values
            
            # 过滤无效数据
            valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
            hist_closes = raw_closes[valid_mask]
            hist_volumes = raw_volumes[valid_mask]
            
            hist_closes = hist_closes[-lookback:]
            hist_volumes = hist_volumes[-lookback:]
            
            if len(hist_closes) < max(g.lookback_days, g.short_momentum_lookback):
                continue
            
            etf_name = get_security_name(etf)
            
            # 获取当前价格
            if is_trade() and etf in snapshot_dict:
                current_price = snapshot_dict[etf].get('last_px', hist_closes[-1])
            else:
                current_price = hist_closes[-1]
            
            today_vol = today_vols.get(etf, 0)
            
            metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, 
                                                current_price, today_vol, context)
            if metrics:
                all_metrics.append(metrics)
        except Exception as e:
            continue
    
    # 处理无效得分
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        short_score = item.get('short_momentum_score')
        if pd.isna(short_score) or (isinstance(short_score, float) and np.isnan(short_score)):
            item['short_momentum_score'] = float('-inf')
    # 根据动量模式排序
    if use_short_momentum:
        all_metrics.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    
    # ==================== 第一步：所有ETF按动量得分排序 ====================
    log.info("")
    log.info(">>> 第一步：所有ETF按%s动量得分从大到小排序 <<<" % ('短期' if use_short_momentum else '原'))
    for m in all_metrics[:100]:
        def fmt_status(value_str, passed):
            return "%s %s" % (value_str, "✅" if passed else "❌")
        score_str = "%.4f" % m['momentum_score'] if m['momentum_score'] != float('-inf') else "nan"
        short_score_str = "%.4f" % m['short_momentum_score'] if m['short_momentum_score'] != float('-inf') else "nan"
        r2_str = "%.3f" % m['r_squared'] if not pd.isna(m['r_squared']) else "nan"
        vol_val = "%.2f" % m['volume_ratio'] if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = "%.4f" % min_ratio if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        premium_str = "%.2f%%" % m['premium_rate'] if m['premium_rate'] is not None else "N/A"
        line = ("%s %s: "
                "原动量: %s，"
                "短期动量: %s，"
                "R²: %s，"
                "成交量比值: %s，"
                "短期风控: %s，"
                "溢价率: %s，"
                "拉普拉斯滤波值: %.4f/斜率值: %.4f %s，"
                "高斯滤波值: %.4f/斜率值: %.4f %s") % (
                    m['etf'], m['etf_name'],
                    fmt_status(score_str, m['passed_momentum']),
                    fmt_status(short_score_str, m['passed_short_momentum']),
                    fmt_status(r2_str, m['passed_r2']),
                    fmt_status(vol_val, m['passed_volume']),
                    fmt_status(loss_val, m['passed_loss']),
                    fmt_status(premium_str, m['passed_premium']),
                    m['laplace_value'], m['laplace_slope'],
                    fmt_status('', m['passed_laplace']),
                    m['gaussian_value'], m['gaussian_slope'],
                    fmt_status('', m['passed_gaussian']),
                )
        log.info(line)

    # ==================== 第二步：应用过滤条件 ====================
    filtered_list = apply_filters(all_metrics)
    
    # 重新排序
    if use_short_momentum:
        filtered_list.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    
    top_10 = filtered_list[:10]
    log.info("")
    log.info(">>> 第二步：符合全部过滤条件的ETF按%s动量得分从大到小排序(前10名) <<<" % ('短期' if use_short_momentum else '原'))
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return "%s %s" % (value_str, "✅" if passed else "❌")
            score_str = "%.4f" % m['momentum_score'] if m['momentum_score'] != float('-inf') else "nan"
            short_score_str = "%.4f" % m['short_momentum_score'] if m['short_momentum_score'] != float('-inf') else "nan"
            r2_str = "%.3f" % m['r_squared'] if not pd.isna(m['r_squared']) else "nan"
            vol_val = "%.2f" % m['volume_ratio'] if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = "%.4f" % min_ratio if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = "%.2f%%" % m['premium_rate'] if m['premium_rate'] is not None else "N/A"
            line = ("%s %s: "
                    "原动量: %s，"
                    "短期动量: %s，"
                    "R²: %s，"
                    "成交量比值: %s，"
                    "短期风控: %s，"
                    "溢价率: %s，"
                    "拉普拉斯滤波值: %.4f/斜率值: %.4f %s，"
                    "高斯滤波值: %.4f/斜率值: %.4f %s") % (
                        m['etf'], m['etf_name'],
                        fmt_status(score_str, m['passed_momentum']),
                        fmt_status(short_score_str, m['passed_short_momentum']),
                        fmt_status(r2_str, m['passed_r2']),
                        fmt_status(vol_val, m['passed_volume']),
                        fmt_status(loss_val, m['passed_loss']),
                        fmt_status(premium_str, m['passed_premium']),
                        m['laplace_value'], m['laplace_slope'],
                        fmt_status('', m['passed_laplace']),
                        m['gaussian_value'], m['gaussian_slope'],
                        fmt_status('', m['passed_gaussian']),
                    )
            log.info(line)
    else:
        log.info("（无符合条件的ETF）")
        return []

    # ==================== 第三步：构建候选池 ====================
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        score_threshold = reference_score * g.score_threshold_ratio
        log.info(">>> 第三步：选取动量得分≥第%s名得分%.4f×%.1f=%.4f的ETF <<<" % 
                (g.holdings_num, reference_score, g.score_threshold_ratio, score_threshold))
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log.info(">>> 第三步：前10名不足%s只，全部作为候选池 <<<" % g.holdings_num)
        candidate_pool = top_10[:]
    
    log.info("【候选池】共%s只ETF：" % len(candidate_pool))
    for i, item in enumerate(candidate_pool):
        log.info("  %s. %s(%s)" % (i+1, item['etf_name'], item['etf']))
    # ==================== 第四步：结合持仓调整 ====================

    log.info(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.amount > 0]
    log.info("当前持仓ETF：%s" % current_holdings)
    
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log.info("其中存在于候选池中的持仓ETF：%s" % [item['etf'] for item in retained])
    
    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log.info("保留的持仓ETF数量(%s)超过目标持仓数(%s)，取前%s只" % 
                (len(retained), g.holdings_num, g.holdings_num))
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
        log.info("保留持仓ETF %s只，还需补充%s只" % (len(retained), need))
    
    log.info("【最终目标】共%s只ETF：" % len(final_result))
    for i, item in enumerate(final_result):
        log.info("  %s. %s(%s)" % (i+1, item['etf_name'], item['etf']))
    
    return final_result

# ==================== 交易执行 ====================
def execute_sell_trades(context):
    # 卖出交易逻辑
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    
    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info("确定最终目标: %s %s" % (metrics['etf'], metrics['etf_name']))
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            etf_name = get_security_name(g.defensive_etf)
            log.info("确定最终目标(防御模式): %s %s" % (g.defensive_etf, etf_name))
        else:
            log.info("无最终目标(空仓模式)")
            target_etfs = []
    
    g.target_etfs_list = target_etfs
    
    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)
    sell_count = 0
    
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                g.sold_today.add(security)   # 仅记录，不修改 amount
                log.info("已成功卖出: %s %s" % (security, security_name))
    
    log.info("本次共计划卖出%s只ETF" % sell_count)
    log.info("【卖出操作完成】")


def execute_buy_trades(context):
    # 买入交易逻辑
    log.info("=" * 50)
    log.info("【买入操作开始】")
    
    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("今日无目标ETF，保持空仓")
        log.info("【买入操作完成】")
        return
    
    # 获取当前实际持仓（排除今日已卖出的）
    current_positions = set(context.portfolio.positions.keys())
    effective_holdings = current_positions - g.sold_today   # 重要！
    etfs_to_buy = [etf for etf in target_etfs if etf not in effective_holdings]
    actual_holding_count = len(effective_holdings)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    
    if num_etfs_to_buy <= 0:
        log.info("当前实际持仓数量(%s)已达到目标(%s)，无需买入" % (actual_holding_count, g.holdings_num))
        log.info("【买入操作完成】")
        return
    
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info("当前实际持仓: %s只, 目标持仓: %s只, 本次计划买入: %s只" % 
            (actual_holding_count, g.holdings_num, num_etfs_to_buy))
    
    available_cash = context.portfolio.cash
    allocated_value_per_etf = available_cash // num_etfs_to_buy
    log.info("账户可用现金: %.2f, 分配给每只ETF的资金: %.2f" % (available_cash, allocated_value_per_etf))
    
    if allocated_value_per_etf < g.min_money:
        log.info("单只ETF分配金额%.2f小于最小交易额%.2f，无法买入" % (allocated_value_per_etf, g.min_money))
        log.info("【买入操作完成】")
        return
    
    for i, etf in enumerate(etfs_to_buy):
        target_value_for_this_etf = allocated_value_per_etf
        if i == len(etfs_to_buy) - 1 and context.portfolio.cash >= g.min_money:
            target_value_for_this_etf = context.portfolio.cash
        
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info("ETF %s 下单成功" % etf)
        else:
            log.info("ETF %s 下单失败" % etf)
    
    log.info("【买入操作完成】")

def smart_order_target_value(security, target_value, context):
    # 智能下单
    security_name = get_security_name(security)
    
    # 检查停牌和涨跌停
    if is_trade():
        snapshot = get_snapshot(security)
        if snapshot and snapshot.get(security):
            trade_status = snapshot[security].get('trade_status', '')
            if trade_status in ['HALT', 'SUSP', 'STOPT']:
                log.info("%s %s: 今日停牌，跳过交易" % (security, security_name))
                return False
            
            current_price = snapshot[security].get('last_px', 0)
            high_limit = snapshot[security].get('up_px', 0)
            low_limit = snapshot[security].get('down_px', 0)
            
            if current_price >= high_limit and high_limit > 0:
                log.info("%s %s: 当前涨停，跳过交易" % (security, security_name))
                return False
            if current_price <= low_limit and low_limit > 0:
                log.info("%s %s: 当前跌停，跳过交易" % (security, security_name))
                return False
    else:
        # 回测模式：从历史数据获取价格
        today_str = context.blotter.current_dt.strftime('%Y%m%d')
        price_df = get_history(1, '1m', ['close'], security, fq='pre', include=True)
        price_df = _normalize_price_df(price_df)
        if price_df is None or len(price_df) == 0:
            return False
        current_price = price_df['close'].iloc[-1]
    
    if current_price == 0:
        log.info("%s %s: 当前价格为0，跳过交易" % (security, security_name))
        return False
    
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    
    if 0 < trade_value < g.min_money:
        log.info("%s %s: 交易金额%.2f小于最小交易额%.2f，跳过" % 
                (security, security_name, trade_value, g.min_money))
        return False
    
    if amount_diff < 0:
        closeable_amount = current_position.enable_amount if current_position else 0
        if closeable_amount == 0:
            log.info("%s %s: 当天买入不可卖出(T+1)" % (security, security_name))
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            if amount_diff > 0:
                log.info("买入%s %s，数量: %s，价格: %.3f" % (security, security_name, amount_diff, current_price))
            else:
                log.info("卖出%s %s，数量: %s，价格: %.3f" % (security, security_name, abs(amount_diff), current_price))
            return True
        else:
            log.info("下单失败: %s %s，数量: %s" % (security, security_name, amount_diff))
            return False
    
    return False

# ==================== 止损函数 ====================
def minute_level_stop_loss(context):
    # 分钟级固定比例止损
    if not g.use_fixed_stop_loss:
        return
    
    if is_trade():
        securities = list(context.portfolio.positions.keys())
        if not securities:
            return
        snapshot = get_snapshot(securities) or {}
    
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.amount <= 0:
            continue
        
        if is_trade():
            if security not in snapshot:
                continue
            current_price = snapshot[security].get('last_px', 0)
        else:
            today_str = context.blotter.current_dt.strftime('%Y%m%d')
            price_df = get_history(1, '1m', ['close'], security, fq='pre', include=True)
            price_df = _normalize_price_df(price_df)
            if price_df is None or len(price_df) == 0:
                continue
            current_price = price_df['close'].iloc[-1]
        
        if current_price <= 0:
            continue
        
        cost_price = position.cost_basis
        if cost_price <= 0:
            continue
        
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info("【分钟级固定止损】%s %s 触发止损，亏损: %.2f%%" % (security, security_name, loss_percent))
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info("【止损触发】记录今日止损，将在13:10检查并进入震荡期")

def minute_level_pct_stop_loss(context):
    # 分钟级当日跌幅止损
    if not g.use_pct_stop_loss:
        return
    
    current_date = context.blotter.current_dt.date()
    if not hasattr(g, 'cache_date') or g.cache_date != current_date:
        g.yesterday_close_cache = {}
        g.cache_date = current_date
    
    if is_trade():
        securities = list(context.portfolio.positions.keys())
        if not securities:
            return
        snapshot = get_snapshot(securities) or {}
    
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.amount <= 0:
            continue
        
        yesterday_close = g.yesterday_close_cache.get(security)
        if yesterday_close is None:
            try:
                yesterday = get_trading_day(-1)
                yesterday_str = str(yesterday).replace('-', '')
                close_df = get_history(1, '1d', ['close'], security, fq='pre', include=False)
                close_df = _normalize_price_df(close_df)
                if close_df is None or len(close_df) == 0:
                    continue
                yesterday_close = close_df['close'].iloc[-1]
                if yesterday_close <= 0:
                    continue
                g.yesterday_close_cache[security] = yesterday_close
            except Exception:
                continue
        
        if is_trade():
            if security not in snapshot:
                continue
            current_price = snapshot[security].get('last_px', 0)
        else:
            today_str = context.blotter.current_dt.strftime('%Y%m%d')
            price_df = get_history(1, '1m', ['close'], security, fq='pre', include=True)
            price_df = _normalize_price_df(price_df)
            if price_df is None or len(price_df) == 0:
                continue
            current_price = price_df['close'].iloc[-1]
        
        if current_price <= 0:
            continue
        
        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info("【分钟级跌幅止损】%s %s 触发止损，当日跌幅: %.2f%%" % (security, security_name, daily_loss))
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info("【止损触发】记录今日止损")

# ==================== 辅助函数 ====================
def get_security_name(security):
    # 安全获取证券名称
    try:
        if security in g.etf_names_dict:
            return g.etf_names_dict[security]
        name_dict = get_stock_name(security)
        if name_dict and security in name_dict:
            return name_dict[security]
        return "未知"
    except Exception:
        return "未知"

def check_defensive_etf_available(context):
    # 检查防御性ETF是否可交易
    if not is_trade():
        return True
    
    defensive_etf = g.defensive_etf
    snapshot = get_snapshot(defensive_etf)
    
    if not snapshot or defensive_etf not in snapshot:
        return False
    
    etf_info = snapshot[defensive_etf]
    trade_status = etf_info.get('trade_status', '')
    if trade_status in ['HALT', 'SUSP', 'STOPT']:
        log.info("防御性ETF %s 今日停牌" % defensive_etf)
        return False
    
    last_px = etf_info.get('last_px', 0)
    up_px = etf_info.get('up_px', 0)
    down_px = etf_info.get('down_px', 0)
    
    if last_px >= up_px and up_px > 0:
        log.info("防御性ETF %s 当前涨停" % defensive_etf)
        return False
    if last_px <= down_px and down_px > 0:
        log.info("防御性ETF %s 当前跌停" % defensive_etf)
        return False
    
    return True

# ==================== 主函数 ====================
def handle_data(context, data):
    # 主函数（必须保留）
    pass




