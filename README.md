# exact
Exact is simple in-memory read-only database for structured public data with REST API with python expressions.

## Example usage
Main purpose of Exact is to have secure, fast and very flexible public back-end for searching public data. For example, you may have online store, and your frontend needs API to quickly get *all smartphones with price from X to Y, brand Samsung or Apple* or *All green or red t-shirts, XXL size, cotton>80, sorted by price, min and max price*

## Quick start

To play with Exact, you can use our demo server at [back4app](https://www.back4app.com/) (([httpie](https://github.com/httpie/httpie) is recommended)):
~~~
http POST https://exact-yaroslaff.b4a.run/search/dummy limit=3
~~~

Or if you prefer curl:
~~~
curl -H 'Content-Type: application/json' -X POST https://exact-yaroslaff.b4a.run/search/dummy -d '{"expr": "price<800 and brand==\"Apple\""}'
~~~

(pipe output to [jq](https://github.com/jqlang/jq) to get it formatted and colored)

## Running your own instance

If you want to run your own instance of exact, better to start with docker image.

Download/start exact with default configuration and default dummy [products](https://dummyjson.com/) list:
~~~
sudo docker run --rm --name exact -p 8000:80 -it yaroslaff/exact
~~~

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

  sudo docker build -t yaroslaff/exact ./

## Sample data sources
- https://fakestoreapi.com/products
- https://www.mockaroo.com/
- https://dummyjson.com/