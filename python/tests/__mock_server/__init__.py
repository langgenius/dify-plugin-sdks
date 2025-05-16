# start openai mock server
from tests.__mock_server.openai import openai_server_mock

import threading

openai_server = threading.Thread(target=openai_server_mock, daemon=True)
openai_server.start()
openai_server.join()
