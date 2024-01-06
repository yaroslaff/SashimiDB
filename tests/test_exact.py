import requests
import json
import yaml
import os
import pytest
from rich import print

from sashimi import SashimiClient

project_url = 'http://localhost:8000/ds/test'

dataset = None
token = os.getenv('SASHIMI_TOKEN')
ds_name = 'products'

sashimi = SashimiClient(project_url=project_url, token=token)

def init():
    global dataset
    with open('tests/products.json') as fh:
        content = json.load(fh)
    dataset = content['products']

init()

"""
    run uvicorn exactapp:app in other console
"""

@pytest.fixture
def setup_products():
    rc = sashimi.put(ds_name, dataset)
    yield


class TestExact():
    #def setup_method(self, method):
    #    print("Setup before each test method")

    #def teardown_method(self, method):
    #    print("Teardown after each test method")

    def test_is_up(self):
        # r = requests.get(project_url)
        r = sashimi.info()
        assert r['project'] == 'test'


    def test_info(self, setup_products):
        info = sashimi.info()
        assert info
        assert isinstance(info, dict)
        assert 'datasets' in info
        assert 'products' in info['datasets']

    def test_queries(self, setup_products):             
        
        bool(setup_products) # just to make it used to make VSCode happy
        
        r = sashimi.query(ds_name=ds_name, expr='True')
        assert len(r['result'])
        assert r['matches'] == 100

        r = sashimi.query(ds_name=ds_name, expr='True', limit=1)
        assert len(r['result']) == 1

        r = sashimi.query(ds_name=ds_name, expr='True', discard=True)
        assert 'result' not in r

        r = sashimi.query(ds_name=ds_name, expr='price>20', discard=True)
        assert r['matches'] == 89

        r = sashimi.query(ds_name=ds_name, expr='True', sort='price', limit=1)
        item = r['result'][0]
        assert item['title'] == 'FREE FIRE T Shirt'
        assert item['id'] == 52
        assert item['price'] == 10

        r = sashimi.query(ds_name=ds_name, expr='True', sort='price', reverse=True, limit=1)
        item = r['result'][0]
        assert item['title'] == 'MacBook Pro'
        assert item['id'] == 6
        assert item['price'] == 1749

        r = sashimi.query(ds_name=ds_name, expr='price>50', sort='price', limit=10, offset=10)
        assert r['matches'] == 40
        assert len(r['result']) == 10

        item = r['result'][0]
        assert item['price'] == 68

        item = r['result'][9]
        assert item['price'] == 120



        r = sashimi.query(ds_name=ds_name, filter={'category': 'laptops'}, discard=1)
        assert(r['matches'] == 5)

        r = sashimi.query(ds_name=ds_name, filter={'category': 'laptops', 'brand': 'Samsung'}, discard=1)
        assert(r['matches'] == 1)

        r = sashimi.query(ds_name=ds_name, aggregate=['distinct:brand', 'distinct:category'], discard=1)

        assert len(r['aggregation']['distinct:brand']) == 78 # we have 78 brands
        assert len(r['aggregation']['distinct:category']) == 20 # we have 20 categories


        r = sashimi.query(ds_name=ds_name, filter={'category': 'smartphones'}, aggregate=['distinct:brand'], discard=1)
        assert len(r['aggregation']['distinct:brand']) == 4

        r = sashimi.query(ds_name=ds_name, filter={'category': 'smartphones'}, aggregate=['min:price', 'max:price'], discard=1)
        #print(json.dumps(r, indent=4))
        assert r['aggregation']['min:price'] == 280
        assert r['aggregation']['max:price'] == 1249

        r = sashimi.query(ds_name=ds_name, filter={'category': 'smartphones', 'brand': 'Apple'}, discard=True)
        assert r['matches'] == 2

        r = sashimi.query(ds_name=ds_name, filter={'brand': 'Apple'}, sort='price')
        assert r['matches'] == 3
        assert r['result'][0]['price'] == 549

        r = sashimi.query(ds_name=ds_name, filter={'brand': 'Apple'}, sort='price', reverse=True)
        assert r['matches'] == 3
        assert r['result'][0]['price'] == 1749

        r = sashimi.query(ds_name=ds_name, filter={'brand': 'Apple', 'price__lt': 1000}, sort='price', reverse=True)
        assert r['matches'] == 2
        assert r['result'][0]['price'] == 899

        r = sashimi.query(ds_name=ds_name, fields=['title', 'price'], limit=1)
        assert len(r['result'][0].keys()) == 2

    def test_bad_query(self, setup_products):
        r = sashimi.query(ds_name=ds_name, expr="SomethingWrong")
        assert len(r['result']) == 0
        assert r['exceptions'] == 100
        assert r['last_exception']


    def test_config_named(self, setup_products):
        """
        test ds config and named queries
        """

        config = """
search:
  one:
    expr: id==23
  cheap:
    expr: price < 100
    limit: 10
"""

        sashimi.set_ds_config(ds_name=ds_name, config=config)
        remote_config_str = sashimi.get_ds_config(ds_name=ds_name)

        assert config == remote_config_str

        remote_config = yaml.safe_load(remote_config_str)

        assert 'search' in remote_config
        assert 'one' in remote_config['search']
        assert 'cheap' in remote_config['search']        
        r = sashimi.named_query(ds_name=ds_name, name = "one")
        assert len(r['result']) == 1
        assert r['result'][0]['id'] == 23

        r = sashimi.named_query(ds_name=ds_name, name = "cheap")

        assert r['limit'] == 10
        assert r['matches'] == 77
        assert r['truncated'] == True
        assert len(r['result']) == 10

    def test_pconfig(self, setup_products):
        config = """
tokens:
  - test_token
"""
        # set out new config
        sashimi.set_project_config(config=config)
        remote_config_str = sashimi.get_project_config()

        assert config == remote_config_str
        remote_config = yaml.safe_load(remote_config_str)

        # test if new test token working?
        sashimi2 = SashimiClient(project_url=project_url, token='test_token')
        remote_config_str = sashimi2.get_project_config()
        assert config == remote_config_str

        # test if wrong token working?
        sashimi2 = SashimiClient(project_url=project_url, token='WRONG')
        with pytest.raises(requests.exceptions.HTTPError):
            sashimi2.get_project_config()


    def test_rm(self, setup_products):
        info = sashimi.info()
        assert 'products' in info['datasets']

        sashimi.rm('products')
        info = sashimi.info()
        assert 'products' not in info['datasets']

    def test_insert_delete(self, setup_products):

        record = {'id': 666, 'title': 'xxx', 'price': 1234 }
        r = sashimi.insert(ds_name=ds_name, data=record)

        r = sashimi.query(ds_name=ds_name, expr='id==666')
        assert len(r['result']) == 1

        sashimi.delete(ds_name=ds_name, expr='id==666')

        r = sashimi.query(ds_name=ds_name, expr='id==666')
        assert len(r['result']) == 0

    def test_update(self, setup_products):
        sashimi.update(ds_name=ds_name, expr='id==23', data=dict(x="xxx", price=123))
        r = sashimi.query(ds_name=ds_name, expr='id==23')
        product = r['result'][0]

        assert product['x'] == 'xxx'
        assert product['price'] == 123
