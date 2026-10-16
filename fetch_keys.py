import json
import sys

import tinytuya


def main():
    if len(sys.argv) < 3:
        print("Usage: python fetch_keys.py <ACCESS_ID> <ACCESS_SECRET> [REGION]")
        print("Example: python fetch_keys.py your_access_id your_access_secret eu")
        return

    api_key = sys.argv[1].strip()
    api_secret = sys.argv[2].strip()
    region = sys.argv[3].strip() if len(sys.argv) > 3 else "eu"

    print(f"Connecting to Tuya Cloud (region: {region})...")
    # Try to load device ID from snapshot.json if available
    known_dev_id = None
    try:
        with open("snapshot.json") as f:
            snap = json.load(f)
            if snap.get("devices"):
                known_dev_id = snap["devices"][0].get("id")
    except Exception:
        pass

    c = tinytuya.Cloud(
        apiRegion=region, apiKey=api_key, apiSecret=api_secret, apiDeviceID=known_dev_id
    )

    devices = c.getdevices()
    if not devices:
        print("[-] getdevices() returned empty, attempting direct query using device ID...")
        if known_dev_id:
            dev_info = c.getdevicesummary(known_dev_id)
            print("Device summary:", dev_info)
        print("[-] Check if project has 'IoT Core' API authorized and account is linked.")
        return

    print(f"[+] Successfully fetched {len(devices)} device(s)!\n")
    for dev in devices:
        name = dev.get("name", "Unknown")
        dev_id = dev.get("id", "")
        key = dev.get("key", "")
        product_name = dev.get("product_name", "")
        print(f"Device: {name} ({product_name})")
        print(f"  Device ID: {dev_id}")
        print(f"  Local Key: {key}")
        print("-" * 40)

    with open("tuya_devices.json", "w") as f:
        json.dump(devices, f, indent=4)
    print("\nSaved full details to tuya_devices.json")


if __name__ == "__main__":
    main()
