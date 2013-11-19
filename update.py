"""
Processes crashplan device data to SSO service
"""

from crashplan import Crashplan
import redis
from config import Config
import json
import datetime
from instrumentation import *
import _mysql


class CrashplanUpdate:
    """ .update() fetches all devices and processes all sessions """

    def __init__(self):
        self.config = Config()
        self.crashplan = Crashplan()
        self._db = None
        self.redis = redis.Redis(host=self.config.get("redis-hostname"), 
           port=self.config.get("redis-port"), db=self.config.get("redis-db"))

    @property
    def db(self):
        """ Returns (cached) mysql instance """
        if self._db:
            return self._db
        self._db = _mysql.connect(self.config.get("mysql-hostname"), 
                                 self.config.get("mysql-username"), 
                                 self.config.get("mysql-password"), 
                                 self.config.get("mysql-database"))
        return self._db


    @classmethod
    def _escape(cls, string):
        """ Crappy workaround to escape MySQL query parameters """
        if string is None:
            return "null"
        return "'"+_mysql.escape_string(str(string))+"'"

    @classmethod
    def escape(cls, items):
        """ If items is list, returns escaped list of MySQL query
            parameters. Otherwise, escaped string """
        if isinstance(items, list):
            return [cls._escape(item) for item in items]
        return cls._escape(items)

    def open_session(self, username, device_id, device_ip, start_time, 
                                                         end_time=None):
        """ Opens a new session for a device """
        statsd.incr("crashplan.update.session.open")
        now = datetime.datetime.now()

        self.db.query("UPDATE crashplan_per_device SET end_time=%s, end_time_real=%s WHERE device_id=%s AND end_time is NULL" % tuple(self.escape([now, now, device_id])))
        self.db.store_result()
        e_real = now
        if not end_time:
            e_real = None
        self.db.query("INSERT INTO crashplan_per_device VALUES (%s,%s,%s,%s,%s,%s,%s)" % tuple(self.escape([username, device_id, device_ip, start_time, end_time, now, e_real])))
        self.db.store_result()

    def close_session(self, device_id, end_time):
        """ Closes a session for a device """
        statsd.incr("crashplan.update.session.close")
        now = datetime.datetime.now()
        if end_time is None:
            end_time = now
        self.db.query("UPDATE crashplan_per_device SET end_time=%s, end_time_real=%s WHERE device_id=%s AND end_time is NULL" % tuple(self.escape([end_time, now, device_id])))
        self.db.store_result()

    def _process_device(self, user, device):
        """ Processes a single device. User is a string (username),
             device is device dictionary from Crashplan """
        did = device["computerId"]
        self.redis.sadd("devices-for-%s-tmp" % user, did)
        self.redis.set("device-by-id-%s" % did, json.dumps(device))
        connected_status = device.get("backupUsage")[0].get("activity", {}).get("connected", False)
        device_ip = device.get("remoteAddress").split(":")
        device_ip = device_ip[0]
        self.redis.rpush("ip-resolve-queue", device_ip)
        previous_connected_status = self.redis.get("device-connected-%s" % did)
        previous_device_ip = self.redis.get("device-ip-%s" % did)
                    
        if previous_device_ip != device_ip:
            # IP changed. Close previous session
            self.close_session(did, None)
            if connected_status:
                # Session is still open. Open a new entry.
                self.open_session(user, did, device_ip, device["lastConnected"])
        elif connected_status:
            if previous_connected_status == 'False':
                # New session
                self.open_session(user, did, device_ip, device["lastConnected"])
        elif not connected_status:
            if previous_connected_status == 'True':
                # Disconnected. Close session, and don't open a new one.
                self.close_session(did, None)

        self.redis.set("device-connected-%s" % did, connected_status)
        self.redis.set("device-ip-%s" % did, device_ip)

    @timing("crashplan.update.update")
    def update(self):
        """ Process all user entries """
        statsd.incr("crashplan.update.counter")
        users = self.crashplan.get_devices_per_user()
        for user in users:
            userd = users[user]
            self.redis.set("id-for-username-%s" % user, userd["userId"])
            self.redis.set("username-for-id-%s" % userd["userId"], user)
            if "devices" in userd:
                for device in userd["devices"]:
                    self._process_device(user, device)
                if self.redis.exists("devices-for-%s-tmp" % user):
                    self.redis.rename("devices-for-%s-tmp" % user, "devices-for-%s" % user)
            else:
                self.redis.delete("devices-for-%s" % user)

def main():
    """ Processes all user entries. No output nor return value """
    cpu = CrashplanUpdate()
    cpu.update()

if __name__ == '__main__':
    main()
