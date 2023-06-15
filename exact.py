#!/usr/bin/env python

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
import os
import sys
import yaml
import requests
import json
import time
from yaml.loader import SafeLoader
from pprint import pprint
import datetime 
import argparse

from sqlalchemy import create_engine
import sqlalchemy as sa

import evalidate

version='0.1'

started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
docker_build_time = None
docker_build_time_path = '/app/docker-build-time.txt'
app = FastAPI()

args = None

config_path = None
config = None
views = None



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


class View():
    def __init__(self, name: str, vspec: dict):
        self.name = name
        self.vspec = vspec or dict()
        self._data = None
        
        self.load()
    
    def load(self):
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

        if self.vspec.get('multiply'):
            data = data * int(self.vspec.get('multiply'))

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
            node = evalidate.evalidate(sq.expr, addnodes=config.get('nodes'), attrs=config.get('attrs')) 
        except evalidate.EvalException as e:
            raise HTTPException(status_code=400, detail=f'Eval exception: {e}')
        
        code = compile(node, f'<user: {sq.expr}>', 'eval')

        if op == 'filter':

            # Filter

            truncated = False

            outlist = list()
            for item in self._data:
                try:
                    if eval(code, item.copy()):
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



@app.get("/")
def read_root():
    return {
        "Description": "ExactAPI :: Fast and secure search inside structured data",
        "Repo URL": "https://github.com/yaroslaff/exact",
        "version": version,
        "started": started,
        "docker_build_time": docker_build_time
        }


@app.post('/search/{view}')
def search(view: str, sq: SearchQuery):
    try:
        v = views[view]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such view {view!r}")
    start = time.time()
    r = v.op(sq)
    r['time'] = round(time.time() - start, 3)
    return r

def init():
    global config, views, docker_build_time

    config_path = os.environ.get("EXACT_CONFIG", find_config())

    if config_path is None:
        print("Config file not found", file=sys.stderr)
        sys.exit(1)
        return

    with open(config_path) as f:
        config = yaml.load(f, Loader=SafeLoader)
    
    views = dict()
    if config.get('views'):
        for vname, vspec in config['views'].items():
            print("Load", vname)
            views[vname] = View(vname, vspec)

    if config.get('viewdir'):
        for vd in config['viewdir']:
            for f in os.listdir(vd):
                path = os.path.join(vd, os.path.basename(f))
                vspec = {"file": path}
                vname = os.path.splitext(f)[0]
                print(vname, path)
                views[vname] = View(vname, vspec)


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
