from dataclasses import dataclass
from typing import Optional


@dataclass
class ReleaseItem:
    id: str
    title: str
    os_type: str
    version: str
    build: Optional[str]
    release_type: str
    link: str
    pub_date: str
