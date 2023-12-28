from fastapi import APIRouter, Request
from ..prettyjson import PrettyJSONResponse
from ..project import projects
from .. import __version__, started, docker_build_time

router = APIRouter()

@router.get("/", response_class=PrettyJSONResponse)
def read_root(request: Request):

    return {
        "Description": "ExactAPI :: Fast and secure search inside structured data",
        "Repo URL": "https://github.com/yaroslaff/exact",
        "version": __version__,
        "started": started,
        "docker_build_time": docker_build_time,
        "client_host": request.client.host,
        # "headers": request.headers
        "tenants": str(projects)
        }
