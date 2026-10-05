#!/usr/bin/env python3
"""Aqara device firmware query

Given an Aqara account (username/password or userid/token), a server region, and a
device DID (e.g. lumi1.123456789abc), prints the server's OTA firmware response for that
device as returned.

For interoperability with devices you own. Not affiliated with Aqara. Use at your own
risk. The embedded app credentials and RSA public key are already public/documented across
various open-source projects.
"""
from __future__ import annotations
import argparse, base64, getpass, hashlib, json, os, ssl, sys, urllib.error, urllib.request, uuid, time

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


def query_firmware(host, token, userid, combos, did):
    """GET the firmware query for `did`, trying each combo until one is not rejected as unsigned (106)."""
    q = "did=" + did
    r = None
    for appid, appkey in combos:
        r = request(host, "GET", FIRMWARE_PATH, q, token, appid, appkey, userid)
        if str(r.get("code")) != "106":
            return r
    raise AqaraError(f"could not sign requests for this region with the supplied token; last={r}")


def resolve_host(region):
    """Accept a region key (EU, US, ...) or a server host/URL (e.g. rpc-ger.aqara.com)."""
    if region.upper() in REGIONS:
        return REGIONS[region.upper()]
    host = region.rstrip("/")
    return host if host.startswith(("http://", "https://")) else "https://" + host


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Query the Aqara OTA firmware for a single device by DID.")
    ap.add_argument("--region", required=True,
                    help=f"server region ({', '.join(sorted(REGIONS))}) or host, e.g. rpc-ger.aqara.com")
    ap.add_argument("--did", required=True, help="device DID, e.g. lumi1.123456789abc")
    ap.add_argument("--username"); ap.add_argument("--password")
    ap.add_argument("--userid"); ap.add_argument("--token")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    host = resolve_host(args.region)
    try:
        if args.token and args.userid:
            token, userid, combos = args.token, args.userid, COMBOS
        else:
            username = args.username or input("Aqara username (email/phone): ").strip()
            password = args.password or getpass.getpass("Aqara password: ")
            userid, token, combo = login(host, username, password)
            combos = [combo]
            print(f"# logged in. Reuse next time with:  --userid {userid} --token {token}\n", file=sys.stderr)
        r = query_firmware(host, token, userid, combos, args.did)
        print(json.dumps(r, indent=4, ensure_ascii=False))
        return 0 if str(r.get("code")) == "0" else 1
    except AqaraError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
