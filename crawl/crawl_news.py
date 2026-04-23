import asyncio
from playwright.async_api import async_playwright
import pdfplumber
import io
import requests
async def crawl_cafef(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0...")
        page = await context.new_page()
        
        await page.goto(url)
        
        # 1. Lấy danh sách bài viết
        links = await page.query_selector_all(".docnhanhTitle")
        max_articles = 20
        links = links[:max_articles] # Selector ví dụ của Cafef
        
        for link in links:
            href = await link.get_attribute("href")
            full_url = f"https://cafef.vn{href}" if href.startswith("/") else href
            
            # Chuyển hướng sang trang chi tiết
            detail_page = await browser.new_page()
            await detail_page.goto(full_url, wait_until="domcontentloaded")
            
            # 2. Kiểm tra nếu là trang chứa PDF (Thường có class hoặc text đặc trưng)
            pdf_link_element = await detail_page.query_selector("a[href$='.pdf']")
            
            if pdf_link_element:
                pdf_url = await pdf_link_element.get_attribute("href")
                # Xử lý PDF
                content = extract_pdf_content(pdf_url)
                print(f"PDF Content from {pdf_url[:50]}...")
            else:
                # Xử lý Text thường
                paragraphs = await detail_page.query_selector_all("p[dir='ltr']")
                texts = []

                for p in paragraphs:
                    text = await p.inner_text()
                    if text.strip():
                        texts.append(text.strip())

                content = "\n".join(texts)
                print(f"Text Content: {content[:100]}...")
            
            await detail_page.close()
        await browser.close()
def extract_pdf_content(pdf_url):
    response = requests.get(pdf_url)
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
async def main():
    ticker = 'fpt'
    url = f"https://cafef.vn/du-lieu/tin-doanh-nghiep/{ticker}/event.chn#tat-ca"
    await crawl_cafef(url)

if __name__ == "__main__":
    asyncio.run(main())