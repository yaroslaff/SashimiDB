#!/usr/bin/env python

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from pydantic import BaseModel
import os
import sys
import yaml
import requests
import json
import time
import typing
from yaml.loader import SafeLoader
from pprint import pprint
import datetime 

from sqlalchemy import create_engine
import sqlalchemy as sa

from evalidate import Expr, EvalException, base_eval_model, EvalModel

version='0.1'

started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
docker_build_time = None
docker_build_time_path = '/app/docker-build-time.txt'
app = FastAPI()

def_limit = int(os.getenv('EXACT_LIMIT', '100'))

args = None

config_path = None
config = None
datasets = dict()



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

        self.load()
    
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

        print(f".. load dataset {self.name} from {path}")
        
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
        print(f".. load dataset {self.name} from {url}")
        return requests.get(url).json()

    def op(self, sq: SearchQuery):

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
        
        if op == 'filter':

            # Filter

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

            # Truncate to offset/limit
            
            if sq.offset:
                outlist = outlist[sq.offset:]
            
            if limit is not None and len(outlist) > limit:
                outlist = outlist[:limit]
                truncated = True

            result = {
                'status': 'OK',
                'limit': limit,
                'matches': matches,
                'trunctated': truncated,

                'exceptions': exceptions,
                'last_exception': last_exception
            }


            # Discard
            if not sq.discard:
                result['result'] = outlist


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
                            agg_result = {x[field] for x in outlist}
                        else:
                            raise HTTPException(status_code=400, detail=f'Unknown aggregation method {method!r} must be one of sum/min/max/avg/distinct, e.g. min:price')

                    else:
                        # empty outlist
                        agg_result=None
                    
                    
                    result['aggregation'][agg] = agg_result

            return result



@app.get("/", response_class=PrettyJSONResponse)
def read_root():
    return {
        "Description": "ExactAPI :: Fast and secure search inside structured data",
        "Repo URL": "https://github.com/yaroslaff/exact",
        "version": version,
        "started": started,
        "docker_build_time": docker_build_time
        }


@app.post('/search/{dataset}')
def search(dataset: str, sq: SearchQuery):
    try:
        v = datasets[dataset]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such dataset {dataset!r}")
    start = time.time()
    r = v.op(sq)
    r['time'] = round(time.time() - start, 3)
    return r

def init():
    global config, def_limit, docker_build_time
    model = None

    config_path = os.environ.get("EXACT_CONFIG", find_config())

    if config_path is None:
        print("Config file not found", file=sys.stderr)
        sys.exit(1)
        return

    with open(config_path) as f:
        config = yaml.load(f, Loader=SafeLoader)
    
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

    if config.get('datasets'):
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
            allow_methods=["POST"]
            #allow_headers=["*"],
        )

    if os.path.exists(docker_build_time_path):
        with open(docker_build_time_path) as fh: 
            docker_build_time = fh.read().strip()

    # check
    if not datasets:
        print("Empty datasets", file=sys.stderr)
        sys.exit(1)

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
