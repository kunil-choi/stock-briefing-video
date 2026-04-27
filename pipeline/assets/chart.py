# pipeline/assets/chart.py
import os
from typing import Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
from datetime import datetime, timedelta
from .config import C, STOCK_CODES, normalize_stock_name


def _set_korean_font():
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/Library/Fonts/NanumGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            matplotlib.rcParams["font.family"] = prop.get_name()
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
    matplotlib.rcParams["axes.unicode_minus"] = False

_set_korean_font()


def fetch_ohlcv(stock_name: str, days: int = 20) -> Optional[pd.DataFrame]:
    normalized = normalize_stock_name(stock_name)
    code = STOCK_CODES.get(normalized)
    if not code:
        print(f"  [chart] 종목코드 없음: {stock_name} (정규화: {normalized})")
        return None
    try:
        from pykrx import stock as krx
        end   = datetime.today().strftime("%Y%m%d")
        start = (datetime.today() - timedelta(days=days * 3)).strftime("%Y%m%d")
        df    = krx.get_market_ohlcv_by_date(start, end, code)
        if df is None or df.empty:
            print(f"  [chart] 데이터 없음: {stock_name}")
            return None
        df = df.tail(days)
        df.index = pd.to_datetime(df.index)

        # 한글 컬럼명 → 영문으로 변환
        col_map = {
            "시가": "Open", "고가": "High", "저가": "Low",
            "종가": "Close", "거래량": "Volume"
        }
        df = df.rename(columns=col_map)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in df.columns:
                print(f"  [chart] 컬럼 없음: {col}")
                return None
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

        # ── figsize: 가로는 1920px 기준, 세로는 자막 영역(200px) 제외한 높이
        # 실제 차트 영역: 74(상단바) ~ H-200(CHART_BOTTOM) = 806px
        # dpi=100 기준 → 19.2 x 8.06 인치
        fig, (ax_c, ax_v) = plt.subplots(
            2, 1,
            figsize=(19.2, 8.0),
            facecolor=bg,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.04}
        )

        for ax in (ax_c, ax_v):
            ax.set_facecolor(bg)
            ax.tick_params(colors=text_c, labelsize=13)
            for spine in ax.spines.values():
                spine.set_color(grid_c)
            ax.yaxis.grid(True, color=grid_c, linewidth=0.8, linestyle="--")
            ax.set_axisbelow(True)

        # ── 캔들 바디 + 심지
        for i, (_, row) in enumerate(df.iterrows()):
            is_up   = row["Close"] >= row["Open"]
            color   = up_col if is_up else dn_col
            body_b  = min(row["Open"], row["Close"])
            body_h  = abs(row["Close"] - row["Open"]) or (row["High"] * 0.001)
            ax_c.bar(i, body_h, bottom=body_b, color=color, width=0.6, zorder=3)
            ax_c.plot([i, i], [row["Low"], row["High"]],
                      color=color, linewidth=1.5, zorder=2)

        # ── 종가 라인
        ax_c.plot(list(range(len(df))), df["Close"].tolist(),
                  color=gold_c, linewidth=1.2, alpha=0.5, zorder=1)

        # ── 거래량
        for i, (_, row) in enumerate(df.iterrows()):
            is_up = row["Close"] >= row["Open"]
            ax_v.bar(i, row["Volume"],
                     color=(up_col if is_up else dn_col),
                     width=0.6, alpha=0.75, zorder=3)

        # ── x축 날짜 레이블
        step   = max(1, len(df) // 7)
        ticks  = list(range(0, len(df), step))
        labels = [df.index[i].strftime("%m/%d") for i in ticks]
        ax_c.set_xticks([])
        ax_v.set_xticks(ticks)
        ax_v.set_xticklabels(labels, color=text_c, fontsize=13)

        # ── Y축 (좌측) 가격 표시 — 핵심 수정
        ax_c.yaxis.set_visible(True)
        ax_c.yaxis.set_label_position("left")
        ax_c.yaxis.tick_left()

        # 가격을 콤마 포맷으로 표시 (예: 551,000)
        ax_c.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )
        ax_c.tick_params(axis="y", colors=text_c, labelsize=12, left=True)

        # 거래량 Y축은 숨김 유지
        ax_v.yaxis.set_visible(False)

        # ── 고가/저가 어노테이션
        hi_i = df["High"].idxmax()
        lo_i = df["Low"].idxmin()
        hi_x = df.index.get_loc(hi_i)
        lo_x = df.index.get_loc(lo_i)

        ax_c.annotate(
            f"▲ {int(df.loc[hi_i, 'High']):,}",
            xy=(hi_x, df.loc[hi_i, "High"]),
            xytext=(hi_x + 0.5, df.loc[hi_i, "High"] * 1.010),
            fontsize=13, color=up_col,
            arrowprops=dict(arrowstyle="-", color=up_col, lw=1.0)
        )
        ax_c.annotate(
            f"▼ {int(df.loc[lo_i, 'Low']):,}",
            xy=(lo_x, df.loc[lo_i, "Low"]),
            xytext=(lo_x + 0.5, df.loc[lo_i, "Low"] * 0.990),
            fontsize=13, color=dn_col,
            arrowprops=dict(arrowstyle="-", color=dn_col, lw=1.0)
        )

        # ── 종목명 워터마크
        ax_c.text(0.01, 0.96, stock_name,
                  transform=ax_c.transAxes,
                  fontsize=18, color=gold_c,
                  fontweight="bold", va="top", alpha=0.9)

        ax_c.set_xlim(-0.8, len(df) - 0.2)
        ax_v.set_xlim(-0.8, len(df) - 0.2)

        plt.tight_layout(pad=0.3)
        plt.savefig(save_path, dpi=100, bbox_inches="tight", facecolor=bg)
        plt.close(fig)
        print(f"  [chart] 저장 완료: {save_path}")
        return save_path

    except Exception as e:
        print(f"  [chart] 차트 생성 실패 ({stock_name}): {e}")
        plt.close("all")
        return None


def build_chart_image(stock_name: str, img_dir: str) -> Optional[str]:
    normalized = normalize_stock_name(stock_name)
    save_path  = os.path.join(img_dir, f"chart_{normalized}.png")
    if os.path.exists(save_path):
        print(f"  [chart] 캐시 사용: {normalized}")
        return save_path
    df = fetch_ohlcv(normalized, days=14)
    if df is None or len(df) < 3:
        print(f"  [chart] 데이터 부족: {normalized}")
        return None
    return draw_candle_chart(df, normalized, save_path)
