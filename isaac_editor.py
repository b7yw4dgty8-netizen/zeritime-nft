#!/usr/bin/env python3
"""Stat editor for PC-format Isaac saves that the Mac App Store build imports.

Loads a save, lets every counter be edited, re-signs it with the checksum the
game actually validates (see isaac_pc_checksum) and writes the result out.
Installing into the save folder is left to the user.

The interface is a page served on localhost rather than a desktop window: the
Tk that ships with macOS is stuck at 8.5.9 and silently refuses to draw labels
and entry fields, which made a native window come up blank.
"""

from __future__ import annotations

import html
import http.server
import os
import socket
import struct
import subprocess
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import isaac_pc_checksum as pccrc

HEADER = b"ISAACNGSAVE06R  "
COUNTER_SECTION_TYPE = 2
ENTRY_LENGTHS = [1, 4, 4, 1, 1, 1, 1, 4, 4, 1]
DESKTOP = Path.home() / "Desktop"
DEFAULT_OUTPUT = DESKTOP / "persistentgamedata3.dat"
HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE / "isaac_saves" / "capture" / "source_downloads_persistentgamedata2.dat"

GAME_SAVES = Path.home() / "Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents"
SEARCH_DIRS = [
    ("папка игры", GAME_SAVES, False),
    ("папка проекта", HERE / "isaac_saves", True),
    ("рабочий стол", DESKTOP, False),
    ("загрузки", Path.home() / "Downloads", False),
]
MAX_FOUND = 60

# Counter names by index within the stats section. Taken from the open parser
# at github.com/ihabunek/isaac, whose section base (223) matches ours, and
# checked here against three counters whose values the game displayed for this
# save: mom kills 545, deaths 772, donated coins 1113. All three line up, and
# so does best streak, which bounds the block from the other side.
STAT_NAMES = {
    1: "Убийства мамы",
    2: "Разбито камней",
    3: "Разбито цветных камней",
    4: "Разбито какашек",
    5: "Съедено таблеток",
    6: "Использований карты смерти",
    8: "Заходов в аркады",
    9: "Смерти",
    10: "Убийств Айзека",
    11: "Взорвано торговцев",
    12: "Убийств Сатаны",
    13: "Игр в напёрстки",
    14: "Ангельских сделок",
    15: "Сделок с дьяволом",
    16: "Сдач крови",
    17: "Взорвано аркад",
    18: "Уровень разблокировки The Lost",
    19: "Монет в автомате пожертвований",
    20: "Жетоны Эдема",
    21: "Текущий стрик побед",
    22: "Лучший стрик (BEST STREAK)",
    23: "Убийств ??? (Blue Baby)",
    24: "Убийств Агнца",
    92: "Побед в Boss Rush",
    94: "Стрик поражений",
}


def counter_section(data: bytes) -> tuple[int, int]:
    """Return (payload_offset, entry_count) of the stats section."""
    ofs = 0x14
    for entry_len in ENTRY_LENGTHS:
        if ofs + 12 > len(data):
            break
        section_type, _param, count = struct.unpack_from("<III", data, ofs)
        if section_type == 0 or section_type > 12 or count > 4000:
            break
        payload = ofs + 12
        if section_type == COUNTER_SECTION_TYPE:
            return payload, count
        ofs = payload + count * entry_len
    raise ValueError("Секция статистики не найдена")


def progress(data: bytes) -> str:
    ofs, counts = 0x14, {}
    for entry_len in ENTRY_LENGTHS:
        if ofs + 12 > len(data):
            break
        section_type, _param, count = struct.unpack_from("<III", data, ofs)
        if section_type == 0 or section_type > 12 or count > 4000:
            break
        payload = ofs + 12
        counts[section_type] = (payload, count, entry_len)
        ofs = payload + count * entry_len

    def filled(section_type: int) -> str:
        if section_type not in counts:
            return "?"
        payload, count, entry_len = counts[section_type]
        if entry_len != 1:
            return "?"
        # index 0 is a placeholder the game never sets
        return f"{sum(1 for i in range(1, count) if data[payload + i])}/{count - 1}"

    return f"предметы {filled(4)} · секреты {filled(1)} · испытания {filled(7)}"


class Save:
    def __init__(self, path: Path) -> None:
        data = bytearray(path.read_bytes())
        if data[:16] != HEADER:
            raise ValueError(
                "Это не PC-формат сейва. Нужен файл с заголовком ISAACNGSAVE06R — "
                "мобильные сейвы, которые пишет сама игра, редактировать пока нельзя."
            )
        self.path = path.resolve()
        self.data = data
        try:
            self.base, self.count = counter_section(bytes(data))
        except ValueError:
            raise ValueError(
                "Заголовок PC-формата на месте, но разложить файл на секции не "
                "получилось — скорее всего это сейв от другой версии игры."
            ) from None

    def value(self, index: int) -> int:
        return struct.unpack_from("<I", self.data, self.base + index * 4)[0]

    def summary(self) -> tuple[str, bool]:
        valid = pccrc.verify(bytes(self.data))
        text = (f"{self.path.name} · {len(self.data)} байт · подпись "
                f"{'верна' if valid else 'не сходится'} · {progress(bytes(self.data))}")
        return text, valid

    def write(self, values: dict[int, int], target: Path) -> list[str]:
        out = bytearray(self.data)
        changed = []
        for index, value in values.items():
            old = struct.unpack_from("<I", out, self.base + index * 4)[0]
            if old == value:
                continue
            struct.pack_into("<I", out, self.base + index * 4, value)
            name = STAT_NAMES.get(index, f"счётчик {index}")
            changed.append(f"{name}: {old} → {value}")
        pccrc.sign(out)
        if not pccrc.verify(bytes(out)):
            raise ValueError("Подпись не сошлась после записи, файл не сохранён")
        target.write_bytes(out)
        self.data = out
        return changed


def describe(path: Path) -> tuple[str, bool]:
    """Return a short description of a save file and whether it can be edited.

    A PC header alone is not enough: saves from other builds carry a section
    layout this parser does not understand, so the counters are looked up here
    rather than letting the file fail only once it is opened.
    """
    try:
        head = path.open("rb").read(24)
        size = path.stat().st_size
    except OSError as exc:
        return f"не прочитать: {exc}", False
    if head[:16] == HEADER:
        try:
            counter_section(path.read_bytes())
        except (OSError, ValueError):
            return f"PC-формат · {size} байт · раскладка не распознана", False
        return f"PC-формат · {size} байт", True
    if head[:2] == b"\xf3\x0a" or b"ISAACNGSAVE" in head:
        return f"мобильный формат · {size} байт · правка недоступна", False
    return f"не сейв Isaac · {size} байт", False


def find_saves() -> list[tuple[str, Path | None, str, bool]]:
    """Look for save files in the usual places.

    Entries with no path are notes: the game keeps its saves inside a protected
    container, which macOS hides from any app without Full Disk Access.
    """
    found, seen = [], set()
    for where, directory, recursive in SEARCH_DIRS:
        if not directory.is_dir():
            continue
        try:
            # glob swallows permission errors and just yields nothing, so the
            # directory is probed directly to tell "empty" from "not allowed"
            os.listdir(directory)
            paths = directory.rglob("*.dat") if recursive else directory.glob("*.dat")
            entries = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
        except PermissionError:
            found.append((where, None, "macOS закрыла доступ к этой папке — "
                          "выдай Терминалу полный доступ к диску", False))
            continue
        except OSError:
            continue
        for path in entries:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            description, editable = describe(path)
            found.append((where, path, description, editable))
            if len(found) >= MAX_FOUND:
                return found
    return found


def choose_file() -> Path | None:
    """Open the real Finder dialog and return what was picked."""
    script = ('set f to choose file with prompt "Выбери файл сейва Isaac" '
              'default location (path to home folder)\nPOSIX path of f')
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:  # cancelled
        return None
    return Path(result.stdout.strip())


PAGE = """<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<title>Isaac — редактор сейва</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 -apple-system, system-ui, sans-serif; margin: 0;
          background: Canvas; color: CanvasText; }}
  header {{ padding: 22px 28px 14px; border-bottom: 1px solid rgba(128,128,128,.3); }}
  h1 {{ font-size: 19px; margin: 0 0 6px; }}
  .meta {{ font-size: 13px; opacity: .75; }}
  .ok {{ color: #1d9a3c; }} .bad {{ color: #d1342f; }}
  main {{ padding: 18px 28px 40px; }}
  .banner {{ margin: 0 0 18px; padding: 12px 14px; border-radius: 8px;
             background: rgba(29,154,60,.12); border: 1px solid rgba(29,154,60,.4); }}
  .banner.error {{ background: rgba(209,52,47,.12); border-color: rgba(209,52,47,.45); }}
  .banner pre {{ margin: 8px 0 0; font: 13px/1.5 ui-monospace, monospace; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
           gap: 4px 26px; }}
  .row {{ display: flex; align-items: center; gap: 10px; padding: 3px 0; }}
  .row label {{ flex: 1; }}
  .row.unknown label {{ opacity: .55; }}
  input[type=number] {{ width: 108px; padding: 5px 7px; text-align: right;
      border: 1px solid rgba(128,128,128,.5); border-radius: 6px;
      background: Field; color: FieldText; font: inherit; }}
  input[type=text] {{ width: 100%; padding: 7px 9px; border-radius: 6px;
      border: 1px solid rgba(128,128,128,.5); background: Field; color: FieldText;
      font: inherit; }}
  h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: .06em;
        opacity: .6; margin: 26px 0 10px; }}
  .bar {{ position: sticky; bottom: 0; padding: 14px 28px;
          background: Canvas; border-top: 1px solid rgba(128,128,128,.3);
          display: flex; align-items: center; gap: 16px; }}
  button {{ font: inherit; font-weight: 600; padding: 9px 18px; border: 0;
            border-radius: 8px; background: #2f6fd0; color: #fff; cursor: pointer; }}
  button.quit {{ background: transparent; color: CanvasText; opacity: .6;
                 font-weight: 400; padding: 9px 4px; }}
  .warn {{ color: #b06000; font-size: 13px; }}
  .out {{ flex: 1; }}
  .pick {{ display: flex; align-items: center; gap: 10px; margin-top: 12px; }}
  .pick form {{ display: flex; gap: 8px; }}
  .pick .manual {{ flex: 1; }}
  .pick button {{ padding: 7px 14px; font-weight: 500; }}
  .link {{ color: inherit; opacity: .6; font-size: 13px; white-space: nowrap; }}
  details {{ margin-top: 12px; font-size: 13px; }}
  summary {{ cursor: pointer; opacity: .7; }}
  .files {{ margin-top: 10px; max-height: 260px; overflow: auto;
            border: 1px solid rgba(128,128,128,.3); border-radius: 8px; }}
  .file {{ display: flex; align-items: center; gap: 12px; padding: 7px 12px;
           border-bottom: 1px solid rgba(128,128,128,.18); }}
  .file:last-child {{ border-bottom: 0; }}
  .file .name {{ flex: 1; overflow: hidden; text-overflow: ellipsis;
                 white-space: nowrap; }}
  .file .desc {{ opacity: .6; white-space: nowrap; }}
  .file .where {{ opacity: .45; white-space: nowrap; }}
  .file button {{ padding: 4px 12px; font-size: 13px; font-weight: 500; }}
  .file.current {{ background: rgba(47,111,208,.12); }}
  .file.locked .desc {{ color: #b06000; }}
</style>
<header>
  <h1>Редактор статистики Isaac</h1>
  <div class="meta {status_class}">{status}</div>
  <div class="pick">
    <form method="post" action="/browse"><button type="submit">Обзор…</button></form>
    <form method="post" action="/open" class="manual">
      <input type="text" name="path" value="{source}" spellcheck="false">
      <button type="submit">Открыть</button>
    </form>
    <a href="#" onclick="document.getElementById('found').open=true;return false"
       class="link">найденные файлы</a>
  </div>
  <details id="found"><summary>Сейвы, найденные на компьютере</summary>
    <div class="files">{files}</div>
  </details>
</header>
<form method="post" action="/save">
<main>
  {banner}
  <h2>Основные</h2>
  <div class="grid">{known}</div>
  <h2>Остальные счётчики</h2>
  <div class="grid">{unknown}</div>
</main>
<div class="bar">
  <div class="out">
    <input type="text" name="output" value="{output}" spellcheck="false">
  </div>
  <span class="warn">Выключи Wi-Fi и закрой игру перед заменой</span>
  <button type="submit">Сохранить файл</button>
  <button type="submit" formaction="/quit" formnovalidate class="quit">Закрыть редактор</button>
</div>
</form>
</html>
"""

BYE = """<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Закрыто</title>
<body style="font: 15px -apple-system, system-ui, sans-serif; padding: 40px;
             color-scheme: light dark; background: Canvas; color: CanvasText;">
<h1 style="font-size:18px">Редактор закрыт</h1>
<p>Вкладку можно закрывать. Чтобы открыть снова — запусти «Редактор сейва Isaac».</p>
</html>
"""


def render(save: Save, banner: str = "", output: str = str(DEFAULT_OUTPUT)) -> bytes:
    known_rows, unknown_rows = [], []
    for index in range(save.count):
        offset = index * 4
        value = save.value(index)
        named = STAT_NAMES.get(index)
        if named:
            label = html.escape(named)
            rows, css = known_rows, "row"
        else:
            label = f"счётчик {index} · 0x{offset:02X}"
            rows, css = unknown_rows, "row unknown"
        rows.append(
            f'<div class="{css}"><label for="c{index}">{label}</label>'
            f'<input type="number" id="c{index}" name="c{index}" min="0" '
            f'max="4294967295" value="{value}"></div>'
        )

    file_rows = []
    for where, path, description, editable in find_saves():
        if path is None:
            file_rows.append(
                f'<div class="file locked"><span class="name">{where}</span>'
                f'<span class="desc">{html.escape(description)}</span></div>'
            )
            continue
        current = " current" if path == save.path else ""
        locked = "" if editable else " locked"
        action = ('<button type="submit">Открыть</button>' if editable
                  else '<span class="where">—</span>')
        file_rows.append(
            f'<form method="post" action="/open" class="file{current}{locked}">'
            f'<input type="hidden" name="path" value="{html.escape(str(path))}">'
            f'<span class="name">{html.escape(path.name)}</span>'
            f'<span class="desc">{html.escape(description)}</span>'
            f'<span class="where">{where}</span>{action}</form>'
        )

    status, valid = save.summary()
    page = PAGE.format(
        status=html.escape(status),
        status_class="ok" if valid else "bad",
        banner=banner,
        known="".join(known_rows),
        unknown="".join(unknown_rows),
        output=html.escape(output),
        source=html.escape(str(save.path)),
        files="".join(file_rows) or "<div class=file>ничего не нашлось</div>",
    )
    return page.encode()


class Handler(http.server.BaseHTTPRequestHandler):
    save: Save

    def log_message(self, *_args) -> None:  # keep the console quiet
        pass

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        self._send(render(self.save))

    def _open(self, form: dict[str, list[str]]) -> None:
        if self.path == "/browse":
            chosen = choose_file()
            if chosen is None:
                self._send(render(self.save, '<div class="banner">Выбор отменён.</div>'))
                return
        else:
            chosen = Path(form.get("path", [""])[0].strip()).expanduser()

        try:
            self.__class__.save = Save(chosen)
        except (OSError, ValueError) as exc:
            banner = (f'<div class="banner error"><b>Не открылось:</b> '
                      f'{html.escape(str(chosen))}<pre>{html.escape(str(exc))}</pre></div>')
            self._send(render(self.save, banner))
            return

        self._send(render(self.save, f'<div class="banner"><b>Открыт файл:</b> '
                                     f'{html.escape(str(chosen))}</div>'))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())

        if self.path == "/quit":
            self._send(BYE.encode())
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if self.path in ("/open", "/browse"):
            self._open(form)
            return
        target = Path(form.get("output", [str(DEFAULT_OUTPUT)])[0]).expanduser()

        values = {}
        for key, raw in form.items():
            if not key.startswith("c"):
                continue
            try:
                value = int(raw[0])
            except ValueError:
                continue
            if 0 <= value <= 0xFFFFFFFF:
                values[int(key[1:])] = value

        try:
            changed = self.save.write(values, target)
        except (OSError, ValueError) as exc:
            banner = (f'<div class="banner error"><b>Не сохранилось.</b><pre>'
                      f'{html.escape(str(exc))}</pre></div>')
        else:
            listing = html.escape("\n".join(changed) or "значения не менялись")
            banner = (f'<div class="banner"><b>Сохранено:</b> {html.escape(str(target))}'
                      f'<pre>{listing}</pre>Дальше: выключи Wi-Fi, закрой игру через '
                      f'Cmd+Q, скопируй файл в папку сейвов, запусти игру.</div>')
        self._send(render(self.save, banner, str(target)))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main(source: Path = DEFAULT_SOURCE, open_browser: bool = True) -> None:
    Handler.save = Save(source)
    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Редактор открыт: {url}\nЗакрыть — Ctrl+C в этом окне.", flush=True)
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=[url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nЗакрыто.")


if __name__ == "__main__":
    main()
