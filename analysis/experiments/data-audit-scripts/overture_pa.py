import pyarrow.dataset as ds, pyarrow.fs as fs, pyarrow.compute as pc, pyarrow.parquet as pq, sys, time, os
out=sys.argv[1]; typ=sys.argv[2]; th=sys.argv[3] if len(sys.argv)>3 else 'transportation'; rel='2026-11-18.0'
s3=fs.S3FileSystem(anonymous=True, region='us-west-2', proxy_options=os.environ.get('HTTPS_PROXY'))
t0=time.time()
d=ds.dataset(f'overturemaps-us-west-2/release/{rel}/theme={th}/type={typ}/', filesystem=s3, format='parquet')
print('files', len(d.files), round(time.time()-t0)); 
F=lambda k: pc.field(('bbox',k))
f=(F('xmin')>-83.80)&(F('xmax')<-83.67)&(F('ymin')>42.22)&(F('ymax')<42.33)
t=d.to_table(filter=f)
pq.write_table(t, f'{out}/{typ}.parquet'); print(typ, t.num_rows, t.column_names, round(time.time()-t0),'s')
