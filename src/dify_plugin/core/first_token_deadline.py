"""Bound how long a streamed LLM invocation may take to produce its first token.

``LargeLanguageModel.invoke`` is a generator function, so its whole body -- parameter
validation, the provider request, and the first chunk -- runs on the first ``next()``.
Guarding that single pull therefore also covers providers that issue their HTTP request
eagerly rather than lazily, which is the common shape and the one a guard placed further
in would miss. The budget is dropped as soon as a chunk carrying generated content
arrives, so gaps between later tokens are never bounded by it.

``gevent.Timeout`` unwinds the provider's own context managers, which releases the
upstream connection instead of leaving it in flight -- the precondition for the caller
retrying without doubling up on an already struggling provider. Outside a
gevent-patched runtime there is nothing that can interrupt a blocking read, so the
budget is ignored and the caller's own timeout stays the backstop.
"""

import logging
import time
from collections.abc import Generator

import gevent

from dify_plugin.core.gevent_runtime import interruptible
from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.errors.model import FirstTokenTimeoutError

logger = logging.getLogger(__name__)


def _carries_first_token(chunk: object) -> bool:
    # Only the chunk type the SDK builds can be inspected; anything else is taken at
    # face value so a caller with a different payload keeps the old single-pull rule.
    if isinstance(chunk, LLMResultChunk):
        return chunk.carries_first_token()
    return True


def guard_first_token[T](
    stream: Generator[T, None, None],
    first_token_timeout: float | None,
) -> Generator[T, None, None]:
    """Yield from ``stream``, bounding only the wait for its first token."""
    if not first_token_timeout or first_token_timeout <= 0:
        yield from stream
        return

    if not interruptible():
        logger.warning(
            "Ignoring a %ss first-token timeout: a blocking read cannot be "
            "interrupted outside a gevent runtime.",
            first_token_timeout,
        )
        yield from stream
        return

    msg = f"The first token was not received within {first_token_timeout}s."
    deadline = time.monotonic() + first_token_timeout

    while True:
        # Re-armed per pull rather than held across the yield below: while this
        # generator is suspended the timer would belong to whoever is consuming it,
        # and would fire inside their frame instead of ours.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FirstTokenTimeoutError(msg)

        timeout = gevent.Timeout(remaining)
        timeout.start()
        try:
            chunk = next(stream)
        except StopIteration:
            return
        except gevent.Timeout as raised:
            if raised is not timeout:
                raise
            raise FirstTokenTimeoutError(msg) from None
        finally:
            timeout.close()

        yield chunk
        if _carries_first_token(chunk):
            break

    yield from stream
