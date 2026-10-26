"""Run the phone's real TypeScript next to the desktop's Python, for tests that check both apps answer alike.

The phone's library (mobile/src/lib) and data are copied into mobile/.crosscheck/h/, with each import given its
.ts ending (and JSON imports their `with { type: 'json' }`), and the packages that only exist on a phone --
storage, secure storage, React Native itself, Expo's modules -- swapped for small stand-ins that keep things in
memory. Plain-JavaScript packages (fast-xml-parser, @noble/...) are used as they are. Needs Node 22.6+.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
WORK = MOBILE / ".crosscheck" / "h"

STUBS = {
    "@react-native-async-storage/async-storage": """
const m = new Map<string, string>();
const AsyncStorage = {
  getItem: async (k: string) => (m.has(k) ? m.get(k)! : null),
  setItem: async (k: string, v: string) => { m.set(k, String(v)); },
  removeItem: async (k: string) => { m.delete(k); },
  multiRemove: async (ks: string[]) => { ks.forEach((k) => m.delete(k)); },
  getAllKeys: async () => [...m.keys()],
  clear: async () => { m.clear(); },
};
export default AsyncStorage;
""",
    "expo-secure-store": """
const m = new Map<string, string>();
export const getItemAsync = async (k: string) => (m.has(k) ? m.get(k)! : null);
export const setItemAsync = async (k: string, v: string) => { m.set(k, v); };
export const deleteItemAsync = async (k: string) => { m.delete(k); };
""",
    "react-native": """
export const Platform = { OS: 'android', select: (o: any) => o.android ?? o.default };
export const Linking = { openURL: async () => true, openSettings: async () => true };
export const Alert = { alert: () => undefined };
export const AppState = { addEventListener: () => ({ remove: () => undefined }), currentState: 'active' };
export const Appearance = { getColorScheme: () => 'dark' };
""",
    "expo-crypto": """
import { createHash, randomBytes } from 'node:crypto';
export const getRandomBytes = (n: number) => new Uint8Array(randomBytes(n));
export const getRandomValues = (a: Uint8Array) => { a.set(randomBytes(a.length)); return a; };
export const CryptoDigestAlgorithm = { SHA256: 'sha256' };
export const CryptoEncoding = { HEX: 'hex', BASE64: 'base64' };
export const digestStringAsync = async (_alg: string, s: string, o?: any) =>
  createHash('sha256').update(s).digest(o?.encoding === 'base64' ? 'base64' : 'hex');
export const randomUUID = () => crypto.randomUUID();
""",
    "expo-web-browser": "export const openAuthSessionAsync = async () => ({ type: 'cancel' });\n"
                        "export const openBrowserAsync = async () => ({ type: 'cancel' });\n",
    "expo-constants": "export default { expoConfig: { version: 'test' } };\n",
    "expo": "export const requireOptionalNativeModule = () => null;\n",       # native modules (Google sign-in): none here
}
_IMPORT = re.compile(r"""(from\s+|import\s+|import\()(['"])([^'"]+)\2""")


def _fix(text: str, depth: int) -> str:
    up = "../" * depth

    def sub(m: re.Match) -> str:
        head, q, spec = m.group(1), m.group(2), m.group(3)
        if spec in STUBS:
            return f"{head}{q}{up}stubs/{spec.replace('/', '__')}.ts{q}"
        if spec.startswith("."):
            if spec.endswith(".json"):
                return f"{head}{q}{spec}{q}"
            if not spec.endswith(".ts"):
                return f"{head}{q}{spec}.ts{q}"
        return m.group(0)

    out = _IMPORT.sub(sub, text)
    if re.search(r"\brequire\(", out):        # data loaded on first use (require) works in Node's ES modules too
        out = "import { createRequire } from 'node:module';\nconst require = createRequire(import.meta.url);\n" + out
    return re.sub(r"""(from\s+['"][^'"]+\.json['"])(?!\s*with)""", r"\1 with { type: 'json' }", out)


_TYPE_EXPORT = re.compile(r"^export\s+(?:type|interface)\s+([A-Za-z_]\w*)", re.M)
_NAMED = re.compile(r"import\s+(type\s+)?\{([^}]*)\}\s+from\s+(['\"])(\.[^'\"]+)\3", re.S)


def _mark_types(text: str, types_of: dict[str, set[str]]) -> str:
    """`import { match, Weights } from './interests'` -> `import { match, type Weights } ...`: Node strips
    types only when it is told which names are types."""
    def sub(m: re.Match) -> str:
        if m.group(1):
            return m.group(0)
        mod = Path(m.group(4)).stem.replace(".ts", "")
        types = types_of.get(mod, set())
        names = []
        for part in m.group(2).split(","):
            n = part.strip()
            if not n:
                continue
            base = n.split(" as ")[0].strip()
            names.append(f"type {n}" if base in types and not n.startswith("type ") else n)
        return m.group(0).replace("{" + m.group(2) + "}", "{ " + ", ".join(names) + " }")
    return _NAMED.sub(sub, text)


def prepare() -> Path:
    """A fresh copy of the phone's lib and data, ready for Node. Returns the folder."""
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "lib").mkdir(parents=True)
    (WORK / "stubs").mkdir()
    shutil.copytree(MOBILE / "src" / "data", WORK / "data")
    files = {f.stem: f.read_text(encoding="utf-8") for f in (MOBILE / "src" / "lib").glob("*.ts")}
    types_of = {stem: set(_TYPE_EXPORT.findall(text)) for stem, text in files.items()}
    for stem, text in files.items():
        (WORK / "lib" / f"{stem}.ts").write_text(_fix(_mark_types(text, types_of), 1), encoding="utf-8")
    for name, body in STUBS.items():
        (WORK / "stubs" / f"{name.replace('/', '__')}.ts").write_text(body, encoding="utf-8")
    return WORK


def node_ok() -> bool:
    """Node 22.6+ and the phone's packages installed (`npm ci` in mobile/; CI machines that only test the desktop
    have Node but not these)."""
    if not shutil.which("node") or not (MOBILE / "node_modules").is_dir():
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=120).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


_fresh = False


def run(script: str, data: Any = None, name: str = "side") -> Any:
    """Run a TypeScript snippet next to the phone's lib (import from './lib/x.ts'); `data` arrives as INPUT;
    whatever it prints with `out(value)` comes back as Python."""
    global _fresh
    if not _fresh or not (WORK / "lib").is_dir():   # the phone's code as it is now, once per test run (and
        prepare()                                   # again if another test cleared .crosscheck away)
        _fresh = True
    work = WORK
    body = ("import { readFileSync } from 'node:fs';\n"
            "const INPUT = JSON.parse(readFileSync(0, 'utf8'));\n"
            "const out = (v: unknown) => console.log(JSON.stringify(v));\n" + script)
    path = work / f"{name}.ts"
    path.write_text(body, encoding="utf-8")
    r = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", str(path)], input=json.dumps(data),
                       capture_output=True, text=True, cwd=MOBILE, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-1500:])
    return json.loads(r.stdout.strip().splitlines()[-1])
