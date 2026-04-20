# pipeline/assets/chart.py
import os
from typing import Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from .config import C, STOCK_CODES, normalize_stock_name


def fetch_ohlcv(stock_name: str, days: int = 20) -> Optional[pd.DataFrame]:
    # 종목명 정규화 후 코드 조회
    normalized = normalize_stock_name(stock_name)
    code = STOCK_CODES.get(normalized)
    if not code:
        print(f"  [chart] 종목코드 없음: {stock_name} (정규화: {normalized})")
        return None
    try:
        from pykrx import stock as krx
        end   = datetime.today().strftime("%Y%m%d")
        start = (datetime.today() - timedelta(days=days * 2)).strftime("%Y%m%d")
        df = krx.get_market_ohlcv_by_date(start, end, code)
        if df is None or df.empty:
            return None
        df = df.tail(days)
        df.index = pd.to_datetime(df.index)
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        return df
    except Exception as e:
        print(f"  [chart] pykrx 오류 ({stock_name}): {e}")
        return None


def draw_candle_chart(df: pd.DataFrame, stock_name: str, save_path: str) -> Optional[str]:
    try:
        bg     = tuple(v / 255 for v in C["chart_bg"])
        up_col = "#%02x%02x%02x" % C["chart_up"]
        dn_col = "#%02x%02x%02x" % C["chart_down"]
        grid_c = "#%02x%02x%02x" % C["chart_grid"]
        text_c = "#%02x%02x%02x" % C["chart_text"]
        gold_c = "#%02x%02x%02x" % C["gold"]

        fig, (ax_c, ax_v) = plt.subplots(
            2, 1, figsize=(14, 7),
            facecolor=bg,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.04}
        )

        for ax in (ax_c, ax_v):
            ax.set_facecolor(bg)
            ax.tick_params(colors=text_c, labelsize=10)
            for spine in ax.spines.values():
                spine.set_color(grid_c)
            ax.yaxis.grid(True, color=grid_c, linewidth=0.6, linestyle="--")
            ax.set_axisbelow(True)

        for i, (_, row) in enumerate(df.iterrows()):
            is_up  = row["Close"] >= row["Open"]
            color  = up_col if is_up else dn_col
            body_b = min(row["Open"], row["Close"])
            body_h = abs(row["Close"] - row["Open"]) or (row["High"] * 0.001)
            ax_c.bar(i, body_h, bottom=body_b, color=color, width=0.6, zorder=3)
            ax_c.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=1.2, zorder=2)

        ax_c.plot(list(range(len(df))), df["Close"].tolist(),
                  color=gold_c, linewidth=1.0, alpha=0.45, zorder=1)

        for i, (_, row) in enumerate(df.iterrows()):
            is_up = row["Close"] >= row["Open"]
            ax_v.bar(i, row["Volume"],
                     color=(up_col if is_up else dn_col),
                     width=0.6, alpha=0.7, zorder=3)

        step   = max(1, len(df) // 6)
        ticks  = list(range(0, len(df), step))
        labels = [df.index[i].strftime("%m/%d") for i in ticks]
        ax_c.set_xticks([])
        ax_v.set_xticks(ticks)
        ax_v.set_xticklabels(labels, color=text_c, fontsize=10)

        hi_i = df["High"].idxmax()
        lo_i = df["Low"].idxmin()
        hi_x = df.index.get_loc(hi_i)
        lo_x = df.index.get_loc(lo_i)
        ax_c.annotate(
            f"▲ {int(df.loc[hi_i, 'High']):,}",
            xy=(hi_x, df.loc[hi_i, "High"]),
            xytext=(hi_x + 0.4, df.loc[hi_i, "High"] * 1.008),
            fontsize=10, color=up_col,
            arrowprops=dict(arrowstyle="-", color=up_col, lw=0.8)
        )
        ax_c.annotate(
            f"▼ {int(df.loc[lo_i, 'Low']):,}",
            xy=(lo_x, df.loc[lo_i, "Low"]),
            xytext=(lo_x + 0.4, df.loc[lo_i, "Low"] * 0.992),
            fontsize=10, color=dn_col,
            arrowprops=dict(arrowstyle="-", color=dn_col, lw=0.8)
        )

        ax_c.text(0.01, 0.96, stock_name,
                  transform=ax_c.transAxes,
                  fontsize=14, color=gold_c,
                  fontweight="bold", va="top", alpha=0.9)

        ax_c.set_xlim(-0.8, len(df) - 0.2)
        ax_v.set_xlim(-0.8, len(df) - 0.2)
        ax_v.set_yticks([])

        plt.tight_layout(pad=0.5)
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=bg)
        plt.close(fig)
        return save_path

    except Exception as e:
        print(f"  [chart] 차트 생성 실패 ({stock_name}): {e}")
        plt.close("all")
        return None


def build_chart_image(stock_name: str, img_dir: str) -> Optional[str]:
    normalized = normalize_stock_name(stock_name)
    save_path = os.path.join(img_dir, f"chart_{normalized}.png")
    if os.path.exists(save_path):
        print(f"  [chart] 캐시 사용: {normalized}")
        return save_path
    df = fetch_ohlcv(normalized, days=14)
    if df is None or len(df) < 3:
        return None
    return draw_candle_chart(df, normalized, save_path)
