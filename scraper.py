"""
RTW Daily — 자동 신상품 크롤러
실행: python scraper.py
매일 자동 실행: GitHub Actions (schedule) 으로 설정
"""

import os, json, time, hashlib, re
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from supabase import create_client

# ── Supabase 연결 (환경변수에서 읽기)
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────
# 브랜드별 크롤러 함수
# 각 함수는 list of dict 반환:
#   { id, brand_id, title, price, image_url, product_url, fabric, tags }
# ─────────────────────────────────────────

def scrape_gap():
    url = "https://www.gap.com/browse/category.do?cid=8792&seo=8792_Women_New_Arrivals"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("article.product-card")[:20]
        for card in cards:
            name_el = card.select_one(".product-name")
            price_el = card.select_one(".price-current")
            img_el   = card.select_one("img.product-image")
            link_el  = card.select_one("a.product-card-link")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el["src"] if img_el and img_el.get("src") else ""
            link  = "https://www.gap.com" + link_el["href"] if link_el else url
            items.append(make_item("gap", title, price, image, link, ["데님","캐주얼"]))
    except Exception as e:
        print(f"[Gap] 오류: {e}")
    return items


def scrape_jcrew():
    url = "https://www.jcrew.com/womens-clothing/new-arrivals"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".product-tile")[:20]
        for card in cards:
            name_el  = card.select_one(".product-name")
            price_el = card.select_one(".price")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src","") if img_el else ""
            link  = "https://www.jcrew.com" + link_el["href"] if link_el else url
            items.append(make_item("jcrew", title, price, image, link, ["프리미엄","클래식"]))
    except Exception as e:
        print(f"[J.Crew] 오류: {e}")
    return items


def scrape_target():
    # Target은 공개 API 제공
    url = (
        "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
        "?key=9f36aeafbe60771e321a7cc95a78140772ab3e96"
        "&category=5xtg6&count=20&offset=0&platform=desktop"
        "&pricing_store_id=3991&scheduled_delivery_store_id=3991"
        "&store_id=3991&useragent=Mozilla"
        "&visitor_id=RTW_DAILY_TRACKER"
    )
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        products = data.get("data", {}).get("search", {}).get("products", [])
        for p in products[:20]:
            item_data = p.get("item", {})
            title = item_data.get("product_description", {}).get("title", "")
            price = "$" + str(item_data.get("price", {}).get("current_retail", ""))
            image_url = ""
            images = item_data.get("enrichment", {}).get("images", {})
            if images.get("primary_image_url"):
                image_url = images["primary_image_url"]
            tcin = item_data.get("tcin", "")
            link = f"https://www.target.com/p/-/A-{tcin}" if tcin else "https://www.target.com"
            if title:
                items.append(make_item("target", title, price, image_url, link, ["매스마켓","베이직"]))
    except Exception as e:
        print(f"[Target] 오류: {e}")
    return items


def scrape_freepeople():
    url = "https://www.freepeople.com/new-arrivals/"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("[class*='ProductCard']")[:20]
        for card in cards:
            name_el  = card.select_one("[class*='ProductName'], [class*='product-name']")
            price_el = card.select_one("[class*='Price'], [class*='price']")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src", img_el.get("data-src","")) if img_el else ""
            link  = "https://www.freepeople.com" + link_el["href"] if link_el and link_el.get("href","").startswith("/") else url
            items.append(make_item("freepeople", title, price, image, link, ["보헤미안","플로럴"]))
    except Exception as e:
        print(f"[Free People] 오류: {e}")
    return items


def scrape_alo():
    url = "https://www.aloyoga.com/collections/new-arrivals-women"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".product-item, [class*='product-card']")[:20]
        for card in cards:
            name_el  = card.select_one(".product-item__title, [class*='ProductName']")
            price_el = card.select_one(".price, [class*='Price']")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src", img_el.get("data-srcset","").split()[0]) if img_el else ""
            link  = "https://www.aloyoga.com" + link_el["href"] if link_el and link_el.get("href","").startswith("/") else url
            items.append(make_item("alo", title, price, image, link, ["액티브","요가"]))
    except Exception as e:
        print(f"[Alo Yoga] 오류: {e}")
    return items


def scrape_skims():
    url = "https://www.skims.com/collections/new"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("[class*='product']")[:20]
        for card in cards:
            name_el  = card.select_one("[class*='title'], [class*='name']")
            price_el = card.select_one("[class*='price']")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            if not title or len(title) < 3: continue
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src","") if img_el else ""
            link  = "https://www.skims.com" + link_el["href"] if link_el and link_el.get("href","").startswith("/") else url
            items.append(make_item("skims", title, price, image, link, ["이너웨어","쉐입웨어"]))
    except Exception as e:
        print(f"[Skims] 오류: {e}")
    return items


def scrape_walmart():
    # Walmart 검색 API
    url = "https://www.walmart.com/search?q=women+new+arrivals+clothing&sort=new"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        # Walmart은 JSON-LD 데이터 파싱
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data[:20]:
                        if item.get("@type") == "Product":
                            title = item.get("name","")
                            price = str(item.get("offers",{}).get("price",""))
                            image = item.get("image","")
                            link  = item.get("url","https://www.walmart.com")
                            if title:
                                items.append(make_item("walmart", title, "$"+price if price else "", image, link, ["매스마켓","베이직"]))
            except: pass
    except Exception as e:
        print(f"[Walmart] 오류: {e}")
    return items


def scrape_aeo():
    url = "https://www.ae.com/us/en/c/new-arrivals/womens/cat4840011"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".product-card, [class*='product']")[:20]
        for card in cards:
            name_el  = card.select_one("[class*='name'], [class*='title']")
            price_el = card.select_one("[class*='price']")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            if not title or len(title) < 3: continue
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src","") if img_el else ""
            link  = "https://www.ae.com" + link_el["href"] if link_el and link_el.get("href","").startswith("/") else url
            items.append(make_item("aeo", title, price, image, link, ["캐주얼","데님"]))
    except Exception as e:
        print(f"[AEO] 오류: {e}")
    return items


def scrape_carhartt():
    url = "https://www.carhartt.com/catalog/category/view/id/new_arrivals"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".product-tile, .product-item")[:20]
        for card in cards:
            name_el  = card.select_one(".product-name, .product-title")
            price_el = card.select_one(".price")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src","") if img_el else ""
            link  = link_el["href"] if link_el else url
            items.append(make_item("carhartt", title, price, image, link, ["워크웨어","내구성"]))
    except Exception as e:
        print(f"[Carhartt] 오류: {e}")
    return items


def scrape_costco():
    url = "https://www.costco.com/women-s-clothing.html"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".product")[:20]
        for card in cards:
            name_el  = card.select_one(".description a")
            price_el = card.select_one(".price")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src","") if img_el else ""
            link  = "https://www.costco.com" + link_el["href"] if link_el and link_el.get("href","").startswith("/") else url
            items.append(make_item("costco", title, price, image, link, ["매스마켓","가성비"]))
    except Exception as e:
        print(f"[Costco] 오류: {e}")
    return items


def scrape_wellmade():
    url = "https://www.wellmade.co.kr/category/new/44/"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".prdList li, .goods-item")[:20]
        for card in cards:
            name_el  = card.select_one(".name, .goods-name")
            price_el = card.select_one(".price, .goods-price")
            img_el   = card.select_one("img")
            link_el  = card.select_one("a")
            if not name_el: continue
            title = name_el.get_text(strip=True)
            price = price_el.get_text(strip=True) if price_el else ""
            image = img_el.get("src","") if img_el else ""
            if image.startswith("//"): image = "https:" + image
            link  = link_el["href"] if link_el else url
            if link.startswith("/"): link = "https://www.wellmade.co.kr" + link
            items.append(make_item("wellmade", title, price, image, link, ["프리미엄","린넨"]))
    except Exception as e:
        print(f"[Wellmade] 오류: {e}")
    return items


# ─────────────────────────────────────────
# 헬퍼: 상품 dict 만들기 + 중복 방지용 ID
# ─────────────────────────────────────────
def make_item(brand_id, title, price, image_url, product_url, tags):
    unique_str = f"{brand_id}:{title}:{product_url}"
    item_id = hashlib.md5(unique_str.encode()).hexdigest()
    return {
        "id":          item_id,
        "brand_id":    brand_id,
        "title":       title.strip(),
        "price":       price.strip(),
        "image_url":   image_url,
        "product_url": product_url,
        "tags":        tags,
        "fabric":      "",          # 상세 페이지 크롤링 시 채워짐
        "scraped_at":  datetime.now(timezone.utc).isoformat(),
        "likes":       0,
        "comments":    0,
    }


# ─────────────────────────────────────────
# DB 저장 (이미 있는 상품은 건너뜀)
# ─────────────────────────────────────────
def save_to_db(items: list[dict]):
    if not items:
        return 0
    saved = 0
    for item in items:
        try:
            # id 기준으로 upsert — 같은 상품 중복 저장 안 됨
            supabase.table("products").upsert(item, on_conflict="id").execute()
            saved += 1
        except Exception as e:
            print(f"  DB 저장 오류 ({item.get('title','?')}): {e}")
    return saved


# ─────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────
SCRAPERS = [
    ("J.Crew",       scrape_jcrew),
    ("Gap",          scrape_gap),
    ("Wellmade",     scrape_wellmade),
    ("Alo Yoga",     scrape_alo),
    ("Skims",        scrape_skims),
    ("Target",       scrape_target),
    ("Carhartt",     scrape_carhartt),
    ("Walmart",      scrape_walmart),
    ("Costco",       scrape_costco),
    ("AEO",          scrape_aeo),
    ("Free People",  scrape_freepeople),
]

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f" RTW Daily 크롤러 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    total = 0
    for name, fn in SCRAPERS:
        print(f"▶ {name} 크롤링 중...")
        items = fn()
        saved = save_to_db(items)
        print(f"  → {len(items)}개 수집, {saved}개 저장\n")
        total += saved
        time.sleep(2)  # 브랜드 사이트 부담 줄이기

    print(f"{'='*50}")
    print(f" 완료! 총 {total}개 신상품 저장됨")
    print(f"{'='*50}\n")
