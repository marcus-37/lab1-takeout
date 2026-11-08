"""商家与店铺服务（对应组件图 SHOP，REQ-002/003/026）。"""

from campus_eats.models.account import Account
from campus_eats.models.enums import Role, ShopStatus
from campus_eats.models.errors import PermissionDeniedError, ValidationError
from campus_eats.models.shop_dish import Shop
from campus_eats.services.audit_service import AuditService
from campus_eats.services.context import ServiceContext


class ShopService:
    """入驻申请与审核、营业状态切换、平台强制关店。"""

    def __init__(self, context: ServiceContext, audit: AuditService) -> None:
        """绑定上下文与审计服务。"""
        self._ctx = context
        self._audit = audit

    def apply(self, merchant: Account, name: str, category: str, area_code: str,
              address_text: str, license_no: str) -> Shop:
        """商家提交入驻申请：店铺进入待审核状态（REQ-002）。

        一个商家只能有一家店铺（REQ-001 商家与店铺一一对应）。
        """
        if merchant.role is not Role.MERCHANT:
            raise PermissionDeniedError("只有商家账号可以提交入驻申请")
        if self._ctx.repos.shops.get_by_merchant(merchant.account_id) is not None:
            raise ValidationError("该商家已有店铺，本期不设多店")
        if not name.strip() or not license_no.strip():
            raise ValidationError("店铺名称与执照号不能为空")
        shop = Shop(merchant_id=merchant.account_id, name=name.strip(),
                    category=category.strip(), area_code=area_code.strip(),
                    address_text=address_text.strip(), license_no=license_no.strip(),
                    status=ShopStatus.PENDING_REVIEW, created_at=self._ctx.clock.now())
        self._ctx.repos.shops.add(shop)
        self._audit.record(merchant, "SHOP", shop.shop_id, f"店铺 {shop.name}",
                           "提交入驻申请", after=ShopStatus.PENDING_REVIEW.label)
        return shop

    def review(self, operator: Account, shop_id: int, approve: bool,
               reason: str = "") -> Shop:
        """管理员审核入驻申请（REQ-002）。

        通过：店铺转休息中，商家配置菜品后可自行开业；驳回：转已驳回，
        必须填写原因；同一申请不能重复审核。
        """
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可审核入驻申请")
        if not approve and not reason.strip():
            raise ValidationError("驳回必须填写原因")
        with self._ctx.lock:
            shop = self._require_shop(shop_id)
            if shop.status is not ShopStatus.PENDING_REVIEW:
                raise ValidationError(
                    f"店铺当前为「{shop.status.label}」，不能重复审核（REQ-002）")
            before = shop.status.label
            shop.status = ShopStatus.RESTING if approve else ShopStatus.REJECTED
            shop.review_reason = "" if approve else reason.strip()
            self._ctx.repos.shops.update(shop)
            action = "审核通过" if approve else "驳回入驻"
            self._audit.record(operator, "SHOP", shop_id, f"店铺 {shop.name}",
                               action, before=before, after=shop.status.label,
                               reason=reason)
            self._audit.notify(shop.merchant_id,
                               f"入驻申请{action}" if not approve else "入驻审核通过",
                               reason if not approve else "请配置菜品后开业")
            return shop

    def open(self, merchant: Account) -> Shop:
        """商家开业：休息中 -> 营业中（REQ-003）。"""
        with self._ctx.lock:
            shop = self._require_own_shop(merchant)
            before = shop.status.label
            shop.open()
            self._ctx.repos.shops.update(shop)
            self._audit.record(merchant, "SHOP", shop.shop_id, f"店铺 {shop.name}",
                               "开业", before=before, after=shop.status.label)
            return shop

    def rest(self, merchant: Account) -> Shop:
        """商家休息：营业中 -> 休息中；存量订单不受影响（REQ-003）。"""
        with self._ctx.lock:
            shop = self._require_own_shop(merchant)
            before = shop.status.label
            shop.rest()
            self._ctx.repos.shops.update(shop)
            self._audit.record(merchant, "SHOP", shop.shop_id, f"店铺 {shop.name}",
                               "转休息", before=before, after=shop.status.label)
            return shop

    def close_by_platform(self, operator: Account, shop_id: int, reason: str) -> Shop:
        """平台强制关店（REQ-026）：任何非待审核状态可关，必须记录原因。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可强制关店")
        with self._ctx.lock:
            shop = self._require_shop(shop_id)
            before = shop.status.label
            shop.close_by_platform(reason)
            self._ctx.repos.shops.update(shop)
            self._audit.record(operator, "SHOP", shop_id, f"店铺 {shop.name}",
                               "强制关店", before=before, after=shop.status.label,
                               reason=reason)
            self._audit.notify(shop.merchant_id, "店铺被平台强制关闭", reason)
            return shop

    def get_shop(self, shop_id: int) -> Shop:
        """按 id 取店铺。"""
        return self._require_shop(shop_id)

    def get_own_shop(self, merchant: Account) -> Shop:
        """取商家名下店铺。"""
        return self._require_own_shop(merchant)

    def list_operating(self) -> list[Shop]:
        """顾客可见店铺：营业中 + 休息中；平台关闭不可浏览（REQ-003）。"""
        return self._ctx.repos.shops.list_operating()

    def list_pending(self, operator: Account) -> list[Shop]:
        """管理员看待审核申请列表。"""
        if operator.role is not Role.ADMIN:
            raise PermissionDeniedError("仅管理员可查看待审核列表")
        return self._ctx.repos.shops.list_by_status(ShopStatus.PENDING_REVIEW)

    def _require_shop(self, shop_id: int) -> Shop:
        """取店铺或抛错。"""
        shop = self._ctx.repos.shops.get(shop_id)
        if shop is None:
            raise ValidationError("店铺不存在")
        return shop

    def _require_own_shop(self, merchant: Account) -> Shop:
        """取商家自己的店铺，身份不符抛错。"""
        if merchant.role is not Role.MERCHANT:
            raise PermissionDeniedError("只有商家账号可执行该操作")
        shop = self._ctx.repos.shops.get_by_merchant(merchant.account_id)
        if shop is None:
            raise ValidationError("商家尚未提交入驻申请")
        return shop
