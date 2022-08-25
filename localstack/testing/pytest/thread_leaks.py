"""
Sample test to try out this plugin with:

tests.integration.awslambda.test_lambda_integration.TestDynamoDBEventSourceMapping.test_dynamodb_event_source_mapping
"""

import logging
import threading
from typing import Optional

import pytest
from _pytest.config import PytestPluginManager
from _pytest.config.argparsing import Parser
from _pytest.nodes import Item

LOG = logging.getLogger(__file__)


@pytest.hookimpl
def pytest_addoption(parser: Parser, pluginmanager: PytestPluginManager):
    parser.addoption("--check-thread-leaks", action="store_true")
    # TODO: optional filter
    # parser.addoption("--check-thread-leaks-filter", action="store_true")
    # TODO: optional wait time before checking threads after a test call
    # parser.addoption("--check-thread-leaks-wait-seconds", action="store_true")
    # TODO: optional output file (e.g. json report)
    # parser.addoption("--check-thread-leaks-report", action="store_true")
    # TODO: custom whitelist - resets the default one
    # parser.addoption("--check-thread-leaks-whitelist", action="store_true")


def get_running_threads() -> set[str]:
    return {t.name for t in threading.enumerate()}


DEFAULT_WHITELIST = {
    "MainThread",
    "startup_monitor",
    "watchdog",
    "asgi_gw",
    "asyncio_",
    "aws-api-",
    "start_edge",
    "HypercornServer",
}

# for a simple report at the end of the whole pytest session
COLLECT_ALL = set()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: Item, nextitem: Optional[Item]):

    before_test = get_running_threads()
    COLLECT_ALL.update(before_test)

    yield

    # TODO: optional
    # time.sleep(2)
    after_test = get_running_threads()
    COLLECT_ALL.update(after_test)
    # determine which threads are new and should have been killed

    new_threads = after_test.difference(before_test)
    filtered_new_threads = new_threads.symmetric_difference(DEFAULT_WHITELIST)
    for t in filtered_new_threads:
        print(f"thread leaked: {t}")
