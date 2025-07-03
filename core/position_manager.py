import logging
from decimal import Decimal
from typing import List, Dict, Any

class PositionManager:
    # Комиссия биржи с запасом
    COMMISSION_RATE = Decimal('0.0015')  # 0.15% (0.11% + запас)
    
    def __init__(self):
        self.logger = logging.getLogger("PositionManager")
        self.reset_position()

    def reset_position(self):
        """Сбрасывает позицию к нулевым значениям"""
        self.position_qty = Decimal('0')
        self.avg_entry_price = Decimal('0')
        self.total_cost = Decimal('0')
        self.realized_pnl = Decimal('0')
        self.logger.info("Позиция сброшена.")

    def update_position(self, qty: Decimal, price: Decimal):
        """
        Обновляет позицию с учетом нового ордера
        qty: количество монет (может быть отрицательным для продажи)
        price: цена исполнения
        """
        try:
            qty = Decimal(str(qty))
            price = Decimal(str(price))
            
            if qty > 0:  # Покупка
                # Учитываем комиссию при покупке
                effective_price = price * (Decimal('1') + self.COMMISSION_RATE)
                new_cost = qty * effective_price
                
                if self.position_qty == 0:
                    # Новая позиция
                    self.position_qty = qty
                    self.avg_entry_price = effective_price
                    self.total_cost = new_cost
                else:
                    # Добавляем к существующей позиции
                    self.total_cost += new_cost
                    self.position_qty += qty
                    self.avg_entry_price = self.total_cost / self.position_qty
                    
            elif qty < 0:  # Продажа
                qty = abs(qty)
                if qty > self.position_qty:
                    self.logger.warning(f"Попытка продать {qty} при позиции {self.position_qty}")
                    qty = self.position_qty
                
                # Учитываем комиссию при продаже
                effective_price = price * (Decimal('1') - self.COMMISSION_RATE)
                
                # Рассчитываем реализованный PnL
                cost_basis = self.avg_entry_price * qty
                sale_proceeds = effective_price * qty
                realized_pnl = sale_proceeds - cost_basis
                self.realized_pnl += realized_pnl
                
                # Обновляем позицию
                self.position_qty -= qty
                if self.position_qty <= 0:
                    self.position_qty = Decimal('0')
                    self.avg_entry_price = Decimal('0')
                    self.total_cost = Decimal('0')
                else:
                    self.total_cost -= cost_basis
                    
            self.logger.info(f"Позиция обновлена: qty={self.position_qty}, avg_entry_price={self.avg_entry_price}, realized_pnl={self.realized_pnl}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления позиции: {e}")

    def calculate_tp_levels(self, tp_settings: List[tuple]) -> List[Dict[str, Any]]:
        """
        Рассчитывает уровни тейк-профита с учетом комиссии
        tp_settings: [(percent, volume_percent), ...]
        Возвращает список словарей с ценой и количеством для тейк-профитов.
        """
        tps = []
        try:
            for tp_percent, tp_volume in tp_settings:
                if self.position_qty <= 0:
                    continue
                    
                tp_percent = Decimal(str(tp_percent))
                tp_volume = Decimal(str(tp_volume))
                
                # Количество для продажи
                qty = self.position_qty * (tp_volume / Decimal('100'))
                
                # Цена TP с учетом комиссии (добавляем комиссию к желаемому профиту)
                profit_multiplier = Decimal('1') + tp_percent / Decimal('100')
                commission_multiplier = Decimal('1') + self.COMMISSION_RATE
                tp_price = self.avg_entry_price * profit_multiplier * commission_multiplier
                
                tps.append({
                    'price': tp_price,
                    'quantity': qty,
                    'profit_percent': tp_percent,
                    'volume_percent': tp_volume,
                    'expected_proceeds': tp_price * qty * (Decimal('1') - self.COMMISSION_RATE),
                    'cost_basis': self.avg_entry_price * qty,
                })
                
            self.logger.info(f"Рассчитано {len(tps)} уровней TP")
            return tps
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета TP уровней: {e}")
            return []

    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """
        Рассчитывает нереализованный PnL
        current_price: текущая цена актива
        """
        try:
            if self.position_qty <= 0:
                return Decimal('0')
                
            current_price = Decimal(str(current_price))
            
            # Текущая стоимость позиции с учетом комиссии при продаже
            current_value = current_price * self.position_qty * (Decimal('1') - self.COMMISSION_RATE)
            
            # Нереализованный PnL = текущая стоимость - общая стоимость входа
            unrealized_pnl = current_value - self.total_cost
            
            return unrealized_pnl
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета нереализованного PnL: {e}")
            return Decimal('0')

    def calculate_total_pnl(self, current_price: Decimal) -> Decimal:
        """
        Рассчитывает общий PnL (реализованный + нереализованный)
        """
        try:
            unrealized = self.calculate_unrealized_pnl(current_price)
            return self.realized_pnl + unrealized
        except Exception as e:
            self.logger.error(f"Ошибка расчета общего PnL: {e}")
            return Decimal('0')

    def get_position_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о текущей позиции
        """
        return {
            'quantity': self.position_qty,
            'avg_entry_price': self.avg_entry_price,
            'total_cost': self.total_cost,
            'realized_pnl': self.realized_pnl,
            'has_position': self.position_qty > 0
        }

    def calculate_dca_levels(self, current_price: Decimal, dca_settings: List[tuple], 
                           available_usdt: Decimal) -> List[Dict[str, Any]]:
        """
        Рассчитывает уровни DCA с учетом комиссии
        dca_settings: [(step_percent, volume_percent), ...]
        available_usdt: доступный USDT для DCA
        """
        dca_levels = []
        try:
            current_price = Decimal(str(current_price))
            available_usdt = Decimal(str(available_usdt))
            
            # Учитываем комиссию в доступном балансе
            effective_usdt = available_usdt * (Decimal('1') - self.COMMISSION_RATE)
            
            for step_percent, volume_percent in dca_settings:
                step_percent = Decimal(str(step_percent))
                volume_percent = Decimal(str(volume_percent))
                
                # Цена DCA
                dca_price = current_price * (Decimal('1') - step_percent / Decimal('100'))
                
                # Сумма для DCA
                dca_usdt = effective_usdt * volume_percent / Decimal('100')
                
                # Количество монет
                dca_quantity = dca_usdt / dca_price
                
                dca_levels.append({
                    'price': dca_price,
                    'quantity': dca_quantity,
                    'usdt_amount': dca_usdt,
                    'step_percent': step_percent,
                    'volume_percent': volume_percent
                })
                
            self.logger.info(f"Рассчитано {len(dca_levels)} уровней DCA")
            return dca_levels
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета DCA уровней: {e}")
            return []

    def can_place_order(self, order_type: str, quantity: Decimal, price: Decimal) -> bool:
        """
        Проверяет, можно ли разместить ордер
        """
        try:
            quantity = Decimal(str(quantity))
            price = Decimal(str(price))
            
            if order_type.lower() == 'buy':
                return True  # Покупка всегда возможна при наличии средств
            elif order_type.lower() == 'sell':
                return quantity <= self.position_qty
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка проверки возможности размещения ордера: {e}")
            return False

    def __str__(self) -> str:
        return f"Position(qty={self.position_qty}, avg_price={self.avg_entry_price}, cost={self.total_cost}, pnl={self.realized_pnl})"