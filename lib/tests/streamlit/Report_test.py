# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for Report.py."""

import copy
import unittest

from mock import patch

from streamlit import config
from streamlit.Report import Report
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from streamlit.proto.StaticManifest_pb2 import StaticManifest

INIT_MSG = ForwardMsg()
INIT_MSG.initialize.config.sharing_enabled = True

TEXT_DELTA_MSG = ForwardMsg()
TEXT_DELTA_MSG.delta.new_element.text.body = "text1"

EMPTY_DELTA_MSG = ForwardMsg()
EMPTY_DELTA_MSG.delta.new_element.empty.unused = True


def _enqueue(report, msg):
    msg = copy.deepcopy(msg)
    msg.metadata.delta_id = len(list(report._master_queue))
    report.enqueue(msg)


def _parse_msg(msg_string):
    """Parse a ForwardMsg from a string"""
    msg = ForwardMsg()
    msg.ParseFromString(msg_string)
    return msg


class ReportTest(unittest.TestCase):
    def test_serialize_final_report(self):
        report = Report("/not/a/script.py", "")
        _enqueue(report, INIT_MSG)
        _enqueue(report, EMPTY_DELTA_MSG)
        _enqueue(report, TEXT_DELTA_MSG)
        _enqueue(report, EMPTY_DELTA_MSG)

        files = report.serialize_final_report_to_files()

        # Validate our messages. We should have two: INIT, and TEXT_DELTA_MSG.
        # (Empty messages don't get serialized.)
        messages = [_parse_msg(msg_string) for _, msg_string in files[:-1]]
        self.assertEqual(2, len(messages))
        self.assertEqual("initialize", messages[0].WhichOneof("type"))
        self.assertEqual("delta", messages[1].WhichOneof("type"))
        self.assertEqual("text1", messages[1].delta.new_element.text.body)

        # Validate the manifest, which should be the final file.
        _, manifest_string = files[-1]
        manifest = StaticManifest()
        manifest.ParseFromString(manifest_string)
        self.assertEqual("script", manifest.name)
        self.assertEqual(2, manifest.num_messages)
        self.assertEqual(StaticManifest.DONE, manifest.server_status)
        self.assertEqual("", manifest.external_server_ip)
        self.assertEqual("", manifest.internal_server_ip)
        self.assertEqual(0, manifest.server_port)

    def test_serialize_running_report(self):
        report = Report("/not/a/script.py", "")
        _enqueue(report, INIT_MSG)
        _enqueue(report, EMPTY_DELTA_MSG)
        _enqueue(report, TEXT_DELTA_MSG)
        _enqueue(report, EMPTY_DELTA_MSG)

        get_external_ip_patch = patch(
            "streamlit.Report.util.get_external_ip", return_value="external_ip"
        )
        get_internal_ip_patch = patch(
            "streamlit.Report.util.get_internal_ip", return_value="internal_ip"
        )
        with get_external_ip_patch, get_internal_ip_patch:
            files = report.serialize_running_report_to_files()

        # Running reports just serialize the manifest
        self.assertEqual(1, len(files))

        # Validate the manifest.
        _, manifest_string = files[-1]
        manifest = StaticManifest()
        manifest.ParseFromString(manifest_string)
        self.assertEqual("script", manifest.name)
        self.assertEqual(0, manifest.num_messages)
        self.assertEqual(StaticManifest.RUNNING, manifest.server_status)
        self.assertEqual(
            config.get_option("browser.serverAddress"),
            manifest.configured_server_address,
        )
        self.assertEqual(config.get_option("browser.serverPort"), manifest.server_port)
        self.assertEqual("external_ip", manifest.external_server_ip)
        self.assertEqual("internal_ip", manifest.internal_server_ip)
