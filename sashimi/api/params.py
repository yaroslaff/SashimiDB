
import string
from typing import Optional, Union, List, Dict
from typing_extensions import Annotated
from pydantic import BaseModel, StrictInt, StrictFloat, StrictStr, validator, Field



class DatasetDeleteParameter(BaseModel):
    name: str




class DatasetPutParameter(BaseModel):
    ds: list = Field(description='dataset itself, list of dicts')
    name: str = Field(description='name of dataset')
    secret: Optional[str] = Field(default=None, description='Secret for dataset (only in sandbox)')

    @validator('name')
    def valid_name(cls, name):

        if name.startswith('_'):
            raise ValueError('Invalid dataset name (must not start with underscode)')

        ds_name_allowed = set(
            string.ascii_letters 
            + string.digits 
            + '_-.')
        
        if not set(name) <= ds_name_allowed:
            raise ValueError("Invalid dataset name (invalid chars)")
        return name

class SearchQuery(BaseModel):
    expr: Optional[str] = None
    filter: Dict[str, Union[int, float, str, List] ] = None
    op: str = None
    sort: str = None
    reverse: bool = False
    token: str = None
    limit: int = None
    offset: int = 0
    fields: list[str] = None
    aggregate: list[str] = None
    discard: bool = False
    
    # JSON-encoded data for INSERT
    data: str = None
    
    # field to update
    # update_field: str = None
    
    # update: dict of fields to set on update
    update: dict = None
