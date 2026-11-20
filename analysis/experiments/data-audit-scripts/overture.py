import duckdb, sys, time
out = sys.argv[1]; rel='2026-11-18.0'
con = duckdb.connect()
con.sql("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
bb = "bbox.xmin > -83.80 AND bbox.xmax < -83.67 AND bbox.ymin > 42.22 AND bbox.ymax < 42.33"
for t,typ,cols in [("transportation","segment","id, subtype, class, names.primary AS name, connectors, road_flags, access_restrictions, ST_AsText(geometry) AS wkt"),
                   ("transportation","connector","id, ST_X(geometry) lon, ST_Y(geometry) lat")]:
    t0=time.time()
    con.sql(f"COPY (SELECT {cols} FROM read_parquet('s3://overturemaps-us-west-2/release/{rel}/theme={t}/type={typ}/*', hive_partitioning=1) WHERE {bb}) TO '{out}/{typ}.parquet' (FORMAT parquet)")
    print(typ, con.sql(f"select count(*) from '{out}/{typ}.parquet'").fetchone(), round(time.time()-t0),'s')
