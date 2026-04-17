import os
import json
import time
import textwrap
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

# ── 기본 설정
W, H = 1920, 1080
FONT_PATH     = "assets/fonts/NotoSansKR-Bold.ttf"
FONT_PATH_REG = "assets/fonts/NotoSansKR-Regular.ttf"

C = {
    "bg":      (10, 12, 25),
    "bg2":     (18, 22, 45),
    "bg3":     (22, 28, 58),
    "gold":    (255, 195, 0),
    "white":   (235, 235, 245),
    "sub":     (160, 165, 185),
    "green":   (0, 210, 120),
    "red":     (255, 75, 75),
    "blue":    (50, 140, 255),
    "purple":  (160, 50, 200),
    "name_bg": (255, 255, 255),
    "name_tx": (20, 20, 30),
    "tag_red": (180, 0, 0),
    "tag_bl":  (0, 80, 200),
}

TODAY   = datetime.now().strftime("%Y년 %m월 %d일")
PROGRAM = "AI 주식 브리핑"

STOCK_CODES = {
    "삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380",
    "현대로템": "064350", "현대위아": "011210", "신세계": "004170",
    "두산에너빌리티": "034020", "크래프톤": "259960", "하이브": "352820",
    "에이피알": "278470",
}

# 연합뉴스 검색 키워드 (관련도 높은 키워드)
YONHAP_KW = {
    "삼성전자":    "삼성전자 반도체 파운드리",
    "SK하이닉스":  "SK하이닉스 HBM 메모리",
    "현대차":      "현대차 로보틱스 보스턴다이내믹스",
    "현대로템":    "현대로템 방산 K2전차",
    "현대위아":    "현대위아 로봇",
    "신세계":      "신세계 면세점 외국인관광",
    "두산에너빌리티": "두산에너빌리티 원전 SMR",
    "크래프톤":    "크래프톤 PUBG 게임",
    "하이브":      "하이브 BTS 컴백",
    "에이피알":    "에이피알 메디큐브 K뷰티",
    "시장요약":    "코스피 증시",
}

# 기업 공식 로고/이미지 fallback URL
COMPANY_LOGO = {
    "삼성전자":    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Samsung_Logo.svg/800px-Samsung_Logo.svg.png",
    "SK하이닉스":  "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/SK_hynix_logo.svg/800px-SK_hynix_logo.svg.png",
    "현대차":      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Hyundai_Motor_Company_logo.svg/800px-Hyundai_Motor_Company_logo.svg.png",
    "현대로템":    "https://www.hyundai-rotem.co.kr/images/common/logo.png",
    "현대위아":    "https://www.hyundai-wia.com/resources/images/common/logo.png",
    "신세계":      "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Shinsegae_logo.svg/800px-Shinsegae_logo.svg.png",
    "두산에너빌리티": "https://www.doosanenerbility.com/resources/images/common/logo.png",
    "크래프톤":    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Krafton_logo.svg/800px-Krafton_logo.svg.png",
    "하이브":      "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/HYBE_Logo.svg/800px-HYBE_Logo.svg.png",
    "에이피알":    "https://www.aprilskin.com/favicon.ico",
}


# ── 폰트
def font(size, bold=True):
    try:
        return ImageFont.truetype(FONT_PATH if bold else FONT_PATH_REG, size)
    except:
        return ImageFont.load_default()


# ── 기본 프레임
def new_frame():
    img = Image.new("RGB", (W, H), C["bg"])
    draw = ImageDraw.Draw(img)
    for y in range(200):
        v = int(6 * (1 - y / 200))
        draw.line([(0, y), (W, y)],
                  fill=(C["bg"][0]+v, C["bg"][1]+v, C["bg"][2]+v+3))
    return img


def top_bar(img, tag, tag_color, program=PROGRAM, date=TODAY):
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0,0),(W,72)], fill=C["bg2"])
    draw.line([(0,72),(W,72)], fill=C["gold"], width=2)
    f = font(22)
    tw = int(f.getlength(tag)) + 28
    draw.rounded_rectangle([(20,18),(20+tw,54)], radius=5, fill=tag_color)
    draw.text((20+14, 36), tag,     font=f,       fill=C["white"], anchor="lm")
    draw.text((20+tw+18, 36), program, font=font(28), fill=C["white"], anchor="lm")
    draw.text((W-30, 36), date,     font=font(22,False), fill=C["sub"], anchor="rm")
    return img


def bottom_strip(img, name, sub=""):
    draw = ImageDraw.Draw(img)
    sy, sh = H-130, 85
    crop = img.crop((0,sy,W,sy+sh)).convert("RGBA")
    ov   = Image.new("RGBA",(W,sh),(15,18,40,220))
    img.paste(Image.alpha_composite(crop,ov).convert("RGB"),(0,sy))
    draw = ImageDraw.Draw(img)
    draw.line([(0,sy),(W,sy)], fill=C["gold"], width=2)
    f  = font(30)
    nw = int(f.getlength(name)) + 36
    draw.rectangle([(40,sy+16),(40+nw,sy+sh-16)], fill=C["name_bg"])
    draw.text((40+18, sy+sh//2), name, font=f, fill=C["name_tx"], anchor="lm")
    if sub:
        draw.text((40+nw+24, sy+sh//2), sub,
                  font=font(24,False), fill=C["sub"], anchor="lm")
    draw.text((W-30, sy+sh//2), "AI STOCK BRIEFING",
              font=font(20,False), fill=(80,85,110), anchor="rm")
    return img


def divider(img, y, color=None, w=2):
    ImageDraw.Draw(img).line([(60,y),(W-60,y)], fill=color or C["gold"], width=w)
    return img


# ── 이미지 합성
def paste_img(img, path, x, y, w, h):
    try:
        ph = Image.open(path).convert("RGB")
        pr = ph.width / ph.height
        tr = w / h
        if pr > tr:
            nh, nw = h, int(h*pr)
        else:
            nw, nh = w, int(w/pr)
        ph = ph.resize((nw,nh), Image.LANCZOS)
        ph = ph.crop(((nw-w)//2,(nh-h)//2,(nw-w)//2+w,(nh-h)//2+h))
        border = Image.new("RGB",(w+4,h+4),C["gold"])
        border.paste(ph,(2,2))
        img.paste(border,(x-2,y-2))
        return True
    except:
        return False


def placeholder(img, x, y, w, h, label, sub=""):
    draw = ImageDraw.Draw(img)
    draw.rectangle([(x,y),(x+w,y+h)], fill=(22,27,55), outline=(70,80,130), width=2)
    draw.line([(x,y),(x+w,y+h)], fill=(35,40,75), width=1)
    draw.line([(x+w,y),(x,y+h)],  fill=(35,40,75), width=1)
    draw.text((x+w//2,y+h//2-16), label, font=font(26,False), fill=(90,100,150), anchor="mm")
    if sub:
        draw.text((x+w//2,y+h//2+20), sub, font=font(20,False), fill=(65,75,120), anchor="mm")


# ── 연합뉴스 크롤링 (관련도 우선)
def fetch_yonhap(keyword, save_path):
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--no-sandbox"])
            pg = br.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"))
            pg.goto(
                f"https://www.yna.co.kr/search/index?query="
                f"{requests.utils.quote(keyword)}&ctype=A&from=0&sort=rel",
                wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            src = None
            for sel in [".news-list li img",".list-type038 li img",
                        "article img",".thumb img","figure img"]:
                for el in pg.query_selector_all(sel):
                    s = el.get_attribute("src") or el.get_attribute("data-src") or ""
                    if s and not s.endswith(".gif") and "logo" not in s.lower():
                        if s.startswith("//"):
                            s = "https:" + s
                        src = s
                        break
                if src:
                    break
            br.close()
            if src:
                r = requests.get(src, timeout=15,
                                 headers={"User-Agent":"Mozilla/5.0"})
                if r.status_code == 200:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    open(save_path,"wb").write(r.content)
                    print(f"  연합뉴스 이미지: {keyword}")
                    return save_path
    except Exception as e:
        print(f"  연합뉴스 실패 ({keyword}): {e}")
    return None


# 로고 fallback
def fetch_logo(stock_name, save_path):
    url = COMPANY_LOGO.get(stock_name)
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            open(save_path,"wb").write(r.content)
            # 로고를 다크 배경 위에 올리기 위해 패딩 처리
            logo = Image.open(save_path).convert("RGBA")
            bg   = Image.new("RGB",(600,400),C["bg2"])
            lw, lh = logo.size
            ratio  = min(500/lw, 320/lh)
            logo   = logo.resize((int(lw*ratio),int(lh*ratio)), Image.LANCZOS)
            ox = (600-logo.width)//2
            oy = (400-logo.height)//2
            bg.paste(logo,(ox,oy), mask=logo.split()[3] if logo.mode=="RGBA" else None)
            bg.save(save_path)
            return save_path
    except:
        pass
    return None


def get_news_image(stock_name, img_dir):
    path = os.path.join(img_dir, f"news_{stock_name}.jpg")
    if os.path.exists(path):
        return path
    kw   = YONHAP_KW.get(stock_name, stock_name)
    result = fetch_yonhap(kw, path)
    if result:
        return result
    # fallback: 로고
    logo_path = os.path.join(img_dir, f"logo_{stock_name}.png")
    return fetch_logo(stock_name, logo_path)


# ── 네이버 차트 캡처 (차트 영역만)
def capture_chart(stock_name, save_path):
    code = STOCK_CODES.get(stock_name)
    if not code:
        return None
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--no-sandbox"])
            pg = br.new_page(viewport={"width":1200,"height":800})
            pg.goto(f"https://finance.naver.com/item/main.naver?code={code}",
                    wait_until="networkidle", timeout=25000)
            time.sleep(3)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 차트 캔버스만 캡처
            captured = False
            for sel in ["#tab_con1 > div.chart", "#chartArea", ".chart_area",
                        "#chart_area","canvas"]:
                el = pg.query_selector(sel)
                if el:
                    box = el.bounding_box()
                    if box and box["width"] > 100:
                        el.screenshot(path=save_path)
                        captured = True
                        break

            if not captured:
                # 차트 영역 좌표 직접 크롭
                pg.screenshot(path=save_path,
                              clip={"x":10,"y":250,"width":760,"height":400})
            br.close()

            # 후처리: 흰 배경을 다크 배경으로 교체
            chart = Image.open(save_path).convert("RGB")
            # 상단 광고/헤더 잘라내기 (상위 60px)
            w2, h2 = chart.size
            chart = chart.crop((0, min(60,h2//5), w2, h2))
            chart.save(save_path)
            print(f"  차트 캡처: {stock_name}")
            return save_path
    except Exception as e:
        print(f"  차트 실패 ({stock_name}): {e}")
    return None


# ════════════════════════════════════════════════════════
# 섹션 빌더
# ════════════════════════════════════════════════════════

def build_opening(sec, out_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = top_bar(img, "TODAY", C["tag_bl"])

    draw.text((W//2, 230), PROGRAM, font=font(100), fill=C["gold"], anchor="mm")
    draw.text((W//2, 345), TODAY,   font=font(38,False), fill=C["sub"], anchor="mm")
    img = divider(img, 405)

    kws = sec.get("keywords", ["코스피 회복","주도 섹터","관심 종목"])[:3]
    bw, bh, gap = 480, 100, 60
    sx = (W - (bw*3 + gap*2)) // 2
    for i, kw in enumerate(kws):
        bx = sx + i*(bw+gap)
        draw.rounded_rectangle([(bx,450),(bx+bw,550)],
                                radius=12, fill=C["bg2"], outline=C["gold"], width=2)
        draw.text((bx+bw//2, 500), kw, font=font(32), fill=C["white"], anchor="mm")

    narr = sec.get("narration","")
    line = narr[:70]
    draw.text((W//2, 640), line, font=font(30,False), fill=C["sub"], anchor="mm")

    img = bottom_strip(img, "최건일", "진행자  AI 주식 브리핑")
    path = os.path.join(out_dir, "01_opening.png")
    img.save(path)
    print(f"[완료] 오프닝")
    return path


def build_market_summary(sec, out_dir, img_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = top_bar(img, "시장 요약", C["tag_red"])

    draw.text((80,98), "오늘의 시장 요약", font=font(54), fill=C["gold"])
    img = divider(img, 168)

    kospi   = sec.get("kospi_value","6,226")
    chg     = sec.get("kospi_change","+2.21%")
    pos     = sec.get("kospi_change_positive", True)
    cc      = C["green"] if pos else C["red"]

    draw.text((80,196), "KOSPI", font=font(30,False), fill=C["sub"])
    draw.text((80,234), kospi,   font=font(100),      fill=C["white"])
    draw.text((80 + int(font(100).getlength(kospi)) + 22, 282),
              chg, font=font(52), fill=cc)

    img = divider(img, 375, color=(40,45,80), w=1)

    pts = sec.get("points",[
        "33거래일 만에 6,200선 완전 회복",
        "외국인 순매수 전환",
        "AI 반도체 방산 섹터 주도",
        "전고점 6,347 돌파 여부 관건",
    ])
    for i, pt in enumerate(pts[:4]):
        py = 395 + i*82
        draw.rectangle([(80,py+10),(92,py+52)], fill=C["gold"])
        draw.text((112, py+31), pt, font=font(34), fill=C["white"], anchor="lm")

    img_path = get_news_image("시장요약", img_dir)
    if img_path and os.path.exists(img_path):
        paste_img(img, img_path, 960, 185, 910, 710)
    else:
        placeholder(img, 960, 185, 910, 710, "뉴스 사진 영역")

    img = bottom_strip(img, "시장 요약", TODAY)
    path = os.path.join(out_dir, "02_market_summary.png")
    img.save(path); print(f"[완료] 시장요약")
    return path


def build_sector(sec, out_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = top_bar(img, "주목 섹터", (0,120,180))

    draw.text((W//2, 145), "오늘의 주목 섹터",
              font=font(64), fill=C["gold"], anchor="mm")
    img = divider(img, 208)

    sectors = sec.get("sector_list",[
        {"name":"AI 반도체 & HBM",    "desc":"TSMC 실적, 수요 폭발적 증가"},
        {"name":"피지컬AI & 로보틱스",  "desc":"현대차 보스턴다이내믹스 Atlas"},
        {"name":"원자력 & 에너지",     "desc":"SMR 대형 원전 수주 확대"},
    ])
    cw, ch, gap = 520, 520, 60
    sx = (W - (cw*3+gap*2)) // 2
    icons_txt = ["AI", "ROBOT", "NUCLEAR"]

    for i, s in enumerate(sectors[:3]):
        cx = sx + i*(cw+gap); cy = 248
        draw.rounded_rectangle([(cx,cy),(cx+cw,cy+ch)],
                                radius=16, fill=C["bg2"], outline=C["gold"], width=2)
        draw.text((cx+cw//2, cy+95),  icons_txt[i],
                  font=font(50), fill=C["gold"], anchor="mm")
        draw.text((cx+cw//2, cy+195), s["name"],
                  font=font(36), fill=C["white"], anchor="mm")
        draw.line([(cx+40,cy+242),(cx+cw-40,cy+242)], fill=C["gold"], width=1)
        for j, dl in enumerate(textwrap.wrap(s.get("desc",""),width=18)[:3]):
            draw.text((cx+cw//2, cy+292+j*52), dl,
                      font=font(28,False), fill=C["sub"], anchor="mm")

    img = bottom_strip(img, "주목 섹터", TODAY)
    path = os.path.join(out_dir, "03_sectors.png")
    img.save(path); print(f"[완료] 섹터")
    return path


def build_stock(sec, name, out_dir, img_dir, hidden=False, idx=10):
    paths = []
    prefix     = "H" if hidden else "S"
    tag_label  = "히든 종목" if hidden else "관심 종목"
    tag_color  = C["purple"] if hidden else C["tag_bl"]

    # ── 프레임 1: 종목 요약 + 뉴스사진
    img = new_frame(); draw = ImageDraw.Draw(img)
    img = top_bar(img, tag_label, tag_color)

    draw.text((80,98),  name,                     font=font(80), fill=C["gold"])
    draw.text((80,192), sec.get("summary",""),    font=font(30,False), fill=C["sub"])

    price = sec.get("price","")
    chg   = sec.get("change","")
    pos   = sec.get("change_positive","+" in chg)
    cc    = C["green"] if pos else C["red"]

    draw.text((80,248), price, font=font(88), fill=C["white"])
    if chg and price:
        ox = int(font(88).getlength(price)) + 24
        draw.text((80+ox, 296), chg, font=font(52), fill=cc)

    img = divider(img, 375)

    # 내레이션 핵심 3줄
    narr = sec.get("narration","")
    for i, ln in enumerate(textwrap.wrap(narr[:100], width=30)[:3]):
        draw.text((80, 400+i*65), ln, font=font(32,False), fill=C["white"])

    img_path = get_news_image(name, img_dir)
    if img_path and os.path.exists(img_path):
        paste_img(img, img_path, 960, 98, 910, 720)
    else:
        placeholder(img, 960, 98, 910, 720, "뉴스 사진 영역", f"{name} 관련")

    img = bottom_strip(img, name, sec.get("label",""))
    p1 = os.path.join(out_dir, f"{idx:02d}_{prefix}_{name}_1_summary.png")
    img.save(p1); paths.append(p1)
    print(f"[완료] {name} 요약")

    # ── 프레임 2: 주가 흐름 (차트만)
    img = new_frame(); draw = ImageDraw.Draw(img)
    img = top_bar(img, f"{name} 주가 흐름", tag_color)
    draw.text((80,92), f"{name}  최근 주가 흐름", font=font(54), fill=C["gold"])
    img = divider(img, 160)

    chart_path = os.path.join(img_dir, f"chart_{name}.png")
    if not os.path.exists(chart_path):
        capture_chart(name, chart_path)

    if os.path.exists(chart_path):
        paste_img(img, chart_path, 60, 180, 1800, 680)
    else:
        placeholder(img, 60, 180, 1800, 680, "주가 차트 영역", "네이버 금융")

    img = bottom_strip(img, name, "주가 흐름")
    p2 = os.path.join(out_dir, f"{idx:02d}_{prefix}_{name}_2_chart.png")
    img.save(p2); paths.append(p2)
    print(f"[완료] {name} 차트")

    # ── 프레임 3: 상승촉매 + 리스크
    img = new_frame(); draw = ImageDraw.Draw(img)
    img = top_bar(img, f"{name} 분석", tag_color)
    draw.text((80,92), f"{name}  —  촉매 & 리스크", font=font(52), fill=C["gold"])
    img = divider(img, 158)

    # 촉매 박스
    draw.rounded_rectangle([(55,175),(940,880)],
                            radius=12, fill=C["bg2"], outline=C["green"], width=2)
    draw.text((498,215), "상승 촉매",
              font=font(38), fill=C["green"], anchor="mm")
    draw.line([(75,250),(920,250)], fill=C["green"], width=1)

    for i, cat in enumerate(sec.get("catalysts",[])[:5]):
        cy2 = 272 + i*118
        draw.rectangle([(78,cy2+8),(94,cy2+54)], fill=C["green"])
        for k, cl in enumerate(textwrap.wrap(cat, width=22)[:2]):
            draw.text((108, cy2+6+k*46), cl,
                      font=font(32 if k==0 else 28, bold=(k==0)), fill=C["white"])

    # 리스크 박스
    draw.rounded_rectangle([(980,175),(1865,880)],
                            radius=12, fill=C["bg2"], outline=C["red"], width=2)
    draw.text((1423,215), "리스크",
              font=font(38), fill=C["red"], anchor="mm")
    draw.line([(1000,250),(1845,250)], fill=C["red"], width=1)

    for i, risk in enumerate(sec.get("risks",[])[:5]):
        ry = 272 + i*118
        draw.rectangle([(1003,ry+8),(1019,ry+54)], fill=C["red"])
        for k, rl in enumerate(textwrap.wrap(risk, width=22)[:2]):
            draw.text((1038, ry+6+k*46), rl,
                      font=font(32 if k==0 else 28, bold=(k==0)), fill=C["white"])

    img = bottom_strip(img, name, "촉매 & 리스크")
    p3 = os.path.join(out_dir, f"{idx:02d}_{prefix}_{name}_3_analysis.png")
    img.save(p3); paths.append(p3)
    print(f"[완료] {name} 분석")

    # ── 프레임 4+: 채널 언급 (채널별 1페이지씩)
    mentions = sec.get("mentions", [])
    for mi, m in enumerate(mentions):
        img = new_frame(); draw = ImageDraw.Draw(img)
        img = top_bar(img, f"{name} 채널 언급", tag_color)
        draw.text((80,92), f"{name}  —  채널 언급",
                  font=font(52), fill=C["gold"])
        img = divider(img, 158)

        # 채널 카드
        draw.rounded_rectangle([(55,175),(1865,870)],
                                radius=16, fill=C["bg2"], outline=C["blue"], width=2)

        # 채널명
        source = m.get("source","")
        draw.text((120, 230), source, font=font(60), fill=C["blue"])
        img = divider(img, 310, color=C["blue"], w=1)

        # 출연자/애널리스트
        reporter = m.get("reporter", m.get("analyst",""))
        report   = m.get("report","")
        if reporter:
            draw.text((120, 335), reporter, font=font(36,False), fill=C["sub"])

        # 발언/보고서 제목
        if report:
            draw.text((120, 390), "보고서 제목", font=font(28,False), fill=C["sub"])
            draw.text((120, 430), report, font=font(36), fill=C["white"])
            img = divider(img, 490, color=(40,45,80), w=1)

        # 핵심 발언 인용
        quote = m.get("quote","")
        if quote:
            draw.text((120, 390 if not report else 510),
                      "핵심 발언", font=font(28,False), fill=C["sub"])
            # 큰 따옴표 장식
            draw.text((110, 430 if not report else 545),
                      '"', font=font(120,False), fill=(40,50,90))
            for k, ql in enumerate(textwrap.wrap(quote, width=52)[:4]):
                draw.text((160, 470 if not report else 580 + k*60), ql,
                          font=font(36,False), fill=C["white"])

        img = bottom_strip(img, name, f"채널 언급  {source}")
        p4 = os.path.join(out_dir,
             f"{idx:02d}_{prefix}_{name}_4_mention_{mi+1:02d}.png")
        img.save(p4); paths.append(p4)
        print(f"[완료] {name} 채널언급 {mi+1}")

    return paths


def build_ai_strategy(sec, out_dir):
    img = new_frame(); draw = ImageDraw.Draw(img)
    img = top_bar(img, "AI 투자 전략", C["purple"])
    draw.text((W//2, 142), "AI 투자 전략",
              font=font(64), fill=C["gold"], anchor="mm")
    img = divider(img, 205)

    placeholder(img, 55, 225, 620, 700, "진행자 캐릭터", "애니메이션 영역")

    bullets = sec.get("bullet_points",[])
    for i, bp in enumerate(bullets[:6]):
        by = 238 + i*105
        draw.ellipse([(718,by+4),(776,by+62)], fill=C["gold"])
        draw.text((747, by+33), str(i+1),
                  font=font(30), fill=C["bg"], anchor="mm")
        parts = bp.split("—",1)
        if len(parts)==2:
            draw.text((790, by+8),  parts[0].strip(), font=font(36), fill=C["gold"])
            for k, sl in enumerate(textwrap.wrap(parts[1].strip(), width=44)[:2]):
                draw.text((790, by+52+k*38), sl,
                          font=font(28,False), fill=C["white"])
        else:
            for k, bl in enumerate(textwrap.wrap(bp, width=50)[:2]):
                draw.text((790, by+8+k*44), bl,
                          font=font(32 if k==0 else 26, bold=(k==0)), fill=C["white"])

    img = bottom_strip(img, "최건일", "진행자  AI 주식 브리핑")
    path = os.path.join(out_dir, "90_ai_strategy.png")
    img.save(path); print(f"[완료] AI전략")
    return path


def build_closing(sec, out_dir):
    img = new_frame(); draw = ImageDraw.Draw(img)
    img = top_bar(img, "클로징", C["tag_bl"])
    draw.text((W//2, 285), PROGRAM, font=font(88), fill=C["gold"], anchor="mm")
    draw.text((W//2, 390), TODAY,   font=font(38,False), fill=C["sub"], anchor="mm")
    img = divider(img, 455)

    disc = sec.get("disclaimer",
        "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\n"
        "투자의 최종 판단과 책임은 본인에게 있습니다.")
    for i, ln in enumerate(disc.split("\n")):
        draw.text((W//2, 495+i*60), ln,
                  font=font(28,False), fill=C["sub"], anchor="mm")

    draw.text((W//2, 705), "다음 방송에서 만나요!",
              font=font(52), fill=C["white"], anchor="mm")

    img = bottom_strip(img, "최건일", "진행자  AI 주식 브리핑")
    path = os.path.join(out_dir, "99_closing.png")
    img.save(path); print(f"[완료] 클로징")
    return path


# ════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════

def run(lang="KO"):
    print(f"\n자료 화면 제작 시작 — {lang} ({TODAY})\n")
    script_path = f"output/{lang}/scripts/script.json"
    out_dir     = f"output/{lang}/frames"
    img_dir     = f"output/{lang}/images"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    asset_map = {}
    stock_idx = 10

    for sec in script.get("sections", []):
        sid = sec.get("id","")
        if   sid == "opening":
            asset_map[sid] = build_opening(sec, out_dir)
        elif sid == "market_summary":
            asset_map[sid] = build_market_summary(sec, out_dir, img_dir)
        elif sid == "sectors":
            asset_map[sid] = build_sector(sec, out_dir)
        elif sid.startswith("stock_"):
            n = sid.replace("stock_","")
            asset_map[sid] = build_stock(sec, n, out_dir, img_dir,
                                         hidden=False, idx=stock_idx)
            stock_idx += 1
        elif sid.startswith("hidden_"):
            n = sid.replace("hidden_","")
            asset_map[sid] = build_stock(sec, n, out_dir, img_dir,
                                         hidden=True, idx=stock_idx)
            stock_idx += 1
        elif sid == "ai_strategy":
            asset_map[sid] = build_ai_strategy(sec, out_dir)
        elif sid == "closing":
            asset_map[sid] = build_closing(sec, out_dir)

    map_path = os.path.join(out_dir, "asset_map.json")
    with open(map_path,"w",encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    total = sum(len(v) if isinstance(v,list) else 1
                for v in asset_map.values())
    print(f"\n완료! 총 {total}개 프레임 저장: {out_dir}")


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else "KO")
