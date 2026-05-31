# CONTEXT.md — 股票筛选系统
# 新开对话时粘贴这个文件给 Claude，用于恢复上下文。

---

## 项目基本信息

```
项目名称：美国股票自动筛选和估值系统
项目路径：G:\DEV\stock-screener
技术栈：Python + Streamlit + SQLite + Plotly
环境：Windows 11, Python 3.14.3, venv
工作方式：Claude 生成代码 → 用户粘贴到 VS Code
```

---

## 已完成文件

```
config.py                    ✅
data/fetcher.py              ✅
data/db.py                   ✅
data/updater.py              ✅
data/stocks.db               ✅（已有13支股票数据）
analysis/metrics.py          ✅
analysis/valuation.py        ✅
analysis/screener.py         ✅
visualization/charts.py      ✅
app.py                       ✅
```

下一步：第四阶段（部署）

```
README.md                    ← 待完成
GitHub 上传                  ← 待完成
Streamlit Cloud 部署         ← 待完成
```

---

## 真实命名（最容易踩坑）

### data/db.py 的函数名

```python
get_stock_prices(ticker)      # 返回 DataFrame，列名：date/open/high/low/close/volume
get_financial_data(ticker)    # 返回 dict
get_all_financial_data()
get_last_updated(ticker)
save_stock_prices(...)
save_financial_data(...)
create_tables()
get_connection()
```

### stock_prices 表的列名

```
date, open, high, low, close, volume
注意：是 close，不是 close_price
```

### financial_data 表的列名

```
id, ticker, market_cap, pe_ratio, eps,
revenue, net_income, gross_profit,
total_assets, total_debt, shareholders_equity,
free_cash_flow, fetched_at, updated_at
```

### config.py 的变量名

```python
ALL_TICKERS        # 所有股票列表（13支）
DB_PATH
BASE_DIR
SCREEN_DEFAULTS
DEFAULT_SORT_BY
DEFAULT_SORT_ASCENDING
HISTORICAL_DAYS
APP_TITLE
APP_ICON
```

---

## 已安装的库

```
yfinance 1.4.1
pandas 3.0.3
streamlit 1.58.0
plotly 6.7.0
sqlite3（Python 内置）
```

---

## 已确认的设计决策

### 评分系统
- 使用线性映射，不用阶梯打分（消除悬崖效应）
- 核心函数：_linear_score(value, worst, best, max_points)
- 评分满分100分，6个组件

### screener 接口
- screen_stocks(tickers=None, filters=None, sort_by='score', ascending=False)
- tickers=None 时回退到 config.ALL_TICKERS
- 由 app.py 决定传什么

### charts.py 接口
- 所有函数返回 go.Figure，不显示
- plot_valuation_scatter(profiles, log_scale=False) — log_scale 由 app.py 的 toggle 传入

### 估值散点图离群值处理
- 离群值定义：P/E > 第90百分位（自动计算）
- 线性视图：离群值钉在右边缘，星形标记
- 对数视图：所有股票按真实位置显示，range=[1,3]

### Streamlit 缓存
- @st.cache_data(ttl=3600)
- 参数必须可哈希：list → tuple，dict → tuple(sorted(items()))

### 用户选股模式
- 预设分组 multiselect + 手动输入 text_input
- 自选池持久化暂缓（项目完成后升级）

---

## 已知数据现象（不是 bug）

```
AAPL ROE = 151%：大量回购导致股东权益变小，属正常
MCD  ROE = -478%：股东权益为负数，ROE 失去参考意义
TSLA P/E = 400：市场定价包含极高增长预期
DCF  全部 overvalued：8% 增长假设对大型科技股偏保守
Avg P/E 统计卡片 = 57.2：被 TSLA 拉高（待改为中位数）
```

---

## 暂缓升级事项

```
1. 行业调整（Industry Adjustment）→ 项目完成后实现
2. 自选股票池持久化 → 项目完成后实现
3. 统计卡片 P/E 改用中位数 → 小优化，随时可做
4. Score Breakdown DCF 0分视觉提示 → 小优化，随时可做
```

---

## 遇到命名错误的标准流程

```bash
python -c "import data.db; print(dir(data.db))"
python -c "import config; print(dir(config))"
python -c "
from data.db import get_stock_prices
df = get_stock_prices('AAPL')
print(df.columns.tolist())
"
```

---

最后更新：2026-05-30
当前进度：第三阶段完成，下一步第四阶段（部署）
