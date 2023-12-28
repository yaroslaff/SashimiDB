from typing import Optional, Union, List, Dict
from typing_extensions import Annotated
from pydantic import BaseModel, StrictInt, StrictFloat, StrictStr

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
    update_field: str = None
    
    # update_expr: Expression to set new value in update
    update_data: str =None
