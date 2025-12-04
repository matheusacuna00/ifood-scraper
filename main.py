import os
import json
import asyncio
import sys

print("=== Starting application ===", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"PORT env: {os.environ.get('PORT', 'not set')}", flush=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

print("FastAPI imported successfully", flush=True)

from playwright.async_api import async_playwright

print("Playwright imported successfully", flush=True)
import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIES_FILE = "ifood_cookies.json"

class ScrapeRequest(BaseModel):
    url: str

class LoginRequest(BaseModel):
    email: str
    password: str

def load_cookies():
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r") as f:
            return json.load(f)
    return None

def save_cookies(cookies):
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)

@app.get("/health")
async def health():
    return {"status": "ok", "has_session": os.path.exists(COOKIES_FILE)}

@app.post("/login")
async def login(req: LoginRequest):
    """Faz login no iFood e salva os cookies da sessão"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto("https://www.ifood.com.br")
            await page.wait_for_timeout(3000)
            
            # Clica em "Entrar"
            await page.click('text=Entrar')
            await page.wait_for_timeout(2000)
            
            # Preenche email
            await page.fill('input[type="email"]', req.email)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(2000)
            
            # Preenche senha
            await page.fill('input[type="password"]', req.password)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(5000)
            
            # Salva cookies
            cookies = await context.cookies()
            save_cookies(cookies)
            
            await browser.close()
            return {"success": True, "message": "Login realizado e sessão salva!"}
            
        except Exception as e:
            await browser.close()
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    """Faz scraping de uma página do iFood usando sessão autenticada"""
    cookies = load_cookies()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        if cookies:
            await context.add_cookies(cookies)
        
        page = await context.new_page()
        
        try:
            await page.goto(req.url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
            
            # Extrai dados da loja
            data = await page.evaluate('''() => {
                const getText = (sel) => document.querySelector(sel)?.textContent?.trim() || null;
                const getAll = (sel) => [...document.querySelectorAll(sel)].map(e => e.textContent?.trim());
                
                // Nome da loja
                const name = getText('h1') || getText('[class*="merchant-name"]') || getText('[data-test-id="merchant-name"]');
                
                // Rating
                const ratingEl = document.querySelector('[class*="rating"]') || document.querySelector('[data-test-id="merchant-rating"]');
                const rating = ratingEl?.textContent?.match(/[\\d,\\.]+/)?.[0];
                
                // Número de avaliações
                const reviewsText = document.body.innerText.match(/(\\d+(?:\\.\\d+)?(?:k|mil)?)[\\s]*(?:avalia|opini)/i);
                const reviews = reviewsText ? reviewsText[1] : null;
                
                // Tempo de entrega
                const deliveryTime = document.body.innerText.match(/(\\d+)[-–](\\d+)\\s*min/);
                
                // Taxa de entrega
                const feeMatch = document.body.innerText.match(/(?:entrega|taxa)[:\\s]*R\\$\\s*([\\d,]+)/i);
                
                // Produtos/Menu
                const products = [];
                document.querySelectorAll('[class*="dish-card"], [class*="product-card"], [data-test-id*="product"]').forEach(el => {
                    const name = el.querySelector('h3, [class*="name"]')?.textContent?.trim();
                    const price = el.querySelector('[class*="price"]')?.textContent?.match(/[\\d,]+/)?.[0];
                    const desc = el.querySelector('p, [class*="description"]')?.textContent?.trim();
                    if (name) products.push({ name, price: price ? parseFloat(price.replace(',', '.')) : null, description: desc || '' });
                });
                
                // Reviews recentes
                const reviews_list = [];
                document.querySelectorAll('[class*="review"], [class*="comment"]').forEach(el => {
                    const text = el.querySelector('p, [class*="text"]')?.textContent?.trim();
                    const author = el.querySelector('[class*="author"], [class*="name"]')?.textContent?.trim();
                    const rating = el.querySelector('[class*="rating"]')?.textContent?.match(/[\\d]/)?.[0];
                    if (text) reviews_list.push({ author: author || 'Anônimo', text, rating: rating ? parseInt(rating) : null });
                });
                
                return {
                    name,
                    rating: rating ? parseFloat(rating.replace(',', '.')) : null,
                    reviewCount: reviews,
                    deliveryTime: deliveryTime ? `${deliveryTime[1]}-${deliveryTime[2]} min` : null,
                    deliveryFee: feeMatch ? parseFloat(feeMatch[1].replace(',', '.')) : null,
                    products: products.slice(0, 50),
                    reviews: reviews_list.slice(0, 10),
                    scrapedAt: new Date().toISOString()
                };
            }''')
            
            # Atualiza cookies após navegação
            new_cookies = await context.cookies()
            save_cookies(new_cookies)
            
            await browser.close()
            return {"success": True, "data": data}
            
        except Exception as e:
            await browser.close()
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
