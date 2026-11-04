"""Черновик своего тестового набора: записи пользователей, которые согласились отдавать их для улучшения моделей.

Для каждой записи кладутся звук, расшифровка модели (разметчик правит её до дословной: все «ну», «э-э»,
повторы и оговорки) и оценки человека «верно / неверно» из приложения. Записи без согласия не выгружаются.

    python -m training.export_dataset --out data/own_testset_draft --limit 50
"""
import argparse
import json
import shutil
from pathlib import Path

from sqlalchemy import select


def export(session, audio_dir, out, limit=None):
    from talkmate.models import Speech, User

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    query = (select(Speech).join(User).where(User.share_recordings.is_(True)).order_by(Speech.created_at.desc()))
    if limit:
        query = query.limit(limit)
    exported = 0
    for speech in session.scalars(query):
        source = Path(audio_dir) / speech.audio_file
        if not source.exists():
            continue
        name = f"rec{speech.id:05d}"
        shutil.copyfile(source, out / f"{name}{source.suffix}")
        (out / f"{name}.txt").write_text(speech.text or "", encoding="utf-8")
        meta = {"language": speech.language or "ru", "ratings": {r.metric: r.verdict for r in speech.ratings}}
        (out / f"{name}.model.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        exported += 1
    return exported


def main(argv=None):
    from talkmate.config import Config
    from talkmate.data_connector import DataConnector

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/own_testset_draft")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    config = Config()
    connector = DataConnector(config.DATABASE_URL)
    with connector.session() as session:
        count = export(session, config.AUDIO_DIR, args.out, args.limit)
    print(f"Выгружено записей: {count}. Поправьте .txt до дословной расшифровки и добавьте .json с оценками людей.")


if __name__ == "__main__":
    main()
