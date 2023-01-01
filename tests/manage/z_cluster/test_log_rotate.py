import logging
import time
import pytest
import re

from ocs_ci.ocs import defaults
from ocs_ci.ocs.resources.storage_cluster import verify_storage_cluster
from ocs_ci.utility.utils import TimeoutSampler
from ocs_ci.ocs.resources import pod
from ocs_ci.ocs.exceptions import TimeoutExpiredError
from ocs_ci.ocs.ocp import OCP
from ocs_ci.ocs import constants
from ocs_ci.framework.testlib import (
    ManageTest,
    tier2,
    bugzilla,
    skipif_ocs_version,
    skipif_external_mode,
    ignore_leftovers,
)

log = logging.getLogger(__name__)


@tier2
@ignore_leftovers
@bugzilla("2116416")
@skipif_external_mode
@skipif_ocs_version("<4.10")
@pytest.mark.polarion_id("OCS-XYZ")
class TestLogsRotate(ManageTest):
    """
    Test Logs Rotate

    """

    @pytest.fixture(autouse=True)
    def teardown(self, request):
        def finalizer():
            log.info("Delete logCollector from storage cluster yaml file")
            storagecluster_obj = OCP(
                resource_name=constants.DEFAULT_CLUSTERNAME,
                namespace=defaults.ROOK_CLUSTER_NAMESPACE,
                kind=constants.STORAGECLUSTER,
            )
            params = '[{"op": "remove", "path": "/spec/logCollector"}]'
            storagecluster_obj.patch(params=params, format_type="json")
            log.info(
                "It takes time for storagecluster to update after the edit command"
            )
            time.sleep(30)
            log.info("Verify storagecluster on Ready state")
            verify_storage_cluster()

        request.addfinalizer(finalizer)

    def get_pod_obj_based_on_id(self, pod_type):
        """
        Get Pod Obj

        Args:
            pod_type (str):

        Returns:
            POD Obj:
        """
        pod_objs = self.podtype_id[pod_type][0]()
        for pod_obj in pod_objs:
            if self.podtype_id[pod_type][1] == pod.get_ceph_daemon_id(pod_obj):
                return pod_obj

    def verify_new_log_created(self, pod_type):
        """
        Verify new log created on /var/log/ceph

        Args:
            pod_type (str):

        Returns:
            bool: True if a new log created, otherwise False

        """
        pod_obj = self.get_pod_obj_based_on_id(pod_type)
        output_cmd = pod_obj.exec_cmd_on_pod(command="ls -l /var/log/ceph")
        expected_string = (
            self.podtype_id[pod_type][2]
            if pod_type == "rgw"
            else f"{self.podtype_id[pod_type][2]}{self.podtype_id[pod_type][1]}"
        )
        cnt_logs = len(re.findall(expected_string, output_cmd))
        if cnt_logs != int(self.podtype_id[pod_type][3]) + 1:
            log.info(output_cmd)
            return False
        return True

    def test_logs_rotate(self):
        """
        Test Process:
            1.Verify the number of MGR,MDS,OSD,MON,RGW logs
            2.Add logCollector to spec section on Storagecluster
            3.Write 500M to MGR,MDS,OSD,MON,RGW
            4.Verify new log created
            5.Delete logCollector from Storagecluster

        """
        self.podtype_id = dict()
        self.podtype_id["mgr"] = [
            pod.get_mgr_pods,
            pod.get_ceph_daemon_id(pod.get_mgr_pods()[0]),
            "ceph-mgr.",
        ]
        self.podtype_id["osd"] = [
            pod.get_osd_pods,
            pod.get_ceph_daemon_id(pod.get_osd_pods()[0]),
            "ceph-osd.",
        ]
        self.podtype_id["mon"] = [
            pod.get_mon_pods,
            pod.get_ceph_daemon_id(pod.get_mon_pods()[0]),
            "ceph-mon.",
        ]
        self.podtype_id["rgw"] = [
            pod.get_rgw_pods,
            pod.get_ceph_daemon_id(pod.get_rgw_pods()[0]),
            "ceph-client.rgw.ocs.storagecluster.cephobjectstore.a",
        ]
        self.podtype_id["mds"] = [
            pod.get_mds_pods,
            pod.get_ceph_daemon_id(pod.get_mds_pods()[0]),
            "ceph-mds.",
        ]

        for pod_type in self.podtype_id:
            pod_obj = self.get_pod_obj_based_on_id(pod_type)
            output_cmd = pod_obj.exec_cmd_on_pod(command="ls -l /var/log/ceph")
            expected_string = (
                self.podtype_id[pod_type][2]
                if pod_type == "rgw"
                else f"{self.podtype_id[pod_type][2]}{self.podtype_id[pod_type][1]}"
            )
            self.podtype_id[pod_type].append(
                len(re.findall(expected_string, output_cmd))
            )
        storagecluster_obj = OCP(
            resource_name=constants.DEFAULT_CLUSTERNAME,
            namespace=defaults.ROOK_CLUSTER_NAMESPACE,
            kind=constants.STORAGECLUSTER,
        )
        params = '{"spec": {"logCollector": {"enabled": true,"maxLogSize":"500M", "periodicity": "hourly"}}}'
        storagecluster_obj.patch(
            params=params,
            format_type="merge",
        )
        log.info("It takes time for storagecluster to update after the edit command")
        time.sleep(30)
        log.info("Verify storagecluster on Ready state")
        verify_storage_cluster()

        for pod_type in self.podtype_id:
            pod_obj = self.get_pod_obj_based_on_id(pod_type)
            expected_string = (
                self.podtype_id[pod_type][2]
                if pod_type == "rgw"
                else f"{self.podtype_id[pod_type][2]}{self.podtype_id[pod_type][1]}"
            )
            pod_obj.exec_cmd_on_container(
                container_name="log-collector",
                command=f"dd if=/dev/urandom of=/var/log/ceph/{expected_string}.log bs=1M count=530",
            )

        for pod_type in self.podtype_id:
            sample = TimeoutSampler(
                timeout=963,
                sleep=40,
                func=self.verify_new_log_created,
                pod_type=pod_type,
            )
            if not sample.wait_for_func_status(result=True):
                error_log = f"New {pod_type} log is not created after timeout."
                log.error(error_log)
                raise TimeoutExpiredError(error_log)