import logging

from uvicorn.main import run

from accounts.app import create_app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    try:
        run(app)
    except Exception:
        logging.exception('Encountered error while running app')
