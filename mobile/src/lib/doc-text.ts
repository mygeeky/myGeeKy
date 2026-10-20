// A document's text, on the phone: PDF, Word (.docx) or plain text (.txt, .md, .tex). The desktop reads files with
// pypdf and text_utils.docx_text; this is the phone's own reader, small and dependency-light (fflate only). PDFs
// made by Word, LibreOffice, LaTeX and most journals are read, fonts with a ToUnicode map included; a scan has no
// text to read, and then it says so: paste the text instead. Nothing leaves the phone.
import { inflateSync, strFromU8, unzipSync, unzlibSync } from 'fflate';

export type DocText = { text: string; ok: boolean; why?: string };
export const MAX_BYTES = 15_000_000;
export const TYPES = ['pdf', 'docx', 'txt', 'md', 'tex'];
export const MAX_PAGES = 80;          // a thesis's field shows long before page 80, and phones are slower

const NO_TEXT = "This file's text can't be read here (it may be a scan or an image). Paste the text instead.";

function latin1(b: Uint8Array): string {
  let s = '';
  for (let i = 0; i < b.length; i += 8192) s += String.fromCharCode(...b.subarray(i, i + 8192));
  return s;
}

const XML_ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

function unescapeXml(s: string): string {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e: string) => {
    if (e[0] === '#') {
      const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isFinite(n) && n > 0 && n < 0x110000 ? String.fromCodePoint(n) : m;
    }
    return XML_ENTITIES[e.toLowerCase()] ?? m;
  });
}

/** The text of a Word document: its paragraphs, one per line (the desktop's text_utils.docx_text). */
export function docxText(bytes: Uint8Array): string {
  const files = unzipSync(bytes, { filter: (f) => f.name === 'word/document.xml' });
  const xml = files['word/document.xml'];
  if (!xml) throw new Error('Not a Word document.');
  return unescapeXml(strFromU8(xml).replace(/<\/w:p>|<w:br\s*\/>|<w:cr\s*\/>/g, '\n').replace(/<w:tab\s*\/>/g, ' ')
    .replace(/<[^>]+>/g, ''));
}

// ---------------------------------------------------------------------------------------------------- PDF
// raw: the stream as stored; it's only inflated when read (images and embedded fonts never are)
type Obj = { dict: string; raw?: Uint8Array; flate?: boolean; done?: Uint8Array | null };

function streamOf(o: Obj | undefined): Uint8Array | undefined {
  if (!o?.raw) return undefined;
  if (o.done === undefined) o.done = o.flate ? inflate(o.raw) : o.raw;
  return o.done ?? undefined;
}

function inflate(data: Uint8Array): Uint8Array | null {
  try { return unzlibSync(data); } catch { /* not zlib-wrapped */ }
  try { return inflateSync(data); } catch { return null; }
}

/** Every object: "N G obj << ... >> [stream ... endstream] endobj", and the ones packed inside object streams. */
function readObjects(bytes: Uint8Array): Map<number, Obj> {
  const s = latin1(bytes);
  const objs = new Map<number, Obj>();
  const head = /(\d+)\s+\d+\s+obj\b/g;
  let m: RegExpExecArray | null;
  while ((m = head.exec(s))) {
    const start = m.index + m[0].length;
    const end = s.indexOf('endobj', start);
    if (end < 0) break;
    let body = s.slice(start, end);
    let raw: Uint8Array | undefined, flate = false;
    const at = body.search(/\bstream\r?\n/);
    if (at >= 0) {
      const dataStart = start + at + body.slice(at).indexOf('\n') + 1;
      const dataEnd = s.lastIndexOf('endstream', end);
      body = body.slice(0, at);
      // the stream's own length when it says it plainly; else up to "endstream", less one line ending (a byte of
      // the data itself may be a line-ending byte, so never trim more)
      const len = /\/Length\s+(\d+)(?!\s+\d+\s+R)/.exec(body);
      let to = dataEnd > dataStart ? dataEnd : dataStart;
      if (len && dataStart + Number(len[1]) <= to) to = dataStart + Number(len[1]);
      else if (bytes[to - 1] === 10) to -= bytes[to - 2] === 13 ? 2 : 1;
      else if (bytes[to - 1] === 13) to -= 1;
      flate = /\/FlateDecode/.test(body);
      if ((flate || !/\/Filter/.test(body)) && !/\/Subtype\s*\/Image/.test(body)) raw = bytes.subarray(dataStart, to);
    }
    objs.set(Number(m[1]), { dict: body, raw, flate });
    head.lastIndex = end;
  }
  for (const o of [...objs.values()]) {                       // object streams (PDF 1.5+) hold more objects
    if (!o.raw || !/\/Type\s*\/ObjStm/.test(o.dict)) continue;
    const packed = streamOf(o);
    if (!packed) continue;
    const first = Number(/\/First\s+(\d+)/.exec(o.dict)?.[1] ?? NaN);
    if (!Number.isFinite(first)) continue;
    const text = latin1(packed);
    const nums = text.slice(0, first).trim().split(/\s+/).map(Number);
    for (let i = 0; i + 1 < nums.length; i += 2) {
      const from = first + nums[i + 1], to = i + 3 < nums.length ? first + nums[i + 3] : text.length;
      if (!objs.has(nums[i])) objs.set(nums[i], { dict: text.slice(from, to) });
    }
  }
  return objs;
}

const ref = (dict: string, key: string) => {
  const m = new RegExp(`/${key}\\s+(\\d+)\\s+\\d+\\s+R`).exec(dict);
  return m ? Number(m[1]) : null;
};

function inlineDict(dict: string, key: string): string | null {
  const at = dict.search(new RegExp(`/${key}\\s*<<`));
  if (at < 0) return null;
  let depth = 0;
  for (let i = dict.indexOf('<<', at); i < dict.length - 1; i++) {
    if (dict[i] === '<' && dict[i + 1] === '<') { depth++; i++; } else if (dict[i] === '>' && dict[i + 1] === '>') {
      depth--; i++;
      if (!depth) return dict.slice(dict.indexOf('<<', at) + 2, i - 1);
    }
  }
  return null;
}

/** A font's ToUnicode map: character codes to text, and how many bytes a code takes. */
type Font = { map: Map<number, string>; bytes: number };

function utf16(hex: string): string {
  let out = '';
  for (let i = 0; i + 3 < hex.length; i += 4) out += String.fromCharCode(parseInt(hex.slice(i, i + 4), 16));
  return out;
}

function readCMap(text: string): Map<number, string> {
  const map = new Map<number, string>();
  for (const block of text.match(/beginbfchar([\s\S]*?)endbfchar/g) ?? []) {
    for (const [, src, dst] of block.matchAll(/<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]*)>/g)) map.set(parseInt(src, 16), utf16(dst));
  }
  for (const block of text.match(/beginbfrange([\s\S]*?)endbfrange/g) ?? []) {
    for (const [, a, b, rest] of block.matchAll(/<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(\[[^\]]*\]|<[0-9a-fA-F]+>)/g)) {
      const lo = parseInt(a, 16), hi = Math.min(parseInt(b, 16), lo + 65535);
      if (rest.startsWith('[')) {
        [...rest.matchAll(/<([0-9a-fA-F]*)>/g)].forEach(([, d], i) => { if (lo + i <= hi) map.set(lo + i, utf16(d)); });
      } else {
        const d = rest.slice(1, -1);
        const base = utf16(d);
        for (let c = lo; c <= hi; c++) {
          map.set(c, base.slice(0, -1) + String.fromCharCode(base.charCodeAt(base.length - 1) + (c - lo)));
        }
      }
    }
  }
  return map;
}

function fontsOf(page: Obj, objs: Map<number, Obj>, cache: Map<number, Font | null>): Map<string, Font | null> {
  const out = new Map<string, Font | null>();
  let res = inlineDict(page.dict, 'Resources');
  if (res === null) { const r = ref(page.dict, 'Resources'); res = r !== null ? objs.get(r)?.dict ?? null : null; }
  if (res === null) return out;
  let fonts = inlineDict(res, 'Font');
  if (fonts === null) { const r = ref(res, 'Font'); fonts = r !== null ? objs.get(r)?.dict ?? null : null; }
  for (const [, name, num] of (fonts ?? '').matchAll(/\/([^\s/<>[\]()]+)\s+(\d+)\s+\d+\s+R/g)) {
    const n = Number(num);
    if (!cache.has(n)) {
      const f = objs.get(n);
      const tu = f ? ref(f.dict, 'ToUnicode') : null;
      const cmap = tu !== null ? streamOf(objs.get(tu)) : undefined;
      cache.set(n, cmap ? { map: readCMap(latin1(cmap)), bytes: /\/Subtype\s*\/Type0/.test(f!.dict) ? 2 : 1 } : null);
    }
    out.set(name, cache.get(n)!);
  }
  return out;
}

function decode(raw: string, font: Font | null | undefined): string {
  if (!font) return raw;                                   // a simple font: its bytes are (near enough) Latin-1
  let out = '';
  for (let i = 0; i + font.bytes <= raw.length; i += font.bytes) {
    const code = font.bytes === 2 ? (raw.charCodeAt(i) << 8) | raw.charCodeAt(i + 1) : raw.charCodeAt(i);
    out += font.map.get(code) ?? (font.bytes === 1 ? raw[i] : '');
  }
  return out;
}

/** The text a page's content stream shows: strings drawn with Tj / TJ / ' / ", lines from the moves between them. */
function showText(content: string, fonts: Map<string, Font | null>): string {
  let out = '';
  let font: Font | null | undefined;
  const stack: (string | number | (string | number)[])[] = [];
  let arr: (string | number)[] | null = null;
  let lastY: number | null = null;
  const nl = () => { if (out && !out.endsWith('\n')) out += '\n'; };
  const sp = () => { if (out && !/\s$/.test(out)) out += ' '; };
  let i = 0;
  const n = content.length;
  while (i < n) {
    const ch = content[i];
    if (ch === '(') {                                      // a literal string, with nesting and escapes
      let depth = 1, s = '';
      i++;
      while (i < n && depth) {
        const c = content[i];
        if (c === '\\') {
          const e = content[i + 1];
          const esc: Record<string, string> = { n: '\n', r: '\r', t: '\t', b: '\b', f: '\f', '(': '(', ')': ')', '\\': '\\' };
          if (e in esc) { s += esc[e]; i += 2; } else if (/[0-7]/.test(e)) {
            const oct = /^[0-7]{1,3}/.exec(content.slice(i + 1, i + 4))![0];
            s += String.fromCharCode(parseInt(oct, 8)); i += 1 + oct.length;
          } else if (e === '\r' || e === '\n') { i += e === '\r' && content[i + 2] === '\n' ? 3 : 2; } else { s += e ?? ''; i += 2; }
          continue;
        }
        if (c === '(') depth++;
        else if (c === ')' && !--depth) { i++; break; }
        s += c;
        i++;
      }
      (arr ?? stack).push(s);
      continue;
    }
    if (ch === '<' && content[i + 1] !== '<') {             // a hex string
      const end = content.indexOf('>', i);
      const hex = content.slice(i + 1, end < 0 ? n : end).replace(/\s+/g, '');
      let s = '';
      for (let k = 0; k < hex.length; k += 2) s += String.fromCharCode(parseInt((hex.slice(k, k + 2) + '0').slice(0, 2), 16));
      (arr ?? stack).push(s);
      i = end < 0 ? n : end + 1;
      continue;
    }
    if (ch === '[') { arr = []; i++; continue; }
    if (ch === ']') { if (arr) stack.push(arr); arr = null; i++; continue; }
    if (ch === '%') { while (i < n && content[i] !== '\n' && content[i] !== '\r') i++; continue; }
    if (/\s/.test(ch)) { i++; continue; }
    let j = i;
    while (j < n && !/[\s()<>[\]/%]/.test(content[j])) j++;
    if (ch === '/') { j = i + 1; while (j < n && !/[\s()<>[\]/%]/.test(content[j])) j++; }
    const tok = content.slice(i, j || i + 1);
    i = j > i ? j : i + 1;
    if (tok[0] === '/') { (arr ?? stack).push(tok); continue; }
    const num = Number(tok);
    if (tok !== '' && !Number.isNaN(num)) { (arr ?? stack).push(num); continue; }
    switch (tok) {                                         // an operator: act on what came before it
      case 'Tf': { const name = stack[stack.length - 2]; if (typeof name === 'string') font = fonts.get(name.slice(1)); break; }
      case 'Tj': case "'": case '"': {
        if (tok !== 'Tj') nl();
        const s = stack[stack.length - 1];
        if (typeof s === 'string') out += decode(s, font);
        break;
      }
      case 'TJ': {
        const a = stack[stack.length - 1];
        if (Array.isArray(a)) for (const x of a) { if (typeof x === 'string') out += decode(x, font); else if (x < -200) sp(); }
        break;
      }
      case 'Td': case 'TD': {
        const tx = stack[stack.length - 2], ty = stack[stack.length - 1];
        if (typeof ty === 'number' && Math.abs(ty) > 0.5) nl(); else if (typeof tx === 'number' && Math.abs(tx) > 0.5) sp();
        break;
      }
      case 'T*': nl(); break;
      case 'Tm': {
        const y = stack[stack.length - 1];
        if (typeof y === 'number') { if (lastY !== null && Math.abs(y - lastY) > 0.5) nl(); else sp(); lastY = y; }
        break;
      }
      case 'ET': sp(); break;
      case 'BI': { const e = content.indexOf('EI', i); i = e < 0 ? n : e + 2; break; }   // an inline image: skip it
    }
    if (tok !== 'BT') stack.length = 0;
  }
  return out;
}

function pageOrder(objs: Map<number, Obj>): number[] {
  const root = [...objs.values()].map((o) => ref(o.dict, 'Root')).find((r) => r !== null);
  const catalog = root != null ? objs.get(root) : [...objs.values()].find((o) => /\/Type\s*\/Catalog/.test(o.dict));
  const top = catalog ? ref(catalog.dict, 'Pages') : null;
  const pages: number[] = [];
  const walk = (num: number, depth: number) => {
    const o = objs.get(num);
    if (!o || depth > 50 || pages.length > 2000) return;
    if (/\/Type\s*\/Page\b(?!s)/.test(o.dict)) { pages.push(num); return; }
    const kids = /\/Kids\s*\[([^\]]*)\]/.exec(o.dict)?.[1] ?? '';
    for (const [, k] of kids.matchAll(/(\d+)\s+\d+\s+R/g)) walk(Number(k), depth + 1);
  };
  if (top !== null) walk(top, 0);
  if (!pages.length) {
    for (const [num, o] of objs) if (/\/Type\s*\/Page\b(?!s)/.test(o.dict)) pages.push(num);
  }
  return pages;
}

export function pdfText(bytes: Uint8Array): string {
  const objs = readObjects(bytes);
  const cache = new Map<number, Font | null>();
  const parts: string[] = [];
  for (const num of pageOrder(objs).slice(0, MAX_PAGES)) {
    const page = objs.get(num)!;
    const fonts = fontsOf(page, objs, cache);
    const arr = /\/Contents\s*\[([^\]]*)\]/.exec(page.dict)?.[1];
    const refs = arr ? [...arr.matchAll(/(\d+)\s+\d+\s+R/g)].map((x) => Number(x[1])) : [ref(page.dict, 'Contents')];
    const content = refs.map((r) => (r !== null ? streamOf(objs.get(r)) : undefined)).filter(Boolean).map((b) => latin1(b!)).join('\n');
    parts.push(showText(content, fonts));
  }
  return parts.join('\n');
}

// ---------------------------------------------------------------------------------------------------- any file
/** Whether text looks like real words (a scan's PDF, or a font with no map, gives none). */
export function readable(text: string): boolean {
  const words = text.match(/[A-Za-zÀ-ɏͰ-ϿЀ-ӿ؀-ۿ]{3,}/g) ?? [];
  const visible = text.replace(/\s+/g, '');
  return words.length >= 15 && words.join('').length >= 0.5 * visible.length;
}

export function documentText(bytes: Uint8Array, name: string): DocText {
  const ext = (/\.([a-z0-9]+)$/i.exec(name)?.[1] ?? '').toLowerCase();
  if (bytes.length > MAX_BYTES) return { text: '', ok: false, why: 'That file is too big (over 15 MB). Paste the text instead.' };
  try {
    let text: string;
    if (ext === 'pdf' || latin1(bytes.subarray(0, 5)) === '%PDF-') text = pdfText(bytes);
    else if (ext === 'docx') text = docxText(bytes);
    else if (ext === 'doc') return { text: '', ok: false, why: 'An old Word file (.doc): save it as .docx or PDF, or paste the text.' };
    else text = strFromU8(bytes).replace(/^﻿/, '');
    return readable(text) ? { text, ok: true } : { text, ok: false, why: NO_TEXT };
  } catch {
    return { text: '', ok: false, why: "This file couldn't be read. Try a PDF or .docx, or paste the text." };
  }
}
