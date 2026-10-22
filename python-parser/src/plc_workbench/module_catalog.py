"""Explicit Rockwell catalog facts for browsing captured module declarations.

This offline library identifies a declared product, not an installed device or a
member-to-terminal layout. Catalog suffixes are never generated or stripped.
The listed models and capacities were checked against the cited vendor tables;
capacity is rated/maximum hardware capacity, never a count of configured points.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any


IO_REFERENCE = 'https://configurator.rockwellautomation.com/api/Doc/1756-td002_-en-e.pdf'
COMMUNICATION_REFERENCE = 'https://literature.rockwellautomation.com/idc/groups/literature/documents/td/1756-td003_-en-e.pdf'
CONTROLLER_REFERENCE = 'https://configurator.rockwellautomation.com/api/Doc/1756-td001_-en-p.pdf'
FLEX_ANALOG_REFERENCE = 'https://literature.rockwellautomation.com/idc/groups/literature/documents/um/1794-um062_-en-p.pdf'

# Each entry lists actual published model names. The numeric capacities below
# come from specifications, not from parsing digits in catalog strings.
# 1756-TD002M-EN-E (December 2019), printed page numbers.
# models, field kind, capacity, short description, specification page
_DIGITAL = (
    ('1756-IA8D', 'di', 8, 'AC diagnostic inputs', 5),
    ('1756-IA16 1756-IA16K', 'di', 16, 'AC inputs', 8),
    ('1756-IA16I 1756-IA16IK', 'di', 16, 'Isolated AC inputs', 11),
    ('1756-IA32 1756-IA32K', 'di', 32, 'AC inputs', 14),
    ('1756-IB16 1756-IB16K', 'di', 16, 'DC inputs', 17),
    ('1756-IB16D 1756-IB16DK', 'di', 16, 'Diagnostic DC inputs', 20),
    ('1756-IB16I 1756-IB16IK', 'di', 16, 'Isolated DC inputs', 24),
    ('1756-IB16IF 1756-IB16IFK', 'di', 16, 'Fast isolated DC inputs', 27),
    ('1756-IB16ISOE 1756-IB16ISOEK', 'di', 16, 'Isolated event-recording DC inputs', 30),
    ('1756-IB32 1756-IB32K', 'di', 32, 'DC inputs', 33),
    ('1756-IC16', 'di', 16, 'DC inputs', 36),
    ('1756-IG16', 'di', 16, 'TTL inputs', 82),
    ('1756-IH16I', 'di', 16, 'Isolated DC inputs', 84),
    ('1756-IH16ISOE', 'di', 16, 'Isolated event-recording DC inputs', 87),
    ('1756-IM16I 1756-IM16IK', 'di', 16, 'Isolated AC inputs', 90),
    ('1756-IN16', 'di', 16, 'AC inputs', 93),
    ('1756-IV16 1756-IV16K', 'di', 16, 'Sourcing DC inputs', 124),
    ('1756-IV32 1756-IV32K', 'di', 32, 'Sourcing DC inputs', 127),
    ('1756-OA8', 'do', 8, 'AC outputs', 130),
    ('1756-OA8D', 'do', 8, 'Diagnostic AC outputs', 134),
    ('1756-OA8E', 'do', 8, 'Electronically fused AC outputs', 136),
    ('1756-OA16 1756-OA16K', 'do', 16, 'AC outputs', 140),
    ('1756-OA16I 1756-OA16IK', 'do', 16, 'Isolated AC outputs', 143),
    ('1756-OB8', 'do', 8, 'DC outputs', 146),
    ('1756-OB8EI', 'do', 8, 'Isolated electronically fused DC outputs', 149),
    ('1756-OB8I', 'do', 8, 'Isolated DC outputs', 152),
    ('1756-OB16D 1756-OB16DK', 'do', 16, 'Diagnostic DC outputs', 156),
    ('1756-OB16E 1756-OB16EK', 'do', 16, 'Electronically fused DC outputs', 160),
    ('1756-OB16I', 'do', 16, 'Isolated DC outputs', 163),
    ('1756-OB16IEF 1756-OB16IEFK', 'do', 16, 'Fast isolated DC outputs', 166),
    ('1756-OB16IEFS', 'do', 16, 'Scheduled isolated DC outputs', 169),
    ('1756-OB16IS', 'do', 16, 'Isolated DC outputs with scheduling', 172),
    ('1756-OB32 1756-OB32K', 'do', 32, 'DC outputs', 175),
    ('1756-OC8', 'do', 8, 'DC outputs', 178),
    ('1756-OG16', 'do', 16, 'TTL outputs', 209),
    ('1756-OH8I', 'do', 8, 'Isolated DC outputs', 211),
    ('1756-ON8', 'do', 8, 'AC outputs', 215),
    ('1756-OV16E', 'do', 16, 'Electronically fused sinking DC outputs', 218),
    ('1756-OV32E', 'do', 32, 'Electronically fused sinking DC outputs', 223),
    ('1756-IB16S', 'di', 16, 'Safety DC inputs', 226),
    ('1756-OBV8S', 'do', 8, 'Safety DC outputs', 234),
    ('1756-OW16I', 'do', 16, 'Isolated relay outputs', 244),
    # OX8I has eight changeover channels (NO/NC contacts), not sixteen channels.
    ('1756-OX8I', 'do', 8, 'Isolated changeover relay outputs', 247),
)

_ANALOG = (
    ('1756-IF6CIS', 'ai', 6, 'Isolated current inputs with loop power', 44),
    ('1756-IF6I', 'ai', 6, 'Isolated voltage/current inputs', 48),
    ('1756-IF8 1756-IF8K', 'ai', 8, 'Voltage/current inputs; capacity depends on mode', 53),
    ('1756-IF8H 1756-IF8HK', 'ai', 8, 'Voltage/current inputs with HART', 56),
    ('1756-IF8I 1756-IF8IK', 'ai', 8, 'Isolated voltage/current inputs', 60),
    ('1756-IF8IH 1756-IF8IHK', 'ai', 8, 'Isolated current inputs with HART', 64),
    ('1756-IF16 1756-IF16K', 'ai', 16, 'Voltage/current inputs; capacity depends on mode', 70),
    ('1756-IF16H 1756-IF16HK', 'ai', 16, 'Current inputs with HART', 73),
    ('1756-IF16IH 1756-IF16IHK', 'ai', 16, 'Isolated current inputs with HART', 77),
    ('1756-IR6I', 'ai', 6, 'Isolated resistance/RTD inputs', 97),
    ('1756-IRT8I 1756-IRT8IK', 'ai', 8, 'Isolated RTD/thermocouple inputs', 102),
    ('1756-IR12 1756-IR12K', 'ai', 12, 'RTD inputs', 107),
    ('1756-IT6I', 'ai', 6, 'Isolated thermocouple inputs', 111),
    ('1756-IT6I2', 'ai', 6, 'Isolated thermocouple inputs', 115),
    ('1756-IT16 1756-IT16K', 'ai', 16, 'Thermocouple inputs', 119),
    ('1756-OF4 1756-OF4K', 'ao', 4, 'Voltage/current outputs', 182),
    ('1756-OF6CI', 'ao', 6, 'Isolated current outputs', 186),
    ('1756-OF6VI', 'ao', 6, 'Isolated voltage outputs', 189),
    ('1756-OF8 1756-OF8K', 'ao', 8, 'Voltage/current outputs', 193),
    ('1756-OF8H 1756-OF8HK', 'ao', 8, 'Voltage/current outputs with HART', 196),
    ('1756-OF8I 1756-OF8IK', 'ao', 8, 'Isolated voltage/current outputs', 201),
    ('1756-OF8IH 1756-OF8IHK', 'ao', 8, 'Isolated current outputs with HART', 204),
)

# 1756-TD003R-EN-E (January 2025), cover and network sections.
_COMMUNICATION = (
    ('1756-EN2F 1756-EN2FK 1756-EN2T 1756-EN2TK 1756-EN2TP 1756-EN2TPK '
     '1756-EN2TR 1756-EN2TRK 1756-EN3TR 1756-EN3TRK 1756-EN4TR 1756-EN4TRK '
     '1756-EN2TXT 1756-EN2TPXT 1756-EN2TRXT 1756-EN4TRXT', 'EtherNet/IP interface', 4),
    ('1756-ENBT 1756-ENBTK', 'EtherNet/IP interface', 41),
    ('1756-EWEB 1756-EWEBK', 'Ethernet web interface', 36),
    ('1756-CN2 1756-CN2K 1756-CN2R 1756-CN2RK 1756-CN2RXT '
     '1756-CNB 1756-CNBK 1756-CNBR 1756-CNBRK', 'ControlNet interface', 27),
    ('1756-DNB 1756-DNBK', 'DeviceNet interface', 15),
    ('1756-DHRIO 1756-DHRIOK 1756-DHRIOXT', 'DH+/remote I/O interface', 18),
    ('1756-RIO', 'Remote I/O interface', 18),
    ('1756-SYNCH', 'SynchLink interface', 25),
    ('1756-TIME', 'Time synchronization interface', 39),
)

# 1756-TD001U-EN-P (April 2025), catalog list on printed page 2.
# Partners are deliberately identified as controller-role products; their
# descriptions distinguish them from the primary safety controller.
_CONTROLLERS = (
    ('1756-L71 1756-L72 1756-L73 1756-L74 1756-L75 '
     '1756-L71K 1756-L72K 1756-L73K 1756-L74K 1756-L75K 1756-L73XT',
     'ControlLogix 5570 controller'),
    ('1756-L81E 1756-L82E 1756-L83E 1756-L84E 1756-L85E '
     '1756-L81EK 1756-L82EK 1756-L83EK 1756-L84EK 1756-L85EK '
     '1756-L81EXT 1756-L82EXT 1756-L83EXT 1756-L84EXT 1756-L85EXT',
     'ControlLogix 5580 controller'),
    ('1756-L81E-NSE 1756-L82E-NSE 1756-L83E-NSE 1756-L84E-NSE 1756-L85E-NSE '
     '1756-L81E-NSEXT 1756-L82E-NSEXT 1756-L83E-NSEXT 1756-L84E-NSEXT 1756-L85E-NSEXT',
     'ControlLogix 5580 controller without stored energy'),
    ('1756-L81EP 1756-L83EP 1756-L85EP 1756-L81EPXT 1756-L83EPXT 1756-L85EPXT',
     'ControlLogix 5580 process controller'),
    ('1756-L71S 1756-L72S 1756-L73S 1756-L71SK 1756-L72SK 1756-L73SK 1756-L73SXT',
     'GuardLogix 5570 safety controller'),
    ('1756-L81ES 1756-L82ES 1756-L83ES 1756-L84ES 1756-L85ES '
     '1756-L81ESK 1756-L82ESK 1756-L83ESK 1756-L84ESK '
     '1756-L81EXTS 1756-L82EXTS 1756-L83EXTS 1756-L84EXTS '
     '1756-L81ESXT 1756-L82ESXT 1756-L83ESXT 1756-L84ESXT',
     'GuardLogix 5580 safety controller'),
    ('1756-L7SP 1756-L7SPK 1756-L7SPXT 1756-L8SP 1756-L8SPK 1756-L8XTSP 1756-L8SPXT',
     'GuardLogix safety partner'),
    ('1756-L72EROM 1756-L73EROM', 'Armor ControlLogix controller'),
    ('1756-L72EROMS 1756-L73EROMS', 'Armor GuardLogix safety controller'),
)


def _build() -> MappingProxyType:
    result = {}

    def add(models: str, description: str, family: str, role: str,
            capacity: dict[str, int], basis: str, reference: str, page: int,
            publication: str) -> None:
        for model in models.split():
            if model in result:
                raise ValueError(f'Duplicate documented catalog identity: {model}')
            result[model] = MappingProxyType({
                'catalog_number': model, 'vendor': '1', 'description': description,
                'family': family, 'role': role, 'field_types': tuple(capacity),
                'capacity': MappingProxyType(dict(capacity)), 'capacity_basis': basis,
                'reference': reference, 'reference_page': page, 'publication': publication,
            })

    for models, kind, count, description, page in _DIGITAL + _ANALOG:
        basis = ('maximum_configuration_dependent' if models in {
            '1756-IF8 1756-IF8K', '1756-IF16 1756-IF16K'} else 'documented_capacity')
        family = '1756 ControlLogix analogue I/O' if kind in {'ai', 'ao'} else '1756 ControlLogix digital I/O'
        add(models, description, family, 'field_io', {kind: count}, basis, IO_REFERENCE, page, '1756-TD002M-EN-E')
    add('1756-IF4FXOF2F 1756-IF4FXOF2FK', 'Fast analogue inputs and outputs',
        '1756 ControlLogix mixed analogue I/O', 'field_io', {'ai': 4, 'ao': 2},
        'documented_capacity', IO_REFERENCE, 40, '1756-TD002M-EN-E')
    # 1794-UM062B-EN-P (March 2020), physical input/output counts on
    # printed pages 45-46. Configuration/status word counts are not channels.
    for models, capacity, description, page in (
        ('1794-IE8 1794-IE8XT', {'ai': 8}, 'Voltage/current inputs', 45),
        ('1794-IE12', {'ai': 12}, 'Voltage/current inputs', 45),
        ('1794-OE4 1794-OE4XT', {'ao': 4}, 'Voltage/current outputs', 46),
        ('1794-OE12', {'ao': 12}, 'Voltage/current outputs', 46),
        ('1794-IE4XOE2 1794-IE4XOE2XT', {'ai': 4, 'ao': 2}, 'Analogue inputs and outputs', 45),
        ('1794-IE8XOE4', {'ai': 8, 'ao': 4}, 'Analogue inputs and outputs', 45),
    ):
        add(models, description, '1794 FLEX analogue I/O', 'field_io', capacity,
            'documented_capacity', FLEX_ANALOG_REFERENCE, page, '1794-UM062B-EN-P')
    for models, description, page in _COMMUNICATION:
        add(models, description, '1756 ControlLogix communications', 'communication', {},
            'not_applicable', COMMUNICATION_REFERENCE, page, '1756-TD003R-EN-E')
    for models, description in _CONTROLLERS:
        add(models, description, '1756 Logix controllers', 'controller', {},
            'not_applicable', CONTROLLER_REFERENCE, 2, '1756-TD001U-EN-P')
    return MappingProxyType(result)


CATALOG_LIBRARY = _build()
# A convenience for single-type consumers, never use this to decide that an
# omitted mixed/controller/network product is an unknown product.
CATALOG_TYPES = MappingProxyType({catalog: record['field_types'][0]
    for catalog, record in CATALOG_LIBRARY.items() if len(record['field_types']) == 1})


def lookup_catalog(catalog_number: str, vendor: str | None) -> dict[str, Any] | None:
    """Return detached JSON-compatible metadata only for an exact vendor/model.

    Caller must independently qualify source namespaces and reject authored
    replacement catalogs. Case changes, suffix guesses and series stripping are
    intentionally not performed here.
    """
    if type(catalog_number) is not str or type(vendor) is not str or vendor != '1':
        return None
    record = CATALOG_LIBRARY.get(catalog_number)
    if record is None:
        return None
    return {**record, 'field_types': list(record['field_types']), 'capacity': dict(record['capacity'])}
