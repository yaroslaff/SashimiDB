#!/usr/bin/env python

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from fastapi.security.http import HTTPBearer, HTTPBasicCredentials


from pydantic import BaseModel
import os
import sys
import yaml
import requests
import json
import time
import typing
import re
import ipaddress
from yaml.loader import SafeLoader
from pprint import pprint
import datetime 

from dotenv import load_dotenv

from sqlalchemy import create_engine
import sqlalchemy as sa

from evalidate import Expr, EvalException, base_eval_model, EvalModel

class PrettyJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=4,
            separators=(", ", ": "),
        ).encode("utf-8")

class SearchQuery(BaseModel):
    expr: str = 'True'
    op: str = None
    sort: str = None
    reverse: bool = False
    token: str = None
    limit: int = None
    offset: int = 0
    fields: list[str] = None
    aggregate: list[str] = None
    discard: bool = False
    update: str = None
    update_expr: str=None


class Dataset():
    def __init__(self, name: str, vspec: dict, model: EvalModel):
        self.name = name
        self.vspec = vspec or dict()
        self._data = None
        self.model = model
        
        self.postload_model = base_eval_model.clone()
        self.postload_model.nodes.extend(['Call', 'Attribute'])
        self.postload_model.attributes.extend(['upper', 'lower'])
        # self.postload_model.imported_functions = dict(lower=lower)

        self.named_search = dict()
        vspec_searches = self.vspec.get('search')
        if vspec_searches is not None:
            for search_name, search_desc in vspec_searches.items():
                sq = SearchQuery(**search_desc)
                self.named_search[search_name] = dict(desc = search_desc, sq = sq, r = None)
        self.load()
    
    def reload(self):        
        self.drop_cache()
        self.load()
        return dict(status=f"reloaded ds {self.name!r}")

    def load(self):

        def recursive_lower(x):
            if isinstance(x, str):
                return x.lower()
            elif isinstance(x,list):
                return [ recursive_lower(el) for el in x ]
            elif isinstance(x, dict):
                for k, v in x.items():
                    x[k] = recursive_lower(v)
            else:
                return x

        if self.vspec.get('file'):            
            data = self.load_file(self.vspec['file'], format=self.vspec.get('format'))
        elif self.vspec.get('url'):
            data = self.load_url(self.vspec['url'], format=self.vspec.get('format'))
        elif self.vspec.get('db'):            
            data = self.load_db(self.vspec['db'], sql=self.vspec.get('sql'))


        assert data is not None

        if self.vspec.get('keypath'):
            for k in self.vspec.get('keypath'):
                data = data[k]

        if 'postload' in self.vspec:
            for f, src in self.vspec['postload'].items():
                expr = Expr(src, model=self.postload_model)
                for el in data:
                    el[f] = eval(expr.code, None, el)

        if 'postload_lower' in self.vspec:
            for f in self.vspec['postload_lower']:                
                for el in data:
                    if f == '.':
                        el = recursive_lower(el)
                    else:
                        try:
                            el[f] = recursive_lower(el[f])
                        except KeyError:
                            pass

        if self.vspec.get('multiply'):
            data = data * int(self.vspec.get('multiply'))



        assert isinstance(data, list)
        print(f"Dataset {self.name}: {len(data)} items")

        if 'limit' not in self.vspec:
            self.vspec['limit'] = def_limit
        self._data = data


    def load_db(self, dburl, sql):
        assert(sql is not None)
        engine = create_engine(dburl)
        with engine.begin() as conn:
            qry = sa.text(sql)
            resultset = conn.execute(qry)
            data = [ dict(x) for x in resultset.mappings().all() ]
        return data


    def load_file(self, path, format=None):

        print(f".. load dataset {self.name!r} from {path!r}")
        
        if format is None:
            # guess by extensions            
            if path.lower().endswith('.json'):
                format = 'json'
            elif path.lower().endswith('.yaml') or path.lower().endswith('.yml'):
                format = 'yaml'
        
        # default
        if format is None:
            format = 'json'

        if format == 'json':
            with open(path) as fh:
                return json.load(fh)
                
        elif format == 'yaml':
            with open(path) as f:
                return yaml.load(f, Loader=SafeLoader)
        else:
            raise ValueError(f'Unknown format: {format!r}')

    def load_url(self, url, format=None):
        print(f".. load dataset {self.name!r} from {url!r}")
        return requests.get(url).json()

    def __len__(self):
        return len(self._data)

    def __str__(self):
        return f"ds {self.name} {len(self)} items"
    
    def search(self, sq: SearchQuery):

        def minnone(*args):
            l = [ x for x in args if x is not None ]
            if not l:
                return None
            return min(l)

        exceptions = 0
        last_exception = None
        matches = 0

        op = sq.op or 'filter'

        limit = minnone(self.vspec.get('limit'), sq.limit)

        try:
            expr = Expr(sq.expr, model=self.model) 
        except EvalException as e:
            raise HTTPException(status_code=400, detail=f'Eval exception: {e}')

        truncated = False

        outlist = list()
        for item in self._data:
            try:
                if eval(expr.code, None, item):
                    matches += 1
                    if sq.fields:
                        item = {k: item[k] for k in sq.fields}
                    outlist.append(item)

            except Exception as e:
                exceptions += 1
                last_exception = str(e)

        # Sort
        if sq.sort:
            outlist = sorted(outlist, key=lambda x: x[sq.sort], reverse=sq.reverse)


        result = {
            'status': 'OK',
            'limit': limit,
            'matches': matches,
            'trunctated': truncated,

            'exceptions': exceptions,
            'last_exception': last_exception
        }

        # Aggregation functions
        if sq.aggregate:
            result['aggregation']=dict()
            for agg in sq.aggregate:
                try:
                    method, field = agg.split(':')
                except ValueError:
                    raise HTTPException(status_code=400, detail=f'Can not parse aggregation statement {agg!r} must be in form AGG:FIELD e.g. min:price')

                if outlist:
                    if method == 'sum':
                        agg_result = sum(x[field] for x in outlist)
                    elif method == 'max':
                        agg_result = max(x[field] for x in outlist)
                    elif method == 'min':
                        agg_result = min(x[field] for x in outlist)
                    elif method == 'avg':
                        agg_result = sum(x[field] for x in outlist) / len(outlist)
                    elif method == 'distinct':
                        agg_result = sorted({x[field] for x in outlist})
                    else:
                        raise HTTPException(status_code=400, detail=f'Unknown aggregation method {method!r} must be one of sum/min/max/avg/distinct, e.g. min:price')

                else:
                    # empty outlist
                    agg_result=None
                                    
                result['aggregation'][agg] = agg_result

        # Truncate to offset/limit            
        if sq.offset:
            outlist = outlist[sq.offset:]
        
        if limit is not None and len(outlist) > limit:
            outlist = outlist[:limit]
            truncated = True

        # Discard
        if not sq.discard:
            result['result'] = outlist

        return result
        
    def delete(self, sq: SearchQuery):
        exceptions = 0
        last_exception = None
        try:
            expr = Expr(sq.expr, model=self.model) 
        except EvalException as e:
            raise HTTPException(status_code=400, detail=f'Eval exception: {e}')

        try:
            old_size = len(self._data)
            self._data[:] = [ item for item in self._data if not eval(expr.code, None, item)  ]
            new_size = len(self._data)

        except Exception as e:
            exceptions += 1
            last_exception = str(e)

        result = {
            'status': 'OK',
            'old_size': old_size,
            'new_size': new_size,

            'exceptions': exceptions,
            'last_exception': last_exception
        }
        self.drop_cache()
        return result

    def update(self, sq: SearchQuery):
        exceptions = 0
        last_exception = None

        if sq.update is None:
            raise HTTPException(status_code=400, detail=f'need update')

        if sq.update_expr is None:
            raise HTTPException(status_code=400, detail=f'need update_expr')


        try:
            expr = Expr(sq.expr, model=self.model) 
        except EvalException as e:
            raise HTTPException(status_code=400, detail=f'Compile {sq.expr!r} exception: {e}')
        try:
            update_expr = Expr(sq.update_expr, model=self.model) 
        except EvalException as e:
            raise HTTPException(status_code=400, detail=f'Compile {sq.update_expr!r} exception: {e}')

        matches = 0
        for item in self._data:
            try:
                if eval(expr.code, None, item):
                    matches += 1
                    value = eval(update_expr.code, None, item)
                    item[sq.update] = value

            except Exception as e:
                exceptions += 1
                last_exception = str(e)

        result = {
            'status': 'OK',
            'matches': matches,
            'exceptions': exceptions,
            'last_exception': last_exception
        }
        self.drop_cache()
        return result
    
    def drop_cache(self):
        # Drop all names searches cache
        for ns_name, ns in self.named_search.items():
            ns['r'] = None


### Global variables ###

load_dotenv()

version='0.1'

started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
docker_build_time = None
docker_build_time_path = '/app/docker-build-time.txt'

# FastAPI
app = FastAPI()
auth = HTTPBearer()


def_limit = int(os.getenv('EXACT_LIMIT', '100'))

args = None

config_path = None
config = None
datasets : dict[str, Dataset] = dict()

last_printed = 0



def print_summary():
    global last_printed
    if time.time() > last_printed + 60:
        print("Summary:")
        print(f"PID: {os.getpid()}")
        print(f"started: {started}")

        for dsname, ds in datasets.items():
            print(ds)

        last_printed = time.time()


def validate_token(request: Request, dsname: str, token: str):
    # global token
    ds = datasets[dsname]

    if config.get('ip_header'):
        client_ip_here = request.headers.get(config.get('ip_header'))
    else:
        client_ip_here = request.client.host

    m = re.match('^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})', client_ip_here)
    if m is None:
        raise HTTPException(status_code=401, detail=f'Cannot parse ip from {client_ip_here!r} (ip_header: {config.get("ip_header")!r}')
    client_ip = m.group(0)
    print("client ip:", client_ip)




    tokens_whitelist = config.get('tokens', list()) + ds.vspec.get('tokens', list())

    trusted_ips = config.get('trusted_ips', list()) + ds.vspec.get('trusted_ips', list())

    if trusted_ips:
        if not any(map(lambda subnet:  ipaddress.ip_address(client_ip) in ipaddress.ip_network(subnet), trusted_ips)):
            raise HTTPException(status_code=401, detail=f'client IP {client_ip!r} not found in trusted_ips, sorry')


    if token not in tokens_whitelist:
        raise HTTPException(status_code=401, detail=f'Token {token!r} not found, sorry')


@app.get("/", response_class=PrettyJSONResponse)
def read_root(request: Request):
    print(request.headers)
    return {
        "Description": "ExactAPI :: Fast and secure search inside structured data",
        "Repo URL": "https://github.com/yaroslaff/exact",
        "version": version,
        "started": started,
        "docker_build_time": docker_build_time,
        "client_host": request.client.host,
        "headers": request.headers
        }

@app.post('/ds/{dataset}')
def ds_post(dataset: str, sq: SearchQuery):
    try:
        ds = datasets[dataset]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such dataset {dataset!r}")
    start = time.time()

    r = ds.search(sq)

    r['time'] = round(time.time() - start, 3)
    print_summary()
    return r

@app.get('/ds/{dataset}/{search_name}')
def ds_named_search(dataset: str, search_name: str):
    try:
        ds = datasets[dataset]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such dataset {dataset!r}")
    
    try:
        ns = ds.named_search[search_name]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such named search {search_name!r} in ds {dataset!r}")
    
    start = time.time()

    if ns['r'] is None:
        ns['r'] = ds.search(ns['sq'])
    
    r = ns['r']
    r['time'] = round(time.time() - start, 3)
    print_summary()
    return r


@app.patch('/ds/{dataset}')
def ds_patch(dataset: str, sq: SearchQuery, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):

    #check token or raise exception
    validate_token(request, dataset, authorization.credentials)

    try:
        ds = datasets[dataset]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such dataset {dataset!r}")
    start = time.time()
    if sq.op == "delete":
        r = ds.delete(sq)
    elif sq.op == "update":
        r = ds.update(sq)
    elif sq.op == "reload":
        r = ds.reload()
    else:
        return HTTPException(status_code=400, detail=f"Unknown PATCH operation {sq.op!r}")



    r['time'] = round(time.time() - start, 3)
    print_summary()
    return r




def init():
    global config, def_limit, docker_build_time
    model = None

    config_path = os.environ.get("EXACT_CONFIG", find_config())

    if config_path is None:
        print("Config file not found", file=sys.stderr)
        sys.exit(1)
        return
    
    print(f"Load config {config_path}")

    with open(config_path) as f:
        config = yaml.load(f, Loader=SafeLoader)

    # create default config structure
    if not 'tokens' in config:
        config['tokens'] = list()

    if not 'trusted_ips' in config:
        config['trusted_ips'] = list()

    if not 'datasets' in config:
        config['datasets'] = dict()

    # apply env variables
    if os.environ.get('EXACT_DATASET'):
        for dsline in os.environ.get('EXACT_DATASET').split(' '):
            ds_name, ds_location = dsline.split(':', maxsplit=1)
            if ds_location.startswith('http://') or ds_location.startswith('https://'):
                config['datasets'][ds_name] = {
                    "url": ds_location
                }
            else:
                config['datasets'][ds_name] = {
                    "file": ds_location
                }

    if os.environ.get('EXACT_TOKEN'):
        # add token
        config['tokens'].append(os.environ.get('EXACT_TOKEN'))

    if os.environ.get('EXACT_TRUSTED_IP'):
        # add token
        config['trusted_ips'].append(os.environ.get('EXACT_TRUSTED_IP'))

    if os.environ.get('EXACT_IP_HEADER'):
        # add token
        config['ip_header'] = os.environ.get('EXACT_IP_HEADER')


    def_limit = config.get('limit', def_limit)

    model_name = config.get('model', 'default')
    
    if model_name == 'base':
        model = base_eval_model

    elif model_name == 'default':
        model = base_eval_model.clone()

        model.nodes.extend(['Call', 'Attribute'])
        model.allowed_functions.extend(['int', 'round'])
        model.attributes.extend(['startswith', 'endswith', 'upper', 'lower'])

    elif model_name in ['custom', 'extended']:
        if model_name == 'custom':
            # start from empty
            model = EvalModel(nodes=list())
        else:
            model = base_eval_model.clone()

        model.nodes.extend( config.get('nodes', list()))
        model.attributes.extend( config.get('attributes', list()))
        model.allowed_functions.extend( config.get('functions', list()))

    for ds_name, ds_spec in config['datasets'].items():
        datasets[ds_name] = Dataset(ds_name, ds_spec, model=model)

    if config.get('datadir'):
        for vd in config['datadir']:
            for f in os.listdir(vd):
                path = os.path.join(vd, os.path.basename(f))
                ds_spec = {"file": path}
                ds_name = os.path.splitext(f)[0]
                datasets[ds_name] = Dataset(ds_name, ds_spec, model=model)

    if 'origins' in config:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config['origins'],
            # allow_credentials=True,
            #allow_methods=["*"],
            allow_methods=["POST", "OPTIONS"]
            #allow_headers=["*"],
        )

    if os.path.exists(docker_build_time_path):
        with open(docker_build_time_path) as fh: 
            docker_build_time = fh.read().strip()


    # check
    if not datasets:
        print("Empty datasets", file=sys.stderr)
        sys.exit(1)

    # print(json.dumps(config, indent=4))

def find_config():
    locations = [
        'exact.yml',
        '/data/etc/exact.yml',
        '/etc/exact.yml',
    ]

    locations = [ p for p in locations if os.path.exists(p) ]

    if not locations:
        return None
    
    return locations[0]


def main():
    init()

main()
