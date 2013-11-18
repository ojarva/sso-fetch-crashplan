import urllib, httplib2, json
from config import Config
from pprint import pprint
from instrumentation import *

class Crashplan:
    def __init__(self):
        self.config = Config()
        self.http = httplib2.Http(disable_ssl_certificate_validation=True)
        self.users = {}
        self.user_mapping = {}
        self.devices = []


    def _get_auth_token(self):
        tokens = self.config.get("auth_token")
        if tokens and len(tokens) == 2:
            return "%s-%s" % (tokens[0], tokens[1])
        return False

    def _get_headers(self):
        return {"authorization": "token %s" % self._get_auth_token()}

    def _get_url(self, action):
        return self.config.get("server_url")+action

    def test_authorization(self):
        response, content = self.http.request(self._get_url("AuthToken/%s" % self._get_auth_token()))
        data = json.loads(content)
        if data.get("data", {}).get("valid") == True:
            return True
        return False

    @timing("crashplan.api.get_users.timing")
    def get_users(self):
        statsd.incr("crashplan.api.get_users.counter")
        for x in range(10):
            response, content = self.http.request(self._get_url("User?active=true&pgSize=200&pgNum=%s" % x), headers=self._get_headers())
            statsd.incr("crashplan.api.requests")
            data = json.loads(content)
            users = data.get("data", {}).get("users", [])
            if len(users) == 0:
                break
            for user in users:
                self.users[user["username"]] = user
                self.user_mapping[user["userId"]] = user["username"]

        return self.users

    @timing("crashplan.api.get_devices.timing")
    def get_devices(self):
        statsd.incr("crashplan.api.get_devices.counter")
        self.devices = []
        for x in range(50):
            response, content = self.http.request(self._get_url("Computer?active=true&pgSize=200&incBackupUsage=true&incCounts=true&incActivity=true&pgNum=%s" % x), headers=self._get_headers())
            statsd.incr("crashplan.api.requests")
            data = json.loads(content)
            computers = data.get("data", {}).get("computers")
            if not computers or len(computers) == 0:
                break
            for device in computers:
                self.devices.append(device)
        return self.devices

    def get_devices_per_user(self):
        if len(self.users) == 0:
            self.get_users()
        if len(self.devices) == 0:
            self.get_devices()
        for device in self.devices:
            username_for_device = self.user_mapping[device["userId"]]
            if "devices" not in self.users[username_for_device]:
                self.users[username_for_device]["devices"] = []
            if device not in self.users[username_for_device]["devices"]:
                self.users[username_for_device]["devices"].append(device)
        return self.users

if __name__ == '__main__':
    crashplan = Crashplan()
    print crashplan.get_devices_per_user()


