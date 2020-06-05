from dataclasses import dataclass
from enum import IntEnum
from typing import List


class DynamicType(IntEnum):
    FORWARD = 1
    PHOTO = 2
    PLAIN = 4
    VIDEO = 8
    UNKNOWN = -1

    @classmethod
    def from_int(cls, val: int):
        if val not in [1, 2, 4, 8]:
            return cls.UNKNOWN
        return cls(val)

    def to_event(self) -> str:
        event_map = {
            1: "bili_rt_dyn",
            2: "bili_img_dyn",
            4: "bili_plain_dyn",
            8: "bili_video",
            -1: "bili_unknown"
        }
        return event_map[self.value]


@dataclass
class Dynamic:
    type: DynamicType
    text: str
    photos: List[str]
    link: str
