#!/usr/bin/env python3
"""Collect native DOCS_SCREENSHOT exports, build an index, previews and a ZIP."""
import html
import json
from pathlib import Path
import shutil
import sys
import textwrap
import zipfile
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ENGLISH = '--en' in sys.argv
if ENGLISH: sys.argv.remove('--en')
OUT = ROOT / ('docs/screens/current-ios-en' if ENGLISH else 'docs/screens/current-ios')
LABELS = [
'Онбординг: начало', 'Онбординг: слайды', 'Онбординг: разбор',
'Условия: проект', 'Конфиденциальность: проект', 'Регистрация: верх', 'Регистрация: низ',
'Вход', 'Восстановление: email', 'Восстановление: код', 'Главная',
'Профиль: верх', 'Профиль: низ', 'Настройки: верх', 'Настройки: низ', 'Тренировки',
'Статьи', 'Статья: жесты', 'Статья: площадка', 'Статья: презентация', 'Статья: разогрев',
'Статистика: верх', 'Статистика: середина', 'Запись: до старта', 'Запись: активна',
'Запись: пауза', 'Запись: завершена', 'Разбор: итог', 'Разбор: метрики', 'Разбор: подробности',
'Разбор: содержание', 'Разбор: расшифровка', 'Запись с PDF', 'Просмотр PDF: второй слайд',
'Разбор презентации', 'Статистика: пусто', 'Ошибка соединения', 'Статистика: низ',
]
if ENGLISH:
    LABELS = [
        'Onboarding: start', 'Onboarding: slides', 'Onboarding: review',
        'Terms: draft', 'Privacy: draft', 'Sign up: top', 'Sign up: bottom',
        'Log in', 'Reset password: email', 'Reset password: code', 'Home',
        'Profile: top', 'Profile: bottom', 'Settings: top', 'Settings: bottom', 'Sessions',
        'Articles', 'Article: gestures', 'Article: venue', 'Article: slides', 'Article: warm-up',
        'Progress: top', 'Progress: middle', 'Recording: idle', 'Recording: active',
        'Recording: paused', 'Recording: ready', 'Review: summary', 'Review: metrics', 'Review: details',
        'Review: content', 'Review: transcript', 'Recording with PDF', 'PDF viewer: slide 2',
        'Slides review', 'Progress: empty', 'Connection error', 'Progress: bottom',
    ]
OUT.mkdir(parents=True, exist_ok=True)
exported = set()
for log in map(Path, sys.argv[1:]):
    for line in log.read_text().splitlines():
        if 'DOCS_SCREENSHOT: ' not in line:
            continue
        source = Path(line.split('DOCS_SCREENSHOT: ', 1)[1].strip())
        if source.name.startswith('all_') and source.exists():
            name = source.name.removeprefix('all_')
            shutil.copy2(source, OUT / name)
            exported.add(name)
for stale in OUT.glob('[0-9][0-9]_*.png'):
    if stale.name not in exported: stale.unlink()
files = sorted(OUT / name for name in exported)
entries = []
for path in files:
    number = int(path.name[:2])
    with Image.open(path) as im:
        if im.size != (1206, 2622):
            raise ValueError(f'Unexpected dimensions: {path.name}: {im.size}')
    entries.append({'file': path.name, 'title': LABELS[number - 1], 'width': 1206, 'height': 2622})
missing = sorted(set(range(1, 39)) - {int(p.name[:2]) for p in files})
manifest = {'date': '2026-11-04', 'platform': 'iOS 27.0', 'device': 'iPhone 17 Simulator',
            'language': 'en' if ENGLISH else 'ru', 'appearance': 'light', 'text_size': 'standard',
            'data': 'FakeApi / FakeRecorder; synthetic PDF. No user account or real speech analysis.',
            'screenshots': entries, 'missing': missing}
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
intro = ('Актуальная iOS-версия · 4 ноября 2026 · iPhone 17 Simulator · 1206 × 2622 px. '
         'Русский интерфейс, стандартный текст, светлая тема. Демонстрационные данные FakeApi, '
         'PDF создан для теста. Это нативные кадры приложения, не макеты и не реальные результаты пользователя.')
if ENGLISH:
    intro = ('Current iOS app · 4 November 2026 · iPhone 17 Simulator · 1206 × 2622 px. '
             'English interface, standard text, light appearance. Demo data from FakeApi and FakeRecorder, '
             'with a synthetic test PDF. Native app screenshots, not mockups or a real user speech analysis.')
rows = '\n'.join(f'| [{e["file"]}]({e["file"]}) | {e["title"]} |' for e in entries)
(OUT / 'README.md').write_text('# Все экраны Talk Mate\n\n' + intro + '\n\n'
    '[Галерея](index.html) · [Манифест](manifest.json)\n\n'
    '| Файл | Экран / состояние |\n| --- | --- |\n' + rows + '\n\n'
    'Для длинных экранов сохранены несколько положений прокрутки. Юридические документы остаются проектами. '
    'Этот набор покрывает самостоятельные экраны и перечисленные состояния; он не представляет все возможные ошибки, диалоги и языковые варианты.\n')
if ENGLISH:
    readme = (OUT / 'README.md').read_text().replace('# Все экраны Talk Mate', '# Talk Mate: all screens').replace('[Галерея]', '[Gallery]').replace('[Манифест]', '[Manifest]').replace('| Файл | Экран / состояние |', '| File | Screen / state |')
    readme = readme[:readme.index('Для длинных экранов')] + 'Long screens include multiple scroll positions. Legal documents remain drafts. The set covers app screens and the listed states, not every possible dialog, error or language variant.\n'
    (OUT / 'README.md').write_text(readme)
cards = ''.join(f'<a href="{html.escape(e["file"])}"><img loading="lazy" src="{html.escape(e["file"])}"><span>{html.escape(e["title"])}</span></a>' for e in entries)
(OUT / 'index.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Talk Mate — все экраны</title>'
    '<style>body{font:16px system-ui;background:#f5f5f8;color:#18181d;margin:32px}'
    'p{max-width:850px;line-height:1.6}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:24px}'
    'a{color:inherit;text-decoration:none}img{display:block;width:100%;border-radius:16px;border:1px solid #ddd}'
    'span{display:block;padding:10px 0;font-weight:600}</style><h1>Talk Mate · все экраны</h1><p>'
    + html.escape(intro) + '</p><main>' + cards + '</main></html>')
if ENGLISH:
    page = (OUT / 'index.html').read_text().replace('lang="ru"', 'lang="en"').replace('Talk Mate — все экраны', 'Talk Mate — all screens').replace('Talk Mate · все экраны', 'Talk Mate · all screens')
    (OUT / 'index.html').write_text(page)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
for part in range((len(entries) + 19) // 20):
    batch = entries[part * 20:(part + 1) * 20]
    cols, tile_w, tile_h = 5, 220, 480
    board = Image.new('RGB', (cols * tile_w, ((len(batch) + cols - 1)//cols)*tile_h + 60), '#f1f1f6')
    draw = ImageDraw.Draw(board)
    draw.text((16, 20), f'Talk Mate · iOS · 04.11.2026 · {part + 1}', fill='#18181d', font=font)
    for n, entry in enumerate(batch):
        x, y = (n % cols) * tile_w + 14, (n // cols) * tile_h + 60
        with Image.open(OUT / entry['file']) as shot:
            shot.thumbnail((192, 418), Image.Resampling.LANCZOS)
            board.paste(shot.convert('RGB'), (x, y))
        draw.multiline_text((x, y + 426), "\n".join(textwrap.wrap(f'{entry["file"][:2]} · {entry["title"]}', width=26)), fill='#18181d', font=font, spacing=3)
    board.save(OUT / f'overview-{part + 1}.jpg', quality=90)
archive_dir = ROOT / 'output/screens'
archive_dir.mkdir(parents=True, exist_ok=True)
archive = archive_dir / ('talkmate-all-screens-ios-en-2026-11-04.zip' if ENGLISH else 'talkmate-all-screens-ios-2026-11-04.zip')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for path in sorted(OUT.iterdir()):
        if path.is_file(): zipf.write(path, 'talkmate-screens/' + path.name)
print(json.dumps({'screens': len(entries), 'missing': missing, 'archive': str(archive)}, ensure_ascii=False))
