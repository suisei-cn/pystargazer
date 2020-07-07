from typing import List
from dataclasses import dataclass


@dataclass
class Tweet:
    text: str
    photos: List[str]
    link: str
    is_rt: bool