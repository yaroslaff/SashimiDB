#!/usr/bin/env python

from typing import Union
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import yaml
import requests
import json
import time
from yaml.loader import SafeLoader
from pprint import pprint

from sqlalchemy import create_engine
import sqlalchemy as sa

import evalidate



app = FastAPI()

config_path = "exact.yml"

config = None
views = None

class SearchQuery(BaseModel):
    expr: str
    op: str = None
    token: str = None
    limit: int = None
    fields: list[str] = None



class View():
    def __init__(self, name, vspec):
        self.name = name
        self.vspec = vspec
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
            elif path.lower().endswith('.yaml') or path.lower.endswith('.yml'):
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
            raise HTTPException(status_code=456, detail=f'Eval exception: {e}')
        
        code = compile(node, f'<user: {sq.expr}>', 'eval')

        if op == 'filter':

            truncated = False

            outlist = list()
            for item in self._data:
                try:
                    if eval(code, item.copy()):
                        matches += 1
                        
                        if sq.fields:
                            item = {k: item[k] for k in sq.fields}
                        
                        if limit is None or len(outlist) < limit:
                            outlist.append(item)
                        else:
                            truncated = True
                except Exception as e:
                    exceptions += 1
                    last_exception = str(e)

                    

            if limit is not None and len(outlist) > limit:
                outlist = outlist[:limit]
                truncated = True


            result = {
                'status': 'OK',
                'result': outlist,
                'limit': limit,
                'matches': matches,
                'trunctated': truncated,

                'exceptions': exceptions,
                'last_exception': last_exception
            }
            return result




@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post('/search/{view}')
def search(view: str, sq: SearchQuery):
    try:
        v = views[view]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such view {view!r}")
    start = time.time()
    r = v.op(sq)
    r['time'] = time.time() - start
    return r

def init():
    global config, views
    print("Initialize....")
    with open(config_path) as f:
        config = yaml.load(f, Loader=SafeLoader)
        print(config)
    
    views = dict()
    for vname, vspec in config['views'].items():
        print("Load", vname)
        views[vname] = View(vname, vspec)


init()
