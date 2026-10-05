# Aqara Device Firmware Query

A python script to query the OTA firmware the Aqara cloud offers for a single device on your account, identified by its DID. It prints the server's response as returned.

## Usage

```
python3 aqara_firmware.py --region <REGION> --did <DID>
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
| `--did` | yes | Device DID, e.g. `lumi1.123456789abc` |
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
- A device DID can found in the Aqara App settings for your device, usually called "Accessory ID".
- If no update is on offer, `upgradeFirmware` may be empty or missing.
- Tokens expire. If a run returns code `108`, log in again with username/password.
- The script does not download firmware. Use `downloadUrl` from the response, and check the file against `firmwareMD5`.

## Disclaimer

For interoperability with devices you own. Not affiliated with, endorsed by, or supported by Aqara. Use at your own risk. Flashing incorrect firmware may brick a device.
The embedded app credentials and RSA public key are already public and documented across
various open-source projects.
