#!/usr/bin/env python3
"""Client for the "C Drive窓口" Apps Script relay (tools/drive_relay/Code.gs).

Env:
  DRIVE_RELAY_URL  web app URL (…/exec)
  DRIVE_RELAY_KEY  shared key (read at run time from the owner's private Drive
                   file "C窓口キー_共有禁止.txt"; never commit it)

usage:
  drive_relay.py ping
  drive_relay.py list FOLDER_ID
  drive_relay.py info FILE_ID
  drive_relay.py upload LOCAL_PATH FOLDER_ID [--name NAME] [--mime MIME]
  drive_relay.py download FILE_ID OUT_PATH
Uploads and downloads are verified with size + MD5 against Drive's metadata.
"""
import base64, hashlib, json, mimetypes, os, sys, time, urllib.request, urllib.error

CHUNK_UP = 4 * 1024 * 1024     # multiple of 256 KiB
CHUNK_DOWN = 6 * 1024 * 1024


def _url():
    u = os.environ.get("DRIVE_RELAY_URL")
    if not u:
        sys.exit("DRIVE_RELAY_URL is not set")
    return u


def call(action, retries=4, **params):
    key = os.environ.get("DRIVE_RELAY_KEY")
    if not key:
        sys.exit("DRIVE_RELAY_KEY is not set")
    body = json.dumps({"key": key, "action": action, **params}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(_url(), data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:   # follows the 302 to googleusercontent as GET
                res = json.loads(r.read().decode())
            if res.get("ok"):
                return res
            if res.get("error") in ("unauthorized", "exists", "outside allowed folders", "bad name",
                                    "mimeType not allowed"):
                sys.exit(f"relay refused: {res['error']}")
            err = res.get("error")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            err = repr(e)
        wait = 2 ** (attempt + 1)
        print(f"  retry {action} in {wait}s: {err}", file=sys.stderr)
        time.sleep(wait)
    sys.exit(f"{action} failed: {err}")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def upload(path, folder, name=None, mime=None):
    name = name or os.path.basename(path)
    mime = mime or mimetypes.guess_type(name)[0] or "application/octet-stream"
    if name.endswith(".ass"):
        mime = "text/plain"
    size = os.path.getsize(path)
    init = call("upload_init", folderId=folder, name=name, size=size, mimeType=mime)
    uid, off, res = init["uploadId"], 0, None
    with open(path, "rb") as f:
        while off < size:
            chunk = f.read(CHUNK_UP)
            res = call("upload_chunk", uploadId=uid, offset=off,
                       data=base64.b64encode(chunk).decode())
            off += len(chunk)
            print(f"  uploaded {off}/{size}", file=sys.stderr)
    fid = res["file"]["id"]
    meta = call("info", fileId=fid)["file"]
    ok = int(meta["size"]) == size and meta.get("md5Checksum") == md5(path)
    print(json.dumps({"id": fid, "name": meta["name"], "size": int(meta["size"]),
                      "md5_match": ok, "url": f"https://drive.google.com/file/d/{fid}/view"}, ensure_ascii=False))
    if not ok:
        sys.exit("VERIFY FAILED: size/md5 mismatch")


def download(fid, out):
    meta = call("info", fileId=fid)["file"]
    size = int(meta["size"])
    tmp = out + ".part"
    with open(tmp, "wb") as f:
        off = 0
        while off < size:
            r = call("download_chunk", fileId=fid, offset=off, length=min(CHUNK_DOWN, size - off))
            b = base64.b64decode(r["data"])
            if r["offset"] != off or not b:
                sys.exit("bad chunk")
            f.write(b)
            off += len(b)
            print(f"  downloaded {off}/{size}", file=sys.stderr)
    if md5(tmp) != meta.get("md5Checksum"):
        sys.exit("VERIFY FAILED: md5 mismatch")
    os.replace(tmp, out)
    print(json.dumps({"id": fid, "name": meta["name"], "size": size, "md5_match": True, "out": out},
                     ensure_ascii=False))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "ping":
        with urllib.request.urlopen(_url(), timeout=60) as r:
            print(r.read().decode())
    elif cmd == "list":
        print(json.dumps(call("list", folderId=a[1]), ensure_ascii=False, indent=1))
    elif cmd == "info":
        print(json.dumps(call("info", fileId=a[1]), ensure_ascii=False, indent=1))
    elif cmd == "upload":
        name = a[a.index("--name") + 1] if "--name" in a else None
        mime = a[a.index("--mime") + 1] if "--mime" in a else None
        upload(a[1], a[2], name, mime)
    elif cmd == "download":
        download(a[1], a[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
