import pyarrow.parquet as pq, networkx as nx, shapely, math, sys, time
t0=time.time()
seg=pq.read_table(sys.argv[1], columns=['id','class','subtype','connectors','geometry']).to_pylist()
con={r['id']:None for r in []}
WALK={'footway','path','steps','residential','service','tertiary','secondary','primary','unclassified','living_street','pedestrian','cycleway','track','unknown'}
G=nx.Graph()
def hav(a,b):
    R=6371000; la1,lo1,la2,lo2=map(math.radians,(a[1],a[0],b[1],b[0]))
    return 2*R*math.asin(math.sqrt(math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2))
coords={}
for r in seg:
    if r['subtype']!='road' or r['class'] not in WALK: continue
    g=shapely.from_wkb(r['geometry']); pts=list(g.coords)
    cs=sorted(r['connectors'] or [], key=lambda c:c['at'])
    # cumulative length
    cum=[0]
    for i in range(1,len(pts)): cum.append(cum[-1]+hav(pts[i-1],pts[i]))
    L=cum[-1]
    for a,b in zip(cs,cs[1:]):
        G.add_edge(a['connector_id'],b['connector_id'],w=(b['at']-a['at'])*L)
    for c in cs:
        d=c['at']*L; i=min(range(len(cum)),key=lambda k:abs(cum[k]-d)); coords[c['connector_id']]=pts[i]
print('nodes',G.number_of_nodes(),'edges',G.number_of_edges(),'components',nx.number_connected_components(G), round(time.time()-t0),'s')
def near(lon,lat): return min(coords,key=lambda k:(coords[k][0]-lon)**2+(coords[k][1]-lat)**2)
# Shapiro Library -> Bob and Betty Beyster Building
a=near(-83.73727,42.27573); b=near(-83.71638,42.29301)
d=nx.shortest_path_length(G,a,b,weight='w'); print('Shapiro->Beyster walk m', round(d), 'min @1.34m/s', round(d/1.34/60,1), 'straight m', round(hav((-83.73727,42.27573),(-83.71638,42.29301))))
