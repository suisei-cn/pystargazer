from typing import Tuple
from distutils.util import strtobool as _strtobool


def compare_dict(d1, d2) -> Tuple[dict, dict, dict]:
    set_1 = set(d1)
    set_2 = set(d2)
    added = {k: d2[k] for k in set_2 - set_1}
    removed = {k: d1[k] for k in set_1 - set_2}
    updated = {k: (d1[k], d2[k]) for k in set_1 & set_2 if d1[k] != d2[k]}
    return added, removed, updated


def strtobool(val: str, default: bool = False) -> bool:
    try:
        return _strtobool(val)
    except (AttributeError, ValueError):
        return default


def get_option(app, scope: str):
    async def func(key: str, default: bool = False):
        try:
            return strtobool((await app.configs.get(scope)).value.get(key), default)
        except KeyError:
            return default
    return func
