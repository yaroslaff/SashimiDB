
from evalidate import Expr, EvalException, base_eval_model, EvalModel
import requests
import json
from fastapi import HTTPException
from sqlalchemy import create_engine
import sqlalchemy as sa
import time
import os
import sys

from pydantic import ValidationError

from .api.params import SearchQuery
from .config import Config
from typing import TYPE_CHECKING, List, Dict
if TYPE_CHECKING:
    from .project import Project


def get_deep_size(obj, seen=None):
    """Recursively finds size of objects"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([get_deep_size(v, seen) for v in obj.values()])
        size += sum([get_deep_size(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += get_deep_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([get_deep_size(i, seen) for i in obj])
    return size



class Dataset():
    def __init__(self, name: str, project: "Project", model: EvalModel, path: os.DirEntry = None):
        self.name = name
        self._data = None
        self.model = model
        self.project = project
        self.loaded = None
        self.size = None
        self.load_ip = None
        self.update_ip = None
        self.path: os.DirEntry = path
        self.status = "OK"

        self.postload_model = base_eval_model.clone()
        self.postload_model.nodes.extend(['Call', 'Attribute'])
        self.postload_model.attributes.extend(['upper', 'lower'])
        # self.postload_model.imported_functions = dict(lower=lower)

        self.read_config()


        if path:
            self._data = self.load_file(self.path, format=self.config.get('format'))

    def get_config_path(self):
        return os.path.join(self.project.path, '_' + self.name + '.yaml')

    def get_dataset_path(self):
        return os.path.join(self.project.path, self.name + '.json')

    def read_config(self):
        try:
            self.config = Config(self.get_config_path(), role="dataset", parent=self.project.config)
        except FileNotFoundError as e:
            self.config = Config(role="dataset", parent=self.project.config)

        self.named_search = dict()
        vspec_searches = self.config.get('search')
        if vspec_searches is not None:
            for search_name, search_desc in vspec_searches.items():
                try:
                    sq = SearchQuery(**search_desc)
                    self.named_search[search_name] = dict(desc = search_desc, sq = sq, r = None)
                except ValidationError as e:
                    self.status = f"named search {search_name!r} error: {e}"
        
        self.allowed_operations = self.config.get('allowed_operations', list())

        self.set_defaults()



    def set_defaults(self):
        """
            set defaults variables for dataset
        """

        def_allowed_operations = ['update', 'reload', 'delete']

        if not self.allowed_operations:
            self.allowed_operations = list(def_allowed_operations)
            
    def reload(self):
        self.check_allowed_operation("reload")
        self.drop_cache()
        return dict(status=f"reloaded ds {self.name!r}")


    def set_dataset(self, data, size=None, ip=None):
        self._data = data
        self.loaded = int(time.time())
        # self.size = size
        self.update_size()
        self.load_ip = ip

    def load_db(self, dburl, sql):
        assert(sql is not None)
        engine = create_engine(dburl)
        with engine.begin() as conn:
            qry = sa.text(sql)
            resultset = conn.execute(qry)
            data = [ dict(x) for x in resultset.mappings().all() ]
        return data


    def load_file(self, path: os.DirEntry, format=None) -> List[Dict]:

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
    

    def check_allowed_operation(self, opname):
        
        if opname in self.allowed_operations:
            return

        raise HTTPException(status_code=401, detail=f'Operation {opname!r} not allowed for ds {self.name!r}')


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

        limit = minnone(self.config.get('limit'), sq.limit)

        try:
            expr = Expr(sq.expr, model=self.model) 
        except EvalException as e:
            raise HTTPException(status_code=400, detail=f'Eval exception: {e}')

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
            'truncated': False,

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

                try:

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
                
                except KeyError as e:
                    field = e.args[0]
                    raise HTTPException(status_code=400, detail=f'Key exception {field!r} during aggregation')

                except Exception as e:
                    raise HTTPException(status_code=400, detail=f'Exception during aggregation: {e!r}')
                                    
                result['aggregation'][agg] = agg_result

        # Truncate to offset/limit            
        if sq.offset:
            outlist = outlist[sq.offset:]
        
        if limit is not None and len(outlist) > limit:
            outlist = outlist[:limit]
            result['truncated'] = True

        # Discard
        if not sq.discard:
            result['result'] = outlist

        return result
            
    def delete(self, sq: SearchQuery):

        self.check_allowed_operation("delete")

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

    def insert(self, record):
        self._data.append(record)

    def update(self, sq: SearchQuery, ip: str = None):

        self.check_allowed_operation("update")

        exceptions = 0
        last_exception = None

        if sq.update_field is None:
            raise HTTPException(status_code=400, detail=f'need update_field')

        if sq.update_data is None:
            raise HTTPException(status_code=400, detail=f'need update_data')


        try:
            expr = Expr(sq.expr, model=self.model) 
        except EvalException as e:
            raise HTTPException(status_code=400, detail=f'Compile {sq.expr!r} exception: {e}')

        matches = 0

        try:
            value = json.loads(sq.update_data)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON error: {str(e)}")

        for item in self._data:
            try:
                if eval(expr.code, None, item):
                    matches += 1
                    # value = eval(update_expr.code, None, item)
                    item[sq.update_field] = value

            except Exception as e:
                exceptions += 1
                last_exception = str(e)

        self.update_size()
        self.update_ip = ip

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


    def update_size(self):
        self.size = get_deep_size(self._data)

