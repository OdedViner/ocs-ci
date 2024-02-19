import logging
import pytest

from ocs_ci.framework.pytest_customization.marks import brown_squad
from ocs_ci.framework.testlib import (
    ManageTest,
    tier2,
    skipif_external_mode,
    skipif_ms_consumer,
    skipif_hci_client,
    hci_provider_and_client_required,
    turquoise_squad,
)
from ocs_ci.ocs.must_gather.must_gather import MustGather
from ocs_ci.ocs.must_gather import const_must_gather

logger = logging.getLogger(__name__)


@brown_squad
class TestMustGather(ManageTest):
    @tier2
    @pytest.mark.parametrize(
        argnames=[
            "ceph",
            "ceph_logs",
            "namespaced",
            "clusterscoped",
            "noobaa",
            "dr",
            "provider",
        ],
        argvalues=[
            pytest.param(
                *[True, True, False, True, False, False, False],
                marks=[
                    pytest.mark.polarion_id("OCS-XXX"),
                    skipif_external_mode,
                    skipif_ms_consumer,
                    skipif_hci_client,
                ],
            ),
            pytest.param(
                *[True, True, True, True, False, False, False],
                marks=[
                    pytest.mark.polarion_id("OCS-XXX"),
                    skipif_external_mode,
                    skipif_ms_consumer,
                    skipif_hci_client,
                ],
            ),
            pytest.param(
                *[False, False, False, False, False, False, True],
                marks=[
                    pytest.mark.polarion_id("OCS-XXX"),
                    hci_provider_and_client_required,
                ],
            ),
            pytest.param(
                *[False, False, False, False, False, True, False],
                marks=[
                    pytest.mark.polarion_id("OCS-XXX"),
                    turquoise_squad,
                ],
            ),
        ],
    )
    def test_must_gather_modular(
        self, ceph, ceph_logs, namespaced, clusterscoped, noobaa, dr, provider
    ):
        """
        Tests OCS must gather with flags

        Test Process:
        1.Collect mg with relevant flags for example
            oc adm must-gather --image=quay.io/rhceph-dev/ocs-must-gather:latest-4.15 -- /usr/bin/gather -c -cl -n
        2.Calculate the paths that should be included in the ocs mg dir
        3.Calculate the paths that should not be included in the ocs mg dir
        4.Verify paths exist in must gather directory
        5.Verify paths do not exist in must gather directory
        """

        flags_cmd = "/usr/bin/gather "
        paths_exist = list()
        paths_not_exist = list()

        options = [
            (ceph, const_must_gather.CEPH_ONLY, "-c "),
            (ceph_logs, const_must_gather.CEPH_LOGS_ONLY, "-cl "),
            (namespaced, const_must_gather.NAMESPACED_ONLY, "-ns "),
            (clusterscoped, const_must_gather.CLUSTERSCOPED_ONLY, "-cs "),
            (noobaa, const_must_gather.NOOBAA_ONLY, "-n "),
            (dr, const_must_gather.DR_ONLY, "-d "),
            (provider, const_must_gather.PROVIDER_ONLY, "-p "),
        ]

        for flag, paths, param_value in options:
            if flag:
                for path in paths:
                    paths_exist.append(path)
                flags_cmd += param_value
            else:
                for path in paths:
                    paths_not_exist.append(path)
        mustgather_obj = MustGather()
        mustgather_obj.collect_must_gather(ocs_flags=flags_cmd)
        mustgather_obj.get_all_paths()
        folders_exist = mustgather_obj.verify_paths_in_dir(paths_exist)
        folders_not_exist = mustgather_obj.verify_paths_not_in_dir(paths_not_exist)
        assert len(folders_not_exist) + len(folders_exist) == 0, (
            f"\nMode: {flags_cmd}"
            f"\nThe folders don't exist [should exist]: {folders_exist} "
            f"\nThe folders exist [should not exist]: {folders_not_exist}"
        )