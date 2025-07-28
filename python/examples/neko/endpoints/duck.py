import contextlib
import time
from collections.abc import Mapping

from werkzeug import Request, Response

from shai_plugin import Endpoint

text = """<pre>
                   _____
                  /  __  \\
 / \\ ----/ \\     / /    \\ \\
                 \\/      \\ \\
  < >   < >              | |
\\     ^     /------------| |     <-- It's Yeuoly's cat! you can touch her if you want ~
  \\  -^-  /        ____    |       (but it's not recommended, she might bite, have a nice day!)
 |   ---          /    \\   |
 |                      |  |
  \\--  \\         /------|  /
   --------------_________/
</pre>
"""


class Duck(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.
        """

        def generator():
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
