import json
import os


class FileDict(dict):
    def __init__(self, fn):
        super().__init__()

        if not os.path.exists(fn):
            with open(fn, mode="w"):
                pass

        self.f = open(fn, mode="r+")

        try:
            tmp_dict = json.load(self.f)
        except json.JSONDecodeError:
            return

        if isinstance(tmp_dict, dict):
            self.update(tmp_dict)

    def save(self):
        self.f.seek(0)
        json.dump(dict(self), self.f, ensure_ascii=False)
        self.f.truncate()
        self.f.flush()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.save()

    def clear(self) -> None:
        super().clear()
        self.save()

    def __delitem__(self, key):
        super().__delitem__(key)
        self.save()

    def update(self, *args, **kwargs) -> None:
        super().update(*args, **kwargs)
        self.save()

    def pop(self, k):
        r = super().pop(k)
        self.save()
        return r
