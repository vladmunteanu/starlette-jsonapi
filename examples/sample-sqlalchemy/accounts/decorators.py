from functools import wraps

from accounts.app import Session


def with_sqlalchemy_session(f):
    @wraps(f)
    async def inner(self, *args, **kwargs):
        self.db_session = Session()
        try:
            return await f(self, *args, **kwargs)
        except Exception:
            self.db_session.rollback()
            raise
        finally:
            self.db_session.close()
    return inner
