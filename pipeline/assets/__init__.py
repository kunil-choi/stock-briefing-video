# pipeline/assets/__init__.py
from .config   import W, H, C, STOCK_CODES
from .drawing  import fnt, new_frame, draw_topbar, draw_bottombar
from .chart    import build_chart_image
from .builders import (
    build_opening, build_market_summary, build_sector,
    build_stock_cards, build_ai_strategy, build_closing,
)
