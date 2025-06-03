from typing import List, Optional

from openg2p_g2pconnect_common_lib.schemas import Request, SyncResponse
from pydantic import BaseModel


class AgencyAllocationDetail(BaseModel):
    agency_code: Optional[str] = None
    allocated: Optional[bool] = None


class AgencyAllocationRequest(Request):
    message: List[str]


class AgencyAllocationResponse(SyncResponse):
    message: Optional[List[AgencyAllocationDetail]] = None


class WarehouseAllocationDetail(BaseModel):
    warehouse_code: Optional[str] = None
    allocated: Optional[bool] = None


class WarehouseAllocationRequest(Request):
    message: List[str]


class WarehouseAllocationResponse(SyncResponse):
    message: Optional[List[WarehouseAllocationDetail]] = None
