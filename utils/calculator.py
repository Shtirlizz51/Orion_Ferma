from decimal import Decimal

def calculate_order_amounts(total_quote, dca_count, martingale_multiplier, commission_rate=Decimal('0.0015')):
    """
    Распределяет total_quote (например, USDT) на dca_count + 1 частей (основной ордер и DCA ордера)
    с учетом коэффициента мартингейла (martingale_multiplier) и комиссии (commission_rate).
    Возвращает список сумм для каждого ордера: [main, dca1, dca2, ...]
    Все суммы уже уменьшены на комиссию.
    """
    if dca_count < 1:
        return [total_quote * (Decimal('1') - commission_rate)]
    amounts = []
    coef_sum = sum(martingale_multiplier ** i for i in range(dca_count + 1))
    base_amount = total_quote / coef_sum
    for i in range(dca_count + 1):
        amt = base_amount * (martingale_multiplier ** i)
        amt = amt * (Decimal('1') - commission_rate)
        amounts.append(amt)
    return amounts