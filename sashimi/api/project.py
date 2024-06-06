import time
import datetime
import os
import json
import yaml

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security.http import HTTPBearer, HTTPBasicCredentials
from fastapi.responses import PlainTextResponse, FileResponse

from pydantic import BaseModel, validator

from ..prettyjson import PrettyJSONResponse
from ..project import Project, projects
from ..dataset import Dataset
from ..config import Config
from .params import DatasetDeleteParameter, DatasetPutParameter, SearchQuery
from .utils import make_expr, get_project, get_project_ds, check_token, check_permission, client_ip
from ..exception import ProjectExistsException

router = APIRouter()
auth = HTTPBearer()


class NewProject(BaseModel):
    name: str

@router.post('/')
def new_project(np: NewProject, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):
    check_token(request=request, config=projects.config, credentials=authorization.credentials )
    try:
        key = projects.create(np.name)
    except ProjectExistsException as e:
        raise HTTPException(status_code=409, detail=str(e))
    print("OK")
    
    return dict(apikey=key)

class ProjectOp(BaseModel):
    op: str

@router.post('/{project_name}')
def project_op(project_name: str, request: Request, op: ProjectOp, 
                authorization: HTTPBasicCredentials = Depends(auth)):
    check_token(request=request, config=projects.config, credentials=authorization.credentials )
    project = get_project(project_name=project_name)
    if op.op == 'new-key':
        apikey = project.new_key()
        return dict(apikey=apikey)


@router.get('/{project_name}')
def ds_project_info(project_name:str, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):

    project = get_project(project_name)

    check_token(request=request, config=project.config, credentials=authorization.credentials )

    #if authorization.credentials not in tokens:
    #    raise HTTPException(status_code=401, detail=f'Token {authorization.credentials!r} not found, sorry')

    data = dict()
    data['project'] = project.name

    if project.is_sandbox():
        data['sandbox'] = True

    data['datasets'] = dict()
    for dsname, ds in project._d.items():
        data['datasets'][dsname] = {
            "items": len(ds._data),
            "size": ds.size,
            "status": ds.status,
            "local": ds.is_local(),
            "update IP": ds.update_ip,            
            "loaded": datetime.datetime.fromtimestamp(ds.loaded, timestamp=datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')
        }

        if project.is_sandbox():
            data['datasets'][dsname]['secret'] = bool(ds.secret)
    
    return data


@router.get('/{project_name}/_config')
async def project_get_config(project_name: str, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):
    """
        get project config
    """

    project = get_project(project_name=project_name)

    check_token(request=request, config=project.config, credentials=authorization.credentials)
    check_permission(project, ds=None, op='getpconf')

    if not os.path.exists(project.get_config_path()):
        raise HTTPException(status_code=404, detail=f'No config set for {project_name}')

    return FileResponse(project.get_config_path())

    
@router.post('/{project_name}/_config')
async def project_post_config(project_name: str, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):
    """
        post project config
    """

    project = get_project(project_name=project_name)


    check_token(request=request, config=project.config, credentials=authorization.credentials)
    check_permission(project, ds=None, op='setpconf')

    rawconfig = await request.body()
    try:
        yaml.safe_load(rawconfig)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f'YAML error: {str(e)}')

    with open(project.get_config_path(), "wb") as fh:
        fh.write(rawconfig)

    project.read_config()

    return PlainTextResponse(f'Saved config for {project_name}')



@router.get('/{project_name}/{ds_name}/_config')
async def ds_get_config(project_name: str, ds_name: str, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):
    """
        get dataset config
    """

    _, ds = get_project_ds(project_name=project_name, ds_name=ds_name)


    check_token(request=request, config=ds.config, credentials=authorization.credentials)

    if not os.path.exists(ds.get_config_path()):
        raise HTTPException(status_code=404, detail=f'No config set for {project_name} / {ds_name}')

    return FileResponse(ds.get_config_path())
    
@router.post('/{project_name}/{ds_name}/_config')
async def ds_post_config(project_name: str, ds_name: str, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):
    """
        post dataset config
    """
    project, ds = get_project_ds(project_name=project_name, ds_name=ds_name)

    check_token(request=request, config=ds.config, credentials=authorization.credentials)


    rawconfig = await request.body()
    try:
        yaml.safe_load(rawconfig)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f'YAML error: {str(e)}')

    with open(ds.get_config_path(), "wb") as fh:
        fh.write(rawconfig)

    ds.read_config()

    return PlainTextResponse(f'Saved config for {project_name} / {ds_name}')


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


@router.patch('/{project_name}/{ds_name}')
def ds_patch(project_name: str, ds_name: str, sq: SearchQuery, request: Request, authorization: HTTPBasicCredentials = Depends(auth)):

    project, ds = get_project_ds(project_name=project_name, ds_name=ds_name)
    check_token(request, config=ds.config, credentials=authorization.credentials)
    #check token or raise exception

    check_permission(project, ds=None, op=sq.op)


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
    check_token(request, config=ds.config, credentials=authorization.credentials)
    #check token or raise exception

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
    project, ds = get_project_ds(project_name=project_name, ds_name=ds_param.name)

    check_token(request, ds.config, authorization.credentials)
    check_permission(project, ds=ds, op="rm")

    # rm config
    if ds.get_config_path() and os.path.exists(ds.get_config_path()):
        os.unlink(ds.get_config_path())

    # rm dataset
    if ds.path and os.path.exists(ds.path):
        os.unlink(ds.path)

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

    projects.cron()

    #check token or raise exception
    #check token or raise exception
    # validate_token(request, ds_name, authorization.credentials)
    project = get_project(project_name=project_name)

    try:
        dataset = project[ds_param.name]
        config = dataset.config
            
    except KeyError:
        dataset = None
        config = project.config
    

    check_token(request, config, authorization.credentials)
    check_permission(project, ds=dataset, op="upload")

    if dataset is None:
        dataset = Dataset(
            name = ds_param.name, 
            project=project,
            model=project.model)

        dataset.config = Config(role="dataset", parent=project.config)


    if project.is_sandbox() and dataset.secret:
        if ds_param.secret != dataset.secret:
            raise HTTPException(status_code=401, 
                                detail=f'secret mismatch')




    if project.is_sandbox():
        secret = ds_param.secret
    else:
        secret = None

    dataset.set_dataset(ds_param.ds, ip=client_ip(request), secret=secret)
    project[ds_param.name] = dataset

    # save dataset (if not sandbox)
    if not project.is_sandbox():
        with open(dataset.get_dataset_path(), "w") as fh:
            json.dump(ds_param.ds, fh)

    return PlainTextResponse(f"Loaded dataset {ds_param.name!r} ({len(ds_param.ds)} records)")
