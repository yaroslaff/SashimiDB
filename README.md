# exact
Exact search API for structured data (json, yaml, database queries)

##  Examples



http -v  POST localhost:8000/search/big 'expr=price<10' limit=0 fields[]=id fields[]=title fields[]=price

## Sample data sources
- https://fakestoreapi.com/products
- https://www.mockaroo.com/
- https://dummyjson.com/