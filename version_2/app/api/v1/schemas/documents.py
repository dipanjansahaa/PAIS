from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_type: str
    file_name: str | None
    mime_type: str | None
    project_id: uuid.UUID | None