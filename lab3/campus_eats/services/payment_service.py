"""支付与退款服务（对应组件图 PAY，REQ-010/014/022/025）。

金额一致性（REQ-022）：扣款金额必须等于订单快照金额；同一订单重复支付
返回首次结果（REQ-010/024）；退款累计不超过实付；余额不为负。
订单状态回写经由注入的订单服务窄接口（组件图 PAY -> ORD）完成。
"""

from datetime import date

from campus_eats.models.account import Account
from campus_eats.models.cart_order import Order
from campus_eats.models.enums import OrderStatus, PayStatus, RefundStatus, RefundType
from campus_eats.models.errors import InsufficientBalanceError, ValidationError
from campus_eats.models.money import fen_to_yuan
from campus_eats.models.payment_refund import Payment, Refund
from campus_eats.services.audit_service import AuditService
from campus_eats.services.context import ServiceContext
from campus_eats.services.ids import next_no

# REQ-025：骑手收入按单固定金额（口径待甲方确认，先按 4 元/单实现）
RIDER_INCOME_PER_ORDER_FEN = 400


class PaymentService:
    """余额支付、退款入账、营业额与收入统计。"""

    def __init__(self, context: ServiceContext, audit: AuditService) -> None:
        """绑定上下文与审计；order_service 由装配层注入以回写状态。"""
        self._ctx = context
        self._audit = audit
        self._orders = None

    def set_order_service(self, order_service) -> None:
        """装配期注入订单服务（回写状态的唯一通道）。"""
        self._orders = order_service

    # ---------- 支付 ----------

    def pay(self, customer: Account, order_id: int) -> Payment:
        """余额支付（时序图「下单与支付」）。

        规约（REQ-010）：
        - 幂等：已有成功流水时直接返回首次结果，不重复扣款；
        - 订单必须处于待支付；支付金额必须等于订单快照金额；
        - 余额不足抛 InsufficientBalanceError，订单保持待支付；
        - 成功后：预占转已售（confirm）、销量累计、订单转待接单。
        """
        with self._ctx.lock:
            order = self._ctx.repos.orders.get(order_id)
            if order is None or order.customer_id != customer.account_id:
                raise ValidationError("订单不存在")
            first = self._ctx.repos.payments.find_by_order(order_id)
            if first is not None:
                return first                    # 重复支付返回首次结果
            if order.status is not OrderStatus.PENDING_PAY:
                raise ValidationError(f"订单当前为「{order.status.label}」，不能支付")
            customer_acct = self._ctx.repos.accounts.get(order.customer_id)
            if customer_acct.balance_fen < order.pay_amount_fen:
                raise InsufficientBalanceError(
                    f"余额不足：应付 {fen_to_yuan(order.pay_amount_fen)} 元，"
                    f"余额 {fen_to_yuan(customer_acct.balance_fen)} 元")

            customer_acct.deduct(order.pay_amount_fen)
            self._ctx.repos.accounts.update(customer_acct)

            now = self._ctx.clock.now().replace(microsecond=0)
            payment = Payment(pay_no=next_no(self._ctx.clock, "P"),
                              order_id=order.order_id, order_no=order.order_no,
                              amount_fen=order.pay_amount_fen,
                              status=PayStatus.SUCCESS, paid_at=now)
            self._ctx.repos.payments.add(payment)

            self._confirm_stock(order)          # 预占转已售（REQ-005）
            self._bump_sales(order)             # 销量累计（REQ-006 排序依据）
            self._orders.mark_paid(order.order_id, "支付服务")
            self._audit.record(customer, "PAYMENT", payment.payment_id,
                               f"支付 {payment.pay_no}", "余额支付",
                               after=f"扣款{fen_to_yuan(payment.amount_fen)}元")
            self._audit.notify(self._shop_merchant_id(order.shop_id), "新订单待接单",
                               f"订单 {order.order_no}，10 分钟内未接单将自动取消")
            return payment

    # ---------- 退款 ----------

    def refund_to_balance(self, order: Order, amount_fen: int, reason: str,
                          requested_by: str, refund_type: RefundType = RefundType.FULL,
                          pending: bool = False) -> Refund:
        """退款入账（即时到账）或登记待处理申请（pending=True，REQ-014/026）。

        退款累计不得超过实付金额（REQ-022）；同单累计退款受 refunded_fen 约束。
        """
        with self._ctx.lock:
            if amount_fen <= 0 or order.refunded_fen + amount_fen > order.pay_amount_fen:
                raise ValidationError("退款金额不合法或累计超过实付金额（REQ-022）")
            now = self._ctx.clock.now().replace(microsecond=0)
            refund = Refund(refund_no=next_no(self._ctx.clock, "R"),
                            order_id=order.order_id, order_no=order.order_no,
                            amount_fen=amount_fen, type=refund_type,
                            status=RefundStatus.PENDING if pending else RefundStatus.DONE,
                            reason=reason, requested_by=requested_by, created_at=now)
            if not pending:
                customer = self._ctx.repos.accounts.get(order.customer_id)
                customer.recharge(amount_fen)
                self._ctx.repos.accounts.update(customer)
                refund.settled_at = now
                order.refunded_fen += amount_fen
                self._ctx.repos.orders.update(order)
            self._ctx.repos.refunds.add(refund)
            return refund

    def record_refund(self, order: Order, amount_fen: int, reason: str,
                      operator: Account) -> Refund:
        """商家部分退款：立即入账顾客余额（REQ-014）。"""
        return self.refund_to_balance(order, amount_fen, reason,
                                      requested_by=f"商家 {operator.name}",
                                      refund_type=RefundType.PARTIAL)

    def settle_refund(self, refund: Refund, agree: bool, operator: Account | None,
                      reason: str = "") -> Refund:
        """处理待处理退款：同意则入账并累计已退；拒绝须说明原因（REQ-014/026）。"""
        with self._ctx.lock:
            if refund.status is not RefundStatus.PENDING:
                raise ValidationError("该退款申请不在待处理状态")
            order = self._ctx.repos.orders.get(refund.order_id)
            if agree:
                if order.refunded_fen + refund.amount_fen > order.pay_amount_fen:
                    raise ValidationError("累计退款将超过实付金额（REQ-022）")
                refund.status = RefundStatus.DONE
                refund.settled_at = self._ctx.clock.now().replace(microsecond=0)
                customer = self._ctx.repos.accounts.get(order.customer_id)
                customer.recharge(refund.amount_fen)
                self._ctx.repos.accounts.update(customer)
                order.refunded_fen += refund.amount_fen
                self._ctx.repos.orders.update(order)
            else:
                refund.status = RefundStatus.REJECTED
                refund.reason = f"{refund.reason}；拒绝原因：{reason}"
            self._ctx.repos.refunds.update(refund)
            self._audit.record(operator, "REFUND", refund.refund_id,
                               f"退款 {refund.refund_no}",
                               "同意退款" if agree else "拒绝退款",
                               reason=reason or refund.reason)
            return refund

    def list_refunds(self, order_id: int) -> list[Refund]:
        """订单退款记录（对账用，REQ-022）。"""
        return self._ctx.repos.refunds.list_by_order(order_id)

    def list_pending_refunds(self, merchant: Account) -> list[Refund]:
        """商家看待处理退款申请（含超时即将自动同意的）。"""
        pending = []
        for order in self._ctx.repos.orders.list_by_shop(self._shop_id(merchant)):
            for refund in self._ctx.repos.refunds.list_by_order(order.order_id):
                if refund.status is RefundStatus.PENDING:
                    pending.append(refund)
        return pending

    def list_all_pending(self) -> list[Refund]:
        """全部待处理退款（调度器超时自动同意扫描用，REQ-026）。"""
        return self._ctx.repos.refunds.list_pending_before(
            self._ctx.clock.now().isoformat())

    # ---------- REQ-025 统计（口径：按自然日汇总；退款从营业额中扣减） ----------

    def merchant_daily_stats(self, merchant: Account) -> dict:
        """商家当日订单数与营业额（REQ-025，实收口径）。"""
        shop_id = self._shop_id(merchant)
        today = self._ctx.clock.now().date()
        order_count = 0
        revenue_fen = 0
        for order in self._ctx.repos.orders.list_by_shop(shop_id):
            if self._date_of(order.created_at) != today:
                continue
            if order.status is OrderStatus.CANCELLED:
                continue
            order_count += 1
            revenue_fen += order.pay_amount_fen - order.refunded_fen
        return {"order_count": order_count, "revenue_fen": revenue_fen}

    def rider_daily_stats(self, rider: Account) -> dict:
        """骑手当日完成单量与收入（REQ-025，按单固定 RIDER_INCOME_PER_ORDER_FEN）。"""
        today = self._ctx.clock.now().date()
        done = [t for t in self._ctx.repos.tasks.list_by_rider(rider.account_id)
                if t.status.value == "已完成"
                and self._date_of(t.completed_at) == today]
        return {"done_count": len(done),
                "income_fen": len(done) * RIDER_INCOME_PER_ORDER_FEN}

    # ---------- 内部 ----------

    def _confirm_stock(self, order: Order) -> None:
        """预占转已售：支付成功路径才会走到这里（REQ-005 不得重复回补）。"""
        today = self._ctx.clock.now().date()
        for item in order.items:
            dish = self._ctx.repos.dishes.get(item.dish_id)
            stock = self._ctx.repos.stocks.get_or_create(item.dish_id, today,
                                                         dish.daily_qty)
            if stock.reserved_qty >= item.qty:
                stock.confirm(item.qty)
                self._ctx.repos.stocks.update(stock)

    def _bump_sales(self, order: Order) -> None:
        """菜品销量累计。"""
        for item in order.items:
            dish = self._ctx.repos.dishes.get(item.dish_id)
            dish.sales_count += item.qty
            self._ctx.repos.dishes.update(dish)

    def _shop_merchant_id(self, shop_id: int) -> int | None:
        """店铺对应商家账号。"""
        shop = self._ctx.repos.shops.get(shop_id)
        return shop.merchant_id if shop else None

    def _shop_id(self, merchant: Account) -> int | None:
        """商家店铺 id。"""
        shop = self._ctx.repos.shops.get_by_merchant(merchant.account_id)
        return shop.shop_id if shop else None

    @staticmethod
    def _date_of(value) -> date:
        """datetime 归属自然日，空值给 date.min 保证比较安全。"""
        return value.date() if value else date.min
