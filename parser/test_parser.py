import urllib.request
from bs4 import BeautifulSoup
import json
import re

url = "https://cvg-rus.ru/catalog/usiliteli"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        
        # Check subcategories or products
        subcategories = []
        for a in soup.select("#catalogSectImageList .item a, .catalogSubSect a"):
            subcategories.append((a.get_text(strip=True), a.get("href")))
        
        # Check products in catalog list
        products = []
        for item in soup.select(".catalogList .item, .catalogItem, .prodItem, .catalogTable tr"):
            products.append(item.get_text(" ", strip=True)[:100])
            
        print("Subcategories found:", len(subcategories))
        for name, href in subcategories[:5]:
            print(f"  {name}: {href}")
            
        print("Products found directly:", len(products))
        if not products:
            # Let's inspect links with /catalog/usiliteli/...
            product_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/catalog/usiliteli/" in href and href != "/catalog/usiliteli":
                    product_links.append((a.get_text(strip=True), href))
            print("Found category links inside usiliteli:", len(product_links))
            for name, href in product_links[:10]:
                print(f"    {name} -> {href}")
except Exception as e:
    print("Error:", e)
