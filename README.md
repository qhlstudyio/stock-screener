# 📈 美国股票自动筛选和估值系统

一个基于 Python + Streamlit 构建的股票分析工具，支持财务指标计算、多维度估值和自动评分筛选。

🔗 **在线访问**：（部署后填入链接）

---

## 功能介绍

- **数据获取**：自动从 Yahoo Finance 抓取股价和财务数据
- **财务分析**：计算 ROE、利润率、债务率等核心指标
- **估值模型**：P/E 相对估值 + DCF 现金流折现
- **综合评分**：0–100 分多维度自动评分
- **可视化**：股价趋势图、估值散点图、财务对比图
- **筛选排序**：按行业、指标、评分灵活筛选

---

## 技术栈

| 模块     | 技术      |
| -------- | --------- |
| 数据获取 | yfinance  |
| 数据存储 | SQLite    |
| 数据处理 | pandas    |
| 网页框架 | Streamlit |
| 图表     | Plotly    |

---

## 本地运行

### 1. 克隆项目

git clone https://github.com/你的用户名/stock-screener.git
cd stock-screener

### 2. 安装依赖

pip install -r requirements.txt

### 3. 启动应用

streamlit run app.py

打开浏览器访问 http://localhost:8501

---

## 项目结构

stock-screener/
├── data/
│ ├── fetcher.py # 数据抓取
│ ├── db.py # 数据库操作
│ └── updater.py # 数据更新
├── analysis/
│ ├── metrics.py # 财务指标计算
│ ├── valuation.py # 估值模型
│ └── screener.py # 筛选排名
├── visualization/
│ └── charts.py # 图表生成
├── app.py # 主应用
├── config.py # 配置文件
└── requirements.txt # 依赖清单

---

## 数据说明

- 数据来源：Yahoo Finance（通过 yfinance 库）
- 数据更新：手动刷新（侧边栏按钮）
- 当前收录：13 支美股（科技、消费、医疗等行业）

---

## 开发背景

边做边学项目，目标是同时学习 Python 编程和金融分析知识。用 8 周时间从零构建完整的股票分析系统。
