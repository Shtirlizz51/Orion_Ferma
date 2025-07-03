from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

COMMISSION_RATE = Decimal('0.0015')  # 0.15% комиссия для всех расчетов

class StrategyEngine:
    def __init__(self, exchange_adapter, order_manager, position_manager, config):
        self.exchange = exchange_adapter
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.config = config

    def _calculate_entry_shares(self, total_deposit, dca_count, martingale_coef):
        shares = []
        coef = Decimal(str(martingale_coef))
        if coef <= 0:
            logger.error(f"Некорректный коэффициент мартингейла: {coef}")
            return []
        if dca_count < 0:
            logger.error(f"Некорректное число DCA: {dca_count}")
            return []
        if coef == 1:
            part = total_deposit / Decimal(str(dca_count + 1))
            shares = [part for _ in range(dca_count + 1)]
        else:
            k = coef
            n = dca_count + 1
            sum_geom = (1 - k**n) / (1 - k)
            base = total_deposit / Decimal(str(sum_geom))
            shares = [base * (k**i) for i in range(n)]
        logger.info(f"Рассчитанные доли входа (shares) для dca_count={dca_count}, martingale_coef={coef}: {shares}")
        return shares

    def run(self, symbol):
        """
        Основной запуск стратегии для одного символа.
        """
        try:
            balance = Decimal(str(self.exchange.get_balance('USDT')))
            deposit_percent = Decimal(str(self.config.get('deposit_percent', 99.99))) / Decimal('100')
            dca_count = int(self.config.get('dca_count', 3))
            martingale_coef = Decimal(str(self.config.get('martingale_coef', 1)))
            total_deposit = balance * deposit_percent

            shares = self._calculate_entry_shares(total_deposit, dca_count, martingale_coef)
            if not shares or len(shares) < 1:
                logger.error("Ошибка расчета долей для входа")
                return False

            # --- Рыночный ордер (market) ---
            order_size_usdt = shares[0] * (Decimal('1') - COMMISSION_RATE)
            price = Decimal(str(self.exchange.get_price(symbol)))
            if price <= 0:
                logger.error("Ошибка: цена инструмента <= 0")
                return False

            quantity = order_size_usdt / price

            lot_info = self.exchange._get_symbol_lot_info(symbol)
            min_qty = lot_info['minQty']
            step_size = lot_info['stepSize']
            quantity = (quantity // step_size) * step_size

            if quantity < min_qty:
                logger.error(f"Рыночный ордер не создан: {quantity} < minQty {min_qty}")
                return False

            market_order = self.exchange.create_order(
                symbol=symbol,
                side='buy',
                order_type='market',
                quantity=quantity
            )

            fill_price = Decimal(str(market_order.get("avg_price", price)))
            fill_qty = Decimal(str(market_order.get("filled_qty", market_order.get("amount", quantity))))
            self.position_manager.reset_position()
            self.position_manager.update_position(fill_qty, fill_price)
            logger.info(f"Открыт рыночный ордер: {fill_qty} {symbol} по цене {fill_price}")

            # --- DCA-ордера ---
            dca_step_percent = Decimal(str(self.config.get('dca_step_percent', 2.8))) / Decimal('100')
            current_price = fill_price
            if len(shares) < 2:
                logger.info("Нет долей на DCA-ордера (shares слишком мало)")
            else:
                for i in range(1, min(dca_count + 1, len(shares))):
                    dca_price = current_price * (Decimal('1') - dca_step_percent * Decimal(i))
                    dca_amount_usdt = shares[i] * (Decimal('1') - COMMISSION_RATE)
                    dca_amount_coins = dca_amount_usdt / dca_price
                    dca_amount_coins = (dca_amount_coins // step_size) * step_size

                    if dca_amount_coins < min_qty:
                        logger.warning(f"DCA ордер {i} не создан: {dca_amount_coins} < minQty {min_qty}")
                        continue

                    try:
                        dca_order = self.exchange.create_order(
                            symbol=symbol,
                            side='buy',
                            order_type='limit',
                            quantity=dca_amount_coins,
                            price=dca_price
                        )
                        logger.info(f"DCA ордер {i}: {dca_amount_coins} {symbol} по цене {dca_price}")
                    except Exception as e:
                        logger.error(f"Ошибка создания DCA ордера {i}: {e}")
                        continue

            # --- TP-ордера ---
            position_size = self.position_manager.position.size
            tp_levels = [
                {"percent": Decimal(str(self.config.get('tp1_percent', 1.9))), "volume": Decimal(str(self.config.get('tp1_volume', 33)))},
                {"percent": Decimal(str(self.config.get('tp2_percent', 3.4))), "volume": Decimal(str(self.config.get('tp2_volume', 33)))},
                {"percent": Decimal(str(self.config.get('tp3_percent', 4.9))), "volume": Decimal(str(self.config.get('tp3_volume', 33)))}
            ]
            for i, tp in enumerate(tp_levels, 1):
                tp_price = fill_price * (Decimal('1') + tp["percent"] / Decimal('100'))
                tp_amount = position_size * tp["volume"] / Decimal('100')
                tp_amount = tp_amount * (Decimal('1') - COMMISSION_RATE)
                tp_amount = (tp_amount // step_size) * step_size
                if tp_amount < min_qty:
                    logger.warning(f"TP ордер {i} не создан: {tp_amount} < minQty {min_qty}")
                    continue
                try:
                    tp_order = self.exchange.create_order(
                        symbol=symbol,
                        side='sell',
                        order_type='limit',
                        quantity=tp_amount,
                        price=tp_price
                    )
                    logger.info(f"TP ордер {i}: {tp_amount} {symbol} по цене {tp_price}")
                except Exception as e:
                    logger.error(f"Ошибка создания TP ордера {i}: {e}")
                    continue

            return True
        except Exception as e:
            logger.error(f"Ошибка исполнения стратегии: {e}")
            return False