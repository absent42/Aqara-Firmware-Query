#!/usr/bin/env python3
"""Aqara device firmware query

Given an Aqara account (username/password or userid/token), a server region, and a
device DID (e.g. lumi1.123456789abc), prints the server's OTA firmware response for that
device as returned. Without --did, lists the account's devices and lets you pick one.
With --download DIR, also downloads the offered firmware files and verifies their MD5.

For interoperability with devices you own. Not affiliated with Aqara. Use at your own
risk. The embedded app credentials and RSA public key are already public/documented across
various open-source projects.
"""
from __future__ import annotations
import argparse, base64, getpass, hashlib, json, os, ssl, sys, urllib.error, urllib.parse, urllib.request, uuid, time

RSA_N = 0x86e3ab25079ef4d77249b3856f8f9715c8ca51f5bf81d85f98254eaa8411186e212621d5a914fa4eb818a40ecd8570f4b5f4c896ab522b9b126d908086baba8899152de253faf3c2169449aa1df4b14917f6f9a1f4707f15599d8e6999f90d64881c83c117693133bd6af2cb66a18895d2866cad9cc11ec32e0700382d077107
RSA_E = 65537

REGIONS = {
    "CN": "https://aiot-rpc.aqara.cn",
    "EU": "https://rpc-ger.aqara.com",
    "US": "https://aiot-rpc-usa.aqara.com",
    "RU": "https://rpc-ru.aqara.com",
    "KR": "https://rpc-kr.aqara.com",
    "AU": "https://rpc-au.aqara.com",
}
COMBOS = [
    ("7be1984f0556276133336839", "Jddz01kIORDYrBzqGYgpUXKBnIHfW8E3"),
    ("94549908487478b220992a70", "Jddz01kIORDYrBzqGYgpUXKBnIHfW8E3"),
    ("94549908487478b220992a70", "euGhPe2rcmxwculATNj45eEtnd50zp0I"),
]
_CLIENT_HEADERS = {"User-Agent": "okhttp/4.12.0", "App-Version": "6.1.6",
                   "Sys-Type": "1", "Lang": "en", "Phone-Model": "Pixel 6##Mobile"}
_CTX = ssl.create_default_context()
FIRMWARE_PATH = "/app/v1.0/lumi/ota/query/firmware"
DEVICE_LIST_PATH = "/app/v1.0/lumi/app/position/device/query"
DOWNLOAD_HOSTS = ("aqara.com", "aqara.cn")


def rsa_encrypt(password: str) -> str:
    """base64( RSA-PKCS1v1.5( md5(password).hexdigest() ) )"""
    payload = hashlib.md5(password.encode()).hexdigest().encode()
    k = (RSA_N.bit_length() + 7) // 8
    ps_len = k - 3 - len(payload)
    if ps_len < 8:
        raise ValueError("payload too long for RSA block")
    ps = bytearray()
    while len(ps) < ps_len:
        ps.extend(b for b in os.urandom(ps_len - len(ps)) if b != 0)
    em = b"\x00\x02" + bytes(ps[:ps_len]) + b"\x00" + payload
    c = pow(int.from_bytes(em, "big"), RSA_E, RSA_N)
    return base64.b64encode(c.to_bytes(k, "big")).decode()


def sign(appid: str, appkey: str, token: str, nonce: str, ts: str, body: str) -> str:
    tok = f"&Token={token}" if token else ""
    src = f"Appid={appid}&Nonce={nonce}&Time={ts}{tok}&{body}&{appkey}"
    return hashlib.md5(src.encode()).hexdigest()


def request(host, method, path, signsrc, token, appid, appkey, userid, body=None):
    nonce = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()
    ts = str(round(time.time() * 1000))
    headers = {**_CLIENT_HEADERS, "PhoneId": str(uuid.uuid4()).upper(),
               "Appid": appid, "Nonce": nonce, "Time": ts, "Content-Type": "application/json",
               "Sign": sign(appid, appkey, token, nonce, ts, signsrc)}
    if token: headers["Token"] = token
    if userid: headers["Userid"] = userid
    url = host + path + (("?" + signsrc) if method == "GET" and signsrc else "")
    data = body.encode() if (method == "POST" and body is not None) else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try: text = e.read().decode("utf-8", "replace")
        except Exception: return {"code": "transport", "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"code": "transport", "error": str(e)[:120]}
    try:
        return json.loads(text)
    except Exception:
        return {"code": "transport", "error": f"non-JSON response: {text[:80]!r}"}


class AqaraError(Exception): ...


def login(host, username, password):
    body = json.dumps({"account": username, "encryptType": 2, "password": rsa_encrypt(password)})
    last = None
    for appid, appkey in COMBOS:
        r = request(host, "POST", "/app/v1.0/lumi/user/login", body, "", appid, appkey, "", body=body)
        code = str(r.get("code")); last = r
        if code == "106":
            continue
        if code == "0":
            res = r.get("result") or {}
            uid, tok = res.get("userId"), res.get("token")
            if not uid or not tok:
                raise AqaraError(f"login ok but no userId/token (keys {sorted(res)})")
            return uid, tok, (appid, appkey)
        raise AqaraError(f"login failed (code={code} msg={r.get('message')!r}) - check username/password/region")
    raise AqaraError(f"could not sign login for region; last={last}")


def signed_get(host, token, userid, combos, path, q):
    """GET `path` with query `q`, trying each combo until one is not rejected as unsigned (106)."""
    r = None
    for appid, appkey in combos:
        r = request(host, "GET", path, q, token, appid, appkey, userid)
        if str(r.get("code")) != "106":
            return r
    raise AqaraError(f"could not sign requests for this region with the supplied token; last={r}")


def query_firmware(host, token, userid, combos, did):
    """GET the firmware query for `did`, trying each combo until one is not rejected as unsigned (106)."""
    return signed_get(host, token, userid, combos, FIRMWARE_PATH, "did=" + did)


class AqaraClient:
    """A logged-in session: list devices, query the firmware offered for one, download it."""

    def __init__(self, host, userid, token, combos=COMBOS):
        self.host, self.userid, self.token, self.combos = host, userid, token, list(combos)

    @classmethod
    def login(cls, host, username, password):
        userid, token, combo = login(host, username, password)
        return cls(host, userid, token, [combo])

    def devices(self):
        """All devices on the account (raw cloud records: did, model, deviceName, firmwareVersion, ...)."""
        devices, start = [], 0
        while True:
            r = signed_get(self.host, self.token, self.userid, self.combos,
                           DEVICE_LIST_PATH, f"size=300&startIndex={start}")
            if str(r.get("code")) != "0":
                raise AqaraError(f"device list failed (code={r.get('code')} msg={r.get('message')!r})")
            page = (r.get("result") or {}).get("devices") or []
            devices += page
            if len(page) < 300:
                return devices
            start += len(page)

    def firmware(self, did):
        """The server's firmware response for `did`, unchanged."""
        return query_firmware(self.host, self.token, self.userid, self.combos, did)

    @staticmethod
    def offers(response):
        """Entries of a firmware response that carry a downloadable update."""
        return [e for e in response.get("result") or []
                if (e.get("upgradeFirmware") or {}).get("downloadUrl")]

    @staticmethod
    def download(offer, directory, progress=None):
        """Download one offer into `directory`, verify size and MD5, return the file path.
        `progress(done_bytes, total_bytes)` is called as data arrives (total may be None)."""
        up = offer["upgradeFirmware"]
        url = urllib.parse.urlparse(up["downloadUrl"])
        if not (url.hostname or "").endswith(DOWNLOAD_HOSTS):
            raise AqaraError(f"refusing to download from unexpected host {url.hostname!r}")
        expected_md5 = (up.get("firmwareMD5") or "").lower()
        path = os.path.join(directory, os.path.basename(url.path))
        os.makedirs(directory, exist_ok=True)
        md5, size = hashlib.md5(), 0
        with urllib.request.urlopen(url._replace(scheme="https").geturl(), timeout=60, context=_CTX) as r, \
                open(path + ".part", "wb") as f:
            total = int(up.get("fileSize") or r.headers.get("Content-Length") or 0) or None
            while chunk := r.read(1 << 16):
                md5.update(chunk); f.write(chunk); size += len(chunk)
                if progress:
                    progress(size, total)
        problem = None
        if up.get("fileSize") and size != int(up["fileSize"]):
            problem = f"size {size} != expected {up['fileSize']}"
        elif expected_md5 and md5.hexdigest() != expected_md5:
            problem = f"MD5 {md5.hexdigest()} != expected {expected_md5}"
        if problem:
            os.remove(path + ".part")
            raise AqaraError(f"{os.path.basename(path)}: {problem}")
        os.replace(path + ".part", path)
        return path


def mb(n):
    return f"{n / 1e6:.1f} MB"


def ask(prompt):
    """Prompt on stderr so stdout stays clean for JSON."""
    print(prompt, end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    if not line:
        raise AqaraError("aborted")
    return line.strip()


class ProgressBar:
    """Single-line download progress on stderr (silent when stderr is not a terminal)."""

    def __init__(self, width=30):
        self.width, self.start, self.last = width, time.monotonic(), 0.0
        self.enabled = sys.stderr.isatty()

    def __call__(self, done, total):
        now = time.monotonic()
        if not self.enabled or (now - self.last < 0.1 and done != total):
            return
        self.last = now
        rate = done / max(now - self.start, 1e-6)
        if total:
            filled = int(self.width * done / total)
            bar = f"[{'#' * filled}{'.' * (self.width - filled)}] {100 * done / total:3.0f}%  {mb(done)} / {mb(total)}"
        else:
            bar = mb(done)
        print(f"\r  {bar}  {mb(rate)}/s ", end="", file=sys.stderr, flush=True)

    def finish(self):
        if self.enabled:
            print(file=sys.stderr)


def pick_device(devices):
    """Interactive device menu on stderr; returns the chosen device record."""
    if not sys.stdin.isatty():
        raise AqaraError("no --did given and no terminal to choose one; use --list to see DIDs")
    if not devices:
        raise AqaraError("no devices on this account")
    print("\nDevices on this account:", file=sys.stderr)
    for i, d in enumerate(devices, 1):
        print(f"{i:>4}. {d.get('deviceName')}\n        {d.get('model')}  {d.get('did')}  "
              f"firmware {d.get('firmwareVersion')}", file=sys.stderr)
    choice = ask(f"\nDevice number [1-{len(devices)}]: ")
    if not choice.isdigit() or not 1 <= int(choice) <= len(devices):
        raise AqaraError(f"invalid choice {choice!r}")
    return devices[int(choice) - 1]


def show_offers(device, offers):
    """Human-readable summary of the firmware offered for `device`, on stderr."""
    print(f"\n{device.get('deviceName')} ({device.get('model')}, {device.get('did')})\n"
          f"Installed firmware: {device.get('firmwareVersion')}\n", file=sys.stderr)
    if not offers:
        print("No firmware update offered: the device is up to date.", file=sys.stderr)
        return
    for i, o in enumerate(offers, 1):
        up = o["upgradeFirmware"]
        size = mb(int(up["fileSize"])) if up.get("fileSize") else "size unknown"
        print(f"{i:>4}. [{o.get('firmwareType')}] {o.get('firmwareVersion')} -> {up.get('firmwareVersion')}  ({size})\n"
              f"        {os.path.basename(urllib.parse.urlparse(up['downloadUrl']).path)}", file=sys.stderr)
        if up.get("updateLog"):
            print(f"        {' '.join(str(up['updateLog']).split())}", file=sys.stderr)


def download_all(client, offers, directory):
    for o in offers:
        name = os.path.basename(urllib.parse.urlparse(o["upgradeFirmware"]["downloadUrl"]).path)
        print(f"\nDownloading {name}", file=sys.stderr)
        bar = ProgressBar()
        try:
            path = client.download(o, directory, progress=bar)
        finally:
            bar.finish()
        print(f"  saved {path} (size and MD5 verified)", file=sys.stderr)


def resolve_host(region):
    """Accept a region key (EU, US, ...) or a server host/URL (e.g. rpc-ger.aqara.com)."""
    if region.upper() in REGIONS:
        return REGIONS[region.upper()]
    host = region.rstrip("/")
    return host if host.startswith(("http://", "https://")) else "https://" + host


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Query (and optionally download) the Aqara OTA firmware for a device on your account.")
    ap.add_argument("--region", required=True,
                    help=f"server region ({', '.join(sorted(REGIONS))}) or host, e.g. rpc-ger.aqara.com")
    ap.add_argument("--did", help="device DID, e.g. lumi1.123456789abc; prints the JSON response "
                                  "(omit to pick a device interactively)")
    ap.add_argument("--list", action="store_true", help="print the account's devices as JSON and exit")
    ap.add_argument("--download", metavar="DIR", help="download the offered firmware into DIR and verify "
                                                      "size and MD5 (interactive mode asks if omitted)")
    ap.add_argument("--username"); ap.add_argument("--password")
    ap.add_argument("--userid"); ap.add_argument("--token")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    host = resolve_host(args.region)
    try:
        if args.token and args.userid:
            client = AqaraClient(host, args.userid, args.token)
        else:
            username = args.username or input("Aqara username (email/phone): ").strip()
            password = args.password or getpass.getpass("Aqara password: ")
            client = AqaraClient.login(host, username, password)
            print(f"# logged in. Reuse next time with:  --userid {client.userid} --token {client.token}\n", file=sys.stderr)
        if args.list:
            devices = [{k: d.get(k) for k in ("did", "model", "deviceName", "firmwareVersion")}
                       for d in client.devices()]
            print(json.dumps(devices, indent=4, ensure_ascii=False))
            return 0
        if args.did:
            # Scripted use: print the server's response unchanged, optionally download.
            r = client.firmware(args.did)
            print(json.dumps(r, indent=4, ensure_ascii=False))
            if args.download and str(r.get("code")) == "0":
                offers = client.offers(r)
                if not offers:
                    print("# no firmware offered for this device, nothing to download", file=sys.stderr)
                download_all(client, offers, args.download)
            return 0 if str(r.get("code")) == "0" else 1

        # Interactive use: pick a device, see what is offered, then download or show the JSON.
        device = pick_device(client.devices())
        r = client.firmware(device["did"])
        if str(r.get("code")) != "0":
            print(json.dumps(r, indent=4, ensure_ascii=False))
            raise AqaraError(f"firmware query failed (code={r.get('code')} msg={r.get('message')!r})")
        offers = client.offers(r)
        show_offers(device, offers)
        options = "[d]ownload, show [j]son or [q]uit? [d] " if offers else "Show [j]son or [q]uit? [q] "
        choice = (ask("\n" + options) or ("d" if offers else "q")).lower()[:1]
        if choice == "j":
            print(json.dumps(r, indent=4, ensure_ascii=False))
        elif choice == "d" and offers:
            directory = args.download or ask("Download directory [.]: ") or "."
            download_all(client, offers, directory)
        return 0
    except (AqaraError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
