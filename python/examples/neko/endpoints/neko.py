import contextlib
from collections.abc import Mapping

from flask import Flask, render_template_string
from werkzeug import Request, Response

from shai_plugin import Endpoint

app = Flask(__name__)


class NekoEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        try:
            visitors = int(self.session.storage.get("visitors").decode())
        except Exception:
            visitors = 0

        visitors += 1

        with contextlib.suppress(Exception):
            self.session.storage.set("visitors", str(visitors).encode())

        # align the string length of visitors to the length of 4
        visitors = str(visitors).rjust(4)

        ascii_art = f"""
⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛⬛️⬜️⬜️⬜️⬜️⬜⬜️⬜️️
🟥🟥⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️🟥🟥🟥🟥🟥🟥🟥🟥⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬛🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧⬛️⬜️⬜️⬜️⬜️⬜⬜️️
🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥⬛️🥧🥧🥧💟💟💟💟💟💟💟💟💟💟💟💟💟🥧🥧🥧⬛️⬜️⬜️⬜️⬜⬜️️
🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥⬛️🥧🥧💟💟💟💟💟💟🍓💟💟🍓💟💟💟💟💟🥧🥧⬛️⬜️⬜️⬜️⬜️⬜️️
🟧🟧🟥🟥🟥🟥🟥🟥🟥🟥🟧🟧🟧🟧🟧🟧🟧🟧🟥🟥🟥🟥🟥🟥🟥⬛🥧💟💟🍓💟💟💟💟💟💟💟💟💟💟💟💟💟💟🥧⬛️⬜️⬜️⬜️⬜⬜️️
🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧⬛️🥧💟💟💟💟💟💟💟💟💟💟⬛️⬛️💟💟🍓💟💟🥧⬛️⬜️⬛️️⬛️️⬜⬜️️
🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧⬛️🥧💟💟💟💟💟💟💟💟💟⬛️🌫🌫⬛💟💟💟💟🥧⬛️⬛️🌫🌫⬛⬜️️
🟨🟨🟧🟧🟧🟧🟧🟧🟧🟧{visitors}🟨🟨🟨🟨🟧⬛️⬛️⬛️⬛️🟧🟧⬛️🥧💟💟💟💟💟💟🍓💟💟⬛️🌫🌫🌫⬛💟💟💟🥧⬛️🌫🌫🌫⬛⬜️️
🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨⬛️🌫🌫⬛️⬛️🟧⬛️🥧💟💟💟💟💟💟💟💟💟⬛️🌫🌫🌫🌫⬛️⬛️⬛️⬛️🌫🌫🌫🌫⬛⬜️️
🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨⬛️⬛️🌫🌫⬛️⬛️⬛️🥧💟💟💟🍓💟💟💟💟💟⬛️🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫⬛⬜️️
🟩🟩🟨🟨🟨🟨🟨🟨🟨🟨🟩🟩🟩🟩🟩🟩🟩🟩🟨🟨⬛⬛️🌫🌫⬛️⬛️🥧💟💟💟💟💟💟💟🍓⬛️🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫⬛️
🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️🌫🌫⬛️🥧💟🍓💟💟💟💟💟💟⬛️🌫🌫🌫⬜️⬛️🌫🌫🌫🌫🌫⬜️⬛️🌫🌫⬛️
️🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩⬛️⬛️⬛️⬛️🥧💟💟💟💟💟💟💟💟⬛️🌫🌫🌫⬛️⬛️🌫🌫🌫⬛️🌫⬛️⬛️🌫🌫⬛️
🟦🟦🟩🟩🟩🟩🟩🟩🟩🟩🟦🟦🟦🟦🟦🟦🟦🟦🟩🟩🟩🟩🟩🟩⬛️⬛️🥧💟💟💟💟💟🍓💟💟⬛🌫🟥🟥🌫🌫🌫🌫🌫🌫🌫🌫🌫🟥🟥⬛️
🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦⬛️🥧🥧💟🍓💟💟💟💟💟⬛️🌫🟥🟥🌫⬛️🌫🌫⬛️🌫🌫⬛️🌫🟥🟥⬛️
🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦⬛️🥧🥧🥧💟💟💟💟💟💟💟⬛️🌫🌫🌫⬛️⬛️⬛️⬛️⬛️⬛️⬛️🌫🌫⬛️⬜️
🟪🟪🟦🟦🟦🟦🟦🟦🟦🟦🟪🟪🟪🟪🟪🟪🟪🟪🟦🟦🟦🟦🟦🟦⬛️⬛️⬛️🥧🥧🥧🥧🥧🥧🥧🥧🥧🥧⬛️🌫🌫🌫🌫🌫🌫🌫🌫🌫🌫⬛️⬜️⬜️
🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪⬛️🌫🌫🌫⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬛️⬜️⬜️⬜️
🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪⬛️🌫🌫⬛️⬛️⬜️⬛️🌫🌫⬛️⬜️⬜️⬜️⬜️⬜️⬛️🌫🌫⬛️⬜️⬛️🌫🌫⬛️⬜️⬜️⬜️⬜️
⬜️⬜️🟪🟪🟪🟪🟪🟪🟪🟪⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️🟪🟪🟪🟪🟪⬛️⬛️⬛️⬛⬜️⬜️⬛️⬛️⬛️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬛️⬛️⬛️⬜️⬜️⬛️⬛️⬜️⬜️⬜️⬜️⬜️️
        """
        ascii_art_lines = ascii_art.strip().split("\n")
        with app.app_context():
            return Response(
                render_template_string(
                    """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                background-color: black;
                color: white;
                overflow: hidden;
                margin: 0;
                padding: 0;
            }
            #ascii-art {
                font-family: monospace;
                white-space: pre;
                position: absolute;
                top: 50%;
                transform: translateY(-50%);
                display: inline-block;
                font-size: 16px;
                line-height: 1;
            }
        </style>
    </head>
    <body>
        <div id="ascii-art"></div>
        <script>
            var asciiArtLines = {{ ascii_art_lines | tojson }};
            var asciiArtDiv = document.getElementById("ascii-art");
            var index = 0;
            function displayNextLine() {
                if (index < asciiArtLines.length) {
                    var line = asciiArtLines[index];
                    var lineElement = document.createElement("div");
                    lineElement.innerHTML = line;
                    asciiArtDiv.appendChild(lineElement);
                    index++;
                    setTimeout(displayNextLine, 100);
                } else {
                    animateCat();
                }
            }
            function animateCat() {
                var pos = 0;
                var screenWidth = window.innerWidth;
                var catWidth = asciiArtDiv.offsetWidth;
                function move() {
                    asciiArtDiv.style.left = pos + "px";
                    pos += 2;
                    if (pos > screenWidth) {
                        pos = -catWidth;
                    }
                    requestAnimationFrame(move);
                }
                move();
            }
            displayNextLine();
        </script>
    </body>
    </html>
        """,
                    ascii_art_lines=ascii_art_lines,
                ),
                status=200,
                content_type="text/html",
            )
