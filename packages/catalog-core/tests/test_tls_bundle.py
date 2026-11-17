import ssl
from importlib import metadata

import certifi
from packaging.requirements import Requirement
from packaging.version import Version

_CERTIFI_FLOOR = Version("2026.10.18")


def test_installed_catalog_core_requires_usable_patched_certifi_bundle() -> None:
    requirements = [
        Requirement(value)
        for value in metadata.requires("anibridge-catalog-core") or []
    ]
    certifi_requirements = [
        requirement
        for requirement in requirements
        if requirement.name.lower() == "certifi" and requirement.marker is None
    ]
    assert len(certifi_requirements) == 1
    certifi_specifier = certifi_requirements[0].specifier
    assert Version("2026.7.22") not in certifi_specifier
    assert Version(certifi.__version__) in certifi_specifier

    assert Version(certifi.__version__) >= _CERTIFI_FLOOR

    context = ssl.create_default_context(cafile=certifi.where())
    assert context.get_ca_certs()
    # GHSA-6q48-6c7w-9gw2: compromised intermediates chain to this root.
    # Other emSign roots were restored later and must not be rejected wholesale.
    common_names = {
        "".join(character for character in value.casefold() if character.isalnum())
        for certificate in context.get_ca_certs()
        for relative_name in certificate["subject"]
        for name, value in relative_name
        if name == "commonName"
    }
    assert "emsigneccrootcag3" not in common_names
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
