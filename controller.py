# ==========================================
# TradingBot V4
# controller.py
# ==========================================

import subprocess


SERVICE_NAME = "tradingbot"


def start_bot():

    subprocess.run(
        ["sudo", "systemctl", "start", SERVICE_NAME]
    )


def stop_bot():

    subprocess.run(
        ["sudo", "systemctl", "stop", SERVICE_NAME]
    )


def restart_bot():

    subprocess.run(
        ["sudo", "systemctl", "restart", SERVICE_NAME]
    )


def status_bot():

    r = subprocess.run(

        ["systemctl", "is-active", SERVICE_NAME],

        capture_output=True,

        text=True

    )

    return r.stdout.strip()


def logs_bot(lines=50):

    r = subprocess.run(

        [

            "journalctl",

            "-u",

            SERVICE_NAME,

            "-n",

            str(lines),

            "--no-pager"

        ],

        capture_output=True,

        text=True

    )

    return r.stdout
