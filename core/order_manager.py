import time
import logging
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"

class CycleStage(Enum):
    IDLE = "idle"
    MARKET_ORDER = "market_order"
    WAITING_MARKET = "waiting_market"
    DCA_ORDERS = "dca_orders"
    WAITING_DCA = "waiting_dca"
    TP_ORDERS = "tp_orders"
    WAITING_TP_CANCEL = "waiting_tp_cancel"
    MONITORING = "monitoring"
    CYCLE_WAIT = "cycle_wait"

@dataclass
class Order:
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    type: str  # 'market', 'limit'
    amount: Decimal
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: Decimal = Decimal('0')
    avg_price: Decimal = Decimal('0')
    created_at: float = 0.0

@dataclass
class Position:
    symbol: str
    size: Decimal = Decimal('0')
    avg_price: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    entry_orders: List[Order] = None
    tp_orders: List[Order] = None

    def __post_init__(self):
        if self.entry_orders is None:
            self.entry_orders = []
        if self.tp_orders is None:
            self.tp_orders = []

class OrderManager:
    # Константы для ожидания между этапами
    WAIT_AFTER_MARKET = 5
    WAIT_AFTER_DCA = 10
    WAIT_AFTER_TP_CANCEL = 3
    WAIT_BETWEEN_CYCLES = 15
    
    # Комиссия биржи с запасом
    COMMISSION_RATE = Decimal('0.0015')  # 0.15% (0.11% + запас)

    def __init__(self, exchange, config: dict):
        self.exchange = exchange
        self.config = config
        self.position = Position(symbol=config.get('symbol', 'BTCUSDT'))
        self.active_orders: Dict[str, Order] = {}
        self.current_stage = CycleStage.IDLE
        self._running = False
        self._thread = None
        self.hard_stop_requested = False
        self.soft_stop_enabled = False
        
        # Коллбэки для уведомлений
        self.on_stage_change: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
        self.on_orders_update: Optional[Callable] = None

    def start(self):
        if self._running:
            logger.warning("OrderManager уже запущен")
            return
        
        self._running = True
        self.hard_stop_requested = False
        self.soft_stop_enabled = False
        self._thread = threading.Thread(target=self._trading_cycle, daemon=True)
        self._thread.start()
        logger.info("OrderManager запущен")

    def stop(self):
        if not self._running:
            return
        
        self._running = False
        self.hard_stop_requested = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("OrderManager остановлен")

    def enable_soft_stop(self):
        self.soft_stop_enabled = True
        logger.info("Мягкий стоп активирован")

    def disable_soft_stop(self):
        self.soft_stop_enabled = False
        logger.info("Мягкий стоп деактивирован")

    def _trading_cycle(self):
        try:
            while self._running and not self.hard_stop_requested:
                if self.soft_stop_enabled:
                    logger.info("Мягкий стоп - завершение после цикла")
                    break

                self._execute_strategy_cycle()

                if self._running and not self.hard_stop_requested:
                    self._update_stage(CycleStage.CYCLE_WAIT)
                    self._wait_with_stop_check(self.WAIT_BETWEEN_CYCLES)

        except Exception as e:
            logger.critical(f"Critical error in trading cycle: {e}")
        finally:
            self._running = False
            self._update_stage(CycleStage.IDLE)

    def _update_stage(self, stage: CycleStage):
        self.current_stage = stage
        if self.on_stage_change:
            self.on_stage_change(stage.value)
        logger.debug(f"Этап изменен: {stage.value}")

    def _calculate_entry_shares(self, total_deposit: Decimal, dca_count: int, martingale_coef: Decimal) -> List[Decimal]:
        """
        Расчет долей для входа с учетом комиссии
        """
        try:
            # Учитываем комиссию в общем депозите
            available_deposit = total_deposit * (Decimal('1') - self.COMMISSION_RATE)
            
            # Расчет геометрической прогрессии для мартингейла
            if martingale_coef == Decimal('1'):
                # Равные доли
                share_size = available_deposit / Decimal(str(dca_count + 1))
                shares = [share_size] * (dca_count + 1)
            else:
                # Геометрическая прогрессия
                sum_progression = (Decimal('1') - martingale_coef ** (dca_count + 1)) / (Decimal('1') - martingale_coef)
                first_share = available_deposit / sum_progression
                shares = [first_share * (martingale_coef ** i) for i in range(dca_count + 1)]
            
            logger.info(f"Рассчитаны доли: {[float(s) for s in shares]}")
            return shares
        except Exception as e:
            logger.error(f"Ошибка расчета долей: {e}")
            return []

    def _execute_strategy_cycle(self):
        if not self._create_market_order():
            return

        self._update_stage(CycleStage.WAITING_MARKET)
        if not self._wait_with_stop_check(self.WAIT_AFTER_MARKET):
            return

        self._create_dca_orders()

        self._update_stage(CycleStage.WAITING_DCA)
        if not self._wait_with_stop_check(self.WAIT_AFTER_DCA):
            return

        self._cancel_tp_orders()

        self._update_stage(CycleStage.WAITING_TP_CANCEL)
        if not self._wait_with_stop_check(self.WAIT_AFTER_TP_CANCEL):
            return

        self._create_tp_orders()

        self._update_stage(CycleStage.MONITORING)

        monitoring_duration = 30
        for _ in range(monitoring_duration):
            if self.hard_stop_requested or not self._running:
                break
            self._monitor_orders_during_cycle()
            time.sleep(1)

    def _create_market_order(self) -> bool:
        try:
            self._update_stage(CycleStage.MARKET_ORDER)

            balance = Decimal(str(self.exchange.get_balance('USDT')))
            deposit_percent = Decimal(str(self.config.get('deposit_percent', 99.99))) / Decimal('100')
            dca_count = int(self.config.get('dca_count', 3))
            martingale_coef = Decimal(str(self.config.get('martingale_coef', 1)))
            total_deposit = balance * deposit_percent

            logger.info(f"Параметры для входа: balance={balance}, deposit_percent={deposit_percent}, dca_count={dca_count}, martingale_coef={martingale_coef}")

            shares = self._calculate_entry_shares(total_deposit, dca_count, martingale_coef)
            if not shares or len(shares) < 1:
                logger.error("Ошибка создания ордера: массив shares пустой или недостаточной длины")
                return False
            
            order_size_usdt = shares[0]
            current_price = Decimal(str(self.exchange.get_current_price(self.position.symbol)))
            
            # Получаем информацию о лоте
            lot_info = self.exchange._get_symbol_lot_info(self.position.symbol)
            min_qty = Decimal(str(lot_info['minQty']))
            step_size = Decimal(str(lot_info['stepSize']))
            
            # Рассчитываем количество с учетом комиссии
            gross_quantity = order_size_usdt / current_price
            # Уменьшаем на комиссию
            net_quantity = gross_quantity * (Decimal('1') - self.COMMISSION_RATE)
            
            # Округляем до step_size
            quantity = (net_quantity // step_size) * step_size
            
            if quantity < min_qty:
                logger.error(f"Рассчитанное количество {quantity} меньше минимального {min_qty}")
                return False

            logger.info(f"Создание рыночного ордера: количество={quantity}, цена~{current_price}")

            order_data = self.exchange.create_order(
                symbol=self.position.symbol,
                side='buy',
                order_type='market',
                quantity=quantity
            )

            order = Order(
                id=order_data['id'],
                symbol=self.position.symbol,
                side='buy',
                type='market',
                amount=Decimal(str(order_data['amount'])),
                status=OrderStatus.FILLED if order_data['status'] == 'FILLED' else OrderStatus.PENDING,
                filled_amount=Decimal(str(order_data.get('filled_qty', order_data['amount']))),
                avg_price=Decimal(str(order_data.get('avg_price', order_data['price']))),
                created_at=time.time()
            )

            self.active_orders[order.id] = order
            self.position.entry_orders.append(order)
            self._update_position_from_order(order)
            self._notify_orders_update()

            logger.info(f"Рыночный ордер создан: {order.id}, размер: {order.amount} по цене {order.avg_price}")
            return True

        except Exception as e:
            logger.error(f"Ошибка создания ордера: {e}")
            return False

    def _create_dca_orders(self):
        try:
            self._update_stage(CycleStage.DCA_ORDERS)

            balance = Decimal(str(self.exchange.get_balance('USDT')))
            deposit_percent = Decimal(str(self.config.get('deposit_percent', 99.99))) / Decimal('100')
            dca_count = int(self.config.get('dca_count', 3))
            martingale_coef = Decimal(str(self.config.get('martingale_coef', 1)))
            dca_step_percent = Decimal(str(self.config.get('dca_step_percent', 2.8))) / Decimal('100')
            total_deposit = balance * deposit_percent

            shares = self._calculate_entry_shares(total_deposit, dca_count, martingale_coef)
            current_price = Decimal(str(self.exchange.get_current_price(self.position.symbol)))
            
            # Получаем информацию о лоте
            lot_info = self.exchange._get_symbol_lot_info(self.position.symbol)
            min_qty = Decimal(str(lot_info['minQty']))
            step_size = Decimal(str(lot_info['stepSize']))

            if len(shares) < 2:
                logger.error(f"Недостаточно долей для выставления DCA. len(shares)={len(shares)} (min 2 нужно).")
                return

            max_dca = min(dca_count, len(shares) - 1)
            for i in range(1, max_dca + 1):
                dca_price = current_price * (Decimal('1') - dca_step_percent * Decimal(str(i)))
                dca_amount_usdt = shares[i]
                
                # Рассчитываем количество с учетом комиссии
                gross_quantity = dca_amount_usdt / dca_price
                net_quantity = gross_quantity * (Decimal('1') - self.COMMISSION_RATE)
                dca_amount_coins = (net_quantity // step_size) * step_size

                if dca_amount_coins < min_qty:
                    logger.warning(f"DCA ордер {i} не создан: рассчитано количество монет {dca_amount_coins} < minQty {min_qty}")
                    continue

                try:
                    order_data = self.exchange.create_order(
                        symbol=self.position.symbol,
                        side='buy',
                        order_type='limit',
                        quantity=dca_amount_coins,
                        price=dca_price
                    )
                except Exception as e:
                    logger.error(f"Ошибка создания DCA ордера {i}: {e}")
                    continue

                order = Order(
                    id=order_data['id'],
                    symbol=self.position.symbol,
                    side='buy',
                    type='limit',
                    amount=Decimal(str(order_data['amount'])),
                    price=dca_price,
                    status=OrderStatus.PENDING if order_data['status'] == 'NEW' else OrderStatus.FILLED,
                    filled_amount=Decimal(str(order_data.get('filled_qty', 0))),
                    avg_price=Decimal(str(order_data.get('avg_price', dca_price))),
                    created_at=time.time()
                )

                self.active_orders[order.id] = order
                self.position.entry_orders.append(order)

            logger.info(f"Создано DCA ордеров: {max_dca}")
            self._notify_orders_update()

        except Exception as e:
            logger.error(f"Ошибка создания DCA ордеров: {e}")

    def _create_tp_orders(self):
        try:
            self._update_stage(CycleStage.TP_ORDERS)

            if self.position.size <= 0:
                logger.warning("Нет позиции для создания TP ордеров")
                return

            tp_levels = [
                {'percent': Decimal(str(self.config.get('tp1_percent', 1.9))), 'volume': Decimal(str(self.config.get('tp1_volume', 33)))},
                {'percent': Decimal(str(self.config.get('tp2_percent', 3.4))), 'volume': Decimal(str(self.config.get('tp2_volume', 33)))},
                {'percent': Decimal(str(self.config.get('tp3_percent', 4.9))), 'volume': Decimal(str(self.config.get('tp3_volume', 33)))}
            ]

            # Получаем информацию о лоте
            lot_info = self.exchange._get_symbol_lot_info(self.position.symbol)
            min_qty = Decimal(str(lot_info['minQty']))
            step_size = Decimal(str(lot_info['stepSize']))

            for i, tp_level in enumerate(tp_levels, 1):
                # Учитываем комиссию при расчете TP цены
                tp_price = self.position.avg_price * (Decimal('1') + tp_level['percent'] / Decimal('100') + self.COMMISSION_RATE)
                tp_amount = self.position.size * tp_level['volume'] / Decimal('100')
                tp_amount = (tp_amount // step_size) * step_size

                if tp_amount < min_qty:
                    logger.warning(f"TP ордер {i} не создан: рассчитано количество монет {tp_amount} < minQty {min_qty}")
                    continue

                try:
                    order_data = self.exchange.create_order(
                        symbol=self.position.symbol,
                        side='sell',
                        order_type='limit',
                        quantity=tp_amount,
                        price=tp_price
                    )
                except Exception as e:
                    logger.error(f"Ошибка создания TP ордера {i}: {e}")
                    continue

                order = Order(
                    id=order_data['id'],
                    symbol=self.position.symbol,
                    side='sell',
                    type='limit',
                    amount=Decimal(str(order_data['amount'])),
                    price=tp_price,
                    status=OrderStatus.PENDING if order_data['status'] == 'NEW' else OrderStatus.FILLED,
                    filled_amount=Decimal(str(order_data.get('filled_qty', 0))),
                    avg_price=Decimal(str(order_data.get('avg_price', tp_price))),
                    created_at=time.time()
                )

                self.active_orders[order.id] = order
                self.position.tp_orders.append(order)

            logger.info(f"Создано TP ордеров: {len(self.position.tp_orders)}")
            self._notify_orders_update()

        except Exception as e:
            logger.error(f"Ошибка создания TP ордеров: {e}")

    def _cancel_tp_orders(self):
        try:
            for order in self.position.tp_orders:
                if order.status == OrderStatus.PENDING:
                    try:
                        self.exchange.cancel_order(order.id, order.symbol)
                        order.status = OrderStatus.CANCELLED
                        logger.info(f"TP ордер отменен: {order.id}")
                    except Exception as e:
                        logger.error(f"Ошибка отмены TP ордера {order.id}: {e}")
            
            # Очищаем список TP ордеров
            self.position.tp_orders.clear()
            self._notify_orders_update()
            
        except Exception as e:
            logger.error(f"Ошибка отмены TP ордеров: {e}")

    def _update_position_from_order(self, order: Order):
        if order.status != OrderStatus.FILLED:
            return

        if order.side == 'buy':
            # Если позиции не было - просто устанавливаем значения
            if self.position.size == 0:
                self.position.size = order.filled_amount
                self.position.avg_price = order.avg_price
            else:
                total_cost = self.position.size * self.position.avg_price + order.filled_amount * order.avg_price
                self.position.size += order.filled_amount
                # Защита от деления на ноль
                if self.position.size > 0:
                    self.position.avg_price = total_cost / self.position.size
                else:
                    self.position.avg_price = Decimal('0')

        elif order.side == 'sell':
            self.position.size -= order.filled_amount
            # После продажи всей позиции сбрасываем среднюю цену
            if self.position.size <= 0:
                self.position.size = Decimal('0')
                self.position.avg_price = Decimal('0')

        self._notify_position_update()
        logger.info(f"Позиция обновлена: размер={self.position.size}, средняя цена={self.position.avg_price}")

    def _wait_with_stop_check(self, seconds: int) -> bool:
        for _ in range(seconds):
            if self.hard_stop_requested or not self._running:
                return False
            time.sleep(1)
        return True

    def _notify_position_update(self):
        if self.on_position_update:
            self.on_position_update(self.position)

    def _notify_orders_update(self):
        if self.on_orders_update:
            self.on_orders_update(list(self.active_orders.values()))

    def update_orders_status(self):
        try:
            orders_updated = False
            for order_id, order in list(self.active_orders.items()):
                if order.status == OrderStatus.PENDING:
                    try:
                        order_info = self.exchange.get_order_info(order_id, order.symbol)
                        if order_info:
                            if order_info['status'] == 'FILLED':
                                order.status = OrderStatus.FILLED
                                order.filled_amount = Decimal(str(order_info.get('filled_qty', order.amount)))
                                order.avg_price = Decimal(str(order_info.get('avg_price', order.price or 0)))
                                self._update_position_from_order(order)
                                orders_updated = True
                                logger.info(f"Ордер {order_id} исполнен: {order.filled_amount} по цене {order.avg_price}")
                            elif order_info['status'] == 'CANCELED':
                                order.status = OrderStatus.CANCELLED
                                orders_updated = True
                    except Exception as e:
                        logger.error(f"Ошибка обновления статуса ордера {order_id}: {e}")

            if orders_updated:
                self._notify_orders_update()
                self._notify_position_update()

        except Exception as e:
            logger.error(f"Ошибка обновления статусов ордеров: {e}")

    def _monitor_orders_during_cycle(self):
        try:
            for order in self.position.entry_orders:
                if order.status == OrderStatus.PENDING:
                    if self.exchange.is_order_filled(order.id, order.symbol):
                        order_info = self.exchange.get_order_info(order.id, order.symbol)
                        if order_info:
                            order.status = OrderStatus.FILLED
                            order.filled_amount = Decimal(str(order_info.get('filled_qty', order.amount)))
                            order.avg_price = Decimal(str(order_info.get('avg_price', order.price or 0)))
                            self._update_position_from_order(order)
                            logger.info(f"DCA ордер исполнен: {order.id}")
            for order in self.position.tp_orders:
                if order.status == OrderStatus.PENDING:
                    if self.exchange.is_order_filled(order.id, order.symbol):
                        order_info = self.exchange.get_order_info(order.id, order.symbol)
                        if order_info:
                            order.status = OrderStatus.FILLED
                            order.filled_amount = Decimal(str(order_info.get('filled_qty', order.amount)))
                            order.avg_price = Decimal(str(order_info.get('avg_price', order.price or 0)))
                            self._update_position_from_order(order)
                            logger.info(f"TP ордер исполнен: {order.id}")
        except Exception as e:
            logger.error(f"Ошибка мониторинга ордеров: {e}")
        return {
            'running': self._running,
            'soft_stop': self.soft_stop_enabled,
            'stage': self.current_stage.value,
            'position_size': self.position.size,
            'position_avg_price': self.position.avg_price,
            'active_orders_count': len(self.active_orders)
        }

    def is_running(self) -> bool:
        return self._running

    def is_soft_stop_enabled(self) -> bool:
        return self.soft_stop_enabled

    def get_position(self) -> Position:
        return self.position

    def get_active_orders(self) -> List[Order]:
        return list(self.active_orders.values())

    def get_current_stage(self) -> str:
        return self.current_stage.value