import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import json
import time
import os
import re

BASE_URL = "https://cvg-rus.ru"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

CATEGORIES = [
    "/catalog/usiliteli",
    "/catalog/gromkogovoriteli",
    "/catalog/sabvufery",
    "/catalog/komplekty",
    "/catalog/predusiliteli",
    "/catalog/attenyuatory",
    "/catalog/avtomatizaciya",
    "/catalog/mikrofony",
    "/catalog/mediapleery",
    "/catalog/kommutaciya",
    "/standart"
]

def fetch_html(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[Error] Failed to fetch {url}: {e}")
        return ""

def scrape():
    knowledge_base = []
    visited_urls = set()
    product_urls = set()

    print("[1/3] Поиск товаров по категориям...")
    for cat in CATEGORIES:
        cat_url = urllib.parse.urljoin(BASE_URL, cat)
        html = fetch_html(cat_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        
        # Собираем ссылки на подкатегории и товары
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0].rstrip("/")
            if href.startswith("/catalog/") and href.count("/") >= 3:
                full_url = urllib.parse.urljoin(BASE_URL, href)
                product_urls.add(full_url)
            elif href.startswith("/standart/") and href != "/standart":
                full_url = urllib.parse.urljoin(BASE_URL, href)
                product_urls.add(full_url)

    print(f"Найдено ссылок на товары/решения: {len(product_urls)}")

    # Ограничим для быстрого старта (например, первые 35-50 ключевых позиций)
    sample_urls = list(product_urls)[:45]
    print(f"[2/3] Извлечение детальных описаний и характеристик ({len(sample_urls)} позиций)...")

    for i, p_url in enumerate(sample_urls):
        if p_url in visited_urls:
            continue
        visited_urls.add(p_url)

        html = fetch_html(p_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Заголовок
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title:
            continue

        # Описание и характеристики
        content_side = soup.select_one("#contentSide")
        text_content = ""
        if content_side:
            # Убираем скрипты и стили
            for s in content_side(["script", "style", "nav"]):
                s.decompose()
            text_content = content_side.get_text(" ", strip=True)
            # Очищаем лишние пробелы
            text_content = re.sub(r"\s+", " ", text_content)

        # Категория из хлебных крошек
        breadcrumbs = [b.get_text(strip=True) for b in soup.select("#pagesPathList a, .breadcrumbs a")]
        category = " > ".join(breadcrumbs[1:]) if len(breadcrumbs) > 1 else "Каталог CVGaudio"

        knowledge_base.append({
            "title": title,
            "category": category,
            "url": p_url,
            "content": text_content[:2500] # Берем основную выжимку
        })
        print(f"[{i+1}/{len(sample_urls)}] Добавлен: {title[:40]}...")
        time.sleep(0.3)

    # Добавляем общие данные о компании и контактах
    knowledge_base.append({
        "title": "О компании ООО ЮНИТРЕКС (CVGaudio)",
        "category": "Контакты и доставка",
        "url": "https://cvg-rus.ru/kontakty",
        "content": (
            "ООО 'ЮНИТРЕКС' — официальный дилер оборудования CVGaudio в РФ. "
            "Центральный офис и склад в Москве: Остаповский проезд, д. 5, стр. 17, оф. 202 (БЦ Контакт). Тел: +7 (495) 134-29-44, E-mail: info@cvg-rus.ru. "
            "Филиалы и склады: Санкт-Петербург (+7 812 213-07-12), Нижний Новгород (+7 831 231-30-71), "
            "Екатеринбург (+7 343 226-08-71), Новосибирск (+7 383 207-80-53). "
            "Условия работы: продажа оптом и в розницу, работа с НДС по безналичному расчету, официальная гарантия производителя, "
            "техническая поддержка, проектные расчеты и пусконаладка."
        )
    })

    knowledge_base.append({
        "title": "Типовые решения: Фоновый звук для ресторанов, кафе и магазинов",
        "category": "Типовые решения",
        "url": "https://cvg-rus.ru/standart",
        "content": (
            "Комплекты звукового оборудования CVGaudio проектируются под ключ: "
            "1. Кафе до 50 кв.м: 4 потолочных динамика CRX серии или настенных ODF + трансляционный микшер-усилитель 60 Вт со встроенным Bluetooth/USB. "
            "2. Ресторан с верандой: 6-8 потолочных громкоговорителей в зал + 2 всепогодных IP54/IP65 на веранду + двухзонный усилитель M-серии для независимой громкости. "
            "3. Магазины и торговые залы: 100V трансляционная линия, равномерная расстановка колонок с шагом 4-6 метров, подключение микрофонной консоли MD для голосовых объявлений."
        )
    })

    # Сохраняем результат
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "knowledge_base.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    print(f"\n[3/3] Успешно сохранено {len(knowledge_base)} записей в {out_file}!")

if __name__ == "__main__":
    scrape()
