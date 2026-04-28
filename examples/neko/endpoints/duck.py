import contextlib
import time
from collections.abc import Generator, Mapping

from werkzeug import Request, Response

from dify_plugin import Endpoint

text = (
    "<pre>\n"
    "                   _____\n"
    "                  /  __  \\\n"
    " / \\ ----/ \\     / /    \\ \\\n"
    "                 \\/      \\ \\\n"
    "  < >   < >              | |\n"
    "\\     ^     /------------| |     <-- It's Yeuoly's cat! you can "
    "touch her if you want ~\n"
    "  \\  -^-  /        ____    |       (but it's not recommended, "
    "she might bite, have a nice day!)\n"
    " |   ---          /    \\   |\n"
    " |                      |  |\n"
    "  \\--  \\         /------|  /\n"
    "   --------------_________/\n"
    "</pre>\n"
)


class Duck(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.
        """

        def generator() -> Generator[str, None, None]:
            try:
                visitors = int(self.session.storage.get("visitors").decode())
            except Exception:
                visitors = 0

            visitors += 1

            with contextlib.suppress(Exception):
                self.session.storage.set("visitors", str(visitors).encode())

            yield f"it's your {visitors} time visit this page! <br>"

            for i in range(0, len(text), 2):
                time.sleep(0.05)
                yield text[i : i + 2]

        return Response(generator(), status=200, content_type="text/html")
