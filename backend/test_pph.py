import asyncio
from app.scrapers.peopleperhour import scrape_peopleperhour

result = asyncio.run(scrape_peopleperhour('web development', 'Surat'))
print('Count:', len(result))
print()
for l in result[:5]:
    name = l.get('company_name', '?')[:40]
    url = l.get('platform_url', '?')[:60]
    budget = l.get('budget', '')
    print(f'  {name} | Budget: {budget} | {url}')
