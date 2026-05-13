import asyncio
from app.scrapers.guru import scrape_guru

result = asyncio.run(scrape_guru('web development', 'Surat'))
print('Count:', len(result))
for l in result[:5]:
    name = l.get('company_name', '?')[:40]
    url = l.get('platform_url', '?')[:60]
    print(f'  {name} | {url}')
