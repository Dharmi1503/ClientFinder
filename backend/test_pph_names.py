import asyncio
from app.scrapers.peopleperhour import scrape_peopleperhour

result = asyncio.run(scrape_peopleperhour('web development', 'Surat'))
print('Web Development + Surat:')
print('Total leads:', len(result))
print()
for i, l in enumerate(result[:5], 1):
    name = l.get('company_name', 'N/A')
    title = l.get('post_title', 'N/A')[:45]
    budget = l.get('budget', 'N/A')
    print(f'{i}. Company: {name}')
    print(f'   Title: {title}...')
    print(f'   Budget: {budget}')
    print()
