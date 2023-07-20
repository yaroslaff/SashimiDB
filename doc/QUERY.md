# Query format

## Search/Fetch
Exact accepts search queries as HTTP POST format, with following fields (at least one field is required, POST-body must not be empty):

### Expr
Python-style expression to filter dataset. Example expressions:
- `price<123.45`
- `brand=="Apple" and rating>4.5 and "laptops" in category and "macbook".upper() in description.upper()`

To fetch one specific record (e.g. by id field) just use this as expr to get list of 1 matching element: `id==123`.

~~~
http POST http://localhost:8000/ds/dummy 'expr=brand=="Apple" and rating>4.5 and "laptops" in category and "macbook".upper() in description.upper()' limit=3
~~~

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
    "trunctated": true
}
~~~

### discard
discard `results` field (data elements). Useful if you need short reply with summary details (like "matches") or aggregation info.



### Named queries