# pipeline/assets/chart.py — draw_candle_chart() 함수만 교체
# 변경 7: 주가 금액·날짜가 잘 보이도록 figsize 조정 + left margin 확대

def draw_candle_chart(df: pd.DataFrame, stock_name: str, save_path: str) -> Optional[str]:
    try:
        bg     = tuple(v / 255 for v in C["chart_bg"])
        up_col = "#%02x%02x%02x" % C["chart_up"]
        dn_col = "#%02x%02x%02x" % C["chart_down"]
        grid_c = "#%02x%02x%02x" % C["chart_grid"]
        text_c = "#%02x%02x%02x" % C["chart_text"]
        gold_c = "#%02x%02x%02x" % C["gold"]

        # ── 변경: figsize를 (17.0, 8.0)으로 줄여서 좌측 y축 레이블 공간 확보
        fig, (ax_c, ax_v) = plt.subplots(
            2, 1,
            figsize=(17.0, 8.0),
            facecolor=bg,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06}
        )

        for ax in (ax_c, ax_v):
            ax.set_facecolor(bg)
            ax.tick_params(colors=text_c, labelsize=14)
            for spine in ax.spines.values():
                spine.set_color(grid_c)
            ax.yaxis.grid(True, color=grid_c, linewidth=0.8, linestyle="--")
            ax.set_axisbelow(True)

        # 캔들 몸통 + 심지
        for i, (_, row) in enumerate(df.iterrows()):
            is_up   = row["Close"] >= row["Open"]
            color   = up_col if is_up else dn_col
            body_b  = min(row["Open"], row["Close"])
            body_h  = abs(row["Close"] - row["Open"]) or (row["High"] * 0.001)
            ax_c.bar(i, body_h, bottom=body_b, color=color, width=0.6, zorder=3)
            ax_c.plot([i, i], [row["Low"], row["High"]],
                      color=color, linewidth=1.5, zorder=2)

        # 종가 추세선
        ax_c.plot(list(range(len(df))), df["Close"].tolist(),
                  color=gold_c, linewidth=1.2, alpha=0.5, zorder=1)

        # 거래량 바
        for i, (_, row) in enumerate(df.iterrows()):
            is_up = row["Close"] >= row["Open"]
            ax_v.bar(i, row["Volume"],
                     color=(up_col if is_up else dn_col),
                     width=0.6, alpha=0.75, zorder=3)

        # x축 날짜 레이블
        step   = max(1, len(df) // 7)
        ticks  = list(range(0, len(df), step))
        labels = [df.index[i].strftime("%m/%d") for i in ticks]
        ax_c.set_xticks([])
        ax_v.set_xticks(ticks)
        ax_v.set_xticklabels(labels, color=text_c, fontsize=14)

        # ── 변경: y축 설정 — 폰트 크기 14, 오른쪽도 tick 없애기
        ax_c.yaxis.set_visible(True)
        ax_c.yaxis.set_label_position("left")
        ax_c.yaxis.tick_left()
        ax_c.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )
        # ── 변경: labelsize 14 (더 크게), pad 늘려서 잘림 방지
        ax_c.tick_params(axis="y", colors=text_c, labelsize=14,
                         left=True, pad=10)
        ax_v.yaxis.set_visible(False)

        # 최고가·최저가 어노테이션
        hi_i = df["High"].idxmax()
        lo_i = df["Low"].idxmin()
        idx_list = df.index.tolist()
        hi_x = idx_list.index(hi_i)
        lo_x = idx_list.index(lo_i)

        ax_c.annotate(
            f"▲ {int(df.loc[hi_i, 'High']):,}",
            xy=(hi_x, df.loc[hi_i, "High"]),
            xytext=(hi_x + 0.6, df.loc[hi_i, "High"] * 1.012),
            fontsize=14, color=up_col,
            arrowprops=dict(arrowstyle="-", color=up_col, lw=1.0)
        )
        ax_c.annotate(
            f"▼ {int(df.loc[lo_i, 'Low']):,}",
            xy=(lo_x, df.loc[lo_i, "Low"]),
            xytext=(lo_x + 0.6, df.loc[lo_i, "Low"] * 0.988),
            fontsize=14, color=dn_col,
            arrowprops=dict(arrowstyle="-", color=dn_col, lw=1.0)
        )

        # 종목명 워터마크
        ax_c.text(0.01, 0.96, stock_name,
                  transform=ax_c.transAxes,
                  fontsize=18, color=gold_c,
                  fontweight="bold", va="top", alpha=0.9)

        ax_c.set_xlim(-0.8, len(df) - 0.2)
        ax_v.set_xlim(-0.8, len(df) - 0.2)

        # ── 변경: subplots_adjust로 좌측 여백 명시 확보 (y축 숫자 잘림 방지)
        plt.subplots_adjust(left=0.10, right=0.97, top=0.97, bottom=0.08)
        plt.savefig(save_path, dpi=100, bbox_inches="tight", facecolor=bg)
        plt.close(fig)
        print(f"  [chart] 저장 완료: {save_path}")
        return save_path

    except Exception as e:
        print(f"  [chart] 차트 생성 실패 ({stock_name}): {e}")
        plt.close("all")
        return None
