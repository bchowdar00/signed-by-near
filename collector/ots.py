"""OpenTimestamps receipts without the client: stamp, inspect, upgrade, verify.

  stamp   <file> [<file> ...]   writes <file>.ots, committed at 2 or 3 public calendars
  info    <file.ots> [<file>]   parses the proof, checks it commits to <file>'s SHA-256, lists
                                every attestation with the message it attests
  upgrade <file.ots>            asks each pending calendar for its Bitcoin path; writes the
                                upgraded proof in place (the old one is kept as .ots.bak)
  verify  <file.ots> <file>     for each Bitcoin attestation, compares the attested message with
                                the block's Merkle root from a public block API

The file format is the one the reference client writes and reads
(opentimestamps/python-opentimestamps, core/serialize.py, core/timestamp.py, core/op.py,
core/notary.py): magic, version 1, OpSHA256, the 32-byte file digest, then the timestamp tree.
Here the tree has one branch per calendar: append a 16-byte random nonce, SHA-256, then the
calendar's own reply to POST /digest, which is that calendar's serialized timestamp for the
submitted message. So the standard `ots info` / `ots upgrade` / `ots verify` can read it too.
"""
import hashlib, json, os, shutil, sys, urllib.request

MAGIC = b'\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94'
PENDING = bytes.fromhex('83dfe30d2ef90c8e')
BITCOIN = bytes.fromhex('0588960d73d71901')
LITECOIN = bytes.fromhex('06869a0d73d71b45')
ETHEREUM = bytes.fromhex('30fe8087b5c7ead7')
CALENDARS = ['https://a.pool.opentimestamps.org', 'https://b.pool.opentimestamps.org',
             'https://a.pool.eternitywall.com']
UA = 'research-readonly (NEAR hackathon thesis entry; OpenTimestamps digest only)'
BLOCK_API = 'https://blockstream.info/api'


# ---------- serialization primitives ----------
def varuint(n):
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def varbytes(b):
    return varuint(len(b)) + b


class Reader:
    def __init__(self, data):
        self.d, self.i = data, 0

    def read(self, n):
        if self.i + n > len(self.d):
            raise ValueError('truncated proof')
        b = self.d[self.i:self.i + n]
        self.i += n
        return b

    def varuint(self):
        v, shift = 0, 0
        while True:
            b = self.read(1)[0]
            v |= (b & 0x7f) << shift
            if not b & 0x80:
                return v
            shift += 7

    def varbytes(self, maxlen=8192):
        n = self.varuint()
        if n > maxlen:
            raise ValueError('field too long')
        return self.read(n)

    def eof(self):
        return self.i == len(self.d)


# ---------- ops ----------
UNARY = {0x08: 'sha256', 0x02: 'sha1', 0x03: 'ripemd160', 0x67: 'keccak256', 0xf2: 'reverse', 0xf3: 'hexlify'}
BINARY = {0xf0: 'append', 0xf1: 'prepend'}


def apply(tag, arg, msg):
    if tag == 0xf0:
        return msg + arg
    if tag == 0xf1:
        return arg + msg
    if tag == 0x08:
        return hashlib.sha256(msg).digest()
    if tag == 0x02:
        return hashlib.sha1(msg).digest()
    if tag == 0x03:
        return hashlib.new('ripemd160', msg).digest()
    if tag == 0xf2:
        return msg[::-1]
    if tag == 0xf3:
        return msg.hex().encode()
    raise ValueError(f'op 0x{tag:02x} not supported here')


# ---------- timestamp tree ----------
def parse_timestamp(r, msg, depth=0):
    """Returns a node {'msg', 'attestations': [...], 'ops': [(tag, arg, node), ...]}, in file order."""
    if depth > 256:
        raise ValueError('recursion limit')
    node = {'msg': msg, 'attestations': [], 'ops': []}

    def one(tag):
        if tag == 0x00:
            atag = r.read(8)
            payload = r.varbytes()
            pr = Reader(payload)
            if atag == PENDING:
                node['attestations'].append({'kind': 'pending', 'uri': pr.varbytes(1000).decode(), 'msg': msg})
            elif atag == BITCOIN:
                node['attestations'].append({'kind': 'bitcoin', 'height': pr.varuint(), 'msg': msg})
            elif atag == LITECOIN:
                node['attestations'].append({'kind': 'litecoin', 'height': pr.varuint(), 'msg': msg})
            elif atag == ETHEREUM:
                node['attestations'].append({'kind': 'ethereum', 'height': pr.varuint(), 'msg': msg})
            else:
                node['attestations'].append({'kind': 'unknown', 'tag': atag.hex(), 'payload': payload.hex(), 'msg': msg})
        else:
            arg = r.varbytes(4096) if tag in BINARY else None
            if tag not in BINARY and tag not in UNARY:
                raise ValueError(f'unknown op tag 0x{tag:02x}')
            child = parse_timestamp(r, apply(tag, arg, msg), depth + 1)
            node['ops'].append((tag, arg, child))

    tag = r.read(1)[0]
    while tag == 0xff:
        one(r.read(1)[0])
        tag = r.read(1)[0]
    one(tag)
    return node


def write_timestamp(node):
    """Inverse of parse_timestamp, preserving the order items were parsed in."""
    items = [('a', a) for a in node['attestations']] + [('o', o) for o in node['ops']]
    out = bytearray()
    for k, (kind, it) in enumerate(items):
        if k < len(items) - 1:
            out += b'\xff'
        if kind == 'a':
            out += b'\x00'
            if it['kind'] == 'pending':
                out += PENDING + varbytes(varbytes(it['uri'].encode()))
            elif it['kind'] == 'bitcoin':
                out += BITCOIN + varbytes(varuint(it['height']))
            elif it['kind'] == 'litecoin':
                out += LITECOIN + varbytes(varuint(it['height']))
            elif it['kind'] == 'ethereum':
                out += ETHEREUM + varbytes(varuint(it['height']))
            else:
                out += bytes.fromhex(it['tag']) + varbytes(bytes.fromhex(it['payload']))
        else:
            tag, arg, child = it
            out.append(tag)
            if tag in BINARY:
                out += varbytes(arg)
            out += write_timestamp(child)
    return bytes(out)


def parse_file(data):
    r = Reader(data)
    if r.read(len(MAGIC)) != MAGIC:
        raise ValueError('not an OpenTimestamps proof (bad magic)')
    ver = r.varuint()
    if ver != 1:
        raise ValueError(f'unsupported major version {ver}')
    op = r.read(1)[0]
    if op != 0x08:
        raise ValueError(f'file hash op 0x{op:02x}; only SHA-256 is written here')
    digest = r.read(32)
    tree = parse_timestamp(r, digest)
    if not r.eof():
        raise ValueError('trailing bytes after the timestamp')
    return digest, tree


def file_bytes(digest, tree):
    return MAGIC + varuint(1) + b'\x08' + digest + write_timestamp(tree)


def attestations(node, path=()):
    for a in node['attestations']:
        yield path, a
    for tag, arg, child in node['ops']:
        yield from attestations(child, path + ((tag, arg),))


# ---------- network ----------
def http(url, data=None, accept='application/vnd.opentimestamps.v1'):
    req = urllib.request.Request(url, data=data, headers={'Accept': accept, 'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.digest()


# ---------- commands ----------
def stamp(paths, min_ok=2):
    for p in paths:
        digest = sha256_file(p)
        branches = []
        for cal in CALENDARS:
            nonce = os.urandom(16)
            commit = hashlib.sha256(digest + nonce).digest()
            try:
                st, body = http(cal + '/digest', data=commit)
            except Exception as e:
                print(f'{cal}: failed ({e!r})', flush=True)
                continue
            if st != 200 or not body:
                print(f'{cal}: http {st}', flush=True)
                continue
            # the reply must parse as a timestamp on exactly the submitted message
            sub = parse_timestamp(Reader(body), commit)
            branches.append((nonce, body, sub, cal))
            print(f'{cal}: ok, {len(body)} bytes', flush=True)
        if len(branches) < min_ok:
            raise SystemExit(f'only {len(branches)} calendars answered for {p}; need {min_ok}')
        branches.sort(key=lambda b: b[0])  # the reference client orders sibling ops by argument
        out = bytearray(MAGIC + varuint(1) + b'\x08' + digest)
        for k, (nonce, body, sub, cal) in enumerate(branches):
            if k < len(branches) - 1:
                out += b'\xff'
            out += b'\xf0' + varbytes(nonce) + b'\x08' + body
        with open(p + '.ots', 'wb') as f:
            f.write(out)
        d2, tree = parse_file(bytes(out))  # round trip
        assert d2 == digest and file_bytes(d2, tree) == bytes(out)
        print(f'wrote {p}.ots  sha256(file)={digest.hex()}  calendars={len(branches)}', flush=True)


def info(ots_path, target=None):
    with open(ots_path, 'rb') as f:
        data = f.read()
    digest, tree = parse_file(data)
    out = {'proof': ots_path, 'proof_sha256': hashlib.sha256(data).hexdigest(), 'file_digest': digest.hex()}
    if target:
        out['target'] = target
        out['target_matches'] = sha256_file(target) == digest
    out['attestations'] = [{'kind': a['kind'], **({'uri': a['uri']} if 'uri' in a else {}),
                            **({'height': a['height']} if 'height' in a else {}),
                            'attested_msg': a['msg'].hex(), 'ops_from_digest': len(path)}
                           for path, a in attestations(tree)]
    print(json.dumps(out, indent=1))
    return out


def upgrade(ots_path):
    with open(ots_path, 'rb') as f:
        data = f.read()
    digest, tree = parse_file(data)
    changed = 0

    def walk(node):
        nonlocal changed
        for _, _, child in node['ops']:   # children first, so grafted paths are not re-queried
            walk(child)
        add_att, add_ops = [], []
        for a in node['attestations']:
            if a['kind'] != 'pending':
                continue
            try:
                st, body = http(a['uri'].rstrip('/') + '/timestamp/' + a['msg'].hex())
            except Exception as e:
                print(f"{a['uri']}: not yet ({e!r})", flush=True)
                continue
            sub = parse_timestamp(Reader(body), a['msg'])
            if any(x['kind'] == 'bitcoin' for _, x in attestations(sub)):
                add_att += sub['attestations']
                add_ops += sub['ops']
                changed += 1
                print(f"{a['uri']}: upgraded", flush=True)
            else:
                print(f"{a['uri']}: still pending", flush=True)
        # the pending attestation is kept beside the Bitcoin path, as the reference client keeps it
        node['attestations'] += add_att
        node['ops'] += add_ops

    walk(tree)
    if changed:
        shutil.copy2(ots_path, ots_path + '.bak')
        with open(ots_path, 'wb') as f:
            f.write(file_bytes(digest, tree))
    print(f'upgraded branches: {changed}')
    return changed


def verify(ots_path, target):
    with open(ots_path, 'rb') as f:
        digest, tree = parse_file(f.read())
    if sha256_file(target) != digest:
        raise SystemExit('the proof does not commit to this file')
    res = []
    for path, a in attestations(tree):
        if a['kind'] != 'bitcoin':
            continue
        _, bh = http(f"{BLOCK_API}/block-height/{a['height']}", accept='text/plain')
        _, bj = http(f"{BLOCK_API}/block/{bh.decode().strip()}", accept='application/json')
        b = json.loads(bj)
        ok = a['msg'][::-1].hex() == b['merkle_root']
        res.append({'height': a['height'], 'block': b['id'], 'time_utc': b['timestamp'], 'merkle_root_matches': ok})
    print(json.dumps({'file_digest': digest.hex(), 'bitcoin': res}, indent=1))
    return res


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'stamp' and len(sys.argv) > 2:
        stamp(sys.argv[2:])
    elif cmd == 'info' and len(sys.argv) in (3, 4):
        info(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
    elif cmd == 'upgrade' and len(sys.argv) == 3:
        upgrade(sys.argv[2])
    elif cmd == 'verify' and len(sys.argv) == 4:
        verify(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
