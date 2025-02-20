"""
*********************************************************************
* Skylight Netsim example                                           *
* Implements a couple of actions                                    *
*                                                                   *
* (C) 2023 Cisco Systems                                            *
* Permission to use this code as a starting point hereby granted    *
*********************************************************************
"""

from datetime import datetime
import logging
import os
import random
import socket
import sys
import time

import _ncs
import ncs
from ncs.dp import Action, Daemon
from ncs.maapi import Maapi
from ncs.log import Log

from Accedian_alert_ns import ns
from Accedian_alert_type_ns import ns as ns_type
from Accedian_alert_metric_ns import ns as ns_metric
from skylight_netsim_ns import ns as ns_sn

xmltag = _ncs.XmlTag
value = _ncs.Value
tagvalue = _ncs.TagValue


def get_date_time():
    now = datetime.now()
    confdNow = _ncs.DateTime(
        year=now.year,
        month=now.month,
        day=now.day,
        hour=now.hour,
        min=now.minute,
        sec=now.second,
        micro=now.microsecond,
        timezone=0,
        timezone_minutes=0)
    return confdNow


notif_daemon = None


class NotificationDaemon:
    def __init__(self, name, stream):
        self.ndaemon = ncs.dp.Daemon(name)
        self.nsock = socket.socket()
        _ncs.dp.connect(self.ndaemon.ctx(), self.nsock,
                            _ncs.dp.WORKER_SOCKET, "127.0.0.1", ncs.PORT)
        self.nctx = _ncs.dp.register_notification_stream(self.ndaemon.ctx(),
                                      None, self.nsock, stream)
    def start(self):
        self.ndaemon.start()
    def finish(self):
        self.ndaemon.finish()
    def join(self):
        self.ndaemon.join()

    def send_alert(self, device, jitter, high=False):
        state = ns_type.acdalt_raised if high else ns_type.acdalt_cleared

        values = [
            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_notification),
                     value((ns.acdal_alert_notification, ns.hash),
                           _ncs.C_XMLBEGIN)
                     ),
            tagvalue(xmltag(ns.hash,
                            ns.acdal_policy_id),
                     value(device, _ncs.C_BUF)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_condition_id),
                     value('delay-variation', _ncs.C_BUF)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_session_id),
                     value('session-id-value', _ncs.C_BUF)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_service),
                     value((ns.acdal_service, ns.hash),
                           _ncs.C_XMLBEGIN)
                     ),
            tagvalue(xmltag(ns.hash,
                            ns.acdal_service_id),
                     value('service-id-value', _ncs.C_BUF)),
                     
            tagvalue(xmltag(ns.hash,
                            ns.acdal_group_id),
                     value('group-id-value', _ncs.C_BUF)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_service),
                     value((ns.acdal_service, ns.hash),
                           _ncs.C_XMLEND)),
            
            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_state),
                     value(state, _ncs.C_ENUM_VALUE)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_severity),
                     value(ns_type.acdalt_critical, _ncs.C_ENUM_VALUE)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_type),
                     value((ns_type.hash, ns_type.acdalt_metric), _ncs.C_IDENTITYREF)),
         
            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_data),
                     value((ns.acdal_alert_data, ns.hash),
                           _ncs.C_XMLBEGIN)),

            tagvalue(xmltag(ns_metric.hash,
                            ns_metric.acdalmet_metric),
                     value((ns_metric.acdalmet_metric, ns_metric.hash),
                           _ncs.C_XMLBEGIN)),

            # Delay variation average metric
            tagvalue(xmltag(ns_metric.hash,
                            ns_metric.acdalmet_type),
                     value(ns_metric.acdalmet_delay_var_avg, _ncs.C_ENUM_VALUE)),

            # Direction from source to destination
            tagvalue(xmltag(ns_metric.hash,
                            ns_metric.acdalmet_direction),
                     value(ns_metric.acdalmet_sd, _ncs.C_ENUM_VALUE)),

            tagvalue(xmltag(ns_metric.hash,
                            ns_metric.acdalmet_value),
                     value(str(jitter), _ncs.C_BUF)),

            tagvalue(xmltag(ns_metric.hash,
                            ns_metric.acdalmet_metric),
                     value((ns_metric.acdalmet_metric, ns_metric.hash),
                           _ncs.C_XMLEND)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_data),
                     value((ns.acdal_alert_data, ns.hash),
                           _ncs.C_XMLEND)),

            tagvalue(xmltag(ns.hash,
                            ns.acdal_alert_notification),
                     value((ns.acdal_alert_notification, ns.hash),
                           _ncs.C_XMLEND)
                     )
        ]
        _ncs.dp.notification_send(self.nctx, get_date_time(), values)


    def send_jitter(self, device, jitter):
        values = [
            tagvalue(xmltag(ns_sn.hash,
                            ns_sn.skylight_netsim_jitter_event),
                     value((ns_sn.skylight_netsim_jitter_event, ns_sn.hash),
                           _ncs.C_XMLBEGIN)
                     ),
            tagvalue(xmltag(ns_sn.hash,
                            ns_sn.skylight_netsim_device),
                     value(device, _ncs.C_BUF)),

            tagvalue(xmltag(ns_sn.hash,
                            ns_sn.skylight_netsim_jitter),
                     value((jitter, 3), _ncs.C_DECIMAL64)),

            tagvalue(xmltag(ns_sn.hash,
                            ns_sn.skylight_netsim_jitter_event),
                     value((ns_sn.skylight_netsim_jitter_event, ns_sn.hash),
                           _ncs.C_XMLEND)
                     )
        ]
        _ncs.dp.notification_send(self.nctx, get_date_time(), values)


class SendNotificationAction(Action):
    @Action.rpc
    def cb_action(self, uinfo, name, input, output):
        jitter = None
        if input.jitter:
            jitter = int(float(input.jitter)*1000)
        if name == "send-notification-high-jitter":
            jitter = jitter or random.randint(5000, 8000)
            high = True
        else: # send-notification-low-jitter
            jitter = jitter or random.randint(1000, 3000)
            high = False

        if notif_daemon is not None:
            if input.type in (ns_sn.skylight_netsim_enum_jitter, ns_sn.skylight_netsim_enum_jitter_alert):
                notif_daemon.send_jitter(input.device, jitter)
            if input.type in (ns_sn.skylight_netsim_enum_alert, ns_sn.skylight_netsim_enum_jitter_alert):
                notif_daemon.send_alert(input.device, jitter, high)
            self.log.info("Notification sent")


def load_schemas():
    with Maapi():
        pass


if __name__ == "__main__":
    logger = logging.getLogger('skylight-netsim')
    logging.basicConfig(filename='logs/skylight-netsim.log',
              format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
              level=logging.DEBUG)

    load_schemas()
    log = Log(logger, add_timestamp=True)

    daemons = []

    d = Daemon(name='skylight-netsim', log=log)
    daemons.append(d)

    a = []
    a.append(SendNotificationAction(daemon=d,
                       actionpoint='skylight-send-notification', log=log))

    notif_daemon = NotificationDaemon("skylight-notification-daemon",
                                        "notification-stream")
    daemons.append(notif_daemon)

    log.info('--- Daemon Skylight Netsim STARTED ---')

    try:
        for daemon in daemons:
            daemon.start()

        while True:
            d.join(1)
            if not d.is_alive():
                daemons.remove(d)
                break
    except Exception as e:
        print("ERROR:", e)


    for daemon in daemons:
        daemon.finish()
        daemon.join()


    log.info('--- Daemon myaction FINISHED ---')
