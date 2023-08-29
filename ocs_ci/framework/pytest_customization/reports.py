import os
import pytest
import logging

from _pytest.logging import _LiveLoggingStreamHandler
from py.xml import html
from ocs_ci.utility.utils import email_reports, save_reports
from ocs_ci.framework import config as ocsci_config
from ocs_ci.utility.logging import (
    console_logger,
    CustomLoggerFilter,
    OCSLogFormatter,
    separator,
)


@pytest.mark.optionalhook
def pytest_html_results_table_header(cells):
    """
    Add Description header to the table
    """
    cells.insert(2, html.th("Description"))


@pytest.mark.optionalhook
def pytest_html_results_table_row(report, cells):
    """
    Add content to the column Description
    """
    try:
        cells.insert(2, html.td(report.description))
    except AttributeError:
        cells.insert(2, html.td("--- no description ---"))
    # if logs_url is defined, replace local path Log File links to the logs_url
    if ocsci_config.RUN.get("logs_url"):
        for tag in cells[4][0]:
            if (
                hasattr(tag, "xmlname")
                and tag.xmlname == "a"
                and hasattr(tag.attr, "href")
            ):
                tag.attr.href = tag.attr.href.replace(
                    os.path.expanduser(ocsci_config.RUN.get("log_dir")),
                    ocsci_config.RUN.get("logs_url"),
                )


@pytest.mark.hookwrapper
def pytest_runtest_makereport(item, call):
    """
    Add extra column( Log File) and link the log file location
    """
    pytest_html = item.config.pluginmanager.getplugin("html")
    outcome = yield
    report = outcome.get_result()
    report.description = str(item.function.__doc__)
    extra = getattr(report, "extra", [])

    if report.when == "call":
        log_file = ""
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.FileHandler):
                log_file = handler.baseFilename
                break
        extra.append(pytest_html.extras.url(log_file, name="Log File"))
        report.extra = extra
        item.session.results[item] = report
    if report.skipped:
        item.session.results[item] = report
    if report.when in ("setup", "teardown") and report.failed:
        item.session.results[item] = report


def pytest_sessionstart(session):
    """
    Prepare results dict
    """
    session.results = dict()
    handlers = logging.getLogger().handlers
    for handler in handlers:
        if isinstance(handler, _LiveLoggingStreamHandler):
            custom_filter = CustomLoggerFilter()
            handler.addFilter(custom_filter)


def pytest_sessionfinish(session, exitstatus):
    """
    save session's report files and send email report
    """
    if ocsci_config.REPORTING.get("save_mem_report"):
        save_reports()
    if ocsci_config.RUN["cli_params"].get("email"):
        email_reports(session)


def pytest_logger_config(logger_config):
    logger_config.add_loggers([""], stdout_level="info")
    logger_config.set_log_option_default("")
    logger_config.split_by_outcome()
    logger_config.set_formatter_class(OCSLogFormatter)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    test_name = f"TEST NAME: {item.name}"
    console_logger.info(f"\n{separator(symbol_='-', val=test_name)}")
    info_text = f"SETUP for {item.name}"
    console_logger.info(f"{separator(symbol_='-', val=info_text)}")


def pytest_fixture_setup(fixturedef, request):
    console_logger.info(
        f"Executing {fixturedef.scope} scope fixture: {fixturedef.argname}"
    )


def pytest_fixture_post_finalizer(fixturedef, request):
    if fixturedef.scope != "session":
        console_logger.info(
            f"Finished finalizer from {fixturedef.scope} scope fixture: {fixturedef.argname}"
        )


def pytest_runtest_call(item):
    info_text = f"CALL for {item.name}"
    console_logger.info(f"{separator(symbol_='-', val=info_text)}")


def pytest_runtest_teardown(item):
    info_text = f"TEARDOWN for {item.name}"
    console_logger.info(f"{separator(symbol_='-', val=info_text)}")
