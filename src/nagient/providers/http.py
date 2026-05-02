from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener, urlopen


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


def _default_urlopen(request: Request, timeout: float = 60.0) -> ResponseContextManager:
    return cast(ResponseContextManager, urlopen(request, timeout=timeout))


def build_proxy_json_http_client(
    proxy_url: str,
    *,
    username: str | None = None,
    password: str | None = None,
    default_timeout: float = 60.0,
) -> JsonHttpClient:
    target_proxy = _proxy_target(proxy_url, username=username, password=password)
    opener = build_opener(
        ProxyHandler(
            {
                "http": target_proxy,
                "https": target_proxy,
            }
        )
    ).open
    return JsonHttpClient(
        opener=cast(UrlopenLike, opener),
        default_timeout=default_timeout,
    )


@dataclass(frozen=True)
class JsonHttpClient:
    opener: UrlopenLike = _default_urlopen
    default_timeout: float = 60.0

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

    def post_form_json(
        self,
        url: str,
        form: Mapping[str, str],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> object:
        request_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            **dict(headers or {}),
        }
        request = Request(
            url,
            data=urlencode(dict(form)).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        return self._open_json(request, timeout or self.default_timeout)

    def post_json(
        self,
        url: str,
        payload: object,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> object:
        request_headers = {
            "Content-Type": "application/json",
            **dict(headers or {}),
        }
        request = Request(
            _merge_query(url, query or {}),
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
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
        except TimeoutError as exc:
            raise ProviderHttpError(
                f"Timed out while waiting for {request.full_url}: {exc}"
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


def _proxy_target(
    proxy_url: str,
    *,
    username: str | None,
    password: str | None,
) -> str:
    split = urlsplit(proxy_url)
    if not split.scheme or not split.netloc:
        raise ValueError("Proxy URL must include a scheme and host.")
    if split.username or split.password:
        return proxy_url

    if username is None or password is None:
        return proxy_url

    host = split.hostname or ""
    port = f":{split.port}" if split.port is not None else ""
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}"
    netloc = f"{credentials}@{host}{port}"
    return urlunsplit(
        (
            split.scheme,
            netloc,
            split.path,
            split.query,
            split.fragment,
        )
    )
