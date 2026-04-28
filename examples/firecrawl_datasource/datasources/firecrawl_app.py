import json
import logging
import time
from collections.abc import Mapping
from typing import Any

import requests
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


class FirecrawlApp:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url or "https://api.firecrawl.dev"
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)

    def _prepare_headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request(
        self,
        method: str,
        url: str,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        retries: int = 3,
        backoff_factor: float = 0.3,
    ) -> Mapping[str, Any] | None:
        if not headers:
            headers = self._prepare_headers()
        for i in range(retries):
            try:
                response = requests.request(
                    method,
                    url,
                    json=data,
                    headers=headers,
                    timeout=30,
                )
                return response.json()
            except requests.exceptions.RequestException:
                if i < retries - 1:
                    time.sleep(backoff_factor * (2**i))
                else:
                    raise
        return None

    def scrape_url(self, url: str, **kwargs: object) -> Mapping[str, Any]:
        endpoint = f"{self.base_url}/v1/scrape"
        data = {"url": url, **kwargs}
        logger.debug("Sent request to %s body=%s", endpoint, data)
        response = self._request("POST", endpoint, data)
        if response is None:
            msg = "Failed to scrape URL after multiple retries"
            raise HTTPError(msg)
        return response

    def map(self, url: str, **kwargs: object) -> Mapping[str, Any]:
        endpoint = f"{self.base_url}/v1/map"
        data = {"url": url, **kwargs}
        logger.debug("Sent request to %s body=%s", endpoint, data)
        response = self._request("POST", endpoint, data)
        if response is None:
            msg = "Failed to perform map after multiple retries"
            raise HTTPError(msg)
        return response

    def crawl_url(
        self,
        url: str,
        wait: bool = True,
        poll_interval: int = 2,
        idempotency_key: str | None = None,
        **kwargs: object,
    ) -> Mapping[str, Any]:
        endpoint = f"{self.base_url}/v1/crawl"
        headers = self._prepare_headers(idempotency_key)
        data = {"url": url, **kwargs}
        logger.debug("Sent request to %s body=%s", endpoint, data)
        response = self._request("POST", endpoint, data, headers)
        if response is None:
            msg = "Failed to initiate crawl after multiple retries"
            raise HTTPError(msg)
        if not response.get("success"):
            msg = f"Failed to crawl: {response.get('error')}"
            raise HTTPError(msg)
        job_id: str = response["id"]
        if wait:
            return self._monitor_job_status(job_id=job_id, poll_interval=poll_interval)
        return response

    def check_crawl_status(self, job_id: str) -> Mapping[str, Any]:
        endpoint = f"{self.base_url}/v1/crawl/{job_id}"
        response = self._request("GET", endpoint)
        if response is None:
            msg = f"Failed to check status for job {job_id} after multiple retries"
            raise HTTPError(
                msg,
            )
        return response

    def cancel_crawl_job(self, job_id: str) -> Mapping[str, Any]:
        endpoint = f"{self.base_url}/v1/crawl/{job_id}"
        response = self._request("DELETE", endpoint)
        if response is None:
            msg = f"Failed to cancel job {job_id} after multiple retries"
            raise HTTPError(msg)
        return response

    def _monitor_job_status(
        self,
        job_id: str,
        poll_interval: int,
    ) -> dict[str, Any]:
        while True:
            status = self.check_crawl_status(job_id)
            if status["status"] == "completed":
                return self.format_crawl_status_response(status["status"], status)
            if status["status"] == "failed":
                msg = f"Job {job_id} failed: {status['error']}"
                raise HTTPError(msg)
            time.sleep(poll_interval)

    def format_crawl_status_response(
        self,
        status: str,
        crawl_status_response: dict[str, Any],
    ) -> dict[str, Any]:
        data = crawl_status_response.get("data", [])
        url_data_list = []
        for item in data:
            if isinstance(item, dict) and "metadata" in item and "markdown" in item:
                url_data = self._extract_common_fields(item)
                url_data_list.append(url_data)
        return {
            "status": status,
            "total": crawl_status_response.get("total"),
            "current": crawl_status_response.get("completed"),
            "data": url_data_list,
        }

    def _extract_common_fields(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": item.get("metadata", {}).get("title"),
            "description": item.get("metadata", {}).get("description"),
            "source_url": item.get("metadata", {}).get("sourceURL"),
            "content": item.get("markdown"),
        }


def get_array_params(tool_parameters: dict[str, Any], key: str) -> list[str] | None:
    param = tool_parameters.get(key)
    if param:
        return param.split(",")
    return None


def get_json_params(tool_parameters: dict[str, Any], key: str) -> object | None:
    param = tool_parameters.get(key)
    if param:
        try:
            # support both single quotes and double quotes
            param = param.replace("'", '"')
            param = json.loads(param)
        except Exception as e:
            msg = f"Invalid {key} format."
            raise ValueError(msg) from e
        return param
    return None
