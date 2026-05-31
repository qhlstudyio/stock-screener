# app.py
# Streamlit web application — entry point for the stock screener.

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

import config
from data.updater import update_ticker
from analysis.screener import screen_stocks, get_preset_groups
from visualization.charts import (
    plot_price_history,
    plot_metrics_comparison,
    plot_score_breakdown,
    plot_valuation_scatter,
)
from data.db import create_tables

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout='wide',
)


# ---------------------------------------------------------------------------
# Theme detection
# ---------------------------------------------------------------------------

try:
    current_theme = st.context.theme.get('type', 'dark')
except Exception:
    current_theme = 'dark'

if 'theme' not in st.session_state:
    st.session_state['theme'] = current_theme
elif st.session_state['theme'] != current_theme:
    st.session_state['theme'] = current_theme
    st.rerun()

is_dark = current_theme == 'dark'

# ---------------------------------------------------------------------------
# Cached data loader
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_data(tickers_key, sort_by, ascending, filters_key):
    tickers = list(tickers_key)
    filters = dict(filters_key) if filters_key else None
    return screen_stocks(
        tickers=tickers,
        filters=filters,
        sort_by=sort_by,
        ascending=ascending,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title('⚙️ Controls')

    # --- Stock universe ---
    st.subheader('Stock Universe')
    preset_groups   = get_preset_groups()
    selected_groups = st.multiselect(
        'Preset groups',
        options=list(preset_groups.keys()),
        default=['Default List'],
    )
    
    st.caption('⚠️ Each sector shows top 10 stocks by market cap only, not the full sector.')

    custom_input = st.text_input(
        'Add ticker(s)',
        placeholder='e.g. NVDA, AMD',
    ).upper().strip()

    selected_tickers = []
    for g in selected_groups:
        selected_tickers.extend(preset_groups.get(g, []))

    if custom_input:
        for t in custom_input.split(','):
            t = t.strip()
            if t:
                selected_tickers.append(t)

    selected_tickers = list(dict.fromkeys(selected_tickers))
    if not selected_tickers:
        selected_tickers = config.ALL_TICKERS

    st.caption(f'{len(selected_tickers)} tickers selected')

    st.divider()

    # --- Filters ---
    st.subheader('Filters')

    min_score    = st.slider('Min composite score', 0, 100, 0, step=5)
    max_pe_input = st.number_input('Max P/E ratio', min_value=0.0,
                                   max_value=1000.0, value=500.0, step=10.0)
    min_roe_pct  = st.slider('Min ROE (%)', -100, 200, -100, step=5)
    max_debt_pct = st.slider('Max debt ratio (%)', 0, 100, 100, step=5)

    filters = {}
    if min_score > 0:
        filters['min_score'] = min_score
    if max_pe_input < 500:
        filters['max_pe'] = max_pe_input
    if min_roe_pct > -100:
        filters['min_roe'] = min_roe_pct / 100
    if max_debt_pct < 100:
        filters['max_debt_ratio'] = max_debt_pct / 100

    st.divider()

    # --- Sort ---
    st.subheader('Sort')

    sort_map = {
        'Composite Score': 'score',
        'P/E Ratio':       'pe_ratio',
        'ROE':             'roe',
        'Gross Margin':    'gross_margin',
        'Profit Margin':   'profit_margin',
        'Debt Ratio':      'debt_ratio',
        'Market Cap':      'market_cap',
    }
    sort_label     = st.selectbox('Sort by', list(sort_map.keys()))
    sort_ascending = st.checkbox('Ascending order', value=False)

    st.divider()

    # --- Refresh ---
    if st.button('🔄 Refresh Data', use_container_width=True,
                 disabled=st.session_state.get('refreshing', False)):
        st.session_state['refreshing'] = True
        st.rerun()

    if st.session_state.get('refreshing', False):
        with st.spinner('Fetching data, please wait...'):
            create_tables()
            for ticker in selected_tickers:
                update_ticker(ticker, force=True)
        st.cache_data.clear()
        st.session_state['refreshing'] = False
        st.rerun()


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

profiles = load_data(
    tickers_key=tuple(selected_tickers),
    sort_by=sort_map[sort_label],
    ascending=sort_ascending,
    filters_key=tuple(sorted(filters.items())) if filters else None,
)


# ---------------------------------------------------------------------------
# Main area — header
# ---------------------------------------------------------------------------

st.title(f"{config.APP_ICON} {config.APP_TITLE}")

st.warning(
    "**Disclaimer:** The composite score is a rough screening reference only. "
    "Raw metrics (ROE, P/E, margins) should be the primary basis for any "
    "investment evaluation. This tool does not constitute financial advice.",
)

if not profiles:
    st.info('No stocks match the current filters. Try relaxing the conditions in the sidebar.')
    st.stop()


# ---------------------------------------------------------------------------
# Stats cards
# ---------------------------------------------------------------------------

valid_scores = [p['score']        for p in profiles if p.get('score')        is not None]
valid_pe     = [p['pe_ratio']     for p in profiles if p.get('pe_ratio')     is not None]
valid_roe    = [p['roe']          for p in profiles if p.get('roe')           is not None]
valid_gm     = [p['gross_margin'] for p in profiles if p.get('gross_margin') is not None]

c1, c2, c3, c4 = st.columns(4)
c1.metric('Stocks Shown',     len(profiles))
c2.metric('Avg Score',        f"{sum(valid_scores)/len(valid_scores):.1f}" if valid_scores else '—')
c3.metric('Avg P/E',          f"{sum(valid_pe)/len(valid_pe):.1f}"         if valid_pe     else '—')
c4.metric('Avg Gross Margin', f"{sum(valid_gm)/len(valid_gm):.1%}"         if valid_gm     else '—')

st.divider()


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_detail = st.tabs(['📊 Overview', '🔍 Stock Detail'])


# ── Tab 1: Overview ──────────────────────────────────────────────────────────

with tab_overview:

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('**Metric Comparison**')
        metric_map = {
            'Gross Margin':  'gross_margin',
            'Profit Margin': 'profit_margin',
            'ROE':           'roe',
            'Debt Ratio':    'debt_ratio',
            'P/E Ratio':     'pe_ratio',
            'Score':         'score',
        }
        metric_choice = st.selectbox('Select metric', list(metric_map.keys()))
        fig = plot_metrics_comparison(
            profiles,
            metric=metric_map[metric_choice],
            dark_theme=is_dark,
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('No data available for this metric.')

    with col_right:
        st.markdown('**Valuation Map — P/E vs ROE**')
        log_scale = st.toggle('Log scale (P/E axis)', value=False)
        fig = plot_valuation_scatter(
            profiles,
            log_scale=log_scale,
            dark_theme=is_dark,
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('Not enough data to draw the scatter chart.')

    st.divider()

    st.markdown('**All Stocks**')

    table_rows = []
    for p in profiles:
        table_rows.append({
            'Ticker':         p.get('ticker', ''),
            'Score':          p.get('score'),
            'P/E':            p.get('pe_ratio'),
            'ROE':            p.get('roe'),
            'Gross Margin':   p.get('gross_margin'),
            'Profit Margin':  p.get('profit_margin'),
            'Debt Ratio':     p.get('debt_ratio'),
            'Price':          p.get('current_price'),
            'Mkt Cap':        p.get('market_cap'),
            'P/E Signal':     p.get('pe_signal', ''),
            'DCF Signal':     p.get('dcf_signal', ''),
        })

    df      = pd.DataFrame(table_rows)
    df_disp = df.copy()

    df_disp['Score']         = df_disp['Score'].apply(        lambda x: f"{x:.1f}"  if pd.notna(x) else '—')
    df_disp['P/E']           = df_disp['P/E'].apply(          lambda x: f"{x:.1f}x" if pd.notna(x) else '—')
    df_disp['ROE']           = df_disp['ROE'].apply(          lambda x: f"{x:.1%}"  if pd.notna(x) else '—')
    df_disp['Gross Margin']  = df_disp['Gross Margin'].apply( lambda x: f"{x:.1%}"  if pd.notna(x) else '—')
    df_disp['Profit Margin'] = df_disp['Profit Margin'].apply(lambda x: f"{x:.1%}"  if pd.notna(x) else '—')
    df_disp['Debt Ratio']    = df_disp['Debt Ratio'].apply(   lambda x: f"{x:.1%}"  if pd.notna(x) else '—')
    df_disp['Price']         = df_disp['Price'].apply(        lambda x: f"${x:.2f}" if pd.notna(x) else '—')
    df_disp['Mkt Cap']       = df_disp['Mkt Cap'].apply(      lambda x: f"${x/1e9:.0f}B" if pd.notna(x) else '—')

    st.dataframe(df_disp, use_container_width=True, hide_index=True)


# ── Tab 2: Stock Detail ───────────────────────────────────────────────────────

with tab_detail:

    ticker_options = [p['ticker'] for p in profiles]

    if not ticker_options:
        st.info('No stocks available. Adjust filters in the sidebar.')
    else:
        selected = st.selectbox('Select a stock', ticker_options)
        profile  = next((p for p in profiles if p['ticker'] == selected), None)

        if not profile:
            st.warning('No data available for this stock.')
        else:
            score = profile.get('score') or 0
            st.subheader(f"{selected}  ·  Score: {score:.1f} / 100")

            st.markdown('#### Price History')
            days = st.slider('Days to show', 30, 365, 180, step=30)
            fig  = plot_price_history(selected, days=days, dark_theme=is_dark)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info('No price data found in the database.')

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown('#### Score Breakdown')
                fig = plot_score_breakdown(profile, dark_theme=is_dark)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info('Score breakdown unavailable.')

            with col_b:
                st.markdown('#### Raw Metrics')

                def _pct(v):    return f"{v:.1%}"  if v is not None else '—'
                def _b(v):      return f"${v/1e9:.1f}B" if v is not None else '—'
                def _dollar(v): return f"${v:.2f}" if v is not None else '—'
                def _x(v):      return f"{v:.1f}x" if v is not None else '—'

                raw_rows = [
                    ('Revenue',          _b(profile.get('revenue'))),
                    ('Net Income',       _b(profile.get('net_income'))),
                    ('Free Cash Flow',   _b(profile.get('free_cash_flow'))),
                    ('Market Cap',       _b(profile.get('market_cap'))),
                    ('EPS',              _dollar(profile.get('eps'))),
                    ('P/E Ratio',        _x(profile.get('pe_ratio'))),
                    ('Gross Margin',     _pct(profile.get('gross_margin'))),
                    ('Profit Margin',    _pct(profile.get('profit_margin'))),
                    ('ROE',              _pct(profile.get('roe'))),
                    ('Debt Ratio',       _pct(profile.get('debt_ratio'))),
                    ('Intrinsic Value',  _dollar(profile.get('intrinsic_value'))),
                    ('Current Price',    _dollar(profile.get('current_price'))),
                    ('Margin of Safety', _pct(profile.get('margin_of_safety'))),
                    ('P/E Signal',       profile.get('pe_signal') or '—'),
                    ('DCF Signal',       profile.get('dcf_signal') or '—'),
                ]

                raw_df = pd.DataFrame(raw_rows, columns=['Metric', 'Value'])
                st.dataframe(raw_df, use_container_width=True, hide_index=True)

            st.caption(
                'ℹ️ Composite score is a rough screening guide only. '
                'Raw metrics above are the primary reference for evaluation.'
            )