import re
import ipaddress

from fastapi import Request, HTTPException


from ..project import Project, projects
from ..dataset import Dataset



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


def client_ip(request: Request, header=None):
    if header:
        client_ip_here = request.headers.get(header)
    else:
        client_ip_here = request.client.host

    m = re.match('^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})', client_ip_here)
    if m is None:
        raise HTTPException(status_code=401, detail=f'Cannot parse ip from {client_ip_here!r} (ip_header: {config.get("ip_header")!r}')
    ip = m.group(0)    
    return ip

def UNUSED_validate_token(request: Request, dsname: str, token: str) -> None:
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
