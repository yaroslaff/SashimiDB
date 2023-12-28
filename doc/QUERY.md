# Query format

Examples below supposes exact server is running and listening port 8000 (like explained in "Running your own instance (Alternative 1 (recommended): docker container" in README.md)

Also, here we use `http` command (from [httpie](https://httpie.io)) for local testing, but in front-end development, most likely, you will use JavaScript [fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch).

## Search/Fetch
Exact accepts search queries as HTTP POST format, with following fields (at least one field is required, POST-body must not be empty):

### expr
Python-style expression to filter dataset. Example expressions:
- `price<123.45`
- `brand=="Apple" and rating>4.5 and "laptops" in category and "macbook".upper() in description.upper()`

To fetch one specific record (e.g. by id field) just use this as expr to get list of 1 matching element: `id==123`.

~~~
http POST http://localhost:8000/ds/dummy 'expr=brand=="Apple" and rating>4.5 and "laptops" in category and "macbook".upper() in description.upper()' limit=3
~~~

### filter
This is alternative to `expr` (actually, it's used to construct `expr`). Dictionary of fields and values.

Example:
~~~
http POST http://localhost:8000/ds/dummy filter[category]=skincare filter[price__lt]=50
~~~
This will find products with `price` less then 50 and `category` `"skincare"`.

if value is list `in` operation is supposed. This filter `filter[category][]=skincare filter[category][]=fragrances` will search in these two categories.

Suffixes (after two underscores) are for math comparisions. Available suffixes: lt (`<`), le (`<=`), gt (`>`), ge (`>=`).

All comparisions are joined with "and" logic.

If Expr is given it's joined as well: `filter[category]=skincare filter[price__lt]=50` is equal to `'expr=category=="skincare"' filter[price__lt]=50`, both will make expr `category == "skincare" and price < 50`.


### sort and reverse
sort by thisfield, e.g. "price". Optionally reversed.

~~~
http POST http://localhost:8000/ds/dummy sort=price fields[]=price reverse=1
~~~

### limit and offset
Can be used for pagination and to fit server-side 'limit'
~~~
http POST http://localhost:8000/ds/dummy 'expr=price>100' sort=price limit=2 offset=2
~~~

### fields
Output only listed fields.
~~~
http POST http://localhost:8000/ds/dummy fields[]=price fields[]=description
~~~

### aggregate
Aggregation functions in format 'FUNCTION:field'. Functions is one of:
- min
- max
- sum
- avg
- distinct

~~~
http POST http://localhost:8000/ds/dummy aggregate[]='max:price' aggregate[]='min:price' discard=1
...
{
    "aggregation": {
        "max:price": 1249,
        "min:price": 280
    },
    "exceptions": 0,
    "last_exception": null,
    "limit": 5,
    "matches": 100,
    "status": "OK",
    "time": 0.0,
    "truncated": true
}
~~~

### discard
discard `results` field (data elements). Useful if you need short reply with summary details (like "matches") or aggregation info.



### Named queries


## Write operations (update/delete)
For update/delete operations, need Bearer token authentication, must include token in header:
~~~
Authorization: Bearer mytoken
~~~

**IMPORTANT WARNING**: Write operations MUST NOT be used from public web applications, because token is private and must not exists on client-side. Use DELETE/UPDATE only from your backend servers to update exact datasets, e.g. to set "onstock=False" when item is sold out. If you need write operations from public web app - probably Exact is not good for your project (or any user would be able to delete all records in dataset).

See [Security](doc/SECURITY.md) for more.

### DELETE records
~~~
http -A bearer -a mytoken  PATCH http://localhost:8000/ds/dummy 'expr=id==1' op=delete
~~~

## UPDATE records
~~~
http -A bearer -a mytoken PATCH http://localhost:8000/ds/dummy 'expr=id==1' op=update update=onstock update_expr="False"
~~~

## RELOAD dataset
~~~
http -A bearer -a mytoken PATCH http://localhost:8000/ds/dummy op=reload
~~~
