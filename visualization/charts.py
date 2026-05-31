# visualization/charts.py
# Builds Plotly figures for the Streamlit UI.
# All functions return a go.Figure object. Display is handled by app.py.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go

from data.db import get_stock_prices


# ---------------------------------------------------------------------------
# Shared style constants
# ---------------------------------------------------------------------------

FONT_FAMILY    = 'Arial, sans-serif'
PRIMARY_COLOR  = '#1f77b4'
POSITIVE_COLOR = '#2ecc71'
NEGATIVE_COLOR = '#e74c3c'
NEUTRAL_COLOR  = '#95a5a6'

SCORE_COMPONENT_COLORS = {
    'gross_margin':  '#3498db',
    'profit_margin': '#2ecc71',
    'roe':           '#9b59b6',
    'debt_ratio':    '#e67e22',
    'pe_valuation':  '#e74c3c',
    'dcf_valuation': '#1abc9c',
}

COMPONENT_LABELS = {
    'gross_margin':  'Gross Margin',
    'profit_margin': 'Profit Margin',
    'roe':           'ROE',
    'debt_ratio':    'Debt Ratio',
    'pe_valuation':  'P/E Valuation',
    'dcf_valuation': 'DCF Valuation',
}


# ---------------------------------------------------------------------------
# Theme colors
# ---------------------------------------------------------------------------

def _colors(dark: bool) -> dict:
    if dark:
        return {
            'bg':               '#0e1117',
            'grid':             '#2d2d2d',
            'font':             '#fafafa',
            'gap':              '#2d2d2d',
            'annotation_bg':    '#1e2d1e',
            'annotation_border':'#555555',
            'annotation_font':  '#cccccc',
        }
    else:
        return {
            'bg':               'white',
            'grid':             '#f0f0f0',
            'font':             '#222222',
            'gap':              '#ecf0f1',
            'annotation_bg':    '#fff9e6',
            'annotation_border':'#95a5a6',
            'annotation_font':  '#555555',
        }


def _base_layout(title: str, dark: bool = False) -> dict:
    c = _colors(dark)
    return dict(
        title=dict(text=title, font=dict(size=16, family=FONT_FAMILY, color=c['font'])),
        plot_bgcolor=c['bg'],
        paper_bgcolor=c['bg'],
        font=dict(family=FONT_FAMILY, size=13, color=c['font']),
        margin=dict(l=60, r=40, t=60, b=60),
        hovermode='closest',
        xaxis=dict(showgrid=True, gridcolor=c['grid'], zeroline=False, color=c['font']),
        yaxis=dict(showgrid=True, gridcolor=c['grid'], zeroline=False, color=c['font']),
    )


# ---------------------------------------------------------------------------
# Chart 1: Price history (line)
# ---------------------------------------------------------------------------

def plot_price_history(ticker, days=180, dark_theme=False):
    prices = get_stock_prices(ticker)
    if prices is None or prices.empty:
        return None

    df = prices.tail(days).copy()
    df['date'] = pd.to_datetime(df['date'])

    price_start = df['close'].iloc[0]
    price_end   = df['close'].iloc[-1]
    line_color  = POSITIVE_COLOR if price_end >= price_start else NEGATIVE_COLOR

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['close'],
        mode='lines',
        line=dict(color=line_color, width=2),
        name='Close Price',
        hovertemplate='%{x|%Y-%m-%d}<br>$%{y:.2f}<extra></extra>',
    ))

    fig.add_trace(go.Scatter(
        x=pd.concat([df['date'], df['date'][::-1]]),
        y=pd.concat([df['close'], pd.Series([price_start] * len(df))]),
        fill='toself',
        fillcolor=line_color,
        opacity=0.08,
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip',
    ))

    layout = _base_layout(f'{ticker} — Price History ({days} days)', dark=dark_theme)
    layout['yaxis']['tickprefix'] = '$'
    fig.update_layout(**layout)

    return fig


# ---------------------------------------------------------------------------
# Chart 2: Metrics comparison (horizontal bar)
# ---------------------------------------------------------------------------

METRIC_META = {
    'gross_margin':  {'label': 'Gross Margin',   'color': '#3498db'},
    'profit_margin': {'label': 'Profit Margin',  'color': '#2ecc71'},
    'roe':           {'label': 'ROE',             'color': '#9b59b6'},
    'debt_ratio':    {'label': 'Debt Ratio',      'color': '#e67e22'},
    'pe_ratio':      {'label': 'P/E Ratio',       'color': '#e74c3c'},
    'score':         {'label': 'Composite Score', 'color': '#1abc9c'},
}


def plot_metrics_comparison(profiles, metric='gross_margin', dark_theme=False):
    rows = [
        {'ticker': p['ticker'], 'value': p.get(metric)}
        for p in profiles
        if p.get(metric) is not None
    ]
    if not rows:
        return None

    df        = pd.DataFrame(rows)
    ascending = (metric == 'debt_ratio')
    df        = df.sort_values('value', ascending=ascending)

    meta   = METRIC_META.get(metric, {'label': metric, 'color': PRIMARY_COLOR})
    is_pct = metric not in ('pe_ratio', 'score', 'market_cap', 'eps')

    c         = _colors(dark_theme)
    text_color = c['font']

    text_vals = (
        [f'{v:.1%}' for v in df['value']] if is_pct
        else [f'{v:.1f}' for v in df['value']]
    )

    fig = go.Figure(go.Bar(
        x=df['value'],
        y=df['ticker'],
        orientation='h',
        marker_color=meta['color'],
        text=text_vals,
        textposition='outside',
        textfont=dict(color=text_color),
        hovertemplate='%{y}: %{text}<extra></extra>',
    ))

    layout = _base_layout(f"{meta['label']} — All Stocks", dark=dark_theme)
    layout['xaxis']['tickformat'] = '.0%' if is_pct else '.1f'
    layout['yaxis']['title']      = ''
    layout['height']              = max(300, len(df) * 45)
    fig.update_layout(**layout)

    return fig


# ---------------------------------------------------------------------------
# Chart 3: Score breakdown (stacked horizontal bar)
# ---------------------------------------------------------------------------

def plot_score_breakdown(profile, dark_theme=False):
    breakdown = profile.get('score_breakdown')
    if not breakdown:
        return None

    ticker    = profile.get('ticker', '')
    total     = profile.get('score', 0)
    gap_color = _colors(dark_theme)['gap']

    max_points = {
        'gross_margin': 15, 'profit_margin': 15, 'roe': 20,
        'debt_ratio':   15, 'pe_valuation':  15, 'dcf_valuation': 20,
    }

    fig = go.Figure()

    for key, max_pt in max_points.items():
        earned = breakdown.get(key, 0)
        gap    = max_pt - earned
        color  = SCORE_COMPONENT_COLORS.get(key, PRIMARY_COLOR)
        label  = COMPONENT_LABELS.get(key, key)

        fig.add_trace(go.Bar(
            name=label,
            x=[earned],
            y=[label],
            orientation='h',
            marker_color=color,
            text=f'{earned:.1f}' if earned > 0 else '',
            textposition='inside',
            hovertemplate=f'{label}: {earned:.1f} / {max_pt} pts<extra></extra>',
        ))

        fig.add_trace(go.Bar(
            name=f'{label} (gap)',
            x=[gap],
            y=[label],
            orientation='h',
            marker_color=gap_color,
            showlegend=False,
            hovertemplate=f'Remaining: {gap:.1f} pts<extra></extra>',
        ))

    layout = _base_layout(f'{ticker} — Score Breakdown  ({total:.1f} / 100)', dark=dark_theme)
    layout['barmode']        = 'stack'
    layout['xaxis']['range'] = [0, 100]
    layout['xaxis']['title'] = 'Points'
    layout['yaxis']['title'] = ''
    layout['height']         = 380
    layout['showlegend']     = False
    fig.update_layout(**layout)

    return fig


# ---------------------------------------------------------------------------
# Chart 4: Valuation scatter (P/E vs ROE)
# ---------------------------------------------------------------------------

def plot_valuation_scatter(profiles, log_scale=False, dark_theme=False):
    rows = []
    for p in profiles:
        if None in (p.get('pe_ratio'), p.get('roe'), p.get('score')):
            continue
        rows.append({
            'ticker':     p['ticker'],
            'pe_ratio':   p['pe_ratio'],
            'roe':        p['roe'],
            'score':      p['score'],
            'market_cap': p.get('market_cap') or 1e9,
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)

    pe_threshold  = df['pe_ratio'].quantile(0.90)
    df['outlier'] = df['pe_ratio'] > pe_threshold

    normal   = df[~df['outlier']].copy()
    outliers = df[df['outlier']].copy()

    normal['roe_display']   = normal['roe'].clip(-0.5, 2.0)
    outliers['roe_display'] = outliers['roe'].clip(-0.5, 2.0)

    max_cap = df['market_cap'].max()
    normal['bubble_size']   = (normal['market_cap']   / max_cap * 50).clip(8, 50)
    outliers['bubble_size'] = (outliers['market_cap'] / max_cap * 50).clip(8, 50)

    c                 = _colors(dark_theme)
    annotation_bg     = c['annotation_bg']
    annotation_border = c['annotation_border']
    annotation_font   = c['annotation_font']

    def score_color(score):
        if score >= 60:   return POSITIVE_COLOR
        elif score >= 40: return NEUTRAL_COLOR
        else:             return NEGATIVE_COLOR

    fig = go.Figure()

    for _, row in normal.iterrows():
        roe_label = f"{row['roe']:.1%}" if abs(row['roe']) < 5 else 'N/M'
        fig.add_trace(go.Scatter(
            x=[row['pe_ratio']],
            y=[row['roe_display']],
            mode='markers+text',
            marker=dict(
                size=row['bubble_size'],
                color=score_color(row['score']),
                opacity=0.75,
                line=dict(width=1, color='white'),
            ),
            text=[row['ticker']],
            textposition='top center',
            name=row['ticker'],
            hovertemplate=(
                f"<b>{row['ticker']}</b><br>"
                f"P/E: {row['pe_ratio']:.1f}<br>"
                f"ROE: {roe_label}<br>"
                f"Score: {row['score']:.1f}<extra></extra>"
            ),
        ))

    for _, row in outliers.iterrows():
        roe_label = f"{row['roe']:.1%}" if abs(row['roe']) < 5 else 'N/M'
        x_pos     = row['pe_ratio'] if log_scale else pe_threshold * 1.05

        fig.add_trace(go.Scatter(
            x=[x_pos],
            y=[row['roe_display']],
            mode='markers+text',
            marker=dict(
                size=max(row['bubble_size'] * 0.7, 12),
                color=score_color(row['score']),
                opacity=0.85,
                symbol='star',
                line=dict(width=1, color='white'),
            ),
            text=[row['ticker']],
            textposition='top center',
            name=f"{row['ticker']} (outlier)",
            hovertemplate=(
                f"<b>{row['ticker']}</b> ⚠️ Outlier<br>"
                f"Actual P/E: {row['pe_ratio']:.1f}<br>"
                f"ROE: {roe_label}<br>"
                f"Score: {row['score']:.1f}<extra></extra>"
            ),
        ))

        if not log_scale:
            fig.add_annotation(
                x=x_pos,
                y=row['roe_display'],
                text=f"<b>{row['ticker']}</b> P/E={row['pe_ratio']:.0f} (outlier)",
                showarrow=True,
                arrowhead=2,
                arrowcolor=annotation_border,
                ax=60, ay=-30,
                font=dict(size=11, color=annotation_font),
                bgcolor=annotation_bg,
                bordercolor=annotation_border,
                borderwidth=1,
            )

    median_pe  = normal['pe_ratio'].median()
    median_roe = normal['roe_display'].median()

    fig.add_hline(
        y=median_roe,
        line_dash='dot', line_color=NEUTRAL_COLOR, opacity=0.5,
        annotation_text=f'Median ROE {median_roe:.1%}',
        annotation_position='top left',
    )
    fig.add_vline(
        x=median_pe,
        line_dash='dot', line_color=NEUTRAL_COLOR, opacity=0.5,
        annotation_text=f'Median P/E {median_pe:.1f}',
        annotation_position='top right',
    )

    layout = _base_layout('Valuation Map — P/E vs ROE', dark=dark_theme)
    layout['xaxis']['title']      = 'P/E Ratio (lower = cheaper)'
    layout['yaxis']['title']      = 'ROE (higher = better)'
    layout['yaxis']['tickformat'] = '.0%'
    layout['showlegend']          = False
    layout['height']              = 500
    layout['margin']              = dict(l=60, r=60, t=60, b=60)

    if log_scale:
        layout['xaxis']['type']  = 'log'
        layout['xaxis']['title'] = 'P/E Ratio — log scale (lower = cheaper)'
        layout['xaxis']['range'] = [1, 3]
    else:
        layout['xaxis']['range'] = [0, pe_threshold * 1.25]

    fig.update_layout(**layout)

    return fig


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from analysis.screener import screen_stocks, build_stock_profile

    print("=" * 60)
    print("charts.py — test run")
    print("=" * 60)

    all_passed = True
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_charts')
    os.makedirs(output_dir, exist_ok=True)

    print("\n[Test 1] plot_price_history('AAPL')")
    fig = plot_price_history('AAPL', days=180)
    if fig:
        path = os.path.join(output_dir, 'test_price_history.html')
        fig.write_html(path)
        print(f"  PASS ✅  saved → {path}")
    else:
        print("  FAIL ❌  returned None")
        all_passed = False

    print("\n[Test 2] plot_metrics_comparison(profiles, 'gross_margin')")
    profiles = screen_stocks()
    fig = plot_metrics_comparison(profiles, metric='gross_margin')
    if fig:
        path = os.path.join(output_dir, 'test_metrics_comparison.html')
        fig.write_html(path)
        print(f"  PASS ✅  saved → {path}")
    else:
        print("  FAIL ❌  returned None")
        all_passed = False

    print("\n[Test 3] plot_score_breakdown(MSFT profile)")
    profile = build_stock_profile('MSFT')
    fig = plot_score_breakdown(profile)
    if fig:
        path = os.path.join(output_dir, 'test_score_breakdown.html')
        fig.write_html(path)
        print(f"  PASS ✅  saved → {path}")
    else:
        print("  FAIL ❌  returned None")
        all_passed = False

    print("\n[Test 4] plot_valuation_scatter — linear (default)")
    fig = plot_valuation_scatter(profiles, log_scale=False)
    if fig:
        path = os.path.join(output_dir, 'test_valuation_scatter_linear.html')
        fig.write_html(path)
        print(f"  PASS ✅  saved → {path}")
    else:
        print("  FAIL ❌  returned None")
        all_passed = False

    print("\n[Test 4b] plot_valuation_scatter — log scale")
    fig = plot_valuation_scatter(profiles, log_scale=True)
    if fig:
        path = os.path.join(output_dir, 'test_valuation_scatter_log.html')
        fig.write_html(path)
        print(f"  PASS ✅  saved → {path}")
    else:
        print("  FAIL ❌  returned None")
        all_passed = False

    print(f"\n{'=' * 60}")
    print(f"  Result: {'ALL TESTS PASSED ✅' if all_passed else 'SOME TESTS FAILED ❌'}")
    if all_passed:
        print(f"  Charts saved to: {output_dir}")
        print(f"  Open the .html files in your browser to verify visuals.")
    print(f"{'=' * 60}\n")