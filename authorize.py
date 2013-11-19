"""
Handles fetching Crashplan PROe authorization token.

See http://www.crashplan.com/apidocviewer/#AuthToken for more information.
"""
import base64
import httplib2
import json

from config import Config

__all__ = ["authorize", "interactive_authorize"]

def authorize(username, password):
    """ Fetches authorization token and stores it to Config object. """
    config = Config()
    http = httplib2.Http()
    http.add_credentials(username, password)
    auth_header = "Basic "+base64.b64encode("%s:%s" % (username, password))
    _, content = http.request(config.get("server_url")+"AuthToken", 
                            "POST", headers={"Authorization": auth_header})
    data = json.loads(content)
    config.set("auth_token", data["data"])
    config.set("auth_token_timestamp", data["metadata"]["timestamp"])

def interactive_authorize():
    """ Prompts for Crashplan username and password """
    username = raw_input("Enter username: ")
    password = raw_input("Enter password: ")
    authorize(username, password)

if __name__ == '__main__':
    interactive_authorize()
