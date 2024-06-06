#!/usr/bin/env python

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.http import HTTPBearer, HTTPBasicCredentials


from pydantic import BaseModel, StrictInt, StrictFloat, StrictStr
import os
import sys
import requests
import json
import time
import typing
import re
import ipaddress
import yaml
from yaml.loader import SafeLoader
from pprint import pprint
import datetime 

from dotenv import load_dotenv

from sqlalchemy import create_engine
import sqlalchemy as sa

from evalidate import Expr, EvalException, base_eval_model, EvalModel

from sashimi.dataset import Dataset
from sashimi.project import projects
from sashimi.config import Config
from sashimi.api.query import router as index_router
from sashimi.api.project import router as project_router


### Global variables ###

load_dotenv()

# FastAPI
app = FastAPI()
auth = HTTPBearer()


# def_limit = int(os.getenv('EXACT_LIMIT', '100'))

args = None

config_path = None
config = None
datasets : dict[str, Dataset] = dict()

last_printed = 0

# for uvicorn
reload_dirs=['exact']



def get_evalidate_model(config: dict) -> EvalModel:
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

    return model



def init():
    global config, def_limit, docker_build_time, projects

    # config = get_config()

    config = Config(os.environ.get("SASHIMI_CONFIG", find_config()), role="master")

    print(config)

    model = get_evalidate_model(config)
    projects.config = config
    if 'projects' in config:
        projects.read(config['projects'], model=model)

    print("End of main")

    # print(json.dumps(config, indent=4))

def find_config():
    locations = [
        'sashimi.yml',
        '/data/etc/sashimi.yml',
        '/etc/sashimi.yml',
    ]

    locations = [ p for p in locations if os.path.exists(p) ]

    if not locations:
        return None
    
    return locations[0]


def main():
    app.include_router(index_router)
    app.include_router(prefix="/ds", router=project_router)

    init()

main()
