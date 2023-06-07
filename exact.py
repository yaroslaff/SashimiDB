from typing import Union
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import yaml
import requests
import json
import time
from yaml.loader import SafeLoader
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

        assert data is not None

        if self.vspec.get('keypath'):
            for k in self.vspec.get('keypath'):
                data = data[k]
        
        self._data = data


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

        op = sq.op or 'filter'

        limit = minnone(self.vspec.get('limit'), sq.limit)

        try:
            node = evalidate.evalidate(sq.expr) 
        except evalidate.EvalException as e:
            raise HTTPException(status_code=456, detail=f'Eval exception: {e}')
        
        code = compile(node, f'<user: {sq.expr}>', 'eval')

        if op == 'filter':

            truncated = False

            outlist = list()
            for item in self._data:
                if eval(code, item.copy()):
                    matches += 1
                    
                    if sq.fields:
                        item = {k: item[k] for k in sq.fields}
                    
                    if len(outlist) < limit:
                        outlist.append(item)
                    else:
                        truncated = True
                    

            if limit is not None and len(outlist) > limit:
                outlist = outlist[:limit]
                truncated = True


            result = {
                'status': 'OK',
                'result': outlist,
                'limit': limit,
                'matches': matches,
                'trunctated': truncated
            }
            return result




@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post('/search/{view}')
def search(view: str, sq: SearchQuery):
    v = views[view]
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
