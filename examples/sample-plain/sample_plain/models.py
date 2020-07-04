from typing import Optional, List


db = {}
id_sequences = {}


class Model:
    __db_name__: str
    id: int = None

    @classmethod
    def get_items(cls) -> List['Model']:
        db.setdefault(cls.__db_name__, {})
        return list(db[cls.__db_name__].values())

    @classmethod
    def get_item(cls, item_id: int) -> Optional['Model']:
        db.setdefault(cls.__db_name__, {})
        return db[cls.__db_name__].get(item_id)

    def save(self) -> None:
        db.setdefault(self.__db_name__, {})
        if not self.id:
            id_sequences.setdefault(self.__db_name__, 1)
            self.id = id_sequences[self.__db_name__]
            id_sequences[self.__db_name__] += 1
        db[self.__db_name__][self.id] = self
        return None

    def delete(self) -> None:
        db.setdefault(self.__db_name__, {})
        db[self.__db_name__].pop(self.id, None)


class Organization(Model):
    __db_name__: str = 'organizations'

    name: str
    contact_url: Optional[str] = None
    contact_phone: Optional[str] = None


class User(Model):
    __db_name__: str = 'users'

    username: str
    organization: Organization
