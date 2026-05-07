"""Logical feature groups used by the motor anomaly feature pipeline."""

basic_features = [
    "speed_rpm",
    "speed_Hz",
    "Current",
    "Voltage",
    "temp_mot",
    "temp_amb",
]

vibration_features = [f"{i}x[Vibration]" for i in range(1, 11)]
current_harmonics = [f"{i}x[Current]" for i in range(1, 11)]
voltage_harmonics = [f"{i}x[Voltage]" for i in range(1, 11)]

freq_bands = [
    "0-4kHz",
    "4-8kHz",
    "8-16kHz",
    "16-26kHz",
]

raw_freq_bands = [
    "0-4k_Hz",
    "4k-8k_Hz",
    "8k-16kHz",
    "16k-26kHz",
]

vibration_freq_bands = [f"{band}[Vibration]" for band in raw_freq_bands]
current_freq_bands = [f"{band}[Current]" for band in raw_freq_bands]
voltage_freq_bands = [f"{band}[Voltage]" for band in raw_freq_bands]

all_feature_groups = {
    "basic": basic_features,
    "vibration": vibration_features,
    "current_harmonics": current_harmonics,
    "voltage_harmonics": voltage_harmonics,
    "vibration_freq_bands": vibration_freq_bands,
    "current_freq_bands": current_freq_bands,
    "voltage_freq_bands": voltage_freq_bands,
}

# Backward-compatible aliases for notebooks or scripts that import constants.
BASIC_FEATURES = basic_features
VIBRATION_HARMONICS = vibration_features
CURRENT_HARMONICS = current_harmonics
VOLTAGE_HARMONICS = voltage_harmonics
FREQUENCY_BANDS = freq_bands
VIBRATION_FREQUENCY_BANDS = vibration_freq_bands
CURRENT_FREQUENCY_BANDS = current_freq_bands
VOLTAGE_FREQUENCY_BANDS = voltage_freq_bands
ALL_FEATURE_GROUPS = all_feature_groups
