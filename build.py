#!/usr/bin/env python3
"""Build the standalone site into docs/ (served by GitHub Pages) from app.html.

app.html is the single source. It is written in the Claude Artifact format
(no <html>/<head>/<body>), so the same file can be published as an artifact.
This script wraps it into a full document and adds the PWA bits:
manifest, service worker for offline use, and home-screen icons.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs"

app = (ROOT / "app.html").read_text(encoding="utf8")
split = app.index('<div id="app">')
head_part, body_part = app[:split].strip(), app[split:].strip()

HEAD = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Тренажёр окончаний немецких прилагательных: спринт на 60 секунд и режим обучения.">
<meta name="theme-color" content="#EDF0F3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0D1015" media="(prefers-color-scheme: dark)">
<meta property="og:title" content="Endungen">
<meta property="og:description" content="Окончания немецких прилагательных на скорость. Сколько успеешь за 60 секунд?">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Endungen">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""

SW_REGISTER = """<script>
if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
</script>"""

index = HEAD + head_part + "\n</head>\n<body>\n" + body_part + "\n" + SW_REGISTER + "\n</body>\n</html>\n"

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
(OUT / "index.html").write_text(index, encoding="utf8")
(OUT / ".nojekyll").write_text("")
shutil.copy(ROOT / "icon.svg", OUT / "icon.svg")
for name, size in [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)]:
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(OUT / name), str(ROOT / "icon.svg")], check=True)

manifest = {
    "name": "Endungen",
    "short_name": "Endungen",
    "description": "Окончания немецких прилагательных: спринт и обучение",
    "lang": "ru",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#0D1015",
    "theme_color": "#0D1015",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"},
    ],
}
(OUT / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")

version = hashlib.sha256(index.encode()).hexdigest()[:10]
SW = """// Network first for the page (updates show up at once), cache first for the rest; works offline.
const CACHE = 'endungen-%s';
const CORE = ['./', 'index.html', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  if (r.mode === 'navigate') {
    e.respondWith(fetch(r).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put('index.html', copy));
      return res;
    }).catch(() => caches.match('index.html')));
    return;
  }
  e.respondWith(caches.match(r).then(hit => hit || fetch(r).then(res => {
    if (res.ok || res.type === 'opaque') { const copy = res.clone(); caches.open(CACHE).then(c => c.put(r, copy)); }
    return res;
  })));
});
""" % version
(OUT / "sw.js").write_text(SW, encoding="utf8")
print(f"built {OUT} (cache {version})")
