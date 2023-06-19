# exact
Exact is simple, secure and very fast (fracton of a second even for queries in large database) REST API for structured public data with python expressions syntax.

## Example usage
Main purpose of Exact is to have secure, fast and very flexible back-end for searching public data. For example, you may have online store, and your frontend needs API to quickly get *all smartphones with price from X to Y, brand Samsung or Apple, with Retina* (`category=="smartphones" and price>1 and price<1000 and brand in ["Apple", "Samsung"] and "retina" in description.lower()`) or *All green or red t-shirts, XXL size, cotton>80, sorted by price, min and max price*.

## Quick start

To play with Exact, you can use our demo server at [back4app](https://www.back4app.com/) ([httpie](https://github.com/httpie/httpie) is recommended):
~~~
http POST https://exact-yaroslaff.b4a.run/search/dummy limit=3
~~~

This is free virtual docker container, if no reply - it's sleeping, just repeat request in a few seconds and it will reply very quickly. Or run container locally.

Or if you prefer curl:
~~~
curl -H 'Content-Type: application/json' -X POST https://exact-yaroslaff.b4a.run/search/dummy -d '{"expr": "price<800 and brand==\"Apple\""}'
~~~

(pipe output to [jq](https://github.com/jqlang/jq) to get it formatted and colored)

## Running your own instance (Alternative 1 (recommended): docker container)

If you want to run your own instance of exact, better to start with docker image.

Create following directory structure (/tmp/data):
~~~
mkdir -p /tmp/data/data
mkdir /tmp/data/etc

# make example dataset
wget -O /tmp/data/data/test.json https://fakestoreapi.com/products
~~~

create basic config file `/tmp/data/etc/exact.yml`:
~~~
datadir:
  - /data/data

nodes:
  - List
  - Call
  - Attribute
attrs:
  - startswith
  - endswith
  - upper
  - lower
~~~

Now you can start docker container:
~~~
sudo docker run --rm --name exact -p 8000:80 -it -v /tmp/data/:/data/  yaroslaff/exact
~~~

And make test query: `http POST http://localhost:8000/search/test 'expr=price<10' limit=5`

## Running your own instance (Alternative 2: as python app)
1. Clone repo: `git clone https://github.com/yaroslaff/exact.git`
2. install dependencties: `cd exact; poetry install`
3. activate virtualenv: `poetry shell`
4. `uvicorn exact:app`


## Query format
Exact accepts queries as HTTP POST format, with following fields (at least one field is required, POST-body must not be empty):

### Expr
Python-style expression to apply to view, example expressions:
- `price<123.45`
- `brand=="Apple" and rating>4.5 and "laptops" in category and "macbook".upper() in description.upper()`

~~~
http POST http://localhost:8000/search/dummy 'expr=brand=="Apple" and rating>4.5 and "laptops" in category and "macbook".upper() in description.upper()' limit=3
~~~

### sort and reverse
sort by thisfield, e.g. "price". Optionally reversed.

~~~
http POST http://localhost:8000/search/dummy sort=price fields[]=price reverse=1
~~~

### limit and offset
Can be used for pagination and to fit server-side 'limit'
~~~
http POST http://localhost:8000/search/dummy 'expr=price>100' sort=price limit=2 offset=2
~~~

### fields
Output only listed fields.
~~~
http POST http://localhost:8000/search/dummy fields[]=price fields[]=description
~~~

### aggregate
Aggregation functions in format 'FUNCTION:field'. Functions is one of:
- min
- max
- sum
- avg
- distinct

~~~
http POST http://localhost:8000/search/dummy aggregate[]='max:price' aggregate[]='min:price' discard=1
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


## Memory usage
Docker container with small JSON dataset consumes 41Mb (use plain python app "alternative 2", if you need even smaller memory footprint). When loading large file (1mil.json. 500+Mb), container takes 1.5Gb. Rule of thumb - container will use 3x times of JSON file size for large datasets.


## Security
1. Exact is based on [evalidate](https://github.com/yaroslaff/evalidate) which validates expressions and executes only safe code which matches configuration limitations (e.g. does not allows calling any functions except whitelisted in exact.yml). But be careful when you whitelist new functions (technically, you can allow everything needed to run `os.system('rm -rf')`. Do not do this. Default allowed function is probably both secure and flexible enough for any possible request in real life)
2. Recommended way is to run exact inside docker container, so even if (in theory), someone could exploit eval(), he still locked inside docker container.
3. Exact is read-only, it does not writes anything to dataset or other files.
4. Even if you use Exact with RDBMS, Exact reads data only at initialization stage (REST API is not started), uses SQL statements from config file as-is (without any modification) and does not makes any requests to database later. So, there is no place for SQL Injections or similar kind of attacks. But if you want to fully isolate database from world, export data to JSON files with [SQL Export](https://github.com/yaroslaff/sql-export) or other tool, and use docker with this files. It will be as secure as docker.

## Performance
For test, we use 1mil.json file, list of 1 million of products (each of 100 unique items is duplicated 10 000 times). Searching for items with `price<200` and limit=10 (820 000 matches), takes little more then 0.2 seconds. Aggregation request to find min and max price among whole 1 million dataset takes 0.43 seconds.

## Tips and tricks
- If you will always use upper/lower case in JSON datasets and in frontend, you can disable `upper`/`lower` functions and save few milliseconds on each request.
- Remove all sensitive/not-needed fields when exporting to JSON. Leave only key fields and fields used for searching, such as price, size, color.
- Use `limit` for every dataset.


## MySQL, MariaDB, PostgreSQL and other databases support
Exact uses [SQLAlchemy](https://www.sqlalchemy.org/) to work with database, so it can work with any sqlalchemy-compatible RDBMS, but you need to install proper python modules, e.g. `pip install mysqlclient` (for mysql/mariadb).

https://docs.sqlalchemy.org/en/20/core/engines.html

Example config
~~~
datasets:
  contact:
    db: mysql://scott:tiger@127.0.0.1/contacts
    sql: SELECT * FROM contact
~~~

This will create dataset contact from `contacts.contact` table.

## Build docker image
~~~
sudo docker build -t yaroslaff/exact ./
~~~

## Sample data sources
- https://fakestoreapi.com/products
- https://www.mockaroo.com/
- https://dummyjson.com/

Prepare 1 million items list '1mil.json':
~~~
$ python
Python 3.9.2 (default, Feb 28 2021, 17:03:44) 
[GCC 10.2.1 20210110] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import requests
>>> import  json
>>> data = requests.get('https://dummyjson.com/products?limit=100').json()['products'] * 10000
>>> with open('1mil.json', 'w') as fh:
...   fh.write(json.dumps(data))
... 
~~~
This makes file `1mil.json` (568Mb).