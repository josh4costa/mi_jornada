from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional
from datetime import datetime, date

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
