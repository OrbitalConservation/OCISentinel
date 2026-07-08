from __future__ import annotations

import warnings

import requests
from typing import Generator
from urllib3.exceptions import InsecureRequestWarning

from .models import TrackedObject
from config import CELESTRAK_DATA_GROUPS


class CelesTrakFetcher:
    def __init__(self, verify_ssl: bool = True) -> None:
        self.data_groups = CELESTRAK_DATA_GROUPS
        self.verify_ssl = verify_ssl

    def build_groups_to_fetch(self, category: str = "all", allowed_subgroups: list[str] | None = None) -> dict[str, str]:
        allowed_set = set(allowed_subgroups or [])
        def _is_allowed(subgroup: str) -> bool:
            return not allowed_set or subgroup in allowed_set

        groups_to_fetch: dict[str, str] = {}
        if category == "all":
            for top, submap in self.data_groups.items():
                for subkey, url in submap.items():
                    if _is_allowed(subkey):
                        groups_to_fetch[subkey] = url
        else:
            if category in self.data_groups:
                for subkey, url in self.data_groups[category].items():
                    if _is_allowed(subkey):
                        groups_to_fetch[subkey] = url
            else:
                for top, submap in self.data_groups.items():
                    if category in submap and _is_allowed(category):
                        groups_to_fetch[category] = submap[category]
                        break

        return groups_to_fetch

    def fetch_tle(self, category: str = "all", allowed_subgroups: list[str] | None = None) -> list[TrackedObject]:
        objects: list[TrackedObject] = []
        groups_to_fetch = self.build_groups_to_fetch(category, allowed_subgroups)

        for subgroup_key, url in groups_to_fetch.items():
            with warnings.catch_warnings():
                if not self.verify_ssl:
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                response = requests.get(url, timeout=20, verify=self.verify_ssl)
            response.raise_for_status()
            payload = response.json()
            for item in payload:
                try:
                    objects.append(TrackedObject.from_json(item, subgroup_key))
                except ValueError:
                    continue

        return objects

    def _parse_tle(self, text: str, category: str) -> Generator[TrackedObject, None, None]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index in range(0, len(lines) - 2, 3):
            name = lines[index]
            line1 = lines[index + 1]
            line2 = lines[index + 2]
            try:
                obj = TrackedObject.from_tle(name, line1, line2, category)
            except ValueError:
                continue
            yield obj
