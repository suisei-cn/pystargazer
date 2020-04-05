import json
from typing import List


class Credential:
    def __init__(self, fp: str):
        with open(fp, mode="r") as f:
            self.credentials = json.load(f)
        self.twitter_token: str = self.credentials["twitter"]
        self.youtube_tokens: List[str] = self.credentials["youtube"]
        self.youtube_callback: str = self.credentials["youtube_callback"]
