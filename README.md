# 📈 US Stock Screener & Valuation System

An automated stock analysis tool built with Python + Streamlit, featuring financial metrics calculation, multi-dimensional valuation models, and composite scoring.

🔗 **Live Demo**: <https://qhlstudyio-stock-screener.streamlit.app>

[中文版](README.zh.md)

---

## Features

- **Data Fetching**: Automatically pulls stock prices and financial data from Yahoo Finance
- **Financial Analysis**: Calculates ROE, profit margins, debt ratios, and other core metrics
- **Valuation Models**: P/E relative valuation + DCF discounted cash flow
- **Composite Scoring**: Multi-dimensional auto-scoring on a 0–100 scale
- **Visualization**: Price history charts, valuation scatter plots, metric comparison charts
- **Screening & Sorting**: Flexible filtering by metric thresholds and composite score

---

## Tech Stack

| Module          | Technology |
| --------------- | ---------- |
| Data Fetching   | yfinance   |
| Data Storage    | SQLite     |
| Data Processing | pandas     |
| Web Framework   | Streamlit  |
| Charts          | Plotly     |

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/qhlstudyio/stock-screener.git
cd stock-screener
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app.py
```

Open your browser at <http://localhost:8501>

---

## Project Structure

```text
stock-screener/
├── data/
│   ├── fetcher.py      # Data fetching
│   ├── db.py           # Database operations
│   └── updater.py      # Data update logic
├── analysis/
│   ├── metrics.py      # Financial metrics calculation
│   ├── valuation.py    # Valuation models
│   └── screener.py     # Screening and ranking
├── visualization/
│   └── charts.py       # Chart generation
├── app.py              # Main application
├── config.py           # Configuration
└── requirements.txt    # Dependencies
```

---

## Data

- **Source**: Yahoo Finance via yfinance
- **Update**: Manual refresh via sidebar button
- **Coverage**: 13 US stocks across technology, consumer, and healthcare sectors

---

## Background

A learn-by-doing project built over 8 weeks, with the goal of learning Python programming and financial analysis simultaneously.

---

## Known Limitations

- **Theme switching**: Switching between Light/Dark theme requires one manual interaction (e.g. moving a slider) to refresh the charts. This is a Streamlit framework limitation.

- **Data persistence**: Data is stored in SQLite. On Streamlit Cloud, the database resets after app restarts. Click "Refresh Data" to re-fetch all stock data.
