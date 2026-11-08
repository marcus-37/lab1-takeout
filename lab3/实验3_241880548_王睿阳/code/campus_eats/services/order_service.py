"""订单服务（对应组件图 ORD）：购物车、下单、状态机唯一写入口。

组件图注记的落地：Order.status 只允许本服务修改；支付、配送、售后、
定时任务都通过本服务暴露的窄接口回写状态，保证状态机不被绕过。
"""

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from campus_eats.models.account import Account
from campus_eats.models.cart_order import CartItem, Order, OrderItem
from campus_eats.models.enums import OrderStatus, Role
from campus_eats.models.errors import (
    ConflictError, OutOfStockError, PermissionDeniedError, ValidationError,
)
from campus_eats.models.money import fen_to_yuan
from campus_eats.services.audit_service import AuditService
from campus_eats.services.catalog_service import CatalogService
from campus_eats.services.config import (
    ACCEPT_TIMEOUT_MINUTES, DELIVERY_FEE_FEN, PAY_TIMEOUT_MINUTES, REMARK_MAX_LEN,
)
from campus_eats.services.context import ServiceContext
from campus_eats.services.ids import new_token, next_no


# 空购物车的内容指纹（重试判定基准）
_EMPTY_FINGERPRINT = hashlib.sha256(repr(sorted([])).encode("utf-8")).hexdigest()


@dataclass
class CartLineView:
    """购物车行视图：条目 + 失效原因（REQ-007 提交前拦截依据）。"""

    item: CartItem
    invalid_reason: str = ""      # 空 = 有效；否则为"已下架"/"已售罄"等

    @property
    def valid(self) -> bool:
        """条目是否仍可下单。"""
        return not self.invalid_reason


class OrderService:
    """购物车与订单全生命周期。"""

    def __init__(self, context: ServiceContext, audit: AuditService) -> None:
        """绑定上下文与审计；payment 与 on_order_ready 由装配层注入。"""
        self._ctx = context
        self._audit = audit
        self._payments = None
        self.on_order_ready = None          # Callable[[Order], None]，出餐后建配送任务

    def set_payment_service(self, payment_service) -> None:
        """装配期注入支付服务（退款入账走支付服务，组件图 ORD -> PAY）。"""
        self._payments = payment_service

    # ==================== 购物车（REQ-007） ====================

    def add_to_cart(self, customer: Account, shop_id: int, dish_id: int, qty: int = 1):
        """加购：购物车按店铺隔离，跨店加购先清空或取消（REQ-007）。

        跨店时抛 CartShopMismatchError，由界面层提示用户选择「清空」或「取消」。
        """
        if customer.role is not Role.CUSTOMER:
            raise PermissionDeniedError("只有顾客可以使用购物车")
        if qty <= 0:
            raise ValidationError("数量必须为正整数")
        with self._ctx.lock:
            dish = self._ctx.repos.dishes.get(dish_id)
            if dish is None or dish.shop_id != shop_id or dish.status.value != "上架":
                raise ValidationError("菜品不存在或已下架")
            cart = self._ctx.repos.carts.get_or_create(customer.account_id)
            cart.add_item(shop_id, CartItem(
                dish_id=dish_id, dish_name=dish.name, icon=dish.icon,
                added_price_fen=dish.price_fen, qty=qty))
            self._ctx.repos.carts.save(cart)
            return cart

    def force_add_to_cart(self, customer: Account, shop_id: int, dish_id: int,
                          qty: int = 1):
        """清空旧车后加购（界面「清空并加入」按钮用）。"""
        with self._ctx.lock:
            cart = self._ctx.repos.carts.get_or_create(customer.account_id)
            if cart.shop_id is not None and cart.shop_id != shop_id:
                cart.clear()
                self._ctx.repos.carts.save(cart)
        return self.add_to_cart(customer, shop_id, dish_id, qty)

    def change_cart_qty(self, customer: Account, item_id: int, qty: int):
        """修改条目数量；qty<=0 视为移除。"""
        with self._ctx.lock:
            cart = self._ctx.repos.carts.get_or_create(customer.account_id)
            if qty <= 0:
                return self.remove_cart_item(customer, item_id)
            for item in cart.items:
                if item.item_id == item_id:
                    item.qty = qty
            self._ctx.repos.carts.save(cart)
            return cart

    def remove_cart_item(self, customer: Account, item_id: int):
        """移除购物车条目。"""
        with self._ctx.lock:
            cart = self._ctx.repos.carts.get_or_create(customer.account_id)
            cart.items = [it for it in cart.items if it.item_id != item_id]
            if not cart.items:
                cart.clear()
            self._ctx.repos.carts.save(cart)
            return cart

    def clear_cart(self, customer: Account):
        """清空购物车。"""
        with self._ctx.lock:
            cart = self._ctx.repos.carts.get_or_create(customer.account_id)
            cart.clear()
            self._ctx.repos.carts.save(cart)
            return cart

    def view_cart(self, customer: Account) -> tuple[object, list[CartLineView]]:
        """查看购物车并逐条校验有效性（REQ-007：下架/售罄/店铺休息标记失效）。

        返回（购物车, 行视图列表）；失效条目保留并带原因，供界面标记。
        """
        with self._ctx.lock:
            cart = self._ctx.repos.carts.get_or_create(customer.account_id)
            shop = (self._ctx.repos.shops.get(cart.shop_id)
                    if cart.shop_id is not None else None)
            lines = []
            for item in cart.items:
                reason = ""
                dish = self._ctx.repos.dishes.get(item.dish_id)
                if dish is None or dish.status.value != "上架":
                    reason = "已下架"
                elif shop is None or shop.status.value != "营业中":
                    reason = "店铺暂停营业"
                else:
                    available = self._stock_available(item.dish_id)
                    if available < item.qty:
                        reason = "已售罄" if available == 0 else f"仅剩 {available} 份"
                lines.append(CartLineView(item=item, invalid_reason=reason))
            return cart, lines

    # ==================== 下单（REQ-008/009/024） ====================

    def submit_order(self, customer: Account, token: str, building_code: str,
                     phone: str, remark: str = "") -> Order:
        """提交订单（时序图「下单与支付」的落地）。

        规约：
        - REQ-024 幂等：同一令牌重复提交返回首次生成的订单，不产生新单；
          令牌已用于不同购物车内容时视为重放，抛 ConflictError 要求换新令牌；
          令牌已用且原订单已取消时不复活订单（仍返回原单）。
        - REQ-008：地址只能取预设楼栋编号且必须在配送范围内；电话格式校验；
          备注超长截断。
        - REQ-005/023：预占库存，任一菜品不足则整单失败并全部回滚。
        - REQ-009：明细按提交时刻价格固化快照。
        """
        if customer.role is not Role.CUSTOMER:
            raise PermissionDeniedError("只有顾客可以提交订单")
        if not token:
            raise ValidationError("缺少提交令牌，请刷新确认订单页")
        with self._ctx.lock:
            existing = self._ctx.repos.orders.find_by_token(token)
            if existing is not None:
                if existing.customer_id != customer.account_id:
                    raise ConflictError("提交令牌无效")
                fingerprint = self._cart_fingerprint(customer.account_id)
                # 购物车为空视为对上一单的重试（首单提交即清空购物车）；
                # 非空且内容与首单不同才是令牌重放，要求换新令牌（REQ-024）。
                if fingerprint != _EMPTY_FINGERPRINT and \
                        fingerprint != self._fingerprint_of(existing):
                    raise ConflictError("提交内容已变化，请重新获取令牌后提交")
                return existing            # 返回首次结果，不产生新单

            cart, lines = self.view_cart(customer)
            invalid = [ln for ln in lines if not ln.valid]
            if not cart.items:
                raise ValidationError("购物车为空")
            if invalid:
                names = "、".join(ln.item.dish_name for ln in invalid)
                raise ValidationError(f"以下菜品已失效，请移除后重试：{names}")

            shop = self._ctx.repos.shops.get(cart.shop_id)
            if shop is None or shop.status.value != "营业中":
                raise ValidationError("店铺不在营业中，无法提交订单")

            building = self._ctx.repos.buildings.find(building_code)
            if building is None or not building.in_range:
                raise ValidationError("收货楼栋不在平台配送范围内（REQ-008）")

            order = Order(order_no=next_no(self._ctx.clock, "D"),
                          customer_id=customer.account_id, shop_id=shop.shop_id,
                          submit_token=token, building_code=building.code,
                          address_text=f"{building.name} {building.code} 幢",
                          phone=phone.strip(),
                          remark=remark.strip()[:REMARK_MAX_LEN],
                          created_at=self._ctx.clock.now())
            order.assert_phone_valid()
            for line in lines:
                order.items.append(OrderItem(
                    dish_id=line.item.dish_id, dish_name=line.item.dish_name,
                    unit_price_fen=self._ctx.repos.dishes.get(
                        line.item.dish_id).price_fen,
                    qty=line.item.qty))
            order.settle_amounts(DELIVERY_FEE_FEN)
            order.pay_deadline = (self._ctx.clock.now().replace(microsecond=0)
                                  + timedelta(minutes=PAY_TIMEOUT_MINUTES))

            self._reserve_all_or_rollback(order)
            self._ctx.repos.orders.add(order)
            self._ctx.repos.carts.save(_cleared(cart))
            self._audit.record(customer, "ORDER", order.order_id,
                               f"订单 {order.order_no}", "提交订单",
                               after=f"应付{fen_to_yuan(order.pay_amount_fen)}元")
            return order

    def preview_submit(self, customer: Account, building_code: str) -> dict:
        """确认订单页预览：金额、配送费、地址合法性，不真正下单。"""
        cart, lines = self.view_cart(customer)
        building = self._ctx.repos.buildings.find(building_code)
        goods = sum(self._ctx.repos.dishes.get(ln.item.dish_id).price_fen * ln.item.qty
                    for ln in lines if ln.valid)
        return {"cart": cart, "lines": lines, "goods_fen": goods,
                "delivery_fen": DELIVERY_FEE_FEN,
                "total_fen": goods + DELIVERY_FEE_FEN,
                "building": building,
                "in_range": building is not None and building.in_range}

    def fresh_token(self) -> str:
        """生成新的提交令牌（REQ-024：内容变化后须重新生成）。"""
        return new_token()

    # ==================== 商家操作（REQ-011） ====================

    def accept(self, merchant: Account, order_id: int) -> Order:
        """商家接单：待接单 -> 制作中；重复接单返回首次结果（REQ-011）。"""
        with self._ctx.lock:
            order = self._require_shop_order(merchant, order_id)
            if order.status is OrderStatus.COOKING:
                return order                       # 幂等：重复接单
            order.transit_to(OrderStatus.COOKING, merchant.name)
            order.accept_deadline = None
            self._ctx.repos.orders.update(order)
            self._audit.record(merchant, "ORDER", order_id, f"订单 {order.order_no}",
                               "接单", before=OrderStatus.PENDING_ACCEPT.label,
                               after=OrderStatus.COOKING.label)
            self._audit.notify(order.customer_id, "商家已接单",
                               f"订单 {order.order_no} 制作中")
            return order

    def reject(self, merchant: Account, order_id: int, reason: str) -> Order:
        """商家拒单：必须填写原因，全额退款（REQ-011/014）。

        退款金额与订单回写由售后服务的退款入口完成，这里只负责校验归属
        与转发，保证退款逻辑集中在售后模块。
        """
        if not reason.strip():
            raise ValidationError("拒单必须填写原因")
        self._require_shop_order(merchant, order_id)
        return self._refund_cancel(merchant, order_id,
                                   f"商家拒单：{reason.strip()}", notify_shop=False)

    def ready(self, merchant: Account, order_id: int) -> Order:
        """商家出餐：制作中 -> 待配送，并触发配送任务创建（ORD -> DISP）。"""
        with self._ctx.lock:
            order = self._require_shop_order(merchant, order_id)
            order.transit_to(OrderStatus.PENDING_DELIVERY, merchant.name)
            self._ctx.repos.orders.update(order)
            self._audit.record(merchant, "ORDER", order_id, f"订单 {order.order_no}",
                               "出餐", before=OrderStatus.COOKING.label,
                               after=OrderStatus.PENDING_DELIVERY.label)
            if self.on_order_ready is not None:
                self.on_order_ready(order)
            return order

    # ==================== 状态回写窄接口（其他服务专用） ====================
    # 约定：变异方法一律按 order_id 现取最新订单再迁移，不信任调用方持有的
    # 实体快照，防止陈旧实体覆盖新状态（并发正确性的一部分）。

    def mark_paid(self, order_id: int, operator_name: str) -> None:
        """支付服务专用：待支付 -> 待接单，并设置接单期限（REQ-015）。"""
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            order.transit_to(OrderStatus.PENDING_ACCEPT, operator_name)
            order.accept_deadline = (self._ctx.clock.now().replace(microsecond=0)
                                     + timedelta(minutes=ACCEPT_TIMEOUT_MINUTES))
            self._ctx.repos.orders.update(order)

    def mark_delivering(self, order_id: int, operator_name: str) -> None:
        """配送服务专用：待配送/配送异常 -> 配送中。"""
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            order.transit_to(OrderStatus.DELIVERING, operator_name)
            self._ctx.repos.orders.update(order)

    def mark_delivered(self, order_id: int, operator_name: str) -> None:
        """配送服务专用：配送中 -> 已送达，记录送达时刻（REQ-013）。"""
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            order.transit_to(OrderStatus.DELIVERED, operator_name)
            order.delivered_at = self._ctx.clock.now().replace(microsecond=0)
            self._ctx.repos.orders.update(order)

    def mark_exception(self, order_id: int, reason: str) -> None:
        """配送服务专用：待配送/配送中 -> 配送异常（挂起，REQ-016）。"""
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            before = order.status.label
            order.transit_to(OrderStatus.DELIVERY_EXCEPTION, "配送调度")
            self._ctx.repos.orders.update(order)
            self._audit.record(None, "ORDER", order_id, f"订单 {order.order_no}",
                               "配送异常", before=before, reason=reason)

    def complete(self, order_id: int, operator_name: str) -> None:
        """确认收货 / 自动完成：已送达 -> 已完成（REQ-013）。"""
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            order.transit_to(OrderStatus.COMPLETED, operator_name)
            order.completed_at = self._ctx.clock.now().replace(microsecond=0)
            self._ctx.repos.orders.update(order)
            self._audit.record(None, "ORDER", order_id, f"订单 {order.order_no}",
                               "完成订单" if operator_name == "系统" else "确认收货",
                               before=OrderStatus.DELIVERED.label,
                               after=OrderStatus.COMPLETED.label)

    def cancel(self, order_id: int, reason: str, refund_fen: int,
               operator: Account | None, notify_shop: bool = True,
               release_stock: bool = False) -> Order:
        """取消订单并退款（顾客取消 / 超时 / 配送异常处置 / 强制退款的落点）。

        release_stock 仅未支付订单为 True（预占释放）；已支付订单库存已
        confirm，取消不回补（REQ-005：以支付结果为准，不得重复回补）。
        """
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            before = order.status.label
            order.transit_to(OrderStatus.CANCELLED,
                             operator.name if operator else "系统")
            order.cancel_reason = reason
            order.cancelled_at = self._ctx.clock.now().replace(microsecond=0)
            if release_stock:
                self._release_order_stock(order)
            if refund_fen > 0:
                self._refund_to_customer(order, refund_fen, reason)
            self._ctx.repos.orders.update(order)
            self._audit.record(operator, "ORDER", order_id,
                               f"订单 {order.order_no}", "取消订单",
                               before=before, after=OrderStatus.CANCELLED.label,
                               reason=reason)
            self._audit.notify(order.customer_id, "订单已取消",
                               f"订单 {order.order_no}：{reason}")
            if notify_shop:
                self._audit.notify(self._shop_merchant_id(order.shop_id),
                                   "订单已取消", f"订单 {order.order_no}：{reason}")
            return order

    def refund_partial(self, order_id: int, amount_fen: int, reason: str,
                       operator: Account) -> None:
        """部分退款（REQ-014）：制作中自环，不改状态；配送费不退。

        退款累计不得超过实付金额（REQ-022），流水落库与入账由支付服务完成。
        """
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            if order.status is not OrderStatus.COOKING:
                raise ValidationError("部分退款仅限制作中的订单（出餐后不可取消）")
            payable = order.pay_amount_fen - order.delivery_fee_fen - order.refunded_fen
            if amount_fen <= 0 or amount_fen > payable:
                raise ValidationError("部分退款金额必须为正且不超过可退商品金额")
            self._payments.record_refund(order, amount_fen, reason, operator)
            self._audit.record(operator, "ORDER", order_id,
                               f"订单 {order.order_no}", "部分退款",
                               after=f"退{fen_to_yuan(amount_fen)}元", reason=reason)

    # ==================== 超时任务（REQ-010/015，调度器调用） ====================

    def cancel_unpaid_timeouts(self) -> list[Order]:
        """取消超时未支付订单并释放预占（REQ-010）。"""
        now_text = self._ctx.clock.now().isoformat()
        cancelled = []
        with self._ctx.lock:
            for order in self._ctx.repos.orders.list_unpaid_before(now_text):
                cancelled.append(self.cancel(
                    order.order_id, "30 分钟未支付，自动取消", 0, None,
                    notify_shop=False, release_stock=True))
        return cancelled

    def cancel_unaccepted_timeouts(self) -> list[Order]:
        """取消超时未接单订单并全额退款（REQ-015），计入商家超时统计。"""
        now_text = self._ctx.clock.now().isoformat()
        cancelled = []
        with self._ctx.lock:
            for order in self._ctx.repos.orders.list_unaccepted_before(now_text):
                cancelled.append(self._refund_cancel(None, order.order_id,
                                                     "商家 10 分钟未接单，自动取消"))
        return cancelled

    def auto_complete_timeouts(self) -> list[Order]:
        """已送达超时自动完成（REQ-013）。"""
        cutoff = (self._ctx.clock.now() - timedelta(hours=2)).isoformat()
        done = []
        with self._ctx.lock:
            for order in self._ctx.repos.orders.list_delivered_before(cutoff):
                self.complete(order.order_id, "系统")
                done.append(self._ctx.repos.orders.get(order.order_id))
        return done

    def confirm_receipt(self, customer: Account, order_id: int) -> Order:
        """顾客确认收货：已送达 -> 已完成（REQ-013）。"""
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            if order is None or order.customer_id != customer.account_id:
                raise ValidationError("订单不存在")
            if order.status is OrderStatus.COMPLETED:
                return order
            order.transit_to(OrderStatus.COMPLETED, customer.name)
            order.completed_at = self._ctx.clock.now().replace(microsecond=0)
            self._ctx.repos.orders.update(order)
            self._audit.record(customer, "ORDER", order_id, f"订单 {order.order_no}",
                               "确认收货", before=OrderStatus.DELIVERED.label,
                               after=OrderStatus.COMPLETED.label)
            return order

    # ==================== 查询 ====================

    def get_order(self, operator: Account, order_id: int) -> Order:
        """按 id 取订单：顾客只能看自己的，商家只能看本店的（REQ-001）。"""
        order = self._ctx.repos.orders.get(order_id)
        if order is None:
            raise ValidationError("订单不存在")
        if operator.role is Role.CUSTOMER and order.customer_id != operator.account_id:
            raise PermissionDeniedError("无权查看他人订单")
        if operator.role is Role.MERCHANT:
            shop = self._ctx.repos.shops.get_by_merchant(operator.account_id)
            if shop is None or order.shop_id != shop.shop_id:
                raise PermissionDeniedError("无权查看非本店订单")
        return order

    def find_by_no(self, order_no: str) -> Order | None:
        """按订单号查（界面查询用，不鉴权由调用方负责）。"""
        return self._ctx.repos.orders.find_by_no(order_no)

    def list_customer_orders(self, customer_id: int) -> list[Order]:
        """顾客订单列表。"""
        return self._ctx.repos.orders.list_by_customer(customer_id)

    def list_shop_orders(self, merchant: Account) -> list[Order]:
        """商家订单列表。"""
        shop = self._ctx.repos.shops.get_by_merchant(merchant.account_id)
        if shop is None:
            return []
        return self._ctx.repos.orders.list_by_shop(shop.shop_id)

    def list_by_status(self, status: OrderStatus) -> list[Order]:
        """管理端按状态查订单。"""
        return self._ctx.repos.orders.list_by_status(status)

    # ==================== 内部工具 ====================

    def _refund_cancel(self, operator, order_id: int, reason: str,
                       notify_shop: bool = True) -> Order:
        """已支付订单的取消退款：全额退回余额并走取消流程。"""
        payment = self._ctx.repos.payments.find_by_order(order_id)
        refund_fen = payment.amount_fen if payment else 0
        return self.cancel(order_id, reason, refund_fen, operator,
                           notify_shop=notify_shop, release_stock=False)

    def _reserve_all_or_rollback(self, order: Order) -> None:
        """按订单明细预占库存；任一失败则整体回滚（REQ-005/023）。"""
        today = self._ctx.clock.now().date()
        reserved = []
        for item in order.items:
            dish = self._ctx.repos.dishes.get(item.dish_id)
            stock = self._ctx.repos.stocks.get_or_create(item.dish_id, today,
                                                         dish.daily_qty)
            if not stock.reserve(item.qty):
                for _, done_qty, done_stock in reversed(reserved):
                    done_stock.release(done_qty)
                    self._ctx.repos.stocks.update(done_stock)
                raise OutOfStockError(f"「{dish.name}」当日库存不足，提交失败")
            self._ctx.repos.stocks.update(stock)
            reserved.append((item.dish_id, item.qty, stock))

    def _release_order_stock(self, order: Order) -> None:
        """释放订单全部预占（超时未支付取消用）。"""
        today = self._ctx.clock.now().date()
        for item in order.items:
            dish = self._ctx.repos.dishes.get(item.dish_id)
            stock = self._ctx.repos.stocks.get_or_create(item.dish_id, today,
                                                         dish.daily_qty)
            if stock.reserved_qty >= item.qty:
                stock.release(item.qty)
                self._ctx.repos.stocks.update(stock)

    def _refund_to_customer(self, order: Order, amount_fen: int, reason: str) -> None:
        """退款入账顾客余额并落退款流水（经支付服务，组件图 ORD -> PAY）。"""
        self._payments.refund_to_balance(order, amount_fen, reason, requested_by="系统")

    def _require_shop_order(self, merchant: Account, order_id: int) -> Order:
        """取本店订单，越权拒绝（REQ-001）。"""
        if merchant.role is not Role.MERCHANT:
            raise PermissionDeniedError("只有商家账号可执行该操作")
        order = self._ctx.repos.orders.get(order_id)
        shop = self._ctx.repos.shops.get_by_merchant(merchant.account_id)
        if order is None or shop is None or order.shop_id != shop.shop_id:
            raise ValidationError("订单不存在或不属于本店")
        return order

    def _shop_merchant_id(self, shop_id: int) -> int | None:
        """查店铺对应商家账号 id。"""
        shop = self._ctx.repos.shops.get(shop_id)
        return shop.merchant_id if shop else None

    def _stock_available(self, dish_id: int) -> int:
        """当日可用份数。"""
        return CatalogService(self._ctx, self._audit).available_of(dish_id)

    def _cart_fingerprint(self, customer_id: int) -> str:
        """当前购物车内容指纹（令牌防重放，REQ-024）。"""
        cart = self._ctx.repos.carts.get_or_create(customer_id)
        return self._fingerprint_str([(it.dish_id, it.qty) for it in cart.items])

    def _fingerprint_of(self, order: Order) -> str:
        """下单时刻的内容指纹（按订单明细还原）。"""
        return self._fingerprint_str([(it.dish_id, it.qty) for it in order.items])

    @staticmethod
    def _fingerprint_str(pairs: list[tuple]) -> str:
        """内容指纹：排序后取哈希。"""
        raw = repr(sorted(pairs)).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def _cleared(cart):
    """清空购物车内容（下单成功后调用）。"""
    cart.clear()
    return cart
