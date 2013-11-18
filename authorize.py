import urllib, httplib2, base64
import json

from config import Config
config = Config()

username = raw_input("Enter username: ")
password = raw_input("Enter password: ")

http = httplib2.Http()
http.add_credentials(username, password)


auth_header = "Basic "+base64.b64encode("%s:%s" % (username, password))

response, content = http.request(config.get("server_url")+"AuthToken", "POST", headers={"Authorization": auth_header})

print content
data = json.loads(content)

config.set("auth_token", data["data"])
config.set("auth_token_timestamp", data["metadata"]["timestamp"])
