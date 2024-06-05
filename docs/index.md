# Sashimi
What is Sashimi? 

## Quickstart

### Start local Sashimi server

Start server (in first console)
~~~
uvicorn sashimiapp:app
~~~

this will start server on localhost:8000


### Initialize client
Create `.env` file:
~~~
SASHIMI_PROJECT=http://127.0.0.1:8000/ds/sandbox
SASHIMI_TOKEN=mytoken
~~~

Upload dataset:
~~~
sashimi upload /tmp/products.json myproducts
~~~

### Run queries
Most likely, you will use Sashimi from web browser JavaScript application. But to easier understand how to work with sashimi, we will use sashimi CLI tool first.

Run help to see example commands:
~~~
sashimi query -h
~~~

Run one of example commands:
~~~
  sashimi query products 'price<1000' 'category="smartphones"' 'brand=["Apple", "Huawei"]'
~~~
