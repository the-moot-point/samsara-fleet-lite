import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_driver_add_payload_typing() -> None:
    from src import models

    payload = models.DriverAddPayload(
        carrierSettings=models.CarrierSettings(
            carrierName="Acme Logistics",
            dotNumber=1234567,
            homeTerminalAddress="123 Main St",
            homeTerminalName="Main",
            mainOfficeAddress="456 Elm St",
        ),
        externalIds={"employeeId": "E123"},
        name="John Doe",
        username="jdoe",
        password="secret",
        notes="Test driver",
        phone="555-5555",
        licenseState="CA",
        tagIds=["tag1", "tag2"],
        peerGroupTagId="group1",
    )

    assert payload.tagIds == ["tag1", "tag2"]
    assert payload.peerGroupTagId == "group1"

    payload_no_peer = models.DriverAddPayload(
        carrierSettings=payload.carrierSettings,
        externalIds=payload.externalIds,
        name=payload.name,
        username=payload.username,
        password=payload.password,
        notes=payload.notes,
        phone=payload.phone,
        licenseState=payload.licenseState,
        tagIds=payload.tagIds,
    )

    assert payload_no_peer.peerGroupTagId is None
