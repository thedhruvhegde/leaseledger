import sys, zipfile, csv, io
for p in sys.argv[1:]:
    z = zipfile.ZipFile(p)
    print("==", p)
    for i in z.infolist(): print(f"  {i.filename} {i.file_size}")
    def rows(n):
        if n not in z.namelist(): return []
        return list(csv.DictReader(io.TextIOWrapper(z.open(n), encoding='utf-8-sig')))
    print("  agency:", [(a.get('agency_name'), a.get('agency_id')) for a in rows('agency.txt')])
    r = rows('routes.txt'); print("  routes:", len(r), sorted(x.get('route_short_name') or x.get('route_long_name') for x in r))
    print("  stops:", len(rows('stops.txt')), " trips:", len(rows('trips.txt')))
    c = rows('calendar.txt')
    if c: print("  calendar:", min(x['start_date'] for x in c), max(x['end_date'] for x in c), len(c), "service_ids")
    cd = rows('calendar_dates.txt')
    if cd: print("  calendar_dates:", min(x['date'] for x in cd), max(x['date'] for x in cd), len(cd))
    fi = rows('feed_info.txt'); print("  feed_info:", fi)
