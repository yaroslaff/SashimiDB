import requests
import json
import os
import pytest

from exact_client import ExactClient

base_url = 'http://localhost:8000/'

products_url = 'https://dummyjson.com/products?limit=100'

dataset = None
token = os.getenv('EXACT_TOKEN')
ds_name = 'products'

exact = ExactClient(base_url=base_url, project='sandbox', token=token)

def init():
    global dataset
    print(".. init")
    with open('tests/products.json') as fh:
        content = json.load(fh)
    dataset = content['products']

init()

"""
    run uvicorn exactapp:app in other console
"""

@pytest.fixture
def setup_products():
    exact.put(ds_name, dataset)
    yield
    print("Teardown products")


class TestExact():
    #def setup_method(self, method):
    #    print("Setup before each test method")

    #def teardown_method(self, method):
    #    print("Teardown after each test method")

    def test_is_up(self):
        r = requests.get(base_url)
        r.raise_for_status()

    def test_queries(self, setup_products):             
        
        bool(setup_products) # just to make it used to make VSCode happy
        
        r = exact.query(ds_name=ds_name, expr='True')
        assert len(r['result'])
        assert r['matches'] == 100

        r = exact.query(ds_name=ds_name, expr='True', limit=1)
        assert len(r['result']) == 1

        r = exact.query(ds_name=ds_name, expr='True', discard=True)
        assert 'result' not in r

        r = exact.query(ds_name=ds_name, expr='price>20', discard=True)
        assert r['matches'] == 89

        r = exact.query(ds_name=ds_name, expr='True', sort='price', limit=1)
        item = r['result'][0]
        assert item['title'] == 'FREE FIRE T Shirt'
        assert item['id'] == 52
        assert item['price'] == 10

        r = exact.query(ds_name=ds_name, expr='True', sort='price', reverse=True, limit=1)
        item = r['result'][0]
        assert item['title'] == 'MacBook Pro'
        assert item['id'] == 6
        assert item['price'] == 1749

        r = exact.query(ds_name=ds_name, expr='price>50', sort='price', limit=10, offset=10)
        assert r['matches'] == 40
        assert len(r['result']) == 10

        item = r['result'][0]
        assert item['price'] == 68

        item = r['result'][9]
        assert item['price'] == 120



        r = exact.query(ds_name=ds_name, filter={'category': 'laptops'}, discard=1)
        assert(r['matches'] == 5)

        r = exact.query(ds_name=ds_name, filter={'category': 'laptops', 'brand': 'Samsung'}, discard=1)
        assert(r['matches'] == 1)

        r = exact.query(ds_name=ds_name, aggregate=['distinct:brand', 'distinct:category'], discard=1)

        assert len(r['aggregation']['distinct:brand']) == 78 # we have 78 brands
        assert len(r['aggregation']['distinct:category']) == 20 # we have 20 categories


        r = exact.query(ds_name=ds_name, filter={'category': 'smartphones'}, aggregate=['distinct:brand'], discard=1)
        assert len(r['aggregation']['distinct:brand']) == 4

        r = exact.query(ds_name=ds_name, filter={'category': 'smartphones'}, aggregate=['min:price', 'max:price'], discard=1)
        #print(json.dumps(r, indent=4))
        assert r['aggregation']['min:price'] == 280
        assert r['aggregation']['max:price'] == 1249

        r = exact.query(ds_name=ds_name, filter={'category': 'smartphones', 'brand': 'Apple'}, discard=True)
        assert r['matches'] == 2

        r = exact.query(ds_name=ds_name, filter={'brand': 'Apple'}, sort='price')
        assert r['matches'] == 3
        assert r['result'][0]['price'] == 549

        r = exact.query(ds_name=ds_name, filter={'brand': 'Apple'}, sort='price', reverse=True)
        assert r['matches'] == 3
        assert r['result'][0]['price'] == 1749

        r = exact.query(ds_name=ds_name, filter={'brand': 'Apple', 'price__lt': 1000}, sort='price', reverse=True)
        assert r['matches'] == 2
        assert r['result'][0]['price'] == 899

        r = exact.query(ds_name=ds_name, fields=['title', 'price'], limit=1)
        assert len(r['result'][0].keys()) == 2


