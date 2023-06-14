# exact
Exact is simple in-memory read-only database for structured public data with REST API with python expressions.



http -v  POST localhost:8080/search/products "expr=price<800 and brand=='Apple'"

## Example usage
Main purpose of Exact is to have secure, fast and very flexible public back-end for searching public data. For example, you may have online store, and your frontend needs API to quickly get *all smartphones with price from X to Y, brand Samsung or *


## Quick start

##  Examples


uvicorn exact:app --reload

http -v  POST localhost:8080/search/products "expr=price<800 and brand=='Apple'"

curl -H 'Content-Type: application/json' -X POST localhost:8080/search/products -d '{"expr": "price<800 and brand==\"Apple\""}'| jq

http -v  POST localhost:8000/search/products discard=0 expr=True fields[]=price fields[]=title  sort=price limit=5 reverse=1

sudo docker run --rm --name exact -p 8080:80 -it yaroslaff/exact

## query

## Data examples

## Security

## Performance

## mysql support:
https://docs.sqlalchemy.org/en/20/core/engines.html

pip install mysqlclient

## Build docker image

  sudo docker build -f docker/Dockerfile -t yaroslaff/exact ./

## Sample data sources
- https://fakestoreapi.com/products
- https://www.mockaroo.com/
- https://dummyjson.com/