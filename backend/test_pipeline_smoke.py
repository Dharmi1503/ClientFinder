import asyncio
from app.pipeline import run_intent_pipeline

result = asyncio.run(run_intent_pipeline('web development', 'Surat', 'technology', '10k-50k', 10, False))
print('Pipeline Results:')
print('HOT:', result.get('hot', 0))
print('WARM:', result.get('warm', 0))
print('COLD:', result.get('cold', 0))
print('Total saved:', result.get('total_saved', 0))
print()
print('Sample leads:')
leads = result.get('leads', [])
for i, l in enumerate(leads[:3], 1):
    name = l.get('company_name', '?')[:40]
    source = l.get('source', '?')
    label = l.get('label', '?')
    print(f'{i}. {name} | Source: {source} | Label: {label}')
