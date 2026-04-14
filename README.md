# Voxel AI World v2

Исправлено:
- меню скрывается после входа
- камеру можно крутить пальцем
- отключён zoom/pinch на iPhone

## Запуск
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
