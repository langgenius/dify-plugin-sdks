# start openai mock server
import threading

from tests.__mock_server.openai import openai_server_mock

openai_server = threading.Thread(target=openai_server_mock, daemon=True)
openai_server.start()
openai_server.join()
