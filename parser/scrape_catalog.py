import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json
import time
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://cvg-rus.ru"
SITEMAP_URL = "https://cvg-rus.ru/getxml_sitemap-pages.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

EXCLUDE_PATTERNS = [
    "/basket", "/kontakty/feedback", "/files", "/prices",
    "/pravovaya-informaciya", "/politika-konfidencialnosti",
    "/politika-v-otnoshenii-cookie", "/soglasie-na-obrabotku-personalnyh-dannyh"
]

def fetch_html(url: str, timeout: int = 10) -> str:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        # print(f"[Error] {url}: {e}")
        return ""

def get_sitemap_urls() -> list:
    print("[1/4] Загрузка карты сайта (sitemap)...")
    xml_content = fetch_html(SITEMAP_URL)
    if not xml_content:
        print("[Warn] Не удалось загрузить sitemap.xml, используем прямой обход категорий")
        return []

    root = ET.fromstring(xml_content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text.strip() for loc in root.findall(".//s:loc", ns) if loc.text]
    
    filtered = []
    for u in urls:
        if any(exc in u for exc in EXCLUDE_PATTERNS):
            continue
        filtered.append(u)
    
    print(f"Найдено целевых URL в карте сайта: {len(filtered)}")
    return filtered

def parse_page(url: str):
    html = fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Извлечение заголовка
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        # Если нет H1, пробуем title страницы
        t_tag = soup.find("title")
        title = t_tag.get_text(" ", strip=True) if t_tag else ""
    if not title:
        return None

    # Очистка и извлечение контента
    content_side = soup.select_one("#contentSide") or soup.select_one(".content")
    if not content_side:
        return None

    for s in content_side(["script", "style", "nav", "noscript"]):
        s.decompose()

    text_content = content_side.get_text(" ", strip=True)
    text_content = re.sub(r"\s+", " ", text_content)

    if len(text_content) < 60:
        return None

    # Категория
    breadcrumbs = [b.get_text(strip=True) for b in soup.select("#pagesPathList a, .breadcrumbs a")]
    if len(breadcrumbs) > 1:
        category = " > ".join(breadcrumbs[1:])
    elif "/standart" in url:
        category = "Типовые решения"
    elif "/kontakty" in url or "/informatia" in url or "/dogovor" in url:
        category = "Контакты, доставка и сервис"
    else:
        category = "Каталог CVGaudio"

    return {
        "title": title,
        "category": category,
        "url": url,
        "content": text_content[:3500]  # Берем развернутое описание, артикулы и параметры
    }

def scrape():
    urls = get_sitemap_urls()
    if not urls:
        urls = [
            "https://cvg-rus.ru/kontakty",
            "https://cvg-rus.ru/informatia",
            "https://cvg-rus.ru/standart",
            "https://cvg-rus.ru/catalog/usiliteli",
            "https://cvg-rus.ru/catalog/gromkogovoriteli",
            "https://cvg-rus.ru/catalog/sabvufery"
        ]

    print(f"[2/4] Параллельный сбор страниц (потоков: 8, страниц: {len(urls)})...")
    knowledge_base = []
    visited_urls = set()

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(parse_page, u): u for u in urls if u not in visited_urls}
        done_count = 0
        total_urls = len(future_to_url)

        for future in as_completed(future_to_url):
            u = future_to_url[future]
            done_count += 1
            if done_count % 30 == 0 or done_count == total_urls:
                print(f"  Обработано: {done_count}/{total_urls} страниц...")
            try:
                item = future.result()
                if item and item.get("title") and len(item.get("content", "")) >= 60:
                    knowledge_base.append(item)
            except Exception as e:
                pass

    print(f"[3/4] Успешно спарсено {len(knowledge_base)} страниц.")

    # Добавляем инженерные экспертные блоки (критично для саун, бань, хаммамов, пожарных систем)
    knowledge_base.append({
        "title": "Инженерные стандарты: Озвучивание бань, саун, хаммамов и мокрых зон",
        "category": "Инженерные рекомендации и стандарты монтажа",
        "url": "https://cvg-rus.ru/standart",
        "content": (
            "ПРАВИЛА ОЗВУЧИВАНИЯ БАНЬ, САУН И СПА-ЗОН:\n"
            "1. ВНИМАНИЕ: В парные и финские сауны (с температурами от +75°C до +110°C и горячим паром) "
            "стандартные пластиковые громкоговорители монтировать ЗАПРЕЩЕНО, так как корпус и диффузор деформируются от температуры. "
            "Для парных требуется спецзаказ термостойких моделей с керамическими или металлическими термодиффузорами через инженера ЮНИТРЕКС.\n"
            "2. В комнаты отдыха, предбанники, раздевалки, массажные кабинеты и холлы бань/саун "
            "устанавливаются настенные влагозащищенные громкоговорители серий RF (RF416TW, RF516TW, RF616TW) и ODF, "
            "либо потолочные динамики серии CRX / CR с влагостойкой полипропиленовой мембраной.\n"
            "3. Для помывочных, душевых и бассейнов (высокая влажность, брызги воды) применяются акустические системы со степенью защиты IP54/IP65.\n"
            "4. Усилители мощности (серии M, TR, Rebox) и медиаплееры всегда устанавливаются в сухих проветриваемых помещениях (ресепшн, комната персонала, серверная)."
        )
    })

    knowledge_base.append({
        "title": "Доставка, оплата, гарантия и самовывоз ЮНИТРЕКС (CVGaudio)",
        "category": "Контакты, доставка и сервис",
        "url": "https://cvg-rus.ru/informatia",
        "content": (
            "Условия работы компании ООО 'ЮНИТРЕКС' (дилер CVGaudio):\n"
            "1. Оплата: безналичный расчет для юридических лиц и ИП с НДС 20%, оплата по счету.\n"
            "2. Доставка: по всей России и странам ЕАЭС транспортными компаниями (Деловые Линии, СДЭК, ПЭК, Возовоз).\n"
            "3. Самовывоз со склада в Москве: Остаповский проезд, д. 5, стр. 17, оф. 202 (БЦ Контакт). Время работы: Пн-Пт 9:00 - 18:00.\n"
            "4. Филиалы со складами: Санкт-Петербург, Нижний Новгород, Екатеринбург, Новосибирск.\n"
            "5. Официальная гарантия производителя: от 12 до 24 месяцев на все трансляционное оборудование."
        )
    })

    knowledge_base.append({
        "title": "Контакты и проектный отдел ЮНИТРЕКС",
        "category": "Контакты, доставка и сервис",
        "url": "https://cvg-rus.ru/kontakty",
        "content": (
            "Контакты официального дилера CVGaudio в РФ:\n"
            "Центральный офис: 109316, г. Москва, Остаповский проезд 5, стр. 17, офис 202.\n"
            "Телефон единый: +7 (495) 134-29-44\n"
            "E-mail для заказов и ТЗ: info@cvg-rus.ru, info@unitrex.ru\n"
            "Проектный отдел: бесплатный расчет акустических систем, подбор оборудования по планировкам (AutoCAD, PDF), выезд инженера."
        )
    })

    # Сохраняем в файл
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "knowledge_base.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    print(f"\n[4/4] ГОТОВО! Сохранено {len(knowledge_base)} объектов в {out_file}!")

if __name__ == "__main__":
    scrape()
