from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


class ProviderHttpError(RuntimeError):
    pass


class ResponseReader(Protocol):
    def read(self) -> bytes: ...


class ResponseContextManager(Protocol):
    def __enter__(self) -> ResponseReader: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> object: ...


class UrlopenLike(Protocol):
    def __call__(
        self,
        request: Request,
        timeout: float = ...,
    ) -> ResponseContextManager: ...


@dataclass(frozen=True)
class JsonHttpClient:
    opener: UrlopenLike = urlopen
    default_timeout: float = 15.0

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> object:
        target_url = _merge_query(url, query or {})
        request = Request(target_url, headers=dict(headers or {}), method="GET")
        return self._open_json(request, timeout or self.default_timeout)

    def _open_json(self, request: Request, timeout: float) -> object:
        try:
            with self.opener(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            raise ProviderHttpError(
                f"HTTP {exc.code} from {request.full_url}: {body}"
            ) from exc
        except URLError as exc:
            raise ProviderHttpError(
                f"Failed to reach {request.full_url}: {exc.reason}"
            ) from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ProviderHttpError(
                f"Expected JSON response from {request.full_url}, received invalid payload."
            ) from exc


def _merge_query(url: str, query: Mapping[str, str]) -> str:
    if not query:
        return url
    split = urlsplit(url)
    current_query = dict(parse_qsl(split.query, keep_blank_values=True))
    current_query.update(query)
    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(current_query),
            split.fragment,
        )
    )
