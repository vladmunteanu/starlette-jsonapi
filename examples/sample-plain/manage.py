import logging

from uvicorn.main import run

from sample_plain.app import create_app


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = create_app()
    run(app)
