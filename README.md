# exact
Exact search API for structured data (json, yaml, database queries)




http -v  POST localhost:8080/search/products "expr=price<800 and brand=='Apple'"


##  Examples


uvicorn exact:app --reload

http -v  POST localhost:8080/search/products "expr=price<800 and brand=='Apple'"
curl -H 'Content-Type: application/json' -X POST localhost:8080/search/products -d '{"expr": "price<800 and brand==\"Apple\""}'| jq


sudo docker run --rm --name exact -p 8080:80 -it yaroslaff/exact

## query



## mysql support:
https://docs.sqlalchemy.org/en/20/core/engines.html

pip install mysqlclient

## Build docker image

sudo docker build -t yaroslaff/exact ./

## Sample data sources
- https://fakestoreapi.com/products
- https://www.mockaroo.com/
- https://dummyjson.com/