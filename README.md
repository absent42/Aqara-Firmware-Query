# Aqara Device Firmware Query

A python script to query and download the OTA firmware the Aqara cloud offers for devices linked on your account. It prints the server's response as returned and offers and optional download.

## Usage

```
python3 aqara_firmware.py --region <REGION> --did <DID>
```

### Interactive

Leave out `--did` to pick a device from your account:

```
python3 aqara_firmware.py --region <REGION>
```

```
Devices on this account:
   1. Living room
        lumi.motion.agl001  lumi1.123456789abc  firmware 1.3.6_0003.0099
   2. Hub M3
        lumi.gateway.agl004  lumi1.abcdef123456  firmware 4.5.70_0011

Device number [1-2]: 1

Living room (lumi.motion.agl001, lumi1.123456789abc)
Installed firmware: 1.3.6_0003.0099

   1. [zigbee] 1.3.6_0003.0099 -> 1.3.6_0003.0100  (2.4 MB)
        20250923130946_lumi.motion.agl001_radar_V0100_20250920_445ED8.bin
        Released:     2025-09-23 05:09 UTC
        MD5:          0123456789abcdef0123456789445ed8
        CRC32:        1A2B3C4D
        Install time: ~60 s
        URL:          https://cdn.aqara.com/cdn/opencloud-product/.../20250923130946_lumi.motion.agl001_radar_V0100_20250920_445ED8.bin
        Update log:   Fix known issues

[d]ownload, show [j]son or [q]uit? [d]
Download directory [.]: firmware

Downloading 20250923130946_lumi.motion.agl001_radar_V0100_20250920_445ED8.bin
  [##############################] 100%  2.4 MB / 2.4 MB  8.4 MB/s
  saved firmware/20250923130946_lumi.motion.agl001_radar_V0100_20250920_445ED8.bin (size and MD5 verified)
  metadata firmware/20250923130946_lumi.motion.agl001_radar_V0100_20250920_445ED8.bin.json
```

Each offered update shows the fields the server returned: release date (UTC), `firmwareMD5`, `firmwareCRC32`, `firmwareSha256` (when not empty), whether it is mandatory, the expected install time, `downloadUrl` and `updateLog`.

Downloads are checked against `fileSize` and `firmwareMD5`; a mismatching file is deleted. See [Downloads](#downloads) for the metadata file saved next to each firmware file.

### Scripted

With `--did` the script prints the server's JSON response unchanged (see [Output](#output)). Add `--download <DIR>` to also download the offered files, and use `--list` to print your devices (`did`, `model`, `deviceName`, `firmwareVersion`) as JSON:

```
python3 aqara_firmware.py --region <REGION> --list
python3 aqara_firmware.py --region <REGION> --did <DID> --download firmware/
```

Authenticate and create the necessary userid/token with your Aqara account username/password (the script prompts for anything not passed on the command line) or by reusing a `--userid`/`--token` pair from a previous login.

On a successful username/password login the script prints a line (to stderr) you can copy to skip the login on subsequent runs:

```
# logged in. Reuse next time with:  --userid <ID> --token <TOKEN>
```

## Options

| Flag | Required | Description |
| --- | --- | --- |
| `--region` | yes | Server region, one of: `EU`, `US`, `CN`, `RU`, `KR`, `AU`. A server host (`rpc-ger.aqara.com`) or full URL (`https://rpc-ger.aqara.com`) is also accepted. |
| `--did` | no | Device DID, e.g. `lumi1.123456789abc`. Prints the JSON response. If omitted, the script lists your devices, shows what is offered and asks whether to download it or show the JSON. |
| `--list` | no | Print the account's devices (`did`, `model`, `deviceName`, `firmwareVersion`) as JSON and exit. |
| `--download` | no | Directory to download the offered firmware into (interactive mode asks if omitted). Each file is checked against `fileSize` and `firmwareMD5`; a mismatch deletes it and exits with code `1`. A `<file>.json` with the update's full metadata is written next to each verified file. |
| `--username` | no | Aqara account username (email or phone). Prompted if omitted and no token is given. |
| `--password` | no | Aqara account password. Prompted (hidden) if omitted and no token is given. |
| `--userid` | no | Reuse a previous login's user id (with `--token`). |
| `--token` | no | Reuse a previous login's token (with `--userid`). |

## Example

```
$ python3 aqara_firmware.py --region EU --did lumi1.123456789abc
Aqara username (email/phone): me@example.com
Aqara password:
# logged in. Reuse next time with:  --userid 12345 --token abcdef...

{
    "result": [
        {
            "firmwareType": "main",
            "deviceModel": "lumi.gateway.agl004",
            "firmwareVersion": "4.5.70_0011",
            "upgradeFirmware": {
                "firmwareVersion": "4.5.80_0007",
                "downloadUrl": "https://cdn.aqara.com/cdn/opencloud-product/.../firmwarefilename.ota",
                "fileSize": 33638504,
                "firmwareMD5": "12345678901234567890",
                "updateLog": "1. Optimized device-related functions 2. Fixed known issues",
                ...
            },
            "deviceOnline": 1,
            "deviceName": "Hub M3",
            "did": "lumi1.123456789abc",
            ...
        }
    ],
    "code": 0,
    "message": "Success",
    ...
}
```

Reuse the printed token to skip the login:

```
$ python3 aqara_firmware.py --region EU --did lumi1.123456789abc --userid 12345 --token abcdef...
```

Run with `--help` for a summary of the modes, options, regions and examples.

## Downloads

Each downloaded file is saved into the download directory under the server's file name and checked against `fileSize` and `firmwareMD5`. Once it passes, a metadata file with the same name plus `.json` is written alongside it, holding the full server entry for that update:

```
firmware/
  firmwarefilename.ota
  firmwarefilename.json
```

```
{
    "firmwareType": "main",
    "deviceModel": "lumi.gateway.agl004",
    "firmwareVersion": "4.5.70_0011",
    "upgradeFirmware": {
        "releaseDate": 1788748559000,
        "downloadUrl": "https://cdn.aqara.com/cdn/opencloud-product/.../firmwarefilename.ota",
        "upgradeTakesTime": 40,
        "updateLog": "1. Optimized device-related functions 2. Fixed known issues",
        "fileSize": 33638504,
        "firmwareMD5": "12345567890abcd",
        "firmwareCRC32": "06890B5B",
        "firmwareVersion": "4.5.80_0007",
        ...
    },
    "deviceName": "Hub M3",
    "did": "lumi1.123456789abc",
    ...
}
```

This keeps the update details (versions, checksums, release date, update log) with the firmware, including in interactive mode where the JSON response is not printed when you choose to download. Timestamps such as `releaseDate` are milliseconds since the epoch.

The metadata file includes your device DID, device name and home/room names (`real1Name`, `real2Name`, `realPositionId`, `real2PositionId`). Review it before sharing it with anyone.

## Output

- The JSON response is printed to stdout unchanged (indented). Login and error messages go to stderr, so the output can be piped straight into a tool such as `jq`:

  ```
  python3 aqara_firmware.py --region EU --did lumi1.123456789abc --userid 12345 --token abcdef... \
      | jq -r '.result[].upgradeFirmware.downloadUrl'
  ```

- `firmwareVersion` is the version currently on the device. `upgradeFirmware` holds the update on offer, including `downloadUrl`, `firmwareMD5`, `fileSize` and `updateLog`.
- The exit code is `0` when the response `code` is `0`, and `1` otherwise (for example `108`, token expired).
- If there is no update available for your device, the output will look like this:
   ```
   {
    "result": [],
    "code": 0,
    "requestId": "12345678901234567890.12.12345678901234567890",
    "message": "Success",
    "msgDetails": "Success"
    }
    ```

## Notes

- The DID must belong to a device on the logged-in account, and the region must be the server that account is registered on.
- A device DID can found in the Aqara App settings for your device, usually called "Accessory ID". They usually start with lumi. lumi1. or lumi3. Not every app version shows it; `--list` prints it.
- If no update is on offer, `upgradeFirmware` may be empty or missing.
- Tokens expire. If a run returns code `108`, log in again with username/password.
- Without `--download` the script does not download firmware. Use `downloadUrl` from the response, and check the file against `firmwareMD5`. Firmware downloaded this way does not get a metadata file; save the JSON response yourself.
- Some devices get more than one file. For example the Presence Sensor FP2 (`lumi.motion.agl001`) receives its radar firmware as a separate `zigbee` entry.
- For use from Python, `AqaraClient` wraps a session: `AqaraClient.login(host, username, password)`, then `devices()`, `firmware(did)`, `offers(response)` and `download(offer, directory)`. `download()` only saves and verifies the firmware; the metadata file is written by the command-line script.

## Aqara Firmware Archive

If you have downloaded a firmware missing from the Aqara Firmware Archive, please contribute it 
via a [pull request](https://github.com/absent42/Aqara-Firmware-Archive/pulls).

## Disclaimer

For interoperability with devices you own. Not affiliated with, endorsed by, or supported by Aqara. Use at your own risk. Flashing incorrect firmware may brick a device.
The embedded app credentials and RSA public key are already public and documented across
various open-source projects.
