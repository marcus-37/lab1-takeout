"""账号与楼栋的仓储实现。

账号用单表继承存储：四类角色共用一张表，子类字段（余额、执照、在线、
片区、级别）作为可空列，读取时按 role 还原为对应子类实例。
"""

from campus_eats.models.account import Account, Admin, Customer, Merchant, Rider
from campus_eats.models.delivery import Building
from campus_eats.models.enums import AccountStatus, Role
from campus_eats.repositories.database import Database, parse_dt

_ROLE_CLASSES = {
    Role.CUSTOMER: Customer,
    Role.MERCHANT: Merchant,
    Role.RIDER: Rider,
    Role.ADMIN: Admin,
}


class AccountRepository:
    """账号的增查改。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def _row_to_account(self, row) -> Account:
        """把一行数据还原为对应角色的账号子类实例。"""
        role = Role(row["role"])
        cls = _ROLE_CLASSES[role]
        base = {"phone": row["phone"], "name": row["name"],
                "password_hash": row["password_hash"], "role": role,
                "status": AccountStatus(row["status"]), "account_id": row["account_id"],
                "created_at": parse_dt(row["created_at"])}
        if role is Role.CUSTOMER:
            return cls(**base, balance_fen=row["balance_fen"] or 0)
        if role is Role.MERCHANT:
            return cls(**base, license_no=row["license_no"] or "")
        if role is Role.RIDER:
            return cls(**base, online=bool(row["online"]),
                       area_code=row["area_code"] or "")
        return cls(**base, admin_level=row["admin_level"] or 1)

    def add(self, account: Account) -> int:
        """新增账号，回填 account_id。created_at 须由服务层按服务端时钟设置。"""
        assert account.created_at is not None, "created_at 必须由服务层按服务端时钟设置"
        account.account_id = self._db.execute(
            "INSERT INTO account (phone, name, password_hash, role, status, balance_fen,"
            " license_no, online, area_code, admin_level, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (account.phone, account.name, account.password_hash, account.role.value,
             account.status.value, getattr(account, "balance_fen", 0),
             getattr(account, "license_no", None), int(getattr(account, "online", False)),
             getattr(account, "area_code", ""), getattr(account, "admin_level", None),
             account.created_at.isoformat()))
        return account.account_id

    def get(self, account_id: int) -> Account | None:
        """按主键查账号。"""
        row = self._db.query_one("SELECT * FROM account WHERE account_id=?", (account_id,))
        return self._row_to_account(row) if row else None

    def find_by_phone(self, phone: str) -> Account | None:
        """按手机号查账号（登录用）。"""
        row = self._db.query_one("SELECT * FROM account WHERE phone=?", (phone,))
        return self._row_to_account(row) if row else None

    def list_by_role(self, role: Role) -> list[Account]:
        """列出某角色的全部账号（管理端用）。"""
        rows = self._db.query_all("SELECT * FROM account WHERE role=? ORDER BY account_id",
                                  (role.value,))
        return [self._row_to_account(r) for r in rows]

    def update(self, account: Account) -> None:
        """持久化账号的可变字段：状态、余额、在线、姓名等。"""
        self._db.execute(
            "UPDATE account SET name=?, status=?, balance_fen=?, license_no=?, online=?,"
            " area_code=?, admin_level=? WHERE account_id=?",
            (account.name, account.status.value, getattr(account, "balance_fen", 0),
             getattr(account, "license_no", None), int(getattr(account, "online", False)),
             getattr(account, "area_code", ""), getattr(account, "admin_level", None),
             account.account_id))


class BuildingRepository:
    """预设楼栋的只读仓储（种子数据写入，业务只读，REQ-008）。"""

    def __init__(self, db: Database) -> None:
        """绑定数据库连接。"""
        self._db = db

    def add(self, building: Building) -> None:
        """写入一个楼栋（仅种子脚本使用）。"""
        self._db.execute("INSERT OR REPLACE INTO building VALUES (?,?,?)",
                         (building.code, building.name, int(building.in_range)))

    def find(self, code: str) -> Building | None:
        """按编号查楼栋。"""
        row = self._db.query_one("SELECT * FROM building WHERE code=?", (code,))
        if not row:
            return None
        return Building(code=row["code"], name=row["name"], in_range=bool(row["in_range"]))

    def list_all(self) -> list[Building]:
        """全部楼栋，按编号排序。"""
        rows = self._db.query_all("SELECT * FROM building ORDER BY code")
        return [Building(code=r["code"], name=r["name"], in_range=bool(r["in_range"]))
                for r in rows]
