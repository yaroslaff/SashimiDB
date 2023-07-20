
## Eval exception: Node type 'List' is not allowed. (whitelist it manually)
(Same for other node types)

~~~
http POST http://localhost:8000/ds/dummy expr='category=="smartphones" and price>1 and price<1000 and brand in ["Apple", "Samsung"] and "retina" in description.lower()'

HTTP/1.1 400 Bad Request
content-length: 85
content-type: application/json
date: Thu, 20 Jul 2023 10:56:46 GMT
server: uvicorn

{
    "detail": "Eval exception: Node type 'List' is not allowed. (whitelist it manually)"
}
~~~

### Solution
Add this node type to `exact.yml`, to `nodes` list. e.g.
~~~
model: extended
nodes: 
  - List
  ...
~~~
