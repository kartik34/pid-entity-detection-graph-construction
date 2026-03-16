"""
Shared tag taxonomy for component typing and major equipment classification.
"""

PREFIX_TYPES = {
    "F": "filter_separator",
    "V": "vessel",
    "P": "pump",
    "E": "heat_exchanger",
    "AC": "after_cooler",
    "MV": "motor_valve",
    "PSV": "pressure_safety_valve",
    "RV": "relief_valve",
    "PI": "pressure_indicator",
    "TI": "temperature_indicator",
    "DR": "differential_recorder",
    "LI": "level_indicator",
    "PT": "pressure_transmitter",
    "TT": "temperature_transmitter",
}

MAJOR_PREFIXES = {"V", "F", "P", "E", "AC"}
