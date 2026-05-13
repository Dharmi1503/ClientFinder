import asyncio
from app.scrapers.peopleperhour import scrape_peopleperhour

# Test 1: Web Development
result = asyncio.run(scrape_peopleperhour('web development', 'Surat'))
print('Test 1: Web Development + Surat')
print('Total:', len(result))
print()

# Test 2: Graphic Design
result = asyncio.run(scrape_peopleperhour('graphic design', 'Mumbai'))
print('Test 2: Graphic Design + Mumbai')
print('Total:', len(result))
for i, l in enumerate(result[:3], 1):
    print(f'{i}. {l.get("post_title", "?")[:50]}')
    print(f'   Budget: {l.get("budget", "?")[:30]}')
print()

# Test 3: Digital Marketing
result = asyncio.run(scrape_peopleperhour('digital marketing', 'Bangalore'))
print('Test 3: Digital Marketing + Bangalore')
print('Total:', len(result))
for i, l in enumerate(result[:3], 1):
    print(f'{i}. {l.get("post_title", "?")[:50]}')
