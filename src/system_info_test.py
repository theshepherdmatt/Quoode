#!/usr/bin/env python3

import psutil
import subprocess
import re
import time

def get_cpu_usage():
    """
    Return the CPU usage percentage over 1 second.
    """
    # psutil.cpu_percent(...) calculates usage over an interval.
    return psutil.cpu_percent(interval=1)

def get_memory_usage():
    """
    Return (used_mem_mb, total_mem_mb, usage_percent).
    """
    mem_info = psutil.virtual_memory()
    used_mb = mem_info.used // (1024 * 1024)
    total_mb = mem_info.total // (1024 * 1024)
    usage_pct = mem_info.percent
    return used_mb, total_mb, usage_pct

def get_cpu_temp():
    """
    Return the CPU temperature in Celsius if available.
    Fallback to None if not available on this system.
    """
    temps = psutil.sensors_temperatures()
    if not temps:
        return None

    # 'cpu_thermal' or 'thermal_zone0' or 'soc_thermal' are common keys on Pi.
    # Try a few known keys:
    for key in ("cpu_thermal", "thermal_zone0", "soc_thermal"):
        if key in temps:
            # Usually a list of SensorTemperatures is returned
            return temps[key][0].current

    # If none of the known keys found
    return None

def get_ip_addresses():
    """
    Use `hostname -I` to get all IPs assigned (e.g. eth0, wlan0).
    Returns a list of IP strings or an empty list on error.
    """
    try:
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            # Split on whitespace => multiple IPs
            ips = result.stdout.strip().split()
            return ips
        else:
            return []
    except Exception:
        return []

def get_wifi_signal(interface="wlan0"):
    """
    Parse signal strength from `iwconfig <interface>` or None if not found.
    """
    try:
        # e.g. "iwconfig wlan0" => output with "Link Quality=..." or "Signal level=..."
        result = subprocess.run(["iwconfig", interface], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return None

        output = result.stdout.lower()

        # Common patterns:
        #   Link Quality=70/70  Signal level=-40 dBm
        # or
        #   Signal level=-46 dBm
        # We'll do a quick regex to capture "signal level=-NN dBm"
        match_signal = re.search(r"signal level=(-?\d+)\s*dBm", output)
        if match_signal:
            signal_dbm = int(match_signal.group(1))
            return signal_dbm

        # If not found, you might also parse "link quality=XX/YY"
        match_link = re.search(r"link quality=(\d+)/(\d+)", output)
        if match_link:
            quality_now = int(match_link.group(1))
            quality_max = int(match_link.group(2))
            # Convert to approximate percent
            quality_pct = (quality_now / quality_max) * 100.0
            return round(quality_pct, 1)  # e.g. 78.6%
        
        return None  # Not found
    except Exception:
        return None

def main():
    print("Testing system info retrieval...\n")

    cpu_usage = get_cpu_usage()
    mem_used_mb, mem_total_mb, mem_pct = get_memory_usage()
    cpu_temp = get_cpu_temp()
    ips = get_ip_addresses()
    wifi_signal = get_wifi_signal("wlan0")  # or your interface

    print(f"CPU Usage  : {cpu_usage:.1f}%")
    if cpu_temp is not None:
        print(f"CPU Temp   : {cpu_temp:.1f} °C")
    else:
        print("CPU Temp   : Not available")

    print(f"Memory     : {mem_used_mb} MB used / {mem_total_mb} MB total ({mem_pct:.1f}%)")
    if ips:
        print(f"IP Address : {ips}")
    else:
        print("IP Address : None found")

    if wifi_signal is None:
        print("Wi-Fi      : Not found or not on Wi-Fi")
    elif isinstance(wifi_signal, int) and wifi_signal < 0:
        # Probably dBm
        print(f"Wi-Fi Signal: {wifi_signal} dBm")
    else:
        # Probably a % link quality
        print(f"Wi-Fi Quality: {wifi_signal}%")

    print("\nDone.\n")

if __name__ == "__main__":
    main()
