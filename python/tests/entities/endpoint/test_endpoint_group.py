import os

import yaml

os.environ["GEVENT_SUPPORT"] = "true"

from dify_plugin.entities.endpoint import EndpointProviderConfiguration


def test_load_endpoint_group():
    endpoint_group = EndpointProviderConfiguration(
        **yaml.safe_load(
            """endpoints:
  - path: /test
    method: GET
    hidden: false
    extra:
      python:
        source: test.py
        """
        )
    )

    assert endpoint_group.endpoints[0].path == "/test"
    assert endpoint_group.endpoints[0].method == "GET"
    assert endpoint_group.endpoints[0].hidden is False
    assert endpoint_group.endpoints[0].extra.python.source == "test.py"


def test_load_endpoint_from_file(monkeypatch):
    monkeypatch.setattr(
        EndpointProviderConfiguration,
        "_load_yaml_file",
        lambda x: {
            "path": "/test",
            "method": "GET",
            "hidden": False,
            "extra": {"python": {"source": "test.py"}},
        },
    )

    endpoint_group = EndpointProviderConfiguration(
        **yaml.safe_load(
            """endpoints:
  - "endpoints/aaa.yaml"
            """
        )
    )

    assert endpoint_group.endpoints[0].path == "/test"
    assert endpoint_group.endpoints[0].method == "GET"
    assert endpoint_group.endpoints[0].hidden is False
    assert endpoint_group.endpoints[0].extra.python.source == "test.py"
