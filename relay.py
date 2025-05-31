import sys
from urllib.parse import urljoin
import requests
import re
import time
import subprocess
from loguru import logger
from pydantic_settings import BaseSettings
from pydantic import HttpUrl, IPvAnyAddress, PositiveInt


PORT_RE = r"Mapped public port ([0-9]+) protocol (UDP|TCP) to local port 0"


class Settings(BaseSettings):
    opnsense_key: str
    opnsense_secret: str
    opnsense_url: HttpUrl
    opnsense_alias_name: str

    transmission_url: HttpUrl

    nat_pmp_gateway: IPvAnyAddress
    nat_pmp_timeout: PositiveInt = 60

    refresh_delay: PositiveInt = 45


def natpmpc_get_port(settings: Settings, protocol: str) -> int:
    result = subprocess.run(
        [
            "natpmpc",
            "-a",
            "1",
            "0",
            protocol,
            str(settings.nat_pmp_timeout),
            "-g",
            str(settings.nat_pmp_gateway),
        ],
        timeout=10,
        capture_output=True,
        encoding="utf8",
        check=True,
    )
    match = re.search(PORT_RE, result.stdout)
    if match is None:
        logger.error("natpmpc output: {}", result.stdout)
        logger.error("natpmpc stderr: {}", result.stderr)
        raise Exception("Could not extract port from the output")

    return int(match.group(1))


def opnsense_get_alias_id(settings: Settings) -> str:
    url = urljoin(
        str(settings.opnsense_url),
        f"/api/firewall/alias/get_alias_u_u_i_d/{settings.opnsense_alias_name}",
    )
    r = requests.get(
        url,
        auth=(settings.opnsense_key, settings.opnsense_secret),
        timeout=5,
        verify=False,
    )
    r.raise_for_status()

    return r.json()["uuid"]


def opnsense_update_port(settings: Settings, alias_uuid: str, port: int) -> None:
    url = urljoin(
        str(settings.opnsense_url), f"/api/firewall/alias/setItem/{alias_uuid}"
    )
    r = requests.post(
        url,
        auth=(settings.opnsense_key, settings.opnsense_secret),
        timeout=5,
        verify=False,
        json={"alias": {"content": str(port)}},
    )
    logger.info("Response: {response}", response=r.text)
    r.raise_for_status()
    assert r.json()["result"] == "saved"
    logger.info(
        "Opnsense: updated alias {alias} with new port {port}",
        alias=settings.opnsense_alias_name,
        port=port,
    )

    url = urljoin(str(settings.opnsense_url), "/api/firewall/alias/reconfigure")
    r = requests.post(
        url,
        auth=(settings.opnsense_key, settings.opnsense_secret),
        timeout=5,
        verify=False,
    )
    r.raise_for_status()
    assert r.json()["status"] == "ok"
    logger.info("Opnsense: applied firewall configuration")


def transmission_ping(settings: Settings) -> None:
    subprocess.run(
        ["transmission-remote", str(settings.transmission_url), "-l"],
        check=True,
        encoding="utf-8",
        capture_output=True,
        timeout=5,
    )


def transmission_update_port(settings: Settings, port: int) -> None:
    subprocess.run(
        ["transmission-remote", str(settings.transmission_url), "-p", str(port)],
        capture_output=True,
        check=True,
    )
    logger.info("Transmission: updated port")


def relay() -> None:
    # Load settings
    settings = Settings()
    logger.info("Configuration loaded...")

    # Grab the UUID
    try:
        opnsense_alias_id = opnsense_get_alias_id(settings)
        logger.info("Alias found in OPNSense...")
    except Exception as e:
        logger.exception("Error while fetching the alias from OPNSense")
        sys.exit(1)

    # Ping transmission to check configuration
    try:
        transmission_ping(settings)
        logger.info("Connection to transmission OK...")
    except Exception as e:
        logger.exception("Error while contacting transmission")
        sys.exit(1)

    # Launch the daemon
    current_registered_port: int | None = None
    error_count = 0
    while True:
        try:
            tcp_port = natpmpc_get_port(settings, "TCP")
            udp_port = natpmpc_get_port(settings, "UDP")

            if tcp_port != udp_port:
                logger.warning(
                    "TCP and UDP ports are different: tcp={tcp_port} udp={udp_port}", tcp_port=tcp_port, udp_port=udp_port
                )

            if tcp_port != current_registered_port:
                logger.info("Updating forwarded port to {port}", port=tcp_port)
                opnsense_update_port(settings, opnsense_alias_id, tcp_port)
                transmission_update_port(settings, tcp_port)
                current_registered_port = tcp_port
            
            error_count = 0
        except Exception:
            logger.exception("Error while updating port")
            error_count += 1

            if error_count > 10:
                logger.error("Bailing out")
                sys.exit(1)

        time.sleep(settings.refresh_delay)


if __name__ == "__main__":
    relay()

