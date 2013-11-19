"""
Crashplan PROe API (limited parts only).

Run from command line to print out all devices sorted by user.
Use authorize.py to obtain authentication token.

"""

import httplib2, json
from config import Config
from instrumentation import *

__all__ = ["Crashplan"]

class Crashplan:
    """
    Basic methods for accessing part of Crashplan PROe API.

    API documents: http://www.crashplan.com/apidocviewer/
    """

    
    def __init__(self):
        self.config = Config()
        self.http = httplib2.Http(disable_ssl_certificate_validation=True)
        self.users = {}
        self.user_mapping = {}
        self.devices = []


    def _get_auth_token(self):
        """ Fetches authentication token from config. 
            Use authorize.py to fetch the token """
        tokens = self.config.get("auth_token")
        if tokens and len(tokens) == 2:
            return "%s-%s" % (tokens[0], tokens[1])
        return False

    def _get_headers(self):
        """ Headers for httplib2 """
        return {"authorization": "token %s" % self._get_auth_token()}

    def _get_url(self, action):
        """ Crashplan URL for specific action """
        return self.config.get("server_url")+action

    def test_authorization(self):
        """ Tests authentication token validity against Crashplan AuthToken API """
        _, content = self.http.request(self._get_url("AuthToken/%s" % 
                                              self._get_auth_token()))
        data = json.loads(content)
        if data.get("data", {}).get("valid") == True:
            return True
        return False

    @timing("crashplan.api.get_users.timing")
    def get_users(self):
        """ Gets list of all users. No proper error handling implemented. 
            Stores the results in self.users list """
        statsd.incr("crashplan.api.get_users.counter")
        for pagenum in range(10):
            _, content = self.http.request(
                 self._get_url("User?active=true&pgSize=200&pgNum=%s" 
                  % pagenum), headers=self._get_headers())
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
        """ Gets list of all users. Stores the results in self.devices 
            list, in addition to returning the items """
        statsd.incr("crashplan.api.get_devices.counter")
        self.devices = []
        for pagenum in range(50):
            url = self._get_url("Computer?active=true&pgSize=200&incBackupUsage=true&incCounts=true&incActivity=true&pgNum=%s" % pagenum)
            _, content = self.http.request(url, headers=self._get_headers())
            statsd.incr("crashplan.api.requests")
            data = json.loads(content)
            computers = data.get("data", {}).get("computers")
            if not computers or len(computers) == 0:
                break
            for device in computers:
                self.devices.append(device)
        return self.devices

    def get_devices_per_user(self):
        """ Gets list of devices for a single user """
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

def main():
    """ Prints devices per user dictionary for testing """
    crashplan = Crashplan()
    print crashplan.get_devices_per_user()

if __name__ == '__main__':
    main()
