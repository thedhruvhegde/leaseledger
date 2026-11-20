import pyarrow.parquet as pq, pyarrow.compute as pc, collections, sys, re
s=pq.read_table(sys.argv[1]).to_pylist()
print(collections.Counter((r['subtype'],r['class']) for r in s).most_common(25))
p=pq.read_table(sys.argv[2]).to_pylist()
pat=re.compile(r'duderstadt|shapiro|hatcher|beyster|bob and betty|ross school|michigan union|ccrb|recreational sports|intramural|university hospital|michigan medicine|north campus recreation|chemistry building|mason hall|angell hall|pierpont|michigan stadium|crisler|central campus transit',re.I)
for r in p:
    n=(r['names'] or {}).get('primary') or ''
    if pat.search(n):
        g=r['geometry']; print(n,'|',(r.get('basic_category')),'|',r['bbox']['xmin'],r['bbox']['ymin'],'|conf',round(r['confidence'],2))
cats=collections.Counter(r.get('basic_category') for r in p); print([c for c in cats.most_common() if c[0] and ('apart' in c[0] or 'hous' in c[0] or 'resid' in c[0])])
