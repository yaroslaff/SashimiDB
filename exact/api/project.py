import time
import datetime
import re
import sys
import ipaddress
import string
import json

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security.http import HTTPBearer, HTTPBasicCredentials
from fastapi.responses import PlainTextResponse

from pydantic import BaseModel, validator

from ..prettyjson import PrettyJSONResponse
from ..project import Project, projects
from ..dataset import Dataset
from ..searchquery import SearchQuery
from ..config import Config

class DatasetDeleteParameter(BaseModel):
    name: str

class DatasetPutParameter(BaseModel):
    ds: list
    name: str

    @validator('name')
    def valid_name(cls, name):
        ds_name_allowed = set(
            string.ascii_letters 
            + string.digits 
            + '_-.')
        
        if not set(name) <= ds_name_allowed:
            raise ValueError("Invalid dataset name")
        return name


router = APIRouter()
auth = HTTPBearer()


def make_expr(base_expr: str, filterfields: dict, joinop: str ="and"):

    assert(joinop in ['and', 'or'])

    subop = {
        "lt": "<",
        "le": "<=",
        "gt": ">",
        "ge": ">="
    }

    expr = base_expr
    for k, v in filterfields.items():
        if isinstance(v, list):
            subexpr = f"{k} in {v!r}"
        else:
            try:
                field, op_kind = k.split('__', 1)
                try:
                    subexpr = f"{field} {subop[op_kind]} {v!r}"
                except KeyError:
                    raise HTTPException(status_code=400, detail=f"Unknown sub-operation {op_kind!r}")
                
            except ValueError:
                # Simple case, just ==
                subexpr = f"{k} == {v!r}"

        if expr:
            expr = f'{expr} {joinop} {subexpr}'
        else:
            expr = subexpr
    return expr


def get_project(project_name: str) -> Project:
    try:
        project = projects[project_name]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such project {project_name!r}")
    return project


def get_project_ds(project_name: str, ds_name: str) -> (Project, Dataset):

    project = get_project(project_name=project_name)

    try:
        dataset = project[ds_name]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such dataset {ds_name} in project {project_name!r}")

    return (project, dataset)

def check_ds_token(request, ds: Dataset, credentials: str):
    tokens = ds.config['tokens']

    if ds.config.get('ip_header'):
        client_ip_here = request.headers.get(ds.config.get('ip_header'))
    else:
        client_ip_here = request.client.host

    m = re.match('^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})', client_ip_here)
    if m is None:
        raise HTTPException(status_code=401, detail=f'Cannot parse ip from {client_ip_here!r} (ip_header: {config.get("ip_header")!r}')
    client_ip = m.group(0)
   
    trusted_ips = ds.config['trusted_ips']

    if trusted_ips:
        if not any(map(lambda subnet:  ipaddress.ip_address(client_ip) in ipaddress.ip_network(subnet), trusted_ips)):
            raise HTTPException(status_code=401, detail=f'client IP {client_ip!r} not found in trusted_ips, sorry')

    if credentials not in tokens:
        raise HTTPException(status_code=401, detail=f'Token {credentials!r} not found, sorry')

@router.get('/{project}')
def ds_project_info(project:str, authorization: HTTPBasicCredentials = Depends(auth)):
    project = projects[project]
    tokens = project.config['tokens']

    if authorization.credentials not in tokens:
        raise HTTPException(status_code=401, detail=f'Token {authorization.credentials!r} not found, sorry')

    data = dict()
    data['project'] = project.name
    data['datasets'] = dict()
    for dsname, ds in project._d.items():
        data['datasets'][dsname] = {
            "items": len(ds._data),
            "size": ds.size,
            "status": ds.status,
            "load IP": ds.load_ip,
            "update IP": ds.update_ip,
            "loaded": datetime.datetime.utcfromtimestamp(ds.loaded).strftime('%Y-%m-%d %H:%M:%S')
        }
    
    return data


@router.post('/{project_name}/{ds_name}')
async def ds_post(project_name: str, ds_name: str, request: Request, sq: SearchQuery):
    """
        search for record(s) in project/dataset
    """

    _, ds = get_project_ds(project_name=project_name, ds_name=ds_name)

    if sq.filter:
        sq.expr = make_expr(sq.expr, sq.filter)

    if not sq.expr:
        sq.expr = 'True'

    if sq.op == "get_config":
        return ds.config._d

    start = time.time()

    r = ds.search(sq)

    r['time'] = round(time.time() - start, 3)
    return r


@router.get('/{project}/{dataset}/{search_name}')
def ds_named_search(project:str, dataset: str, search_name: str):
    try:
        ds = projects[project][dataset]
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
    return r

@router.get('/{project}/{dataset}')
def status(project:str, dataset: str):
    try:
        ds = projects[project][dataset]
    except KeyError:
        return HTTPException(status_code=404, detail=f"No such dataset {dataset!r}")

    return ds.status



def client_ip(request: Request, header=None):
    if header:
        client_ip_here = request.headers.get(header)
    else:
        client_ip_here = request.client.host

    m = re.match('^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})', client_ip_here)
    if m is None:
        raise HTTPException(status_code=401, detail=f'Cannot parse ip from {client_ip_here!r} (ip_header: {config.get("ip_header")!r}')
    ip = m.group(0)    
    print("client ip:", ip)
    return ip

def validate_token(request: Request, dsname: str, token: str) -> None:
    # global token
    ds = datasets[dsname]
    client_ip = client_ip(request, config.get('ip_header'))


    tokens_whitelist = config.get('tokens', list()) + ds.vspec.get('tokens', list())

    trusted_ips = config.get('trusted_ips', list()) + ds.vspec.get('trusted_ips', list())

    if trusted_ips:
        if not any(map(lambda subnet:  ipaddress.ip_address(client_ip) in ipaddress.ip_network(subnet), trusted_ips)):
            raise HTTPException(status_code=401, detail=f'client IP {client_ip!r} not found in trusted_ips, sorry')


    if token not in tokens_whitelist:
        raise HTTPException(status_code=401, detail=f'Token {token!r} not found, sorry')


@router.patch('/{project_name}/{ds_name}')
def ds_patch(project_name: str, ds_name: str, sq: SearchQuery, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):

    _, ds = get_project_ds(project_name=project_name, ds_name=ds_name)
    check_ds_token(request, ds, authorization.credentials)
    #check token or raise exception

    start = time.time()
    if sq.op == "delete":        
        r = ds.delete(sq)
    elif sq.op == "update":
        r = ds.update(sq, ip=client_ip(request))
    # elif sq.op == "reload":
    #     r = ds.reload()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown PATCH operation {sq.op!r}")

    r['time'] = round(time.time() - start, 3)
    return r

@router.put('/{project_name}/{ds_name}')
def ds_put(project_name: str, ds_name: str, sq: SearchQuery, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):

    """ INSERT sq.data to dataset """

    project, ds = get_project_ds(project_name=project_name, ds_name=ds_name)
    check_ds_token(request, ds, authorization.credentials)
    #check token or raise exception

    print("now, json data...")
    print(sq.data)

    data = json.loads(sq.data)

    ds.insert(data)

    return PlainTextResponse(f"Inserted record to {ds_name!r} in project {project_name!r} new size: {len(ds)}.")



@router.delete('/{project_name}')
def rm(project_name: str, request: Request, 
        ds_param: DatasetDeleteParameter,
        authorization: HTTPBasicCredentials = Depends(auth)):


    #check token or raise exception
    #check token or raise exception
    # validate_token(request, ds_name, authorization.credentials)
    project = get_project(project_name=project_name)

    try:
        del project[ds_param.name]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Not found dataset {ds_param.name!r} in project {project_name!r}")

    projects.cron()

    return PlainTextResponse(f"Removed dataset {ds_param.name!r} from project {project_name!r}.")



@router.put('/{project_name}')
def put(project_name: str, request: Request, 
        ds_param: DatasetPutParameter,
        authorization: HTTPBasicCredentials = Depends(auth)):

    print(ds_param.name)

    projects.cron()

    #check token or raise exception
    #check token or raise exception
    # validate_token(request, ds_name, authorization.credentials)
    project = get_project(project_name=project_name)

    try:
        dataset = project[ds_param.name]
        ds_config = dataset.config
    except KeyError:
        dataset = Dataset(
            name = ds_param.name, 
            project=project, 
            config_path=None, 
            model=project.model)

        dataset.config = Config(role="dataset", parent=project.config)

    check_ds_token(request, dataset, authorization.credentials)

    dataset.set_dataset(ds_param.ds, size=request.headers['content-length'], ip=client_ip(request))
    project[ds_param.name] = dataset

    return PlainTextResponse(f"Loaded dataset {ds_param.name!r} ({len(ds_param.ds)} records)")
