import math
from typing import List, Dict, Any, Tuple, Optional
from models import ProfileMeasurement, AnomalyDetail

def get_region(lat: float, lon: float) -> str:
    if lat >= 5.0 and lon <= 77.5:
        return "Arabian Sea"
    elif lat >= 5.0 and lon > 77.5:
        return "Bay of Bengal"
    elif lat >= -10.0 and lat < 5.0:
        return "Equatorial Indian Ocean"
    else:
        return "Southern Indian Ocean"

def get_climatology_baseline(region: str, month: int, depth: float, variable: str) -> Tuple[float, float]:
    """
    Returns (mean, std_dev) for a given region, month, depth, and variable.
    Based on INCOIS regional climatology baseline statistics.
    """
    # Depth attenuation factors
    if depth <= 20:
        d_factor = 1.0
    elif depth <= 100:
        d_factor = 0.8
    elif depth <= 300:
        d_factor = 0.5
    elif depth <= 1000:
        d_factor = 0.25
    else:
        d_factor = 0.1

    if variable == "temperature":
        # Base surface temperature by region
        if region == "Arabian Sea":
            base_temp = 28.5 if month in [5, 6, 7, 8] else 26.8
            std = 0.8 * d_factor + 0.2
        elif region == "Bay of Bengal":
            base_temp = 29.2 if month in [4, 5, 9, 10] else 27.5
            std = 0.7 * d_factor + 0.2
        elif region == "Equatorial Indian Ocean":
            base_temp = 28.3
            std = 0.65 * d_factor + 0.15
        else:
            base_temp = 22.0 - (abs(depth) / 100.0) * 0.5
            std = 0.9 * d_factor + 0.2

        # Temperature decreases exponentially with depth
        if depth <= 50:
            mean = base_temp - (depth / 50.0) * 1.5
        elif depth <= 200:
            # Thermocline
            mean = (base_temp - 1.5) - ((depth - 50) / 150.0) * 12.0
        elif depth <= 1000:
            mean = 14.8 - ((depth - 200) / 800.0) * 8.3
        else:
            mean = 6.5 - ((depth - 1000) / 1000.0) * 4.0
        return max(1.8, round(mean, 2)), max(0.15, round(std, 2))

    elif variable == "salinity":
        # Arabian Sea is high salinity (evaporation), Bay of Bengal is low salinity (river inflow)
        if region == "Arabian Sea":
            base_sal = 36.4 if depth < 50 else 35.8
            std = 0.45 * d_factor + 0.1
        elif region == "Bay of Bengal":
            base_sal = 32.8 if depth < 50 else 34.6
            std = 0.65 * d_factor + 0.1
        elif region == "Equatorial Indian Ocean":
            base_sal = 34.8
            std = 0.35 * d_factor + 0.1
        else:
            base_sal = 35.2
            std = 0.3 * d_factor + 0.1

        if depth > 500:
            mean = 34.8 - ((depth - 500) / 1500.0) * 0.2
        else:
            mean = base_sal
        return round(mean, 2), max(0.08, round(std, 2))

    elif variable == "chlorophyll":
        # Subsurface chlorophyll maximum around 50-80m
        if depth > 200:
            mean = 0.03
            std = 0.015
        elif 40 <= depth <= 90:
            mean = 0.92
            std = 0.28
        elif depth < 40:
            mean = 0.48
            std = 0.18
        else:
            mean = 0.22
            std = 0.10
        return round(mean, 3), max(0.01, round(std, 3))

    return 0.0, 1.0

def evaluate_profile_anomalies(
    lat: float,
    lon: float,
    month: int,
    measurements: List[ProfileMeasurement],
    z_threshold: float = 2.0
) -> Tuple[List[AnomalyDetail], bool, float]:
    """
    Evaluates profile measurements against regional climatology baseline.
    Returns (list_of_anomalies, has_anomaly_boolean, max_z_score).
    """
    region = get_region(lat, lon)
    anomalies: List[AnomalyDetail] = []
    max_z = 0.0

    for m in measurements:
        depth = m.depth
        # Evaluate Temperature
        if m.temperature is not None and not math.isnan(m.temperature) and m.temp_qc <= 2:
            mean, std = get_climatology_baseline(region, month, depth, "temperature")
            z = (m.temperature - mean) / std if std > 0 else 0.0
            abs_z = abs(z)
            if abs_z > max_z:
                max_z = abs_z

            if abs_z >= z_threshold:
                severity = "Extreme" if abs_z >= 4.0 else ("High" if abs_z >= 3.0 else "Moderate")
                direction = "warmer" if z > 0 else "colder"
                explanation = (
                    f"This reading is {abs(m.temperature - mean):.1f}°C {direction} than the typical "
                    f"monthly baseline ({mean:.1f}°C) at {depth}m depth in {region} (|z| = {abs_z:.1f}σ)."
                )
                anomalies.append(
                    AnomalyDetail(
                        is_anomaly=True,
                        variable="temperature",
                        depth=depth,
                        observed_value=m.temperature,
                        climatology_mean=mean,
                        climatology_std=std,
                        z_score=round(z, 2),
                        severity=severity,
                        explanation=explanation
                    )
                )

        # Evaluate Salinity
        if m.salinity is not None and not math.isnan(m.salinity) and m.sal_qc <= 2:
            mean, std = get_climatology_baseline(region, month, depth, "salinity")
            z = (m.salinity - mean) / std if std > 0 else 0.0
            abs_z = abs(z)
            if abs_z > max_z:
                max_z = abs_z

            if abs_z >= z_threshold:
                severity = "Extreme" if abs_z >= 4.0 else ("High" if abs_z >= 3.0 else "Moderate")
                direction = "higher" if z > 0 else "lower"
                explanation = (
                    f"Salinity is {abs(m.salinity - mean):.2f} PSU {direction} than the regional "
                    f"baseline ({mean:.2f} PSU) at {depth}m depth in {region} (|z| = {abs_z:.1f}σ)."
                )
                anomalies.append(
                    AnomalyDetail(
                        is_anomaly=True,
                        variable="salinity",
                        depth=depth,
                        observed_value=m.salinity,
                        climatology_mean=mean,
                        climatology_std=std,
                        z_score=round(z, 2),
                        severity=severity,
                        explanation=explanation
                    )
                )

        # Evaluate Chlorophyll
        if m.chlorophyll is not None and not math.isnan(m.chlorophyll) and m.chla_qc <= 2:
            mean, std = get_climatology_baseline(region, month, depth, "chlorophyll")
            z = (m.chlorophyll - mean) / std if std > 0 else 0.0
            abs_z = abs(z)
            if abs_z > max_z:
                max_z = abs_z

            if abs_z >= z_threshold:
                severity = "Extreme" if abs_z >= 4.0 else ("High" if abs_z >= 3.0 else "Moderate")
                direction = "elevated bloom" if z > 0 else "depleted"
                explanation = (
                    f"Chlorophyll concentration ({m.chlorophyll:.2f} mg/m³) shows {direction} "
                    f"relative to baseline ({mean:.2f} mg/m³) at {depth}m in {region} (|z| = {abs_z:.1f}σ)."
                )
                anomalies.append(
                    AnomalyDetail(
                        is_anomaly=True,
                        variable="chlorophyll",
                        depth=depth,
                        observed_value=m.chlorophyll,
                        climatology_mean=mean,
                        climatology_std=std,
                        z_score=round(z, 2),
                        severity=severity,
                        explanation=explanation
                    )
                )

    has_anomaly = len(anomalies) > 0
    return anomalies, has_anomaly, round(max_z, 2)
